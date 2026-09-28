import asyncio

import pytest
from langchain_core.language_models.fake_chat_models import FakeListChatModel
from langchain_core.messages import HumanMessage

from poirot.backend.agents.config.fallback_model import FallbackChatModel, _should_fallback
from poirot.backend.agents.config.model_router import ModelRouter
from poirot.backend.agents.config.provider_config import (
    ProviderConfig,
    ProviderConfigError,
    route_chain_for,
)


def _pc(name: str) -> ProviderConfig:
    return ProviderConfig(
        provider=name, model=f"{name}-m", api_key="k", base_url=None,
        priority=10, default=False, enabled=True,
    )


class _TimeoutModel(FakeListChatModel):
    def _generate(self, *a, **k):
        raise TimeoutError("api timeout")

    async def _agenerate(self, *a, **k):
        raise TimeoutError("api timeout")


class _ClientErrModel(FakeListChatModel):
    def _generate(self, *a, **k):
        raise ValueError("400 bad request")

    async def _agenerate(self, *a, **k):
        raise ValueError("400 bad request")


# --- route_chain_for ---

def test_researcher_chain_ends_with_deepseek() -> None:
    prov = [_pc("openai"), _pc("qwen"), _pc("deepseek")]
    chain = route_chain_for("researcher", prov)
    assert [p.provider for p in chain] == ["openai", "qwen", "deepseek"]


def test_reporter_chain() -> None:
    prov = [_pc("openai"), _pc("qwen"), _pc("deepseek")]
    chain = route_chain_for("reporter", prov)
    assert [p.provider for p in chain] == ["qwen", "deepseek"]


def test_deepseek_appended_as_fallback_when_missing_from_route() -> None:
    prov = [_pc("openai"), _pc("deepseek")]
    chain = route_chain_for("reflection", prov)  # route=["deepseek"]
    assert [p.provider for p in chain] == ["deepseek"]


def test_unknown_role_defaults_to_deepseek() -> None:
    prov = [_pc("deepseek")]
    chain = route_chain_for("unknown_role", prov)
    assert [p.provider for p in chain] == ["deepseek"]


def test_no_available_provider_raises() -> None:
    with pytest.raises(ProviderConfigError):
        route_chain_for("researcher", [])


def test_route_falls_back_to_available_when_role_chain_empty() -> None:
    """只配一个非 deepseek/qwen 的 provider（如 openai）时，reporter/reflection
    的角色链为空，应回退到全部可用 provider 而非抛错——否则单 provider 启动即崩。"""
    prov = [_pc("openai")]
    for role in ("reporter", "reflection"):
        chain = route_chain_for(role, prov)
        assert [p.provider for p in chain] == ["openai"]


def test_route_falls_back_prefers_role_chain_when_partial_match() -> None:
    """角色链部分命中时，用命中的部分，不回退。"""
    prov = [_pc("openai"), _pc("qwen")]
    chain = route_chain_for("reporter", prov)  # route=["qwen","deepseek"]
    assert [p.provider for p in chain] == ["qwen"]


def test_route_fallback_excludes_no_key_providers() -> None:
    """回退时不把 no_key_required 的 fake/ollama 收进降级链。"""
    openai = _pc("openai")
    fake = ProviderConfig(
        provider="fake", model="fake-chat", api_key="", base_url=None,
        priority=999, default=False, enabled=True,
    )
    ollama = ProviderConfig(
        provider="ollama", model="llama3.1", api_key="", base_url="http://localhost:11434",
        priority=110, default=False, enabled=True,
    )
    prov = [openai, ollama, fake]
    chain = route_chain_for("reflection", prov)  # route=["deepseek"]，无交集 → 回退
    assert [p.provider for p in chain] == ["openai"]


# --- _should_fallback ---

def test_should_fallback_on_timeout() -> None:
    assert _should_fallback(TimeoutError()) is True


def test_should_not_fallback_on_client_error() -> None:
    assert _should_fallback(ValueError("400")) is False


# --- FallbackChatModel ---

def test_fallback_on_transient_error() -> None:
    ok = FakeListChatModel(responses=["ok"])
    fb = FallbackChatModel(models=[_TimeoutModel(responses=["x"]), ok], provider_names=["to", "ok"])
    result = fb.invoke([HumanMessage(content="hi")])
    assert result.content == "ok"
    assert fb._active == 1  # 记忆降级后的 provider


def test_async_fallback_on_transient_error() -> None:
    ok = FakeListChatModel(responses=["ok"])
    fb = FallbackChatModel(models=[_TimeoutModel(responses=["x"]), ok], provider_names=["to", "ok"])
    result = asyncio.run(fb.ainvoke([HumanMessage(content="hi")]))
    assert result.content == "ok"


def test_client_error_propagates_without_fallback() -> None:
    ok = FakeListChatModel(responses=["ok"])
    fb = FallbackChatModel(models=[_ClientErrModel(responses=["x"]), ok], provider_names=["ce", "ok"])
    with pytest.raises(ValueError):
        fb.invoke([HumanMessage(content="hi")])


def test_all_failures_raises_last() -> None:
    fb = FallbackChatModel(
        models=[_TimeoutModel(responses=["x"]), _TimeoutModel(responses=["y"])],
        provider_names=["a", "b"],
    )
    with pytest.raises(TimeoutError):
        fb.invoke([HumanMessage(content="hi")])


# --- ModelRouter ---

def test_router_builds_fallback_chain_per_role() -> None:
    router = ModelRouter(providers=[_pc("openai"), _pc("qwen"), _pc("deepseek")])
    rm = router.build_model("researcher")
    assert isinstance(rm, FallbackChatModel)
    assert rm.provider_names == ["openai", "qwen", "deepseek"]
    pm = router.build_model("reporter")
    assert pm.provider_names == ["qwen", "deepseek"]


def test_router_chain_names() -> None:
    router = ModelRouter(providers=[_pc("openai"), _pc("deepseek")])
    assert router.chain_names("researcher") == ["openai", "deepseek"]
