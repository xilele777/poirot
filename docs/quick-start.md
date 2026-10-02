# 本地上手指南

适用日期：2026-10-02。推荐从源码目录、单 provider、传统 CLI 开始。先完成一次问答和报告，再按需启用文件工具、记忆与 Skill。使用边界见[当前限制清单](known-limitations.md)。

## 1. 已有本地环境：直接开始

如果你已在本机 `F:\project\poirot` 完成配置，且 `.venv`、`.env` 均存在，不必重新安装或复制模板。在 PowerShell 中执行：

```powershell
Set-Location 'F:\project\poirot'
.\.venv\Scripts\poirot.exe --provider openai cli
```

这会使用 `.env` 中的 OpenAI 兼容接口和模型。启动命令不需要激活虚拟环境；若你配置的是 DeepSeek，将 `openai` 替换为 `deepseek`。

首次试用建议先在现有 `.env` 中把 `POIROT_MULTIAGENT_ENABLED` 改为 `false`，保持 `POIROT_MCP_ENABLED=false`，减少外部专家 CLI 和工具服务的依赖。保留已有模型配置。修改 `.env` 后重新启动。

配置字段已填写并不保证接口当前可用；进入交互后按第 4 节完成真实问答才算连通。

## 2. 新环境：安装

需要 Python 3.12+；当前 CI 验证配置为 Windows/Python 3.12。已经有仓库时跳过克隆。

```powershell
git clone https://github.com/xilele777/poirot.git
Set-Location poirot
python --version
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
if (-not (Test-Path -LiteralPath '.env')) {
    Copy-Item -LiteralPath '.env.example' -Destination '.env'
}
```

后续命令都在仓库根目录执行。直接调用虚拟环境中的程序可以避开 PowerShell 激活脚本执行策略问题。若 `python --version` 小于 3.12，先选择符合要求的解释器再创建虚拟环境。

Linux/macOS 对应使用 `.venv/bin/python` 和 `.venv/bin/poirot`；也可先 `source .venv/bin/activate` 再运行 `python`、`poirot`。这些平台仍需独立验证。

## 3. 配置一个模型

用编辑器打开仓库根目录 `.env`，修改已有的同名项，避免重复追加配置。以下两种方案任选其一；占位文字必须替换，示例不包含真实凭证。

### OpenAI 或兼容接口

```dotenv
OPENAI_API_KEY=替换为你的密钥
OPENAI_BASE_URL=替换为服务商提供的完整兼容接口地址
OPENAI_MODEL=替换为该接口实际支持的模型ID
```

如果连接 OpenAI 官方接口，`OPENAI_BASE_URL` 可用 `https://api.openai.com/v1`。其他服务商按其文档填写，不要自行重复拼接 `/v1`。模型需要支持工具调用，复杂交互还依赖流式响应兼容性。

### DeepSeek

```dotenv
DEEPSEEK_API_KEY=替换为你的密钥
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=替换为你的接口实际支持的模型ID
```

启动命令对应改用 `--provider deepseek`。

### 首次运行的功能开关

在 `.env` 中调整以下项目。这个配置先验证模型、内置搜索和报告，不启动沙箱、外部专家、记忆或 Skill。

```dotenv
POIROT_SANDBOX_USE=
POIROT_MCP_ENABLED=false
POIROT_MULTIAGENT_ENABLED=false
POIROT_MULTIAGENT_L2_ENABLED=false
POIROT_MULTIAGENT_L3_ENABLED=false
POIROT_MEMORY_USE=
POIROT_SKILL_ENABLED=false
POIROT_SKILL_EVOLVE_ENABLED=false
POIROT_SKILL_EVAL_ENABLED=false
```

如果已有能用的 Local 配置，可以保留，首次任务先做轻量问答即可。关闭 MCP 不会关闭内置 DuckDuckGo 搜索。

CLI 会用 `.env` 覆盖同名 shell 环境变量；例如空的 `OPENAI_API_KEY=` 会覆盖 shell 中已有密钥。使用 shell 注入时，应删除或注释 `.env` 中同名条目。不要提交 `.env`、真实对话日志或输出数据。

## 4. 第一次交互：问答、追问、报告

先确认命令入口，再启动：

```powershell
.\.venv\Scripts\poirot.exe --help
.\.venv\Scripts\poirot.exe --provider openai cli
```

