"""No-console desktop launcher for the local AIWorkSpace server.

The launcher uses only the Python standard library. Per-computer configuration,
runtime control state and bounded logs live under the user's local AppData folder,
never in the Google Drive data directory or the public repository.
"""
from __future__ import annotations

import argparse
import ctypes
from contextlib import contextmanager
import http.client
import json
import os
from pathlib import Path
import re
import secrets
import socket
import subprocess
import sys
import time
import webbrowser

ROOT = Path(__file__).resolve().parent
DEFAULT_PORT = 8770
SERVICE_NAME = "AIWorkSpace"
HEALTH_PATH = "/api/health"
SHUTDOWN_PATH = "/api/local/shutdown"
MAX_LOG_BYTES = 512 * 1024
VERSION_RE = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+$")


class LauncherError(RuntimeError):
    """An expected, user-readable desktop launcher failure."""


def _home_dir() -> Path:
    override = os.environ.get("AIWORKSPACE_LAUNCHER_HOME")
    if override:
        return Path(override).expanduser().resolve()
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        return Path(local_app_data) / SERVICE_NAME
    return Path.home() / ".local" / "share" / SERVICE_NAME


def config_path() -> Path:
    return _home_dir() / "launcher.json"


def runtime_dir() -> Path:
    return _home_dir() / "run"


def log_path() -> Path:
    return _home_dir() / "logs" / "runtime.log"


def _is_within(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def load_config(root: Path | str = ROOT, path: Path | str | None = None) -> dict:
    root_path = Path(root).expanduser().resolve()
    config_file = Path(path).expanduser() if path is not None else config_path()
    if not config_file.is_file():
        raise LauncherError(
            "尚未完成首次设置。请在 AIWorkSpace 程序文件夹中双击 "
            "setup_desktop_shortcuts.vbs，选择现有的 Google Drive 数据目录。"
        )
    try:
        payload = json.loads(config_file.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise LauncherError("桌面启动配置无法读取，请重新运行首次设置脚本。") from exc
    if not isinstance(payload, dict) or set(payload) != {"data_dir", "port"}:
        raise LauncherError("桌面启动配置格式无效，请重新运行首次设置脚本。")
    raw_data_dir = payload.get("data_dir")
    port = payload.get("port")
    if not isinstance(raw_data_dir, str) or not raw_data_dir.strip():
        raise LauncherError("没有设置工作台数据目录，请重新运行首次设置脚本。")
    if isinstance(port, bool) or not isinstance(port, int) or not 1 <= port <= 65535:
        raise LauncherError("工作台端口配置无效，请重新运行首次设置脚本。")
    try:
        data_path = Path(raw_data_dir).expanduser().resolve(strict=True)
    except OSError as exc:
        raise LauncherError("找不到已设置的数据目录；请检查 Google Drive 是否已启动。") from exc
    if not data_path.is_dir():
        raise LauncherError("已设置的数据路径不是文件夹，请重新运行首次设置脚本。")
    if data_path.name.lower() in {"events", "project_events", "step_events"}:
        raise LauncherError("请选择 AIWorkSpaceData 数据根目录，不要选择 events 等子文件夹。")
    if not (data_path / "events").is_dir():
        raise LauncherError("所选目录中没有 events 子文件夹；为避免启动一个空工作台，请检查是否选对数据根目录。")
    if (data_path == root_path or _is_within(data_path, root_path)
            or _is_within(root_path, data_path)):
        raise LauncherError(
            "数据目录不能位于程序目录内，也不能包含程序目录。为保护现有数据，启动已取消。"
        )
    return {"data_dir": data_path, "port": port}


def _request_json(
    port: int,
    path: str,
    method: str = "GET",
    headers: dict | None = None,
) -> tuple[int | None, dict | None]:
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=0.7)
    try:
        connection.request(
            method,
            path,
            body=b"" if method == "POST" else None,
            headers=headers or {},
        )
        response = connection.getresponse()
        raw = response.read(64 * 1024)
        payload = json.loads(raw.decode("utf-8")) if raw else {}
        return response.status, payload if isinstance(payload, dict) else None
    except (OSError, http.client.HTTPException, UnicodeError, json.JSONDecodeError):
        return None, None
    finally:
        connection.close()


def identify_existing_service(port: int) -> str | None:
    """Return current/legacy only for a positively identified AIWorkSpace server."""
    status, payload = _request_json(port, HEALTH_PATH)
    if (status == 200 and isinstance(payload, dict)
            and payload.get("service") == SERVICE_NAME and payload.get("status") == "ok"):
        return "current"

    # 2.9.1 and earlier have no dedicated health endpoint. This read-only
    # endpoint lets the new launcher recognize an already-running old instance.
    status, payload = _request_json(port, "/api/update/status")
    if (status == 200 and isinstance(payload, dict)
            and isinstance(payload.get("version"), str)
            and VERSION_RE.fullmatch(payload["version"])
            and "build_commit" in payload):
        return "legacy"
    return None


def port_in_use(port: int) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.35):
            return True
    except OSError:
        return False


