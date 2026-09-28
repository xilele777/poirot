"""隔离层元测试：验证 ``tests/conftest.py`` 的隔离机制真的生效。

这些用例**故意**直接改全局状态（不走 ``monkeypatch``），并依赖 pytest 在
文件内按定义顺序执行：每个 ``*_pollutes`` 用例留下脏状态，紧随其后的
``*_isolated`` / ``*_restored`` 用例必须看到干净状态。若隔离层失效，
后者会失败——这正是本文件存在的意义（用测试锁住隔离层本身）。
"""
from __future__ import annotations

import os
import sys
import types

_LEAK_KEY = "POIROT_META_TEST_LEAK"
_FAKE_MODULE = "poirot_meta_fake_module"


def test_new_environ_key_pollutes() -> None:
    """故意新增一个环境变量且不清理。"""
    os.environ[_LEAK_KEY] = "leaked"
    assert os.environ[_LEAK_KEY] == "leaked"


def test_new_environ_key_isolated() -> None:
    """上一个用例新增的键，在本用例开始前应已被隔离层清除。"""
    assert _LEAK_KEY not in os.environ


def test_existing_environ_key_mutation_pollutes() -> None:
    """故意篡改一个必然存在的变量（PATH）且不还原。"""
    os.environ["PATH"] = "tampered-by-meta-test"
    assert os.environ["PATH"] == "tampered-by-meta-test"


def test_existing_environ_key_restored() -> None:
    """被篡改的已存在变量应被还原（而非仅清除新增键）。"""
    assert os.environ.get("PATH") != "tampered-by-meta-test"


def test_fake_module_injection_pollutes() -> None:
    """故意注入一个假的占位模块（无 __file__ / __path__）且不清理。"""
    sys.modules[_FAKE_MODULE] = types.ModuleType(_FAKE_MODULE)
    assert _FAKE_MODULE in sys.modules


def test_fake_module_removed() -> None:
    """上一个用例注入的假占位模块应已被隔离层移除。"""
    assert _FAKE_MODULE not in sys.modules
