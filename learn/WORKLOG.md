# 工作日志

## 2026-10-02

- 整理本地待推送工作：将[Responses 去重修复](changes/0014-2026-10-02-变更-修复Responses流式回答重复显示.md)、[失败状态与报告修复](changes/0015-2026-10-02-变更-修复失败证据污染与报告导出.md)、[上手与限制文档](changes/0013-2026-10-02-变更-整理当前限制与本地上手指南.md)拆为三笔提交，并纳入[简历项目评审](reviews/0002-2026-10-02-评审-是否适合作为简历项目.md)。本次默认测试 **2785 passed / 2 skipped / 7 deselected**，wheel 独立安装与构图、文档链接及差异检查通过；本地 `.workbuddy/` 工具记忆不上传。连同原有三笔提交，统一推送目标为 `mine/master`。下一步：核对推送结果与远端分支一致性，再开展用户体验改造。

- 修复[失败证据污染与报告导出](changes/0015-2026-10-02-变更-修复失败证据污染与报告导出.md)：根据实际运行记录，修复搜索失败误入 observations、日志/UI 假成功、手动报告被旧证据遮住及检查点类型未注册警告。新增离线“搜索失败→连续问答→报告落盘”回归，默认全量 **2785 passed / 4 skipped / 1 deselected**。同步更新限制和上手说明。下一步：重启 CLI 后重新验收报告；真实搜索服务的空结果原因另行验证。

- 修复[Responses 流式回答重复显示](changes/0014-2026-10-02-变更-修复Responses流式回答重复显示.md)：复现 provider ID 与 delta ID 不一致导致最终全文重复追加，新增调用范围内消息关联、完整快照去重及空/思考片段兜底。相关服务、CLI/TUI 和对话集成测试 **69 passed**；真实接口短问答复核显示与最终状态一致、正文仅一份。下一步：重启 CLI 加载修复，再按[上手指南](../docs/quick-start.md)验证报告和文件工具。

- 整理[当前限制清单](../docs/known-limitations.md)与[本地上手指南](../docs/quick-start.md)：汇总 15 类现存限制和验收缺口，单列已修复问题；补充单 provider 启动、首个任务、报告路径、可选能力与配置避坑，并更新文档入口。核对并说明轻量 `/report` 的导出边界，修复旧使用说明的损坏代码块及过度表述。CLI 帮助命令验证通过；8 份文档共 112 个本地链接、代码围栏、空白与差异检查通过，未进行真实模型验收。详见[变更记录](changes/0013-2026-10-02-变更-整理当前限制与本地上手指南.md)。下一步：按指南完成真实任务试用，记录质量、耗时与费用。

- 将本轮改造按记忆一致性、路径与运行时、打包与文档三个工作单元提交，分别携带代码、测试和对应记录；前两项补充[记忆提交记录](changes/0011-2026-10-02-变更-修复记忆存储并发一致性.md)及[运行时提交记录](changes/0012-2026-10-02-变更-收紧产物边界并统一运行时装配.md)，打包与文档详见[阶段记录](changes/0010-2026-10-02-变更-修复数据边界并收口工程交付.md)。提交前差异检查通过，沿用本轮已通过的全量测试及 wheel 安装检查结果；保留无关未跟踪文件，未推送。下一步按[后续计划](plans/0004-2026-10-02-计划-自动化能力与真实环境验收.md)推进。

- 完成[工程质量与能力闭环收口](changes/0010-2026-10-02-变更-修复数据边界并收口工程交付.md)：修复产物路径越界、记忆多实例覆盖及原子提交、wheel 资源遗漏；统一 Leader 装配、阻止空依赖专家进化启动、修复 Skill 持久化失败的假成功；新增行为回归、包安装检查、CI 和 docs，校准 README 能力声明。最终 **2755 passed / 4 skipped / 1 deselected**，独立 wheel 安装构图通过；归档[本轮计划](archive/plans/0003-2026-10-02-计划-工程质量与能力闭环收口.md)。下一步：[自动化能力与真实环境验收](plans/0004-2026-10-02-计划-自动化能力与真实环境验收.md)。

