# 工作日志

## 2026-09-28

- 切换非 Docker 开发模式：`POIROT_SANDBOX_USE` 改为 LocalSandboxProvider（宿主进程，无容器）、executor=local、放开 host bash（危险命令仍被黑名单拦截）、MCP 关闭；配置中转站 OpenAI 端点与 `gpt-5.6-sol` 模型。端到端验证 LLM / 沙箱 / 运行时均可用，全程未接触 Docker。过程中发现两个缺陷并记录未修：单 OpenAI 时 reporter/reflection 路由链空报错（已用 `--provider openai` 单 provider 模式绕过）、空 `KEY=` 在 override=True 下覆盖 shell 变量。详见[变更记录](changes/0006-2026-09-28-变更-切换非Docker开发模式.md)。下一步：可删废弃镜像 `all-in-one-sandbox:latest`（13.1 GB）。
- 决策并执行计划事项四、五：新增 `tests/v1/fixtures/sdk_stubs.py` 统一可选依赖占位注入——排查中发现这是真实缺陷而非风格问题，占位模块（无 `__file__`）能骗过 `pytest.importorskip`，使 stage5/6 集成测试带着假 SDK 运行后崩溃（误报失败），已实证复现并修复；事项四（CI 镜像）判为不做，前提不成立（仓库无任何 CI），改记录 `local_container_backend.py` 缺显式 `docker pull` 的真实风险。验证：未安装环境下 613 passed/2 skipped 零误报，完整套件 2723 passed 无回归。计划五项全部收敛，已归档至 `learn/archive/plans/`。详见[变更记录](changes/0005-2026-09-28-变更-统一可选依赖占位注入并评估CI镜像方案.md)。
- 将 README 主入口切换为中文：原英文版迁至 `resource/README.en.md`（内容不变，按新位置修正相对路径），根 `README.md` 重写为中文版，术语沿用 `resource/USAGE.zh-CN.md` 既有风格；四份文档语言切换栏互相连通；克隆地址由占位符改为实际地址。校验 5 份文档相对链接 0 失效、4 张图片路径可达。详见[变更记录](changes/0004-2026-09-28-变更-切换中文README主入口.md)。
- 建立独立仓库 `xilele777/poirot` 并推送完整历史（205 个上游提交 + 本轮 7 个）：确认上游非 fork、提交邮箱已关联账号（7 个提交 `author.login` 均为 `xilele777`）；全历史敏感信息扫描无真实密钥；设置 Topics；新增 README `Provenance` 说明派生关系与署名。保留 `origin` 指向上游，新增 `mine` 为可写远端。详见[变更记录](changes/0003-2026-09-28-变更-建立独立仓库.md)。下一步：按整理计划处理 `USAGE.md` 归属。
- 按 `AGENTS.md` 核对本轮 6 个提交的文档落地情况，补齐遗漏：新增[整理计划](archive/plans/0001-2026-09-28-计划-按规范整理归属文档与仓库展示.md)，记录仓库归属、`USAGE.md` 归属、仓库展示核对等待办；更正下方"是否提交"的过期结论。结果：规范要求的过程资料已齐全。
- 跑通环境并修复测试套件与沙箱并发缺陷：补齐 `agent-sandbox` 依赖、启动 Docker、拉取并验证沙箱镜像；修复 `acquire_async` cancel 后锁泄漏、上下文压缩 prompt 丢失 `${messages_text}` 占位符、沙箱镜像名错误，以及 5 处测试间的环境/模块污染和 4 处测试漂移。结果：完整套件 2723 passed / 0 failed（修复前 21 failed）。详见[变更记录](changes/0002-2026-09-28-变更-修复测试与沙箱并发缺陷.md)。已拆为 5 个提交（`7a08ef0`…`b17416c`）。下一步：决策仓库归属——当前账号对上游 `HezaoHezao/poirot` 无推送权限，6 个提交停在本地。
- 建立根目录 `AGENTS.md`，纳入仓库归属、展示、文档、记录、Agent 阅读范围和提交检查规范；创建 `learn/` 导航与本次[变更记录](changes/0001-2026-09-28-变更-建立仓库约束.md)。结果：后续仓库任务有统一约束。下一步：按规范逐步整理现有文档与仓库展示信息。
