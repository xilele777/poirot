"""Docker 可用性守卫。

背景：Stage5/6 集成测试此前的守卫只查 ``shutil.which("docker")``（CLI 是否在），
但 CLI 存在不等于守护进程可达 —— 本机 Docker Desktop 装了但没起，CLI 命中、
``docker info`` 却连不上 pipe，集成测试于是从"应跳过"退化成"硬失败"。

本守卫按"守护进程真实可达"判定：先查 CLI，再执行 ``docker info`` 看退出码。
"""
from __future__ import annotations

import shutil
import subprocess

__all__ = ["docker_daemon_reachable"]


def docker_daemon_reachable(timeout: int = 15) -> bool:
    """Docker CLI 存在且守护进程可达时返回 True。"""
    if shutil.which("docker") is None:
        return False
    try:
        result = subprocess.run(
            ["docker", "info"],
            capture_output=True,
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return result.returncode == 0
