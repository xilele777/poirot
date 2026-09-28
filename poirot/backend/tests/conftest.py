"""项目级测试隔离层。

背景
----
本仓库测试此前零 ``conftest.py``，隔离全靠各文件自律，导致同一进程内
测试互相污染：

- 有的文件直接 ``os.environ[...] = ...`` 不还原；
- 有的模块级调用 ``load_dotenv()``（如 ``app/cli/main.py`` 导入时即加载
  ``.env``），把宿主 ``.env`` 灌进 ``os.environ``，波及同进程后续所有测试；
- 有的在模块级注入可选依赖占位模块后不清理。

污染者与受害者往往不在同一文件，只有 pytest 按字母序把整棵树串起来跑时
才相遇 —— 所以缺陷在"跑单个文件"时不可见，只在全量验收时集中爆发。

核心机制：会话基线
------------------
``_BASELINE`` 在 **conftest 导入时**快照 ``os.environ``。此刻尚未导入任何
测试模块（pytest 先加载 conftest，再收集/导入用例），因此基线是**未被测试
污染**的原始环境，且已包含调用方有意导出的 shell 变量。

:func:`_isolate_environ` 在每个测试**前后**都把 ``os.environ`` 重置回基线：
- **前**：抹掉此前测试模块导入时造成的污染（如模块级 ``load_dotenv`` 灌入
  的 ``OPENAI_MODEL``），使测试结果与文件收集顺序无关；
- **后**：抹掉本测试自身的改动，不泄漏给后续测试。

这比"快照-还原单个测试"更强：后者挡不住导入期污染（污染发生在快照之前）。
:func:`_isolate_stub_modules` 另外移除测试期间新注入的"假"占位模块。

设计原则：宁可隔离偏严——某用例若依赖跨测试的环境变更，会立刻暴露。暴露即缺陷。
"""
from __future__ import annotations

import os
import sys

import pytest

# 会话基线：conftest 导入时、任何测试模块导入之前的原始进程环境。
_BASELINE_ENV: dict[str, str] = os.environ.copy()

# pytest 自身在用例生命周期内维护的环境变量（如 PYTEST_CURRENT_TEST），
# 重置时必须保留，否则其 teardown 里 pop 这些键会 KeyError。
_PRESERVE_PREFIXES = ("PYTEST_",)

_REAL_MODULE_ATTRS = ("__file__", "__path__")


def _reset_environ() -> None:
    """把 ``os.environ`` 还原回会话基线，保留 pytest 自有变量。

    比整体 ``clear()`` 更稳：既要抹掉测试/导入期新增或改动的键，又不能
    碰 pytest 记账用的 ``PYTEST_*``。
    """
    for key in list(os.environ):
        if key.startswith(_PRESERVE_PREFIXES):
            continue
        if key not in _BASELINE_ENV:
            del os.environ[key]
    for key, value in _BASELINE_ENV.items():
        if key.startswith(_PRESERVE_PREFIXES):
            continue
        if os.environ.get(key) != value:
            os.environ[key] = value


def _is_fake_module(module: object) -> bool:
    """占位模块由 ``types.ModuleType`` 构造，无 ``__file__`` / ``__path__``。

    真实包（含 namespace package）至少有一个，据此区分，不依赖注入方打标记。
    """
    return not any(getattr(module, attr, None) for attr in _REAL_MODULE_ATTRS)


@pytest.fixture(autouse=True)
def _isolate_environ():
    """每个测试前后把进程环境重置回会话基线（见模块 docstring）。"""
    _reset_environ()
    yield
    _reset_environ()


@pytest.fixture(autouse=True)
def _isolate_stub_modules():
    """移除本测试新注入的假可选依赖占位模块。

    只清理测试期间**新增**且**是假的**模块；真实模块保持缓存（性能 + 语义正确），
    测试前已存在的模块也不动（它归上游负责）。
    """
    before = set(sys.modules)
    yield
    for name in set(sys.modules) - before:
        if _is_fake_module(sys.modules[name]):
            del sys.modules[name]
