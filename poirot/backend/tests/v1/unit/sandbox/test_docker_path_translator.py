from __future__ import annotations

import pytest
from pathlib import Path

from poirot.backend.agents.sandbox.contracts import PathTranslator
from poirot.backend.agents.sandbox.translators.docker_path_translator import (
    DockerPathTranslator,
)


class TestDockerPathTranslator:
    def test_translate_path_passthrough(self) -> None:
        translator = DockerPathTranslator("/data/aio_docker", "abc123")
        assert translator.translate_path("/mnt/poirot/user-data/x") == "/mnt/poirot/user-data/x"

    def test_translate_command_passthrough(self) -> None:
        translator = DockerPathTranslator("/data/aio_docker", "abc123")
        cmd = "ls /mnt/poirot/user-data"
        assert translator.translate_command(cmd) == cmd

    def test_mask_output_passthrough(self) -> None:
        translator = DockerPathTranslator("/data/aio_docker", "abc123")
        assert translator.mask_output("output") == "output"

    def test_is_path_translator(self) -> None:
        translator = DockerPathTranslator("/data/aio_docker", "abc123")
        assert isinstance(translator, PathTranslator)

    def test_empty_path_passthrough(self) -> None:
        translator = DockerPathTranslator("/data/aio_docker", "abc123")
        assert translator.translate_path("") == ""

    def test_reverse_translate_nested_path(self) -> None:
        translator = DockerPathTranslator("/data/aio_docker", "abc123")
        result = translator.reverse_translate("/mnt/poirot/user-data/outputs/foo.txt")
        assert result == str(Path("/data/aio_docker/abc123/outputs/foo.txt").resolve()).replace("\\", "/")

    def test_reverse_translate_prefix_only(self) -> None:
        translator = DockerPathTranslator("/data/aio_docker", "abc123")
        result = translator.reverse_translate("/mnt/poirot/user-data")
        assert result == str(Path("/data/aio_docker/abc123").resolve()).replace("\\", "/")

    def test_reverse_translate_prefix_with_trailing_slash(self) -> None:
        translator = DockerPathTranslator("/data/aio_docker", "abc123")
        result = translator.reverse_translate("/mnt/poirot/user-data/")
        assert result == str(Path("/data/aio_docker/abc123").resolve()).replace("\\", "/")

    def test_reverse_translate_single_segment(self) -> None:
        translator = DockerPathTranslator("/data/aio_docker", "abc123")
        result = translator.reverse_translate("/mnt/poirot/user-data/foo")
        assert result == str(Path("/data/aio_docker/abc123/foo").resolve()).replace("\\", "/")

    def test_reverse_translate_non_prefix_raises(self) -> None:
        translator = DockerPathTranslator("/data/aio_docker", "abc123")
        with pytest.raises(ValueError, match="path must be under"):
            translator.reverse_translate("/tmp/foo")

    def test_reverse_translate_partial_prefix_raises(self) -> None:
        translator = DockerPathTranslator("/data/aio_docker", "abc123")
        with pytest.raises(ValueError, match="path must be under"):
            translator.reverse_translate("/mnt/poirot/user-data-extra/foo")

    def test_reverse_translate_windows_root(self) -> None:
        translator = DockerPathTranslator("D:/data/aio_docker", "abc123")
        result = translator.reverse_translate("/mnt/poirot/user-data/foo")
        assert "abc123" in result
        assert "foo" in result

    def test_reverse_translate_pathlib_root(self) -> None:
        from pathlib import Path

        translator = DockerPathTranslator(Path("/data/aio_docker"), "abc123")
        result = translator.reverse_translate("/mnt/poirot/user-data/foo")
        assert result == str(Path("/data/aio_docker/abc123/foo").resolve()).replace("\\", "/")

    def test_reverse_translate_deep_nested(self) -> None:
        translator = DockerPathTranslator("/data/aio_docker", "abc123")
        result = translator.reverse_translate(
            "/mnt/poirot/user-data/workspace/project/src/main.py"
        )
        assert result == str(Path("/data/aio_docker/abc123/workspace/project/src/main.py").resolve()).replace("\\", "/")