def _append_log(message: str) -> None:
    path = log_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as stream:
        stream.write(time.strftime("%Y-%m-%d %H:%M:%S") + " " + message + "\n")
        stream.flush()


def _rotate_log() -> None:
    path = log_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists() or path.stat().st_size <= MAX_LOG_BYTES:
        return
    backup = path.with_name(path.name + ".1")
    try:
        backup.unlink()
    except FileNotFoundError:
        pass
    path.replace(backup)


@contextmanager
def _launch_lock():
    lock_path = runtime_dir() / "start.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+b") as stream:
        if os.name == "nt":
            import msvcrt

            stream.seek(0, os.SEEK_END)
            if stream.tell() == 0:
                stream.write(b"\0")
                stream.flush()
            stream.seek(0)
            try:
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError as exc:
                raise LauncherError("工作台正在启动，请稍后再双击一次。") from exc
            try:
                yield
            finally:
                stream.seek(0)
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl

            try:
                fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError as exc:
                raise LauncherError("工作台正在启动，请稍后再双击一次。") from exc
            try:
                yield
            finally:
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


def _open_browser(port: int) -> bool:
    try:
        return bool(webbrowser.open_new_tab(f"http://127.0.0.1:{port}/"))
    except Exception:
        return False


def _terminate_started_process(process: subprocess.Popen) -> None:
    if process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