- 完成[代码质量、目录架构与能力闭环评审](reviews/0003-2026-10-02-评审-代码质量目录架构与能力闭环.md)：默认测试实测 2729 passed / 4 skipped / 1 deselected；额外复现宿主产物导出路径越界、记忆多实例覆盖、wheel 缺运行资源，确认 Skill 自动触发/回滚未接通及 multiagent 进化评估依赖为空。结论：有真实工程骨架，但高级能力与交付质量尚未收口。本次仅评审，未改生产代码。下一步：优先修复三个已复现缺陷，再校准能力声明和补装配验收。

## 2026-09-28

- 收口[测试环境隔离层](changes/0008-2026-09-28-变更-建立测试环境隔离层并分层集成测试.md)的三项遗留：删除 `app/cli/main.py` 模块级 `load_dotenv`（导入副作用，`main()` 内已有 `override=True` 的加载）、`LocalContainerBackend` 增加显式 `docker pull`（`_image_present` + `_ensure_image`，不再依赖 `docker run` 隐式静默拉取 10GB+ 镜像）、新增隔离层元测试 `tests/test_conftest_isolation.py`（故意污染新增/既有环境变量与假模块，再断言后续用例看见干净状态）。结果：默认全量 **2729 passed / 2 skipped / 7 deselected 零失败**。详见[变更记录](changes/0009-2026-09-28-变更-收口测试环境隔离层遗留三项.md)。下一步：无。

