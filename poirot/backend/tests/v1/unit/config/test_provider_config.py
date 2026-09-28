import pytest

from poirot.backend.agents.config.provider_config import (
    ProviderConfig,
    ProviderConfigError,
    get_provider_config,
    select_provider_config,
)

# 本文件断言 provider 的默认模型（如 gpt-4.1-mini），依赖 *_MODEL 环境变量未设置。
# 但 integration/test_default_strategy_e2e.py 在模块导入时 load_dotenv()，会把
# 本地 .env 里的 OPENAI_MODEL 等灌进 os.environ，污染本文件后续用例。
_PROVIDER_ENV_VARS = (
    "DEEPSEEK_MODEL",
    "OPENAI_MODEL",
    "QWEN_MODEL",
    "ANTHROPIC_MODEL",
    "GEMINI_MODEL",
)


@pytest.fixture(autouse=True)
def _isolate_provider_model_env(monkeypatch):
    for var in _PROVIDER_ENV_VARS:
        monkeypatch.delenv(var, raising=False)
    yield


def test_selects_explicit_provider_before_default() -> None:
    config = select_provider_config(provider="openai")

    assert config.provider == "openai"
    assert config.model == "gpt-4.1-mini"


def test_selects_default_provider_when_not_explicit() -> None:
    config = select_provider_config(provider=None)

    assert config.provider == "deepseek"
    assert config.default is True


def test_model_override_keeps_provider_settings() -> None:
    config = select_provider_config(provider="qwen", model="qwen-max")

    assert config.provider == "qwen"
    assert config.model == "qwen-max"
    assert config.base_url == "https://dashscope.aliyuncs.com/compatible-mode/v1"


def test_missing_api_key_is_clear() -> None:
    config = ProviderConfig(
        provider="deepseek",
        model="deepseek-chat",
        api_key="",
        base_url=None,
        priority=10,
        default=True,
        enabled=True,
    )

    with pytest.raises(ProviderConfigError, match="api_key is empty for provider: deepseek"):
        config.require_api_key()