def start(
    root: Path | str = ROOT,
    config: Path | str | None = None,
    wait_timeout: float = 20,
    poll_interval: float = 0.25,
) -> str:
    root_path = Path(root).expanduser().resolve()
    app_file = root_path / "app.py"
    if not app_file.is_file():
        raise LauncherError("找不到 app.py；请从 AIWorkSpace 程序文件夹启动。")
    settings = load_config(root_path, config)
    port = settings["port"]

    with _launch_lock():
        existing = identify_existing_service(port)
        if existing:
            if not _open_browser(port):
                raise LauncherError(
                    f"工作台已经运行，但浏览器未能自动打开。请访问 http://127.0.0.1:{port}/"
                )
            return "already_running" if existing == "current" else "legacy_running"

        if port_in_use(port):
            raise LauncherError(
                f"端口 {port} 已被其他程序占用。为避免影响其他程序，"
                "AIWorkSpace 没有启动或停止任何进程。"
            )

        token = secrets.token_urlsafe(32)
        runtime = runtime_dir()
        runtime.mkdir(parents=True, exist_ok=True)
        log = log_path()
        _rotate_log()
        env = os.environ.copy()
        env["AIWORKSPACE_LAUNCHER_TOKEN"] = token
        env["AIWORKSPACE_LAUNCHER_STATE_DIR"] = str(runtime)
        command = [
            sys.executable,
            str(app_file),
            "--data-dir",
            str(settings["data_dir"]),
            "--port",
            str(port),
        ]
        options = {
            "cwd": str(root_path),
            "env": env,
            "stdin": subprocess.DEVNULL,
        }
        if os.name == "nt":
            options["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        else:
            options["start_new_session"] = True

        try:
            with log.open("a", encoding="utf-8") as output:
                output.write(
                    time.strftime("%Y-%m-%d %H:%M:%S")
                    + " Starting AIWorkSpace desktop service.\n"
                )
                output.flush()
                process = subprocess.Popen(
                    command, stdout=output, stderr=subprocess.STDOUT, **options
                )
        except OSError as exc:
            _append_log(f"Could not start the Python service: {exc}")
            raise LauncherError(f"启动工作台失败。错误日志：{log}") from exc

        deadline = time.monotonic() + wait_timeout
        while time.monotonic() < deadline:
            if identify_existing_service(port) == "current":
                _append_log("AIWorkSpace service is ready.")
                if not _open_browser(port):
                    raise LauncherError(
                        f"工作台已经启动，但浏览器未能自动打开。请访问 http://127.0.0.1:{port}/"
                    )
                return "started"
            if process.poll() is not None:
                _append_log(f"AIWorkSpace process exited with code {process.returncode}.")
                raise LauncherError(f"工作台启动失败。请查看错误日志：{log}")
            time.sleep(poll_interval)

        _append_log("Timed out waiting for the local health endpoint.")
        _terminate_started_process(process)
        raise LauncherError(f"工作台启动超时，未确认服务就绪。请查看错误日志：{log}")


def _read_service_state(path: Path) -> dict | None:
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise LauncherError("工作台运行状态文件无法读取；没有结束任何进程。") from exc
    if (not isinstance(payload, dict) or payload.get("service") != SERVICE_NAME
            or not isinstance(payload.get("token"), str) or not payload["token"]
            or isinstance(payload.get("port"), bool)
            or not isinstance(payload.get("port"), int)
            or not 1 <= payload["port"] <= 65535):
        raise LauncherError("工作台运行状态文件无效；没有结束任何进程。")
    return payload


def _remove_state_if_token_matches(path: Path, token: str) -> None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(payload, dict) and payload.get("token") == token:
            path.unlink()
    except (OSError, UnicodeError, json.JSONDecodeError):
        pass


def stop(
    config: Path | str | None = None,
    wait_timeout: float = 10,
    poll_interval: float = 0.25,
) -> str:
    state_path = runtime_dir() / "service.json"
    state = _read_service_state(state_path)
    if state is None:
        port = DEFAULT_PORT
        config_file = Path(config).expanduser() if config is not None else config_path()
        if config_file.is_file():
            port = load_config(ROOT, config_file)["port"]
        existing = identify_existing_service(port)
        if existing:
            return "unmanaged"
        if port_in_use(port):
            raise LauncherError(
                f"端口 {port} 正被其他程序使用。为安全起见，没有结束任何进程。"
            )
        return "not_running"

    port = state["port"]
    token = state["token"]
    existing = identify_existing_service(port)
    if not existing:
        if not port_in_use(port):
            _remove_state_if_token_matches(state_path, token)
            return "not_running"
        raise LauncherError(
            f"端口 {port} 被占用，但无法确认它是本工作台。没有结束任何进程。"
        )

    status, _payload = _request_json(
        port,
        SHUTDOWN_PATH,
        method="POST",
        headers={"X-AIWorkSpace-Control-Token": token},
    )
    if status != 202:
        raise LauncherError(
            "停止请求未获本机工作台授权；没有结束任何进程。"
            "如果工作台是从旧 PowerShell 窗口启动的，请先关闭那个窗口。"
        )

    deadline = time.monotonic() + wait_timeout
    while time.monotonic() < deadline:
        if not identify_existing_service(port) and not port_in_use(port):
            _remove_state_if_token_matches(state_path, token)
            return "stopped"
        time.sleep(poll_interval)
    raise LauncherError("已发送停止请求，但服务仍未退出。请稍后检查工作台状态。")


def _show_message(message: str, error: bool = False) -> None:
    if os.name == "nt":
        try:
            flags = 0x10 if error else 0x40
            ctypes.windll.user32.MessageBoxW(None, message, "AI 工作台", flags)
            return
        except Exception:
            pass
    print(message, file=sys.stderr if error else sys.stdout)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="AIWorkSpace desktop launcher")
    parser.add_argument("action", choices=("start", "stop"))
    parser.add_argument("--config", type=Path, default=None)
    args = parser.parse_args(argv)
    try:
        if args.action == "start":
            result = start(config=args.config)
            if result == "legacy_running":
                _show_message(
                    "检测到已经通过旧方式启动的工作台，已打开现有网页，没有重复启动。\n\n"
                    "首次切换时，请先关闭原来的 PowerShell 窗口；之后使用桌面快捷方式启动，"
                    "即可在后台运行。"
                )
        else:
            result = stop(config=args.config)
            if result == "stopped":
                _show_message("AI 工作台已关闭。")
            elif result == "not_running":
                _show_message("AI 工作台当前没有运行。")
            elif result == "unmanaged":
                _show_message(
                    "AI 工作台正在运行，但不是由桌面快捷方式启动的。\n\n"
                    "为避免误结束其他进程，此快捷方式没有停止它。"
                    "请先关闭旧 PowerShell 窗口一次，再使用新的桌面快捷方式启动。"
                )
        return 0
    except LauncherError as exc:
        _show_message(str(exc), error=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
