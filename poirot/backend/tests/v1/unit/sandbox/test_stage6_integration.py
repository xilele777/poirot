"""Stage 6 集成测试（需 Docker + agent_sandbox）。

skip if no docker or no agent_sandbox installed.
"""

from __future__ import annotations

import pytest

from poirot.backend.tests.v1.fixtures.docker_guard import docker_daemon_reachable
from poirot.backend.tests.v1.fixtures.sdk_stubs import has_real_agent_sandbox

pytestmark = pytest.mark.integration

# 不用 pytest.importorskip：它只检查导入是否抛 ImportError，而单测文件注入的
# 占位模块能满足导入，使本文件不再跳过、带着假 SDK 运行后崩溃（误报失败）。
if not has_real_agent_sandbox():
    pytest.skip("agent_sandbox not installed", allow_module_level=True)
if not docker_daemon_reachable():
    pytest.skip("docker daemon not reachable", allow_module_level=True)

from poirot.backend.agents.sandbox.docker.docker_sandbox_provider import (  # noqa: E402
    DockerSandboxProvider,
)
from poirot.backend.agents.sandbox.runtimes.docker_runtime import DockerRuntime  # noqa: E402


@pytest.fixture
def provider() -> DockerSandboxProvider:
    return DockerSandboxProvider(
        image="ghcr.io/agent-infra/sandbox:latest",
        base_port=19000,
        container_prefix="poirot-itest",
        idle_timeout=0,
    )


class TestIntegration:
    """端到端：DockerSandboxProvider acquire → Sandbox 文件操作 → release → reclaim → shutdown。"""

    def test_acquire_and_exec(self, provider: DockerSandboxProvider) -> None:
        sid = provider.acquire("itest-thread")
        try:
            sandbox = provider.get(sid)
            assert sandbox is not None
            output = sandbox.execute_command("echo hello")
            assert "hello" in output
        finally:
            provider.shutdown()

    def test_release_and_reclaim(self, provider: DockerSandboxProvider) -> None:
        sid = provider.acquire("itest-thread")
        provider.release(sid)
        # reclaim from warm pool
        sid2 = provider.acquire("itest-thread")
        assert sid == sid2
        provider.shutdown()

    def test_shutdown_destroys_all(self, provider: DockerSandboxProvider) -> None:
        sid = provider.acquire("itest-thread")
        provider.shutdown()
        # after shutdown, get returns None
        assert provider.get(sid) is None