如果 `.env` 不存在，当前程序会在解析 `--help` 前进入配置向导，所以应先完成上面的配置步骤。

在 Poirot 提示符下逐条输入以下内容；这些是程序内输入，不是 PowerShell 命令：

```text
/default
请用中文解释 BM25 和向量检索的区别，控制在 300 字以内。这一步不需要联网。
如果用于中文个人知识库，你会如何选择？请结合上一条回答说明局限。
请把刚才的讨论整理成一份完整的中文 Markdown 短文，包含比较、建议和局限。
/report 检索方案入门比较
```

预期结果：问答连贯，模型完成短文，随后 `/report` 导出 Markdown 并打印 `report saved:` 路径。当前手动 `/report` 优先保存最新完整 AI 回答，不会另行调用模型重新综合整段对话；仅在没有完整回答时才使用旧报告/证据兜底，所以先让模型写好完整短文再导出。模型问答和深度研究中的模型调用会产生费用。

常用交互命令：

| 输入 | 用途 |
|---|---|
| `/help` | 查看命令 |
| `/default` | 轻量对话，适合先验证接口 |
| `/expert` | 切换深度研究，后续任务通常涉及更多步骤 |
| `/report 可选主题` | 优先将最新完整回答导出为 Markdown；没有完整回答时才使用旧报告/证据兜底 |
| `/thread` | 查看当前会话信息 |
| `/model openai 模型ID` | 切换模型；需要相应 provider 已配置 |
| `/exit` | 退出；`/quit` 同样可用 |

仅清空界面不会清空会话状态；要做独立任务，可以退出再启动。退出后不能恢复本次完整上下文，需要的背景和报告应自行保存。同一会话重复 `/report` 默认写同一个 `report.md`，需要保留多版时请另存。

需要全屏界面时，省略 `cli`：

```powershell
.\.venv\Scripts\poirot.exe --provider openai
```

## 5. 单次任务与联网研究

轻量非交互问答：

```powershell
.\.venv\Scripts\poirot.exe --provider openai run '用中文简述 BM25 的用途，不需要联网。' --no-expert
```

默认 `run` 是深度研究模式。完成轻量验证后，再试一次有限范围的联网研究：

```powershell
.\.venv\Scripts\poirot.exe --provider openai run '请使用 web_search 查找 BM25 与向量检索的资料，最多使用 3 个搜索结果，给出链接并比较适用场景。区分搜索摘要与已核实的正文，搜索失败时明确说明。'
```

“最多 3 个”是任务提示，不是硬性成本上限。搜索结果依赖网络，输出引用需要人工核对。默认内置搜索返回结果摘要，不提供完整网页阅读保证。

参数位置必须正确：`--provider`、`--model` 放在 `run` 或 `cli` 前面；`--no-expert`、`--thread-id`、`--logs-root`、`--no-artifact` 放在 `run` 后面。例如：

```powershell
.\.venv\Scripts\poirot.exe --provider openai --model '替换为实际模型ID' run '你的问题' --no-expert
```

轻量 `run --no-expert` 不自动保存报告。默认深度研究 `run` 在保存成功后会打印 `final_report_md:`；不要把没有报错或创建了日志目录当成研究成功。

## 6. 到哪里找结果

以命令实际打印的路径为准。默认源码运行时，日志和报告位于仓库内 `.poirot/`：

| 内容 | 默认位置 |
|---|---|
| 单次运行事件 | `.poirot/logs/threads/<会话目录>/runs/<run_id>/events.jsonl` |
| 深度研究单次运行报告 | 对应运行目录的 `artifacts/final_report.md` |
| 交互模式 `/report` 报告 | 对应会话目录的 `artifacts/report.md` |
| `present_files` 导出的文件 | `.poirot/outputs/` 下，按虚拟路径保留子目录 |
| 长期记忆（启用并成功写入后） | `.poirot/memory/traces.md` |

非交互 `run` 结束会打印 `run_id`、`events_jsonl`，有报告文件时打印 `final_report_md`。指定 `--thread-id` 不等于恢复旧会话，也不要据此猜测实际输出目录。

## 7. 按需启用文件工具

需要文件读写时，在 `.env` 中设置 Local provider 并重新启动：

