"""Safe, local-only updater for AIWorkSpace.

The updater fetches one fixed public GitHub repository, installs only the
allowlisted application files, keeps backups outside the configured data
folder, and restarts the local server through a helper process.
"""
from __future__ import annotations

import argparse
import ctypes
import json
import os
import re
import shutil
import socket
import stat
import subprocess
import sys
import tempfile
import time
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


REPOSITORY = "yudacheng666/AIWorkSpace"
API_COMMIT_URL = f"https://api.github.com/repos/{REPOSITORY}/commits/main"
RAW_VERSION_URL = f"https://raw.githubusercontent.com/{REPOSITORY}/{{commit}}/VERSION"
ARCHIVE_URL = f"https://api.github.com/repos/{REPOSITORY}/zipball/{{commit}}"
USER_AGENT = "AIWorkSpace-Updater/1"
APP_FILES = ("app.py", "updater.py", "VERSION", "web/index.html")
BUILD_INFO_NAME = ".aiworkspace-build.json"
UPDATE_STATE_NAME = ".aiworkspace-update-state.json"
BACKUP_FILES = APP_FILES + (BUILD_INFO_NAME, UPDATE_STATE_NAME)
VERSION_RE = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+$")
COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
MAX_ARCHIVE_BYTES = 25 * 1024 * 1024
MAX_UNPACKED_BYTES = 40 * 1024 * 1024
MAX_ENTRY_BYTES = 5 * 1024 * 1024
MAX_ARCHIVE_ENTRIES = 5000


class UpdateError(RuntimeError):
    """An expected, user-safe update failure."""


