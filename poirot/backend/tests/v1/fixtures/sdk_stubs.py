"""可选依赖 agent_sandbox 的占位注入工具。

背景
----
被测模块（``docker_runtime.py``）在顶部执行 ``from agent_sandbox import Sandbox``，
而 agent_sandbox 属于可选依赖（``pip install -e ".[docker]"``）。未安装时，
所有经由它的单测文件连导入都会失败。

为什么需要统一工具
------------------
此前每处测试各自在模块级写 ``sys.modules["agent_sandbox"]``，带来两类问题：

1. 模块级写入不会还原，污染同一进程内的后续测试。
2. 占位模块无 ``__file__``，而 ``pytest.importorskip`` 只检查导入是否抛
   ``ImportError`` —— 占位模块能骗过它，使集成测试不再跳过、带着假 SDK
   运行后在运行时崩溃，把"缺少可选依赖"变成误报失败。

用法
----
- 单测文件导入被测模块前调用 :func:`install_stub_if_missing`；
- 集成测试用 :func:`has_real_agent_sandbox` 判断，为假时显式 skip，
  不要用 ``pytest.importorskip``。
"""
from __future__ import annotations

import importlib.util
import sys
import types
from unittest.mock import MagicMock

__all__ = ["has_real_agent_sandbox", "install_stub_if_missing"]

_MODULE = "agent_sandbox"


def has_real_agent_sandbox() -> bool:
    """真实 agent_sandbox 包是否可用（占位模块不算）。

    判据是模块的 ``__file__`` / ``__path__``，而非自定义标记：占位模块由
    ``types.ModuleType`` 构造，两者皆无；真实包（含 namespace package）至少
    有一个。这样无论占位由谁注入，都能被识别，不依赖注入方配合打标记。
    """
    mod = sys.modules.get(_MODULE)
    if mod is not None:
        return bool(
            getattr(mod, "__file__", None) or getattr(mod, "__path__", None)
        )
    return importlib.util.find_spec(_MODULE) is not None


def install_stub_if_missing() -> bool:
    """真实包缺失时注入占位模块。

    返回是否注入了占位（``True`` 表示当前环境的 agent_sandbox 是假的）。
    """
    if has_real_agent_sandbox():
        return False
    if _MODULE in sys.modules:
        return True
    stub = types.ModuleType(_MODULE)
    stub.Sandbox = MagicMock
    sys.modules[_MODULE] = stub
    return True
