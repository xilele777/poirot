from __future__ import annotations

import logging
import shutil
from pathlib import Path
from collections.abc import Awaitable, Callable
from typing import Any

from langchain.agents.middleware.types import AgentMiddleware
from langchain_core.messages import ToolMessage
from langgraph.prebuilt.tool_node import ToolCallRequest
from langgraph.runtime import Runtime
from langgraph.types import Command

from poirot.backend.agents.agent_tools.available import SANDBOX_TOOL_NAMES
from poirot.backend.agents.artifacts.server import ArtifactServer
from poirot.backend.agents.sandbox.contracts import SandboxProvider
from poirot.backend.agents.sandbox.exceptions import SandboxRuntimeError
from poirot.backend.agents.sandbox.utils.paths import contained_path, virtual_relative
from poirot.backend.agents.sandbox.integration.context import (
    get_sandbox_id,
    set_sandbox_id,
)

logger = logging.getLogger(__name__)

_VIRTUAL_PREFIX = "/mnt/poirot/user-data/"


class SandboxMiddleware(AgentMiddleware):
    """Sandbox 生命周期中间件（只 async，Grill #9）。

    INVARIANT:
    - lazy_init 硬编码 True：无 before_agent，sandbox 工具被调用时 acquire
    - abefore_model：从 state["sandbox"] 恢复 ContextVar（subagent 共享父 sandbox_id，块 D1）
    - awrap_tool_call：sandbox 工具首次调用时 acquire + set_sandbox_id + Command 持久化
    - present_files 调用后：验证路径、复制成功后向 ArtifactServer 注册
    - aafter_agent release：release 不销毁（LocalSandboxProvider no-op）
    - Sandbox 在中间件列表外层；ToolCall 在内层 catch SandboxError（Grill #9）
    - 非 sandbox 工具（web_search 等）不触发 acquire
    """

    def __init__(
        self,
        provider: SandboxProvider,
        artifact_server: ArtifactServer | None = None,
        sandbox_root: str | None = None,
        outputs_dir: str | Path | None = None,
    ) -> None:
        self._provider = provider
        self._artifact_server = artifact_server
        self._sandbox_root = sandbox_root
        self._outputs_dir = Path(outputs_dir) if outputs_dir is not None else Path.cwd() / ".poirot" / "outputs"

    async def abefore_model(
        self, state: dict[str, Any], runtime: Runtime
    ) -> dict[str, Any] | None:
        """恢复 ContextVar from state["sandbox"]（subagent 共享父 sandbox_id）。

        lead 首次调用时 state["sandbox"] 为 None，不恢复，走 awrap_tool_call acquire 流程。
        subagent 继承父 sandbox_id（state["sandbox"] 已设），此处恢复 ContextVar，
        awrap_tool_call 看到 ContextVar 已设 → 跳过 acquire → 复用父 Sandbox。
        """
        if get_sandbox_id() is not None:
            return None  # ContextVar 已设（lead 同进程多轮），不覆盖
        sandbox_state = state.get("sandbox")
        if isinstance(sandbox_state, dict) and sandbox_state.get("sandbox_id"):
            set_sandbox_id(sandbox_state["sandbox_id"])
        return None

    @staticmethod
    def _emit_sandbox_acquired(sandbox_id: str) -> None:
        """Push sandbox_acquired custom event to stream (real-time, no values-mode wait)."""
        try:
            from langgraph.config import get_stream_writer
            writer = get_stream_writer()
            writer({
                "type": "sandbox_update",
                "content": sandbox_id,
            })
        except Exception:
            logger.debug("Failed to emit sandbox_update custom event", exc_info=True)

    async def awrap_tool_call(
        self,
        request: ToolCallRequest,
        handler: Callable[[ToolCallRequest], Awaitable[Any]],
    ) -> Any:
        tool_name = request.tool_call.get("name", "")

        if tool_name not in SANDBOX_TOOL_NAMES:
            return await handler(request)

        sandbox_id = get_sandbox_id()
        first_acquire = sandbox_id is None

        if first_acquire:
            config = getattr(request.runtime, "config", None) or {}
            configurable = config.get("configurable", {}) if isinstance(config, dict) else {}
            thread_id = configurable.get("thread_id")
            if thread_id is None:
                raise SandboxRuntimeError(
                    "thread_id missing in runtime config (sandbox acquire requires thread_id)"
                )
            sandbox_id = self._provider.acquire(thread_id)
            set_sandbox_id(sandbox_id)
            self._emit_sandbox_acquired(sandbox_id)

        result = await handler(request)

        # present_files: register artifacts
        if tool_name == "present_files" and self._artifact_server is not None:
            urls = self._register_artifacts(request, sandbox_id)
            if urls and isinstance(result, ToolMessage):
                url_text = "\n".join(f"  {u}" for u in urls)
                content = result.content if isinstance(result.content, str) else str(result.content)
                result = ToolMessage(
                    content=f"{content}\n\nDownload:\n{url_text}",
                    tool_call_id=result.tool_call_id,
                    name=result.name,
                )

        if first_acquire and isinstance(result, ToolMessage):
            return Command(
                update={
                    "sandbox": {"sandbox_id": sandbox_id},
                    "messages": [result],
                }
            )
        return result

    def _register_artifacts(self, request: ToolCallRequest, sandbox_id: str) -> list[str]:
        """Copy validated files; publish a URL only after a successful copy."""
        args = request.tool_call.get("args", {})
        paths = args.get("paths", []) if isinstance(args, dict) else []
        if not isinstance(paths, list):
            return []
        sandbox = self._provider.get(sandbox_id)
        if sandbox is None:
            logger.warning("Cannot export artifacts: sandbox unavailable")
            return []
        urls: list[str] = []
        for virtual_path in paths:
            try:
                relative = virtual_relative(virtual_path)
                # Translators validate the configured source mapping, including symlinks.
                source = Path(sandbox.get_host_path(virtual_path)).resolve(strict=True)
                if not source.is_file():
                    raise ValueError("artifact is not a regular file")
                dest = contained_path(self._outputs_dir, relative)
                dest.parent.mkdir(parents=True, exist_ok=True)
                if source != dest:
                    shutil.copy2(source, dest)
                if self._artifact_server is not None:
                    urls.append(self._artifact_server.register(sandbox_id, relative, str(dest)))
            except (OSError, ValueError, TypeError) as exc:
                logger.warning("Artifact export rejected for %r: %s", virtual_path, exc)
        return urls

    async def aafter_agent(
        self, state: dict[str, Any], runtime: Runtime
    ) -> None:
        sandbox_state = state.get("sandbox")
        if sandbox_state and sandbox_state.get("sandbox_id"):
            self._provider.release(sandbox_state["sandbox_id"])

