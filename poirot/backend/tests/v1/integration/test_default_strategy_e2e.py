"""DefaultStrategy 真实 deepseek 集成测：P4 summarize 实际压缩。"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

langchain_deepseek = pytest.importorskip("langchain_deepseek")
ChatDeepSeek = langchain_deepseek.ChatDeepSeek


def _read_env_file() -> dict[str, str]:
    """只读取项目根 ``.env`` 到字典，**不**写入 ``os.environ``。

    模块级 ``load_dotenv()`` 会在导入时把 .env 灌进进程环境，污染同进程内
    后续测试文件（如 ``test_provider_config`` 对默认模型的断言）。这里改为
    只读取值：跳过判定用文件里的值，真正需要环境变量时由用例在作用域内
    经 ``monkeypatch`` 显式注入。
    """
    for parent in Path(__file__).resolve().parents:
        env_file = parent / ".env"
        if env_file.is_file():
            try:
                from dotenv import dotenv_values
            except ImportError:
                return {}
            return {k: v for k, v in dotenv_values(env_file).items() if v is not None}
    return {}


_ENV_FILE = _read_env_file()
_DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY") or _ENV_FILE.get("DEEPSEEK_API_KEY")
_DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL") or _ENV_FILE.get("DEEPSEEK_BASE_URL")

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not _DEEPSEEK_API_KEY,
        reason="需 DEEPSEEK_API_KEY",
    ),
]

from langchain_core.messages import HumanMessage, RemoveMessage

from poirot.backend.agents.context_engineering.contract import GovernanceContext
from poirot.backend.agents.context_engineering.strategies.default.strategy import (
    DefaultStrategy,
)
from poirot.backend.agents.middlewares.tagged_context_middleware import (
    ContextAssembler,
    POIROT_SUMMARY,
)


def test_p4_summarize_real(tmp_path, monkeypatch) -> None:
    """P4 触发真实 deepseek summarize，产出 summary。"""
    # 作用域内注入凭据，退出即还原；不作为模块级副作用污染其他测试文件。
    monkeypatch.setenv("DEEPSEEK_API_KEY", _DEEPSEEK_API_KEY)
    if _DEEPSEEK_BASE_URL:
        monkeypatch.setenv("DEEPSEEK_BASE_URL", _DEEPSEEK_BASE_URL)
    model = ChatDeepSeek(model="deepseek-chat", temperature=0)
    strategy = DefaultStrategy(
        params={
            "preserve_recent": 2,
            "snapshot_dir": str(tmp_path / "snapshots"),
            "externalize_dir": str(tmp_path / "externalized"),
        },
        model=model,
    )
    messages = [
        HumanMessage(content="研究 LangGraph 上下文工程"),
        HumanMessage(content="deer-flow 有 SummarizationMiddleware"),
        HumanMessage(content="继续设计治理层"),
        HumanMessage(content="设计接入契约 GovernanceStrategy 6 hook"),
        HumanMessage(content="实现标签化"),
    ]
    governance = {"default": {"pending": ["P4"]}}
    ctx = GovernanceContext(
        state={},
        governance=governance,
        config={},
        token_counter=lambda m: 1000,
        runtime=None,
        hook="before_model",
        messages=messages,
    )
    result = strategy.before_model(ctx)
    assert result is not None
    assert result.messages_patch is not None
    assert len(result.messages_patch) >= 3
    summary_msg = next(
        m for m in result.messages_patch
        if isinstance(m, HumanMessage) and m.additional_kwargs.get(POIROT_SUMMARY)
    )
    assert len(summary_msg.content) > 0
    gov = result.state_patch["governance"]
    assert gov["default"]["summary"]
    assert gov["default"]["metrics"]["summarize_count"] == 1
    # regression：summary 写 governance.default.summary + ContextAssembler 读 default.summary 路径打通
    rendered = ContextAssembler().render_context_block({}, gov)
    assert "<summary>" in rendered
    assert gov["default"]["summary"] in rendered