```dotenv
POIROT_SANDBOX_USE=poirot.backend.agents.sandbox.local.local_sandbox_provider:LocalSandboxProvider
POIROT_SANDBOX_EXECUTOR=local
POIROT_SANDBOX_ALLOW_HOST_BASH=false
```

这里允许文件工具，关闭宿主命令执行。Local 仍在宿主运行，不是安全容器。如果确需命令执行，再改为 `true`；Windows 上名为 `bash` 的工具实际调用系统 shell，不能假定所有 Linux 命令都适用。

在交互中尝试：

```text
请使用 write_file 将“这是 Poirot 的第一次文件输出。”写入 /mnt/poirot/user-data/outputs/first-note.md，然后使用 present_files 展示这个文件。不要调用 bash。
```

验收时检查工具返回、实际生成文件及展示结果；Local 无需 Docker。下载链接依赖运行中的产物服务，需要长期保留的文件应另存。Docker、MCP 和专家委派的详细配置见[使用参考](../resource/USAGE.zh-CN.md)，限制以[当前清单](known-limitations.md)为准。

## 8. 按需启用记忆与 Skill

记忆不是默认启用的，也不会恢复重启前的完整对话。要体验召回和后台沉淀，可配置：

```dotenv
POIROT_MEMORY_USE=default
POIROT_MEMORY_ENABLE_RECALL=true
POIROT_MEMORY_PHASE2_ENABLED=true
POIROT_MEMORY_PHASE2_TURNS=10
```

重启后进行若干轮正常交流，观察是否成功写入 `.poirot/memory/traces.md`。后台抽取会增加模型调用；一次问答后没有记忆文件不一定是故障，抽取阈值、模型结果和后台完成时间都会影响它。中文召回仍有限。

基础 Skill 可单独启用：

```dotenv
POIROT_SKILL_ENABLED=true
POIROT_SKILL_EVOLVE_ENABLED=false
POIROT_SKILL_EVAL_ENABLED=false
```

重启后用 `/skill list` 查看已加载项。这只启用基础 Skill，不启动自动进化。专家 L2/L3 开关继续保持关闭。

## 9. 常见问题

| 现象 | 优先检查 |
|---|---|
| 找不到 `poirot` 命令 | 使用本指南的 `.\.venv\Scripts\poirot.exe`；若该文件不存在，运行虚拟环境 Python 的 editable 安装命令 |
| `api_key is empty`、401/403 | `.env` 中选定 provider 的密钥、空值覆盖及账号权限；不要在日志或截图中展示密钥 |
| 模型不存在、404、工具调用不支持 | 检查实际模型 ID、兼容端点路径和服务商的工具调用能力 |
| `unrecognized arguments: --provider` | 把全局参数放到 `run`/`cli` 前面 |
| 出现外部专家未安装或凭证缺失提示 | 首次试用将 `POIROT_MULTIAGENT_ENABLED=false`，重启后验证主流程 |
| 完整回答连续显示两遍 | 已修复 Responses 消息 ID 不一致导致的重复追加；使用包含该修复的代码并退出、重启 CLI，详见[修复记录](../learn/changes/0014-2026-10-02-变更-修复Responses流式回答重复显示.md) |
| 启动时提示 L2/L3 配置不可用 | 将两个专家进化/评估开关设为 `false` |
| `Search failed` 或无搜索结果 | 检查当前网络对 DuckDuckGo 的可达性；先用不联网的问答区分模型与搜索问题 |
| 搜索失败却出现成功勾号，或报告只有错误 JSON | 当前代码已修复状态传播和失败证据污染，重启后重新生成报告；详见[修复记录](../learn/changes/0015-2026-10-02-变更-修复失败证据污染与报告导出.md) |
| `Deserializing unregistered type ... Observation/AgentError` | 旧 serializer 未注册自定义类型；当前代码已显式注册应用状态类型，重启后生效，无需关闭警告或放开全部类型 |
| 文件工具不可用、host bash disabled | 检查 provider 是否配置并重启；只做文件读写时无需打开 host bash |
| 没有报告文件 | `--no-expert` 不自动保存；交互轻量模式使用 `/report`，深度研究检查是否设置 `--no-artifact` |
| 退出后“忘记”对话 | 当前不支持重启恢复会话，重新提供背景或已保存的报告 |

开发检查见[开发与验证](development.md)。本指南核对了命令解析、配置与输出路径；真实模型、网络和工具结果需要在你的环境中按上述步骤验收。
