from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from poirot.backend.agents.middlewares.sandbox_middleware import SandboxMiddleware
from poirot.backend.agents.sandbox.translators.docker_path_translator import DockerPathTranslator
from poirot.backend.agents.sandbox.guards.docker_path_guard import DockerPathGuard
from poirot.backend.agents.sandbox.exceptions import SandboxPermissionError


def exporter(tmp_path):
    root = tmp_path / "sandboxes" / "s1"
    root.mkdir(parents=True)
    translator = DockerPathTranslator(root.parent, "s1")
    sandbox = SimpleNamespace(get_host_path=translator.reverse_translate)
    server = Mock()
    server.register.return_value = "http://localhost/artifact"
    middleware = SandboxMiddleware(SimpleNamespace(get=lambda _: sandbox), server,
                                   outputs_dir=tmp_path / "exports")
    return root, middleware, server


def export(middleware, path):
    return middleware._register_artifacts(SimpleNamespace(tool_call={"args": {"paths": [path]}}), "s1")


@pytest.mark.parametrize("suffix", ["../outside.txt", "a/../../outside.txt", "a\\..\\outside.txt",
                                     "/outside.txt", "C:/outside.txt", "NUL", "file:stream", "dir./file"])
def test_invalid_path_does_not_copy_or_register(tmp_path, suffix):
    root, middleware, server = exporter(tmp_path)
    (root.parent / "outside.txt").write_text("private fixture")
    assert export(middleware, "/mnt/poirot/user-data/" + suffix) == []
    server.register.assert_not_called()
    assert not (tmp_path / "exports").exists()


def test_nested_file_exports_and_missing_file_does_not_register(tmp_path):
    root, middleware, server = exporter(tmp_path)
    (root / "nested").mkdir()
    (root / "nested" / "report.txt").write_text("report")
    assert export(middleware, "/mnt/poirot/user-data/nested/report.txt")
    assert (tmp_path / "exports/nested/report.txt").read_text() == "report"
    server.reset_mock()
    assert export(middleware, "/mnt/poirot/user-data/missing.txt") == []
    server.register.assert_not_called()


@pytest.mark.parametrize("side", ["source", "destination"])
def test_symlink_escape_is_rejected(tmp_path, side):
    root, middleware, server = exporter(tmp_path)
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "report.txt").write_text("outside")
    (root / "report.txt").write_text("inside")
    link = root / "link" if side == "source" else tmp_path / "exports" / "link"
    link.parent.mkdir(exist_ok=True)
    try:
        link.symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("symlink creation unavailable")
    if side == "destination":
        (root / "link").mkdir()
        (root / "link/report.txt").write_text("inside")
    assert export(middleware, "/mnt/poirot/user-data/link/report.txt") == []
    assert (outside / "report.txt").read_text() == "outside"
    server.register.assert_not_called()


def test_copy_failure_does_not_register(tmp_path, monkeypatch):
    root, middleware, server = exporter(tmp_path)
    (root / "report.txt").write_text("fixture")
    monkeypatch.setattr("poirot.backend.agents.middlewares.sandbox_middleware.shutil.copy2",
                        Mock(side_effect=OSError("disk unavailable")))
    assert export(middleware, "/mnt/poirot/user-data/report.txt") == []
    server.register.assert_not_called()


@pytest.mark.parametrize("command", ['echo hi > "/tmp/out"', "echo hi > '/tmp/out'",
                                       "echo hi > /mnt/poirot/user-data/../out"])
def test_guard_rejects_quoted_and_traversal_redirects(command):
    with pytest.raises(SandboxPermissionError):
        DockerPathGuard().validate_command(command)
