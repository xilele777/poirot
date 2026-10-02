# 开发与验证

需要 Python 3.12+，先执行 `python -m pip install -e ".[dev]"`。Docker SDK 仅在真实 Docker 场景安装：`python -m pip install -e ".[dev,docker]"`。

## 默认门禁

```sh
python -m pytest -q
python scripts/check_wheel.py
git diff --check
```

pytest 默认排除 integration marker；无 Docker SDK 的集成模块可能直接跳过。不要把跳过写成通过。

wheel 脚本复制干净源码至临时目录，构建 wheel，检查全部 prompt/Skill/YAML/TS 资源及测试包排除，再 `pip install --target` 到独立目录，使用 `python -I` 验证资源加载与实际构图。不会覆盖当前环境已安装的项目，但构建依赖可能需要网络。源码的 editable 安装不能替代这个检查。

`.github/workflows/checks.yml` 对 push/PR 运行 Windows/Python 3.12 默认测试与安装包检查。文档提交也触发，避免未来设置 required check 后出现等待状态。本轮不添加未验证的依赖锁文件；运行依赖仍使用 pyproject 的版本约束，CI 用于尽早发现兼容性变化，尚非完全可复现环境。

## 重点回归

```sh
python -m pytest -q poirot/backend/tests/v1/unit/artifacts/test_export_boundaries.py
python -m pytest -q poirot/backend/tests/v1/unit/memory/test_store_consistency.py
python -m pytest -q poirot/backend/tests/test_architecture.py
```

产物测试只使用临时文件；记忆测试覆盖多进程写入、独立实例刷新、原子替换失败和条件更新。不能创建符号链接的平台会明确跳过对应测试。

## 真实依赖验收

准备相应 SDK、运行服务及专用测试凭证后执行：

```sh
python -m pytest -m integration
```

真实模型可能产生费用；记录 provider/model、执行用例、通过/跳过数和失败原因。外部 CLI 专家及真实研究质量另需固定任务对照，不能以构图成功或 fake 模型响应代替。
