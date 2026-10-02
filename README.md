# Poirot

面向 Agent 开发者的实验性深度研究内核，提供 ReAct 工具循环、上下文治理、长期记忆、Skill 管理以及 CLI/TUI。

**当前状态：可在本地开发运行，正在进行可靠性和能力闭环收口。** 部分高级模块仍是实验组件，不代表已完成自动进化或生产部署验收。

[English](resource/README.en.md) · [使用说明](resource/USAGE.zh-CN.md) · [能力与限制](docs/capabilities-and-limitations.md) · [开发与验证](docs/development.md)

## 最短运行步骤

需要 Python 3.12+。以下为 PowerShell 命令：

```powershell
git clone https://github.com/xilele777/poirot.git
cd poirot
python -m venv .venv
.venv/Scripts/Activate.ps1
pip install -e ".[dev]"
Copy-Item .env.example .env
```

编辑 `.env`，至少填写一个 provider 的 API key，例如 `DEEPSEEK_API_KEY`。随后启动：

```powershell
poirot
# 传统滚动 CLI
poirot cli
```

Linux/macOS 使用 `source .venv/bin/activate` 和 `cp .env.example .env`。不要提交 `.env` 或真实运行数据。

默认沙箱配置为空；需要文件工具时，在 `.env` 中显式选择本地开发模式：

```dotenv
POIROT_SANDBOX_USE=poirot.backend.agents.sandbox.local.local_sandbox_provider:LocalSandboxProvider
POIROT_SANDBOX_EXECUTOR=local
POIROT_SANDBOX_ALLOW_HOST_BASH=true
```

Local 模式会在宿主执行命令，不提供容器隔离。Docker 模式需要额外安装 `pip install -e ".[docker]"`、启动 Docker 并配置 provider；详见使用说明。

## 当前能力

| 能力 | 状态与边界 |
|---|---|
| ReAct、上下文治理、CLI/TUI | 已有运行链路；质量和稳定性仍依赖模型、工具与配置 |
| 长期记忆 | Markdown 持久化、BM25 检索、衰减与可选后台巩固；不是向量检索 |
| Skill | 加载、选择、注入、版本记录；手动进化可用 |
| 专家/子 Agent 委派 | 有实现；外部 CLI、凭证、共享沙箱需另行配置验收 |
| Skill 自动进化/自动回滚 | 未接入应用调度，不作为已交付能力 |
| 专家自动进化/评估 | 缺应用级模型和任务评估器；启用 L2/L3 会明确报配置错误 |
| 会话恢复 | 检查点仅进程内保存；磁盘报告和长期记忆不等于重启恢复会话 |
| 发布安装包 | 包含 prompt、内置 Skill、配置模板与专家桥接资源；有隔离安装冒烟检查 |

手动 Skill 进化的门控主要检查 Skill 文本规则，不能证明真实任务效果提升。默认检索按空格分词，中文召回仍需改进。安全边界、并发和实际集成验收范围见[能力与限制](docs/capabilities-and-limitations.md)。

## 目录

```text
poirot/backend/app/       CLI、TUI、应用装配
poirot/backend/agents/    Agent、记忆、工具、沙箱与 Skill 领域模块
poirot/backend/tests/     单元和集成测试（不进入 wheel）
docs/                    长期使用、实现与验证说明
resource/                图片及多语言使用参考
scripts/                 构建和验收脚本
learn/                   计划、评审、变更和工作日志
```

应用装配统一通过 `_assemble_leader` 创建主 Agent 和 leaf Agent；领域层不导入应用层，测试检查该依赖约束。详细说明见[架构边界](docs/architecture.md)。

## 开发验证

```powershell
python -m pytest -q
python scripts/check_wheel.py
# 已准备真实服务后单独执行，可能调用 API 或 Docker
python -m pytest -m integration
```

默认套件排除 `integration` marker。通过数不等同真实 LLM、Docker 或研究质量验收。CI 配置为 Windows/Python 3.12 的默认套件及 wheel 安装检查；其他平台另行验证。

## 来源与许可证

本仓库是 [HezaoHezao/poirot](https://github.com/HezaoHezao/poirot) 的独立维护派生版本。保留原始 Git 历史、作者署名和 [MIT 许可证](LICENSE)。第三方声明见 [THIRD_PARTY_LICENSES.md](THIRD_PARTY_LICENSES.md)。

改造过程见 [learn](learn/README.md)，问题反馈请使用[本仓库 Issues](https://github.com/xilele777/poirot/issues)。
