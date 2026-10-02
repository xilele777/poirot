# 当前限制与使用边界

核对日期：2026-10-02。适用代码基线：本地 `4da4ca9`，包含本轮记忆、产物边界、运行时装配与打包修复。

另已修复[Responses 流式回答重复显示](../learn/changes/0014-2026-10-02-变更-修复Responses流式回答重复显示.md)；该修复已通过相关回归和真实接口短问答复核。

随后修复了[失败证据污染、手动报告导出及检查点类型注册](../learn/changes/0015-2026-10-02-变更-修复失败证据污染与报告导出.md)；默认全量 2785 passed / 4 skipped / 1 deselected。真实搜索服务的空结果原因仍未确认。

当前适合个人使用、Agent 二次开发和固定任务的小范围试点；尚未完成稳定对外服务或长期无人值守的验收。本文汇总已确认的限制和验证缺口，不把缺少验收等同于功能必然失败。

开始使用见[上手指南](quick-start.md)，技术边界详解见[能力与限制](capabilities-and-limitations.md)。

## 已确认的限制

### 1. 真实任务成功率与研究质量尚未系统验收

- 默认测试排除 `integration` 标记；部分最小 Agent/CLI 集成测试使用 fake 模型。
- 2026-10-02 已记录 **2755 passed / 4 skipped / 1 deselected**，独立 wheel 安装与构图检查通过。这证明相应测试范围内的行为，不证明真实研究准确率、成本、长任务稳定性或外部服务可用性。
- 2026-09-28 有真实模型对话、Local 命令执行和运行时构建记录，但不能代替本轮修复后的完整真实任务验收。
- 使用建议：先选 5～10 个固定任务，记录完成率、来源质量、耗时、费用和失败原因，人工核对输出后再扩大用途。

依据：[默认测试配置](../pyproject.toml)、[最近验收记录](../learn/changes/0010-2026-10-02-变更-修复数据边界并收口工程交付.md)、[早期环境验证](../learn/changes/0006-2026-09-28-变更-切换非Docker开发模式.md)。

### 2. 重启后不能恢复完整会话

- 检查点使用进程内 `InMemorySaver`。当前进程内切换模式或模型可以保留会话状态，退出后不会保留完整检查点。
- 磁盘日志、报告和长期记忆各有用途，不等于对话恢复；下次传相同 `--thread-id` 也不能据此恢复上次上下文。
- 使用建议：一个任务尽量在同一次交互中完成，退出前生成并另存报告；重新启动时补充必要背景。

依据：[checkpointer.py](../poirot/backend/agents/runtime/checkpointer.py)。

### 3. Skill 自动进化与自动回滚未接入应用调度

- 已有加载、选择、注入、版本记录，以及启用后手动执行的 evolve/capture。
- `EvolutionManager.run_cycle` 和 `GitRatchet` 仍是实验组件，没有接通应用后台调度；打开 Skill 进化开关不会自动获得这两项能力。
- 使用建议：基础 Skill 和手动进化按需启用，不依赖无人值守自我优化。

依据：[EvolutionManager](../poirot/backend/agents/skill/evolution/manager.py)、[GitRatchet](../poirot/backend/agents/skill/evolution/gates/git_ratchet.py)、[应用装配](../poirot/backend/app/bootstrap.py)。

### 4. 专家自动进化与评估尚不可用

- 专家/子 Agent 普通委派有实现，但专家 L2/L3 缺少应用级真实进化模型调用器和任务评估器。
- 当前应用在 MultiAgent 总开关开启时对 L2/L3 做启动前校验，启用后会明确报配置错误；部分进化 CLI 仍是未实现入口。
- 使用建议：保持 `POIROT_MULTIAGENT_L2_ENABLED=false`、`POIROT_MULTIAGENT_L3_ENABLED=false`；不要把普通委派可用理解为自动进化可用。

依据：[专家配置与校验](../poirot/backend/agents/multiagent/config.py)、[进化 CLI](../poirot/backend/agents/multiagent/evolution/cli.py)。

### 5. 手动 Skill 进化的通过分数不能证明任务效果提升

- 当前门控主要检查 Skill 文本格式、关键词和规则；尚未形成固定真实任务上的候选与基线对照验收。
- 使用建议：保留旧版本，用相同任务人工比较新旧结果；不要只凭接受决策或评估分数判断变好。

