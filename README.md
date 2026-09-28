<div align="center">

<img alt="Poirot README Hero" width="960" src="resource/assets/poirot-readme-hero.png">

### 带长期记忆的深度研究 Agent 内核

[![License: MIT](https://img.shields.io/badge/License-MIT-7c6ff0?style=for-the-badge)](LICENSE)
[![Python 3.12+](https://img.shields.io/badge/Python-3.12+-45c4b8?style=for-the-badge)](https://www.python.org/)
[![LangGraph](https://img.shields.io/badge/LangGraph-1.x-5aa9f5?style=for-the-badge)](https://github.com/langchain-ai/langgraph)
[![DeepSeek](https://img.shields.io/badge/LLM-DeepSeek-00BFFF?style=for-the-badge)](https://www.deepseek.com/)

**📚 文档：** [简体中文](README.md) · [English](resource/README.en.md) · [使用说明](resource/USAGE.zh-CN.md) · [日本語](resource/USAGE.ja.md)

<sub>ReAct 循环 · 上下文治理 · 五层记忆 · 多 Agent 编排 · Skill 自进化 · Sandbox 隔离</sub>

</div>

---

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="resource/assets/poirot-logo.png">
  <img alt="Poirot" width="720" src="resource/assets/poirot-logo.png">
</picture>

## 项目简介

Poirot 是面向**关注 Agent 如何被架构的人**设计的深度研究 Agent 内核。它不追求功能清单的堆砌，而是建立一个清晰、解耦、可评估的基础——从 ReAct 核心循环到上下文工程治理，从五层长期记忆系统到共享沙箱隔离的多 Agent 编排，从沙箱路径管控到三层 Skill 自进化体系。

每个模块都独立设计、独立测试、独立可验证。**2400+ 测试**守护每一层。

---

## 核心模块

### 🧠 ReAct 研究内核

单个 `LeaderAgent` 编排研究循环。LangGraph 负责外层流程编排（`prepare → leader_agent → finalize`），**21 个 middleware** 横切每个生命周期钩子：`before/after_agent`、`before/after_model`、`wrap_tool_call`。

**突破点：** middleware 是一等公民——记忆召回、Skill 注入、Sandbox 生命周期、记忆巩固、工具调用配对、求助请求、上下文治理全部是可插拔的横切关注点，而非内嵌在 Agent 循环里。`app → agents` 的依赖严格单向。

### 📐 上下文工程治理

`DefaultStrategy` 基于实时 token 预算动态外置历史消息。窗口大小通过**穿透 `FallbackChatModel`** 解析到当前 provider 的真实上下文窗口——不写死阈值。压缩（摘要）与外置（卸载）双策略并行，让长时间研究会话既不会上下文溢出，也不丢失关键信息。

**突破点：** 治理层把 token 预算当作一等运行时关注点。分母是*真实*模型窗口（调用时解析），而非静态配置——这使 P5 熔断阈值在切换 provider 后依然准确。

### 🧬 五层长期记忆

Poirot 实现了受认知科学启发的五层记忆系统，每层独立可测：

| 层 | 职责 | 关键设计 |
|-------|------|-----------------|
| **L1** | Schema + Protocol | `MemoryTrace` 冻结 dataclass（15 字段）+ `MemoryType` 枚举（episodic/semantic/procedural）+ 5 个原子操作（Encode/Retrieve/Associate/Consolidate/Reconsolidate）——**工具不含 LLM**，纯数据操作 |
| **L2** | Default Strategies | 艾宾浩斯衰减公式（`strength = base×(1-decay)^hours + log(1+access)×0.1 + importance×0.05`）+ 复合遗忘（TTL + 强度阈值）+ 6 条硬编码决策（A1-F2）——**惰性衰减**，strength 在检索时计算，无后台任务 |
| **L3** | Store + Retriever | `MarkdownFileStore`（单一 `traces.md` 真源 + `<!-- trace: {id} -->` 分隔符 + YAML frontmatter）+ `HybridRetriever`（纯 BM25，不依赖向量/图）——**检索强化回写**（1A：命中后 store.update 强化 strength）+ **遗忘过滤**（3B：metadata.forgotten=True 被排除）+ **增量索引**（5B：store 装饰器触发 retriever.on_trace_*） |
| **L4** | Middleware + Bootstrap | `MemoryMiddleware.abefore_model`——按调用注入 `HumanMessage`（保护 prompt 缓存，`hide_from_ui=True`）+ `set_turn_id` ContextVar（可追溯性 C：actor = turn:N）+ bootstrap 生命周期（懒加载双重检查锁 + `set_memory_config` 全局单例同步） |
| **L5** | Auto-Consolidation | `MemoryConsolidationMiddleware.aafter_model`——每 N 轮**非阻塞**提交 + `MemoryWorker`（守护线程 + `threading.Queue` + LLM 构造注入）——LLM 抽取情景记忆 → `manager.encode` → 候选 ≥ N → LLM 生成合并内容 → `manager.consolidate`（max=10，E1）——**出错只记日志并跳过**，绝不阻塞主循环 |

**关键设计：** 记忆以按调用的 `HumanMessage` 注入（而非 system prompt），保护 LLM 的 prompt 缓存前缀。state 中的 `recalled_memories` 只存索引（id+score+strength），不存全文。`MemoryConfig` 有 4 个 STARTUP_ONLY 字段（use/storage_path/vector_store/graph_store），其余可通过 `set_memory_config()` 运行时替换。

### 🤝 多 Agent 编排

Poirot 支持把子任务委派给外部编码 Agent 和内部自我副本：

- **专家委派（Specialist Delegation）**——`delegate_to_specialist(goal, success_criteria)` 通过 MCP `SpecialistMcpServer`（暴露 8 个 sandbox 工具）路由到外部 CLI（pi / codex / claude）。每个专家是独立进程、独立 LLM，但通过 `--sandbox-url` 透传**共享同一个 Docker 沙箱**。
- **子 Agent（自我副本）**——`delegate_to_subagent(goal)` 创建上下文隔离的 Poirot 自我副本（不继承消息历史），但共享 thread sandbox。`SandboxMiddleware.abefore_model` 从 `state["sandbox"]` 恢复 `ContextVar`——子 Agent 复用父级的 `sandbox_id`，无需重新申请。
- **L2 进化层**——数据驱动的专家自进化：`MetricMonitor` 在 `effective_rate < threshold` 时触发，`IVEFocuser` 诊断，`LLMMutator` 变异，`ScoreDeltaGate` 把关，`GitRatchet` 在退化时回滚。
- **L3 评估层**——三层评估：执行判定（逐 Skill 逐任务 LLM）、任务质量评分（四维加权）、响应契约检查。`RuntimeTracker` 把退化信号回馈给 L2。

**突破点：**「共享 thread sandbox」（INV#3）已**真正落地**——子 Agent 从 state 恢复 ContextVar，专家连接到同一挂载区写入，而非容器内的临时路径。

### 🛡️ Sandbox 隔离与路径管控

两个 provider：**Local**（宿主进程，用于开发）与 **Docker**（容器隔离，用于生产）。

**Docker 模式突破点：**

- **`DockerPathTranslator`**——`translate_path` 直通（容器路径 = bind mount 路径），`reverse_translate` 把 `/mnt/poirot/user-data/<x>` 映射回 `<sandbox_root>/<sandbox_id>/<x>`（Windows 宿主路径）——修复了 `present_files` 产物提取链路（`shutil.copy2` 现在拿到的是真实 Windows 路径，而非容器路径）
- **`DockerPathGuard`**——写路径白名单：`write_file`/`str_replace` 的路径必须在 `/mnt/poirot/user-data/` 下，bash 重定向目标（`>{1,2}\s*(/[^\s;|&]*)`）必须在挂载区内——**强制 Agent 的写入落盘持久化**，不会因 `--rm` 丢在容器内部 `/tmp`
- **热池**——预创建容器降低冷启动延迟
- **空闲自动销毁**——`POIROT_SANDBOX_IDLE_TIMEOUT=600`（10 分钟）
- **跨进程锁**——并发 Poirot 实例不冲突（open/lock/unlock 三函数锁）
- **WSL2 executor**——`WslDockerExecutor` 把 `D:\foo\bar` 转换成 `/mnt/d/foo/bar`，适配 WSL2 中的 Docker daemon

### 🔌 MCP 工具生态

三种传输：`stdio`、`sse`、`http`。核心工具启动时加载，非核心工具按需延迟加载。工具等价回退链（如 `web_search` → MCP server → 内置 ddg）保证韧性。工具元数据驱动外置阈值。通过 `.poirot/mcp_servers.yaml` 配置。

### 🎯 三层 Skill 架构

Skill 是**研究过程的知识包**——提示词层面的注入，不是可执行函数。「如何验证一个来源」是 Skill，「执行一次网页搜索」是工具。

- **第 1 层（基础）：** SQLite 存储 + 版本 DAG、质量过滤的 LLM 混合选择、注入 middleware，以及四计数器指标（selections / applied / completions / fallbacks）。
- **第 2 层（进化）：** `IVEFocuser` 诊断、`LLMMutator` 变异、`ScoreDeltaGate` 把关、`GitRatchet` 棘轮回滚。当有效率跌破阈值时 Skill 自动进化。
- **第 3 层（评估）：** 三层评估——执行判定、任务质量评分（四维加权）、响应契约检查。`RuntimeTracker` 监控应用率趋势，把退化信号回馈给第 2 层。

36 个内置 Skill，覆盖 5 个类别（core / research / software-development / creative / productivity）。核心 Skill 自动加载，其余通过 `/skill search` 发现。

### 🎨 双 UI

- **TUI**（默认）：全屏 Textual 应用，含欢迎视图 + 会话视图。左侧可滚动日志、底部输入框、带实时 token 用量的状态栏。宽屏显示右侧会话信息面板。
- **CLI**（`poirot cli`）：传统滚动模式，基于 `prompt_toolkit` + `rich`。支持斜杠命令补全 + 底部工具栏。

### 🔄 多 LLM 回退

`FallbackChatModel` 构建基于角色的路由链（researcher / reporter）。遇到瞬时 API 故障（限流、超时、5xx）时自动降级到下一个 provider。DeepSeek 始终位于链尾作为最终兜底。

### 📊 可观测性

`RunJournal` 记录结构化事件（`skill.select`、`skill.apply`、`memory.encode`、`memory.consolidate`、`compaction`、`budget`）。thread 目录持久化运行产物。`/expand` 命令展开上一轮的完整 Thought 文本与工具结果。

---

## 架构

<div align="center">

<img src="resource/assets/poirot-architecture-diagram.png" alt="Poirot Architecture" width="880">

</div>

<sub>外层流程：`prepare → before_agent → LeaderAgent (ReAct loop) → after_agent → finalize`。21 个 middleware 横切每个钩子。记忆召回（L4）发生在 `before_model`，记忆巩固（L5）在 `after_model`。Skill 注入（L1+L2+L3）在 `before_model`。工具调用经 `wrap_tool_call` 路由到 Sandbox / MCP / Builtin。多 Agent 委派通过 `delegate_to_specialist` / `delegate_to_subagent`。</sub>

---

## 快速开始

```bash
# 1. 克隆
git clone https://github.com/xilele777/poirot.git && cd poirot

# 2. 创建环境（Python 3.12+）
python -m venv .venv
.venv\Scripts\activate         # Windows
# source .venv/bin/activate    # Linux / macOS

# 3. 安装
pip install -e ".[dev]"

# 4. 配置
cp .env.example .env
# 编辑 .env —— 至少填入：DEEPSEEK_API_KEY=sk-xxx

# 5. 启动（默认 TUI）
poirot
```

<sub>输入问题即可开始研究。输入 `/` 触发命令补全，`/help` 查看全部命令。</sub>

### 启用高级功能

```env
# 长期记忆（L4 召回 + L5 自动巩固）
POIROT_MEMORY_USE=default
POIROT_MEMORY_PHASE2_ENABLED=true
POIROT_MEMORY_PHASE2_TURNS=10

# Skill 系统（L1 基础 + L2 进化 + L3 评估）
POIROT_SKILL_ENABLED=true
POIROT_SKILL_EVOLVE_ENABLED=true
POIROT_SKILL_EVAL_ENABLED=true
POIROT_SKILL_MAX_INJECT=15

# 多 Agent（专家委派 + L2/L3）
POIROT_MULTIAGENT_ENABLED=true
POIROT_MULTIAGENT_L2_ENABLED=true
POIROT_MULTIAGENT_L3_ENABLED=true

# Docker 沙箱（容器隔离）
POIROT_SANDBOX_USE=poirot.backend.agents.sandbox.docker.docker_sandbox_provider:DockerSandboxProvider
POIROT_SANDBOX_EXECUTOR=wsl              # Windows + WSL2 Docker

# MCP 工具
POIROT_MCP_ENABLED=true
```

> **👉 完整配置、命令参考与故障排查，见[使用说明书](resource/USAGE.zh-CN.md)。**

---

## 界面截图

<div align="center">

<img src="resource/assets/screenshot-tui-conversation.png" alt="Poirot TUI Conversation" width="880">

<sub>TUI 会话视图——双栏布局，含实时上下文治理、Sandbox 状态与记忆召回</sub>

</div>

---

## 技术栈

<div align="center">

![Python](https://img.shields.io/badge/Python-3776AB?style=flat-square&logo=python&logoColor=white)
![LangGraph](https://img.shields.io/badge/LangGraph-1.x-00BFFF?style=flat-square)
![LangChain](https://img.shields.io/badge/LangChain-1.x-1c3c3c?style=flat-square)
![Rich](https://img.shields.io/badge/Rich-13+-red?style=flat-square)
![Textual](https://img.shields.io/badge/Textual-0.40+-7c6ff0?style=flat-square)
![prompt_toolkit](https://img.shields.io/badge/prompt__toolkit-3+-45c4b8?style=flat-square)
![SQLite](https://img.shields.io/badge/SQLite-skill_store-003B57?style=flat-square&logo=sqlite&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-Sandbox-2496ED?style=flat-square&logo=docker&logoColor=white)
![PyYAML](https://img.shields.io/badge/PyYAML-config-6c4097?style=flat-square)

</div>

---

## 致谢

Poirot 站在巨人的肩膀上。其架构从若干优秀的开源项目与研究框架中获得启发：

**Agent 架构**——middleware 优先的设计与 ReAct 循环编排模式，受现代 Agent 框架启发。关注点分离——记忆、Skill、Sandbox、工具路由都是可插拔的横切 middleware，而非内嵌的 Agent 逻辑——建立在对解耦、可测架构有追求的对话式 Agent 平台之上。

**记忆系统**——五层记忆架构（schema → strategies → store → middleware → auto-consolidation）受认知科学中情景记忆、语义记忆与程序性记忆模型的启发。艾宾浩斯衰减公式、惰性强度计算、Markdown 作为真源等模式，来自 AI Agent 设计中长期记忆的研究。「工具不含 LLM」原则——原子操作是纯数据变换，LLM 编排位于 middleware 层——受那些将引擎与编排分离的记忆框架设计启发。

**多 Agent 编排**——专家委派模型（Poirot 通过 MCP 把编码任务委派给外部 CLI Agent）与共享 thread sandbox 概念，建立在编码 Agent 生态的多 Agent 协作模式之上。由主 Agent 编排各具 LLM 与工具集的专家子 Agent、同时共享统一沙箱以保持产物连续性的思路，受生产级多 Agent 系统设计启发。

**Sandbox 隔离**——三组件沙箱模型（Runtime + PathTranslator + SecurityGuard）与热池生命周期管理，受深度研究 Agent 平台的沙箱隔离模式启发。Docker 路径转换与挂载区强制，解决了跨平台（Windows + WSL2 + Docker）文件持久化的真实难题。

**Skill 自进化**——三层 Skill 架构（基础存储 → LLM 驱动进化 → 多维评估）配合棘轮回滚与质量把关，建立在自我改进 Agent 研究之上。把 Skill 视为「过程知识包」（提示词层注入，而非可执行函数）的概念，来自提示词工程与 Skill 管理框架。

谨向上述项目的开发者与研究者致谢——无论是直接的代码模式、架构思想还是研究论文，你们的工作让 Poirot 成为可能。

---

## 来源说明

本仓库是 [HezaoHezao/poirot](https://github.com/HezaoHezao/poirot) 的独立维护派生版本。原始 Git 历史、上游作者署名与 [`LICENSE`](LICENSE) 均已保留。

本仓库的改动记录在 [`learn/`](learn/) 下，可能未同步到上游。欢迎在本仓库提交 issue 与 PR。

---

## 许可证

[MIT](LICENSE) © Poirot Authors

---

<div align="center">

<sub>为关注 Agent 如何被构建的人而做。</sub><br>
<sub>如果这个项目对你有帮助，欢迎点一个 ⭐</sub>

</div>
