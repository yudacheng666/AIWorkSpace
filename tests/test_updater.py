"""Isolated tests for the safe GitHub application updater."""
from __future__ import annotations

import io
import json
import shutil
import stat
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import updater


COMMIT = "a" * 40
OLD_FILES = {
    "app.py": "old application\n",
    "updater.py": "old updater\n",
    "VERSION": "0.9.0\n",
    "web/index.html": "old page\n",
}
NEW_FILES = {
    "app.py": "from __future__ import annotations\nNEW_BUILD = True\n",
    "updater.py": "from __future__ import annotations\nNEW_UPDATER = True\n",
    "VERSION": "1.0.0\n",
    "web/index.html": "<!doctype html><title>new build</title>\n",
}


def make_archive(entries=None, prefix=None, compression=zipfile.ZIP_DEFLATED):
    values = dict(NEW_FILES if entries is None else entries)
    prefix = prefix or f"yudacheng666-AIWorkSpace-{COMMIT[:7]}"
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression) as archive:
        for name, content in values.items():
            archive.writestr(f"{prefix}/{name}", content)
    return output.getvalue()


class FakeResponse:
    def __init__(self, content, final_url=None):
        self.content = content
        self.headers = {}
        self.final_url = final_url

    def geturl(self):
        return self.final_url or "https://api.github.com/test"

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self, _size=-1):
        return self.content


class UpdaterTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)
        self.root = self.base / "application"
        (self.root / "web").mkdir(parents=True)
        self.data_dir = self.base / "private-data"
        (self.data_dir / "events").mkdir(parents=True)
        self.data_file = self.data_dir / "events" / "evt-fictional.json"
        self.data_file.write_text('{"fictional": "must remain byte-identical"}\n', encoding="utf-8")
        self.original_data = self.data_file.read_bytes()
        for relative, value in OLD_FILES.items():
            target = self.root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(value, encoding="utf-8")

    def tearDown(self):
        self.temp.cleanup()

    def make_stage(self):
        stage = self.root / ".aiworkspace-update-staging-test"
        stage.mkdir()
        for relative, value in NEW_FILES.items():
            target = stage / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(value, encoding="utf-8")
        return stage

    def assert_data_unchanged(self):
        self.assertEqual(self.data_file.read_bytes(), self.original_data)
        self.assertEqual(sorted(p.name for p in (self.data_dir / "events").iterdir()),
                         ["evt-fictional.json"])

    def test_archive_stages_only_allowlisted_application_files(self):
        stage = updater.validate_archive_and_stage(
            make_archive(), COMMIT, self.root, self.data_dir
        )
        self.assertEqual(
            sorted(p.relative_to(stage).as_posix() for p in stage.rglob("*") if p.is_file()),
            sorted(updater.APP_FILES),
        )
        self.assertEqual((stage / "VERSION").read_text(encoding="utf-8"), "1.0.0\n")
        self.assert_data_unchanged()

    def test_archive_rejects_path_traversal(self):
        values = dict(NEW_FILES)
        values["../private-data/events/evil.json"] = '{"should":"never write"}'
        with self.assertRaises(updater.UpdateError):
            updater.validate_archive_and_stage(make_archive(values), COMMIT, self.root, self.data_dir)
        self.assertFalse((self.data_dir / "events" / "evil.json").exists())
        self.assert_data_unchanged()

    def test_archive_rejects_symlink_entries(self):
        output = io.BytesIO()
        prefix = f"yudacheng666-AIWorkSpace-{COMMIT[:7]}"
        with zipfile.ZipFile(output, "w") as archive:
            info = zipfile.ZipInfo(f"{prefix}/untrusted-link")
            info.create_system = 3
            info.external_attr = (stat.S_IFLNK | 0o777) << 16
            archive.writestr(info, "../private-data")
            for name, value in NEW_FILES.items():
                archive.writestr(f"{prefix}/{name}", value)
        with self.assertRaises(updater.UpdateError):
            updater.validate_archive_and_stage(output.getvalue(), COMMIT, self.root, self.data_dir)
        self.assert_data_unchanged()

    def test_archive_rejects_wrong_commit_root_and_missing_files(self):
        with self.assertRaises(updater.UpdateError):
            updater.validate_archive_and_stage(
                make_archive(prefix="yudacheng666-AIWorkSpace-deadbee"),
                COMMIT, self.root, self.data_dir
            )
        with self.assertRaises(updater.UpdateError):
            updater.validate_archive_and_stage(
                make_archive({"app.py": NEW_FILES["app.py"]}),
                COMMIT, self.root, self.data_dir
            )

    def test_archive_rejects_invalid_version_and_python_syntax(self):
        invalid_version = dict(NEW_FILES)
        invalid_version["VERSION"] = "latest\n"
        with self.assertRaises(updater.UpdateError):
            updater.validate_archive_and_stage(make_archive(invalid_version), COMMIT,
                                               self.root, self.data_dir)
        invalid_python = dict(NEW_FILES)
        invalid_python["app.py"] = "def broken(:\n"
        with self.assertRaises(updater.UpdateError):
            updater.validate_archive_and_stage(make_archive(invalid_python), COMMIT,
                                               self.root, self.data_dir)

    def test_update_layout_rejects_data_directory_overlapping_code(self):
        with self.assertRaises(updater.UpdateError):
            updater.validate_archive_and_stage(make_archive(), COMMIT,
                                               self.root, self.root / "web")
        with self.assertRaises(updater.UpdateError):
            updater.validate_archive_and_stage(make_archive(), COMMIT,
                                               self.root, self.base)

    def test_apply_update_backups_code_and_never_changes_data(self):
        stage = self.make_stage()
        backup_base = self.base / "external-backups"
        backup = updater.apply_staged_update(
            self.root, self.data_dir, stage, COMMIT, backup_base
        )
        for relative, value in NEW_FILES.items():
            self.assertEqual((self.root / relative).read_text(encoding="utf-8"), value)
        build = json.loads((self.root / updater.BUILD_INFO_NAME).read_text(encoding="utf-8"))
        self.assertEqual(build["commit"], COMMIT)
        self.assertEqual(build["version"], "1.0.0")
        state = updater.get_install_status(self.root)
        self.assertEqual(state["build_commit"], COMMIT)
        self.assertEqual(state["last_update"]["status"], "installed")
        self.assertTrue((backup / "manifest.json").is_file())
        self.assert_data_unchanged()

    def test_rollback_restores_previous_program_and_removes_new_metadata(self):
        stage = self.make_stage()
        backup = updater.apply_staged_update(
            self.root, self.data_dir, stage, COMMIT, self.base / "backups"
        )
        updater.rollback_from_backup(self.root, self.data_dir, backup)
        for relative, value in OLD_FILES.items():
            self.assertEqual((self.root / relative).read_text(encoding="utf-8"), value)
        self.assertFalse((self.root / updater.BUILD_INFO_NAME).exists())
        self.assertFalse((self.root / updater.UPDATE_STATE_NAME).exists())
        self.assert_data_unchanged()

    def test_install_failure_rolls_back_already_replaced_files(self):
        stage = self.make_stage()
        original_copy = updater._atomic_copy
        failed = False

        def fail_once(source, target):
            nonlocal failed
            if target.name == "updater.py" and not failed:
                failed = True
                raise OSError("simulated install failure")
            return original_copy(source, target)

        with patch.object(updater, "_atomic_copy", side_effect=fail_once):
            with self.assertRaises(updater.UpdateError):
                updater.apply_staged_update(
                    self.root, self.data_dir, stage, COMMIT, self.base / "backups"
                )
        self.assertTrue(failed)
        for relative, value in OLD_FILES.items():
            self.assertEqual((self.root / relative).read_text(encoding="utf-8"), value)
        status = updater.get_install_status(self.root)
        self.assertEqual(status["last_update"]["status"], "rolled_back")
        self.assert_data_unchanged()

    def test_backup_must_be_outside_data_directory(self):
        with self.assertRaises(updater.UpdateError):
            updater.create_backup(self.root, self.data_dir, self.data_dir / "backups")
        self.assert_data_unchanged()

    def test_version_and_build_status_without_registered_build(self):
        status = updater.get_install_status(self.root)
        self.assertEqual(status["version"], "0.9.0")
        self.assertIsNone(status["build_commit"])
        self.assertFalse(status["build_known"])

    def test_update_check_uses_fixed_main_commit_and_version(self):
        self.assertFalse((self.root / updater.BUILD_INFO_NAME).exists())
        commit_payload = json.dumps({
            "sha": COMMIT,
            "commit": {
                "message": "test update\nmore detail",
                "committer": {"date": "2026-10-30T00:00:00Z"},
            },
        }).encode("utf-8")
        with patch.object(updater, "urlopen",
                          side_effect=[FakeResponse(commit_payload), FakeResponse(b"0.9.0\n")]) as mocked:
            result = updater.check_latest_update(self.root)
        self.assertEqual(result["latest_commit"], COMMIT)
        self.assertEqual(result["latest_version"], "0.9.0")
        self.assertTrue(result["update_available"])
        self.assertEqual(result["latest_message"], "test update")
        self.assertEqual(mocked.call_count, 2)
        self.assertIn("/commits/main", mocked.call_args_list[0].args[0].full_url)

    def test_update_check_reports_no_update_for_registered_current_build(self):
        (self.root / updater.BUILD_INFO_NAME).write_text(
            json.dumps({"version": "0.9.0", "commit": COMMIT}), encoding="utf-8"
        )
        commit_payload = json.dumps({"sha": COMMIT, "commit": {"message": "same"}}).encode()
        with patch.object(updater, "urlopen",
                          side_effect=[FakeResponse(commit_payload), FakeResponse(b"0.9.0\n")]):
            result = updater.check_latest_update(self.root)
        self.assertFalse(result["update_available"])

    def test_prepare_update_rejects_stale_or_non_main_commit(self):
        with patch.object(updater, "check_latest_update", return_value={
            "latest_commit": "b" * 40, "latest_version": "1.0.0"
        }), patch.object(updater, "_read_url") as download:
            with self.assertRaises(updater.UpdateError):
                updater.prepare_update(self.root, self.data_dir, COMMIT)
            download.assert_not_called()


    def test_update_check_rejects_redirects_to_untrusted_hosts(self):
        commit_payload = json.dumps({
            "sha": COMMIT, "commit": {"message": "fictional update"}
        }).encode("utf-8")
        with patch.object(updater, "urlopen", return_value=FakeResponse(
            commit_payload, "https://untrusted.example/redirected"
        )):
            with self.assertRaises(updater.UpdateError):
                updater.check_latest_update(self.root)

    def test_archive_rejects_corrupt_crc(self):
        corrupted = bytearray(make_archive(compression=zipfile.ZIP_STORED))
        needle = b"from __future__ import annotations"
        index = corrupted.find(needle)
        self.assertGreaterEqual(index, 0)
        corrupted[index] ^= 1
        with self.assertRaises(updater.UpdateError):
            updater.validate_archive_and_stage(bytes(corrupted), COMMIT,
                                               self.root, self.data_dir)
        self.assert_data_unchanged()

    def test_install_failure_exposes_backup_for_helper_retry(self):
        stage = self.make_stage()
        original_copy = updater._atomic_copy
        failed = False

        def fail_twice(source, target):
            nonlocal failed
            if target.name == "updater.py" and not failed:
                failed = True
                raise OSError("simulated first replace failure")
            return original_copy(source, target)

        with patch.object(updater, "_atomic_copy", side_effect=fail_twice):
            with self.assertRaises(updater.UpdateInstallError) as raised:
                updater.apply_staged_update(
                    self.root, self.data_dir, stage, COMMIT, self.base / "backups"
                )
        self.assertTrue(raised.exception.backup_dir.is_dir())
        self.assertTrue((raised.exception.backup_dir / "manifest.json").is_file())
        self.assert_data_unchanged()


if __name__ == "__main__":
    unittest.main()