- 落地[测试环境隔离改造](archive/plans/0002-2026-09-28-计划-测试环境隔离改造.md)：新增项目级 `tests/conftest.py`（会话基线机制，每测试前后重置 `os.environ` 并清理假占位模块），铲除两处模块级 `load_dotenv` 污染源（e2e 测试 + 生产 `app/cli/main.py` 导入副作用）并撤掉下游挡板 fixture，注册 `integration` marker 使默认全量排除集成层。结果：默认全量 **2720 passed 零失败**（修复前 6 failed），`-m integration` 在无 Docker 守护进程时跳过而非报错。详见[变更记录](changes/0008-2026-09-28-变更-建立测试环境隔离层并分层集成测试.md)。下一步：为隔离层本身补元测试。
- 落地[测试隔离质量评审](reviews/0001-2026-09-28-评审-测试隔离质量.md)：归纳本轮修复的 7 处隔离缺陷、四种根因模式与根治建议。收尾清理 Docker：删除废弃镜像 `all-in-one-sandbox:latest`（此前已不存在）与 `ghcr.io/agent-infra/sandbox:latest`（13.1 GB，非 Docker 模式不再需要），并移除集成测试遗留的 `poirot-itest` 容器。其余 Docker 资源（markflow/openkb/mem0 等）属其他项目，未触碰。
- 修复单 provider 路由空链崩溃：`route_chain_for` 在角色链空时回退到全部可用 provider（排除 fake/ollama）而非抛错，使"只配一个非 DeepSeek 的 provider"成为可用路径；顺带修了 `.env` 引入的测试环境污染——`test_default_strategy_e2e.py` 模块级 `load_dotenv()` 把 `OPENAI_MODEL` 灌进 `os.environ`，污染 `test_provider_config.py` 的默认模型断言，已加 autouse fixture 隔离。完整套件 2726 passed / 0 failed。详见[变更记录](changes/0007-2026-09-28-变更-修复单provider路由空链崩溃.md)。
- 切换非 Docker 开发模式：`POIROT_SANDBOX_USE` 改为 LocalSandboxProvider（宿主进程，无容器）、executor=local、放开 host bash（危险命令仍被黑名单拦截）、MCP 关闭；配置中转站 OpenAI 端点与 `gpt-5.6-sol` 模型。端到端验证 LLM / 沙箱 / 运行时均可用，全程未接触 Docker。过程中发现两个缺陷并记录未修：单 OpenAI 时 reporter/reflection 路由链空报错（已用 `--provider openai` 单 provider 模式绕过）、空 `KEY=` 在 override=True 下覆盖 shell 变量。详见[变更记录](changes/0006-2026-09-28-变更-切换非Docker开发模式.md)。下一步：可删废弃镜像 `all-in-one-sandbox:latest`（13.1 GB）。
- 决策并执行计划事项四、五：新增 `tests/v1/fixtures/sdk_stubs.py` 统一可选依赖占位注入——排查中发现这是真实缺陷而非风格问题，占位模块（无 `__file__`）能骗过 `pytest.importorskip`，使 stage5/6 集成测试带着假 SDK 运行后崩溃（误报失败），已实证复现并修复；事项四（CI 镜像）判为不做，前提不成立（仓库无任何 CI），改记录 `local_container_backend.py` 缺显式 `docker pull` 的真实风险。验证：未安装环境下 613 passed/2 skipped 零误报，完整套件 2723 passed 无回归。计划五项全部收敛，已归档至 `learn/archive/plans/`。详见[变更记录](changes/0005-2026-09-28-变更-统一可选依赖占位注入并评估CI镜像方案.md)。
- 将 README 主入口切换为中文：原英文版迁至 `resource/README.en.md`（内容不变，按新位置修正相对路径），根 `README.md` 重写为中文版，术语沿用 `resource/USAGE.zh-CN.md` 既有风格；四份文档语言切换栏互相连通；克隆地址由占位符改为实际地址。校验 5 份文档相对链接 0 失效、4 张图片路径可达。详见[变更记录](changes/0004-2026-09-28-变更-切换中文README主入口.md)。
- 建立独立仓库 `xilele777/poirot` 并推送完整历史（205 个上游提交 + 本轮 7 个）：确认上游非 fork、提交邮箱已关联账号（7 个提交 `author.login` 均为 `xilele777`）；全历史敏感信息扫描无真实密钥；设置 Topics；新增 README `Provenance` 说明派生关系与署名。保留 `origin` 指向上游，新增 `mine` 为可写远端。详见[变更记录](changes/0003-2026-09-28-变更-建立独立仓库.md)。下一步：按整理计划处理 `USAGE.md` 归属。
- 按 `AGENTS.md` 核对本轮 6 个提交的文档落地情况，补齐遗漏：新增[整理计划](archive/plans/0001-2026-09-28-计划-按规范整理归属文档与仓库展示.md)，记录仓库归属、`USAGE.md` 归属、仓库展示核对等待办；更正下方"是否提交"的过期结论。结果：规范要求的过程资料已齐全。
- 跑通环境并修复测试套件与沙箱并发缺陷：补齐 `agent-sandbox` 依赖、启动 Docker、拉取并验证沙箱镜像；修复 `acquire_async` cancel 后锁泄漏、上下文压缩 prompt 丢失 `${messages_text}` 占位符、沙箱镜像名错误，以及 5 处测试间的环境/模块污染和 4 处测试漂移。结果：完整套件 2723 passed / 0 failed（修复前 21 failed）。详见[变更记录](changes/0002-2026-09-28-变更-修复测试与沙箱并发缺陷.md)。已拆为 5 个提交（`7a08ef0`…`b17416c`）。下一步：决策仓库归属——当前账号对上游 `HezaoHezao/poirot` 无推送权限，6 个提交停在本地。
- 建立根目录 `AGENTS.md`，纳入仓库归属、展示、文档、记录、Agent 阅读范围和提交检查规范；创建 `learn/` 导航与本次[变更记录](changes/0001-2026-09-28-变更-建立仓库约束.md)。结果：后续仓库任务有统一约束。下一步：按规范逐步整理现有文档与仓库展示信息。