依据：[能力与限制：进化与评估](capabilities-and-limitations.md#进化与评估)。

### 6. Skill 版本与评估记录不是一个原子事务

- 创建版本和写入评估记录是两个存储操作。失败会向上传播，但记录失败时，版本可能已经创建。
- 使用建议：失败后先查看 `/skill history <name>`，确认现有版本，再决定是否重试。

依据：[EvolutionManager](../poirot/backend/agents/skill/evolution/manager.py)、[修复记录](../learn/changes/0010-2026-10-02-变更-修复数据边界并收口工程交付.md)。

### 7. 中文长期记忆召回能力有限

- 默认检索为 BM25，使用空格分词；没有中文专用分词、向量检索或图检索。
- 中文查询措辞变化后可能难以命中。当前没有中文召回率基准，不能给出质量比例。
- 使用建议：对关键事实保留稳定关键词；需要准确引用的信息在当前任务中明确提供。

依据：[记忆检索实现](../poirot/backend/agents/memory/strategies/default/retriever.py)。

### 8. 记忆存储不适合直接视为大规模事务数据库

- 独立实例/进程的单次存储操作已有锁与原子替换，但每次提交仍全量序列化 Markdown。
- 多次 manager 调用不构成整体事务；显式 `update` 是整条替换，需要条件更新的调用方应使用 `compare_and_update`。
- 大规模记忆性能以及网络文件系统上的锁、原子替换语义尚未验收。
- 使用建议：先使用本地磁盘和有限规模数据；生产容量与跨主机共享另行评估。

依据：[记忆一致性说明](capabilities-and-limitations.md#记忆一致性)。

### 9. Local 模式没有容器隔离

- Local 文件操作和命令在宿主执行；命令黑名单与路径检查不构成对不可信代码的完整隔离。
- 产物路径检查也不能全面防护恶意宿主进程并发替换文件或符号链接。
- 使用建议：仅做文件读写时可设 `POIROT_SANDBOX_ALLOW_HOST_BASH=false`；确需命令时再启用。处理不可信代码应另外配置、验收隔离运行环境。

依据：[文件和命令边界](capabilities-and-limitations.md#文件和命令边界)、[LocalRuntime](../poirot/backend/agents/sandbox/runtimes/local_runtime.py)。

### 10. Docker 命令检查不能保证所有写入都进入持久化目录

- 已校验文件路径及直接绝对路径重定向，但不会完整解析 shell；变量展开、相对路径、`tee`、脚本内部写入等不受该正则全面约束。
- 这属于命令策略的覆盖范围限制，不是已确认的容器逃逸。
- 使用建议：明确把交付文件写入 `/mnt/poirot/user-data/` 下的配置映射，再用 `present_files` 导出；以实际文件和导出成功结果验收。

依据：[DockerPathGuard](../poirot/backend/agents/sandbox/guards/docker_path_guard.py)。

### 11. 外部工具可用性依赖实际环境

- 外部专家需要对应 CLI、凭证和共享沙箱配置；MCP 需要 server 配置及其运行依赖；Docker 需要 SDK、守护进程和镜像。
- 内置 `web_search` 依赖网络与 DuckDuckGo；返回的是搜索结果及摘要，不代表已读取、核实网页全文。MCP 关闭不等于内置搜索关闭。
- 使用建议：首次只配置一个模型并关闭 MultiAgent/MCP；主链路可用后逐项启用，核对真实工具执行结果。

依据：[专家装配](../poirot/backend/agents/multiagent/bootstrap.py)、[内置搜索](../poirot/backend/agents/agent_tools/builtin/ddg_search.py)、[配置模板](../.env.example)。

### 12. 跨环境安装与持续交付保证仍有限

- 依赖采用版本范围，尚无经过验证的锁文件；新机器解析到的依赖可能不同。
- CI 当前只配置 Windows/Python 3.12；其他平台及 Python 组合需要单独验证。wheel 安装冒烟通过不等于完整部署验收。
- 修复与文档的提交、推送情况见[工作日志](../learn/WORKLOG.md)。本页不代表远端 CI 已通过；CI 结果需按对应提交单独核验。
- 使用建议：记录实际使用的提交和依赖环境。对其他机器先跑默认测试与 wheel 检查，再验收真实任务。

依据：[开发与验证](development.md)、[CI 配置](../.github/workflows/checks.yml)。

### 13. `.env` 的空值可能覆盖已设置的环境变量

- CLI 启动使用 `load_dotenv(..., override=True)`。例如 shell 中已有 `OPENAI_API_KEY`，而 `.env` 中是 `OPENAI_API_KEY=`，启动后仍会变为空值。
- 使用建议：选定 provider 的值直接填入 `.env`；若使用 shell 注入，则删除或注释 `.env` 中同名条目。修改配置后重启。
- 已有 `.env` 时不要重新复制模板覆盖它。

依据：[CLI 入口](../poirot/backend/app/cli/main.py)。

### 14. 工程维护与展示仍有待统一的部分

- 主 Agent 装配已经集中，但流式处理、Skill 命令等仍有职责较多的函数；部分历史设计引用缺少随仓库交付的完整来源。
- 目前没有统一、全面的 lint/type-check 门禁；这些是维护与验证缺口，不应直接折算为缺陷数量。
- 包元数据版本为 `0.1.0`，CLI 状态行仍有硬编码 `v1.0.0`。界面版本字样不能作为成熟度或发布验收依据。
- 使用建议：定位问题时记录 Git 提交、运行命令和错误日志，功能状态以本页及已执行验收为准。

依据：[CLI 入口](../poirot/backend/app/cli/main.py)、[包配置](../pyproject.toml)、[阶段评审](../learn/reviews/0003-2026-10-02-评审-代码质量目录架构与能力闭环.md)。

### 15. 轻量模式报告导出不等于重新综合完整会话

- 当前手动 `/report` 优先导出最新完整 AI 回答，排除工具调用前言；没有完整回答时才使用旧报告/结构化观察兜底。它不会再调用模型综合全部对话。
- 同一会话的手动报告默认保存到同一个 `artifacts/report.md`，再次导出会覆盖该文件。
- 使用建议：先让模型把讨论写成完整的 Markdown 短文，再执行 `/report`；需要多个报告版本时自行另存。

依据：[报告渲染](../poirot/backend/agents/reporting/markdown_reporter.py)、[会话报告服务](../poirot/backend/agents/reporting/thread_report.py)。

## 已修复的问题，不再作为当前未解决缺陷

| 历史问题 | 当前处理 |
|---|---|
| 搜索错误变成研究发现、日志/UI 显示假成功 | 明确失败结果不再进入证据，错误状态贯通工具账本、日志与 CLI/TUI |
| 手动 `/report` 导出旧搜索错误而非刚整理的短文 | 优先保存最新完整回答，旧报告/观察仅在没有完整回答时兜底 |
| 读取 Observation/AgentError 时出现未注册类型警告 | 显式注册应用检查点记录类型；仍是进程内存储，不增加重启恢复能力 |
| Responses 模型回答完整显示两遍 | 已关联同次调用的 provider/delta 消息 ID，防止最终状态重复追加；已修复，重启进程生效 |
| 宿主产物导出路径越界、翻译失败仍尝试降级导出 | 已增加源/目标归属校验，失败不返回成功下载地址；剩余安全范围见第 9、10 项 |
| 记忆独立实例旧快照覆盖、非原子写入 | 已加入跨进程锁、锁内重读、原子替换和索引刷新；剩余事务/容量边界见第 8 项 |
| wheel 缺少 prompt、Skill、配置及专家桥接资源 | 已显式打包运行资源，并验证独立安装后的资源加载与构图 |
| 单一非 DeepSeek provider 因角色路由空链而启动失败 | 已增加路由回退；首次使用仍可显式传 `--provider openai` 简化配置 |
| Skill 持久化失败仍显示成功 | 失败已向上传播；跨两次存储操作的原子性仍见第 6 项 |
| 多处 Leader 装配漂移、领域层反向导入应用层 | 已集中 `_assemble_leader` 并增加架构检查；仍需真实环境集成验收 |

详见[阶段修复记录](../learn/changes/0010-2026-10-02-变更-修复数据边界并收口工程交付.md)与[单 provider 修复记录](../learn/changes/0007-2026-09-28-变更-修复单provider路由空链崩溃.md)。历史评审保留当时结论，阅读时应结合后续修复。

## 建议的验收顺序

1. 单 provider 完成轻量问答、连续追问及报告保存，确认当前模型与费用。
2. 在固定任务上验证搜索来源和文件产物，记录成功、失败、耗时与费用；调用失败必须如实说明。
3. 如业务需要长任务恢复，先完成持久化会话检查点；如需要不可信代码执行，先验收隔离环境。
4. 按需验证中文记忆、外部专家与 MCP。自动进化留待真实任务评估、预算、发布和回滚机制形成闭环后再启用。

本页是限制汇总与使用建议，不代表上述后续工作已经完成。