def _is_within(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def _resolved(path: Path | str) -> Path:
    return Path(path).expanduser().resolve()


def _ensure_safe_layout(root: Path | str, data_dir: Path | str) -> tuple[Path, Path]:
    root_path = _resolved(root)
    data_path = _resolved(data_dir)
    if not root_path.is_dir():
        raise UpdateError("应用程序目录不存在。")
    if root_path == data_path or _is_within(root_path, data_path):
        raise UpdateError("应用程序目录位于数据目录内；为保护数据，已拒绝更新。")
    for relative in APP_FILES + (BUILD_INFO_NAME, UPDATE_STATE_NAME):
        target = (root_path / relative).resolve()
        if not _is_within(target, root_path):
            raise UpdateError("应用程序文件路径异常，已拒绝更新。")
        if target == data_path or _is_within(target, data_path):
            raise UpdateError("应用程序文件与数据目录重叠；为保护数据，已拒绝更新。")
    return root_path, data_path


def _read_json(path: Path) -> dict | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def read_version(root: Path | str) -> str:
    try:
        version = (_resolved(root) / "VERSION").read_text(encoding="utf-8").strip()
    except OSError as exc:
        raise UpdateError("无法读取软件版本文件。") from exc
    if not VERSION_RE.fullmatch(version):
        raise UpdateError("软件版本文件格式无效。")
    return version


def get_install_status(root: Path | str) -> dict:
    root_path = _resolved(root)
    version = read_version(root_path)
    build = _read_json(root_path / BUILD_INFO_NAME) or {}
    commit = build.get("commit")
    if not isinstance(commit, str) or not COMMIT_RE.fullmatch(commit):
        commit = None
    last = _read_json(root_path / UPDATE_STATE_NAME) or {}
    safe_last = None
    if last.get("status") in {"installed", "rolled_back", "failed"}:
        safe_last = {
            "status": last.get("status"),
            "version": last.get("version") if isinstance(last.get("version"), str) else None,
            "commit": last.get("commit") if isinstance(last.get("commit"), str) else None,
            "message": last.get("message") if isinstance(last.get("message"), str) else None,
            "updated_at": last.get("updated_at") if isinstance(last.get("updated_at"), str) else None,
        }
    return {
        "version": version,
        "build_commit": commit,
        "build_short": commit[:7] if commit else None,
        "build_known": bool(commit),
        "last_update": safe_last,
    }


def _read_url(url: str, limit: int, timeout: int = 10) -> bytes:
    request = Request(url, headers={
        "User-Agent": USER_AGENT,
        "Accept": "application/vnd.github+json",
    })
    try:
        with urlopen(request, timeout=timeout) as response:
            length = response.headers.get("Content-Length")
            if length and int(length) > limit:
                raise UpdateError("GitHub 返回的更新文件超过安全大小限制。")
            content = response.read(limit + 1)
    except UpdateError:
        raise
    except (HTTPError, URLError, TimeoutError, OSError) as exc:
        raise UpdateError("无法连接 GitHub；请检查网络后重试。") from exc
    if len(content) > limit:
        raise UpdateError("GitHub 返回的更新文件超过安全大小限制。")
    return content


def check_latest_update(root: Path | str) -> dict:
    local = get_install_status(root)
    raw = _read_url(API_COMMIT_URL, 512 * 1024)
    try:
        remote = json.loads(raw.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise UpdateError("GitHub 返回了无法识别的版本信息。") from exc
    if not isinstance(remote, dict):
        raise UpdateError("GitHub 返回了无法识别的版本信息。")
    commit = remote.get("sha")
    if not isinstance(commit, str) or not COMMIT_RE.fullmatch(commit):
        raise UpdateError("GitHub 返回的提交编号无效。")
    version_bytes = _read_url(RAW_VERSION_URL.format(commit=commit), 128)
    try:
        latest_version = version_bytes.decode("utf-8").strip()
    except UnicodeError as exc:
        raise UpdateError("GitHub 返回的版本号无法读取。") from exc
    if not VERSION_RE.fullmatch(latest_version):
        raise UpdateError("GitHub 上的软件版本号格式无效。")
    commit_data = remote.get("commit") if isinstance(remote.get("commit"), dict) else {}
    message = commit_data.get("message", "")
    if not isinstance(message, str):
        message = ""
    message = message.splitlines()[0][:180] if message else "main 最新构建"
    committer = commit_data.get("committer") if isinstance(commit_data.get("committer"), dict) else {}
    latest_date = committer.get("date") if isinstance(committer.get("date"), str) else None
    current_commit = local["build_commit"]
    available = current_commit != commit or local["version"] != latest_version
    return {
        **local,
        "latest_version": latest_version,
        "latest_commit": commit,
        "latest_short": commit[:7],
        "latest_message": message,
        "latest_date": latest_date,
        "update_available": available,
        "source": "GitHub main",
    }


def validate_archive_and_stage(
    archive_bytes: bytes,
    commit: str,
    root: Path | str,
    data_dir: Path | str,
) -> Path:
    if not COMMIT_RE.fullmatch(commit):
        raise UpdateError("更新提交编号无效。")
    root_path, data_path = _ensure_safe_layout(root, data_dir)
    if not isinstance(archive_bytes, bytes) or not 1 <= len(archive_bytes) <= MAX_ARCHIVE_BYTES:
        raise UpdateError("更新压缩包为空或超过大小限制。")
    extracted: dict[str, bytes] = {}
    total_size = 0
    root_name = None
    try:
        from io import BytesIO
        with zipfile.ZipFile(BytesIO(archive_bytes), "r") as archive:
            entries = archive.infolist()
            if not entries or len(entries) > MAX_ARCHIVE_ENTRIES:
                raise UpdateError("更新压缩包文件数量异常。")
            if archive.testzip() is not None:
                raise UpdateError("更新压缩包完整性校验失败。")
            for info in entries:
                name = info.filename
                if (not name or "\\" in name or name.startswith("/") or
                        "\x00" in name or ":" in name):
                    raise UpdateError("更新压缩包包含不安全路径。")
                parts = PurePosixPath(name).parts
                if not parts or any(part in {"", ".", ".."} for part in parts):
                    raise UpdateError("更新压缩包包含路径穿越内容。")
                if root_name is None:
                    root_name = parts[0]
                elif parts[0] != root_name:
                    raise UpdateError("更新压缩包目录结构异常。")
                mode = (info.external_attr >> 16) & 0xFFFF
                if stat.S_ISLNK(mode):
                    raise UpdateError("更新压缩包包含符号链接，已拒绝安装。")
                if info.flag_bits & 0x1:
                    raise UpdateError("更新压缩包包含加密文件，无法安全校验。")
                total_size += info.file_size
                if total_size > MAX_UNPACKED_BYTES or info.file_size > MAX_ENTRY_BYTES:
                    raise UpdateError("更新压缩包解压大小超过安全限制。")
                relative_parts = parts[1:]
                if info.is_dir() or not relative_parts:
                    continue
                relative = PurePosixPath(*relative_parts).as_posix()
                if relative not in APP_FILES:
                    continue
                if relative in extracted:
                    raise UpdateError("更新压缩包包含重复的程序文件。")
                content = archive.read(info)
                if len(content) != info.file_size:
                    raise UpdateError("更新文件长度校验失败。")
                if relative == "VERSION":
                    try:
                        version = content.decode("utf-8").strip()
                    except UnicodeError as exc:
                        raise UpdateError("更新版本号无法读取。") from exc
                    if not VERSION_RE.fullmatch(version):
                        raise UpdateError("更新版本号格式无效。")
                if relative.endswith(".py"):
                    try:
                        compile(content.decode("utf-8"), relative, "exec")
                    except (UnicodeError, SyntaxError) as exc:
                        raise UpdateError("更新包中的 Python 文件未通过语法校验。") from exc
                extracted[relative] = content
    except UpdateError:
        raise
    except (zipfile.BadZipFile, RuntimeError, OSError, ValueError) as exc:
        raise UpdateError("更新压缩包无法读取或完整性校验失败。") from exc
    if not root_name or not root_name.endswith(commit[:7]):
        raise UpdateError("更新压缩包与目标 GitHub 提交不匹配。")
    if set(extracted) != set(APP_FILES):
        raise UpdateError("更新压缩包缺少必要的程序文件。")

    stage = root_path / f".aiworkspace-update-staging-{uuid.uuid4().hex}"
    if _is_within(stage.resolve(), data_path):
        raise UpdateError("更新暂存目录与数据目录重叠；已拒绝更新。")
    try:
        stage.mkdir(mode=0o700)
        for relative, content in extracted.items():
            target = stage / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)
    except OSError as exc:
        shutil.rmtree(stage, ignore_errors=True)
        raise UpdateError("无法创建更新暂存目录。") from exc
    return stage


def prepare_update(root: Path | str, data_dir: Path | str, commit: str) -> tuple[Path, dict]:
    if not isinstance(commit, str) or not COMMIT_RE.fullmatch(commit):
        raise UpdateError("更新提交编号无效。")
    latest = check_latest_update(root)
    if latest["latest_commit"] != commit:
        raise UpdateError("GitHub main 已发生变化，请重新检查更新。")
    archive = _read_url(ARCHIVE_URL.format(commit=commit), MAX_ARCHIVE_BYTES, timeout=30)
    stage = validate_archive_and_stage(archive, commit, root, data_dir)
    return stage, latest


def _write_json_atomic(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        with temp.open("w", encoding="utf-8", newline="\n") as stream:
            json.dump(payload, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, path)
    finally:
        try:
            temp.unlink()
        except FileNotFoundError:
            pass


def _backup_base(root: Path, data_dir: Path, override: Path | None = None) -> Path:
    candidates = [override] if override is not None else [
        Path.home() / ".aiworkspace" / "update-backups",
        Path(tempfile.gettempdir()) / "AIWorkSpace-update-backups",
    ]
    for candidate in candidates:
        if candidate is None:
            continue
        path = _resolved(candidate)
        if path == root or _is_within(path, root):
            continue
        if path == data_dir or _is_within(path, data_dir):
            continue
        return path
    raise UpdateError("找不到与程序目录和数据目录隔离的更新备份位置。")


def create_backup(
    root: Path | str,
    data_dir: Path | str,
    backup_base: Path | str | None = None,
) -> Path:
    root_path, data_path = _ensure_safe_layout(root, data_dir)
    base = _backup_base(root_path, data_path, Path(backup_base) if backup_base else None)
    backup = base / f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{uuid.uuid4().hex[:8]}"
    backup.mkdir(parents=True, exist_ok=False)
    manifest = {"files": {}}
    try:
        for relative in BACKUP_FILES:
            source = root_path / relative
            if source.exists():
                resolved = source.resolve()
                if not _is_within(resolved, root_path) or source.is_symlink() or not source.is_file():
                    raise UpdateError("程序目录中的文件结构异常，无法安全备份。")
                target = backup / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)
                manifest["files"][relative] = True
            else:
                manifest["files"][relative] = False
        _write_json_atomic(backup / "manifest.json", manifest)
    except Exception:
        shutil.rmtree(backup, ignore_errors=True)
        raise
    return backup


def _atomic_copy(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    temp = target.with_name(f".{target.name}.{uuid.uuid4().hex}.update")
    try:
        with source.open("rb") as src, temp.open("wb") as dst:
            shutil.copyfileobj(src, dst)
            dst.flush()
            os.fsync(dst.fileno())
        os.replace(temp, target)
    finally:
        try:
            temp.unlink()
        except FileNotFoundError:
            pass


def rollback_from_backup(
    root: Path | str,
    data_dir: Path | str,
    backup_dir: Path | str,
) -> None:
    root_path, data_path = _ensure_safe_layout(root, data_dir)
    backup = _resolved(backup_dir)
    if not backup.is_dir() or _is_within(backup, root_path) or _is_within(backup, data_path):
        raise UpdateError("更新备份位置无效，无法自动回滚。")
    manifest = _read_json(backup / "manifest.json")
    if not isinstance(manifest, dict) or not isinstance(manifest.get("files"), dict):
        raise UpdateError("更新备份清单缺失，无法自动回滚。")
    for relative in BACKUP_FILES:
        if relative not in manifest["files"]:
            raise UpdateError("更新备份清单不完整，无法自动回滚。")
        target = root_path / relative
        if manifest["files"][relative] is True:
            source = backup / relative
            if not source.is_file() or source.is_symlink():
                raise UpdateError("更新备份文件缺失，无法自动回滚。")
            _atomic_copy(source, target)
        elif target.exists():
            if target.is_dir() or target.is_symlink():
                raise UpdateError("更新后文件类型异常，无法自动回滚。")
            target.unlink()


def _write_update_state(root: Path, status: str, version: str, commit: str, message: str) -> None:
    _write_json_atomic(root / UPDATE_STATE_NAME, {
        "status": status,
        "version": version,
        "commit": commit,
        "message": message,
        "updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    })


def apply_staged_update(
    root: Path | str,
    data_dir: Path | str,
    stage_dir: Path | str,
    commit: str,
    backup_base: Path | str | None = None,
) -> Path:
    root_path, data_path = _ensure_safe_layout(root, data_dir)
    stage = _resolved(stage_dir)
    if (not stage.is_dir() or not _is_within(stage, root_path) or
            _is_within(stage, data_path) or not stage.name.startswith(".aiworkspace-update-staging-")):
        raise UpdateError("更新暂存目录无效，已拒绝安装。")
    if not COMMIT_RE.fullmatch(commit):
        raise UpdateError("更新提交编号无效。")
    for relative in APP_FILES:
        source = stage / relative
        if not source.is_file() or source.is_symlink() or not _is_within(source.resolve(), stage):
            raise UpdateError("更新暂存文件不完整，已拒绝安装。")
    version = read_version(stage)
    backup = create_backup(root_path, data_path, backup_base)
    try:
        for relative in APP_FILES:
            _atomic_copy(stage / relative, root_path / relative)
        _write_json_atomic(root_path / BUILD_INFO_NAME, {
            "version": version,
            "commit": commit,
            "installed_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        })
        _write_update_state(root_path, "installed", version, commit, "更新安装成功。")
    except Exception as exc:
        try:
            rollback_from_backup(root_path, data_path, backup)
            _write_update_state(root_path, "rolled_back", version, commit,
                                "更新未完成，已自动恢复旧版本。")
        except Exception as rollback_exc:
            raise UpdateError("更新失败且自动回滚未完成；请保留备份并联系维护。") from rollback_exc
        raise UpdateError("更新安装失败，已自动恢复旧版本。") from exc
    return backup


def remove_stage(stage_dir: Path | str) -> None:
    stage = Path(stage_dir)
    if stage.name.startswith(".aiworkspace-update-staging-"):
        shutil.rmtree(stage, ignore_errors=True)


def _pid_running(pid: int) -> bool:
    if os.name == "nt":
        try:
            handle = ctypes.windll.kernel32.OpenProcess(0x00100000, False, pid)
            if not handle:
                return False
            try:
                return ctypes.windll.kernel32.WaitForSingleObject(handle, 0) == 258
            finally:
                ctypes.windll.kernel32.CloseHandle(handle)
        except Exception:
            return False
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


def _wait_for_parent_exit(pid: int, timeout: float = 30) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if not _pid_running(pid):
            return True
        time.sleep(0.2)
    return not _pid_running(pid)


def _start_application(root: Path, data_dir: Path, port: int) -> subprocess.Popen:
    command = [sys.executable, str(root / "app.py"),
               "--data-dir", str(data_dir), "--port", str(port)]
    options = {"cwd": str(root), "stdin": subprocess.DEVNULL}
    if os.name != "nt":
        options["start_new_session"] = True
    return subprocess.Popen(command, **options)


def _wait_for_build(port: int, commit: str | None, process: subprocess.Popen | None, timeout: float) -> bool:
    from urllib.request import urlopen
    from urllib.error import URLError
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if process is not None and process.poll() is not None:
            return False
        try:
            with urlopen(f"http://127.0.0.1:{port}/api/update/status", timeout=1) as response:
                status = json.loads(response.read(64 * 1024).decode("utf-8"))
            if commit is None or status.get("build_commit") == commit:
                return True
        except (URLError, OSError, TimeoutError, ValueError, UnicodeError):
            pass
        time.sleep(0.5)
    return False


def _terminate(process: subprocess.Popen | None) -> None:
    if process is None or process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()


def run_update_helper(
    root: Path | str,
    data_dir: Path | str,
    stage_dir: Path | str,
    commit: str,
    port: int,
    parent_pid: int,
) -> int:
    root_path, data_path = _ensure_safe_layout(root, data_dir)
    stage = _resolved(stage_dir)
    backup = None
    new_process = None
    try:
        if not _wait_for_parent_exit(parent_pid, timeout=30):
            raise UpdateError("原工作台服务未能正常停止，未安装更新。")
        version = read_version(stage)
        backup = apply_staged_update(root_path, data_path, stage, commit)
        new_process = _start_application(root_path, data_path, port)
        if _wait_for_build(port, commit, new_process, timeout=25):
            return 0
        raise UpdateError("新版本启动验证失败，正在恢复旧版本。")
    except Exception as exc:
        _terminate(new_process)
        if backup is not None:
            try:
                rollback_from_backup(root_path, data_path, backup)
            except Exception:
                _write_update_state(root_path, "failed", "unknown", commit,
                                    "更新失败，自动回滚未能完成；请保留备份并联系维护。")
                return 2
        try:
            old_version = read_version(root_path)
        except UpdateError:
            old_version = "unknown"
        _write_update_state(root_path, "rolled_back" if backup else "failed",
                            old_version, commit,
                            "更新未完成，已恢复旧版本。" if backup else "更新未完成，原版本未更改。")
        try:
            old_process = _start_application(root_path, data_path, port)
            _wait_for_build(port, None, old_process, timeout=10)
        except OSError:
            pass
        return 1
    finally:
        remove_stage(stage)


def launch_update_helper(
    stage_dir: Path | str,
    root: Path | str,
    data_dir: Path | str,
    commit: str,
    port: int,
    parent_pid: int,
) -> subprocess.Popen:
    root_path = _resolved(root)
    command = [
        sys.executable, str(root_path / "updater.py"), "--apply",
        "--stage-dir", str(_resolved(stage_dir)),
        "--root", str(root_path),
        "--data-dir", str(_resolved(data_dir)),
        "--commit", commit,
        "--port", str(port),
        "--parent-pid", str(parent_pid),
    ]
    options = {"cwd": str(root_path), "stdin": subprocess.DEVNULL}
    if os.name != "nt":
        options["start_new_session"] = True
    return subprocess.Popen(command, **options)


def main() -> None:
    parser = argparse.ArgumentParser(description="AIWorkSpace update helper")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--stage-dir", type=Path)
    parser.add_argument("--root", type=Path)
    parser.add_argument("--data-dir", type=Path)
    parser.add_argument("--commit")
    parser.add_argument("--port", type=int)
    parser.add_argument("--parent-pid", type=int)
    args = parser.parse_args()
    if not args.apply:
        parser.error("helper mode requires --apply")
    if any(value is None for value in (
        args.stage_dir, args.root, args.data_dir, args.commit, args.port, args.parent_pid
    )):
        parser.error("missing helper arguments")
    if not COMMIT_RE.fullmatch(args.commit) or not 1 <= args.port <= 65535 or args.parent_pid <= 0:
        parser.error("invalid helper arguments")
    raise SystemExit(run_update_helper(
        args.root, args.data_dir, args.stage_dir, args.commit, args.port, args.parent_pid
    ))


if __name__ == "__main__":
    main()
