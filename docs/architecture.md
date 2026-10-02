# 架构边界

`app → agents` 为应用对领域模块的依赖方向。agents 不导入 app；`tests/test_architecture.py` 对绝对 import 执行回归检查。

## 应用装配

`app/bootstrap.py::_assemble_leader` 是应用启动、模式切换、模型切换、MCP 重载及 leaf Agent 的统一入口。它根据当前 config/registry 注入 middleware、输出目录、记忆依赖与委派能力。leaf 不传 multiagent_setup，因此不装配委派工具。

`agents/leader/factory.py` 保留底层可独立调用的构图接口。SandboxMiddleware 只接收配置，不再向上层导入私有项目根目录。Skill evaluator 通过 `set_eval_bridge` 装配。

## 持久化与路径

- `agents/storage`：跨进程文件锁等共享存储原语。
- `agents/memory/strategies/default`：Markdown 存储、BM25 索引与衰减策略。
- `agents/sandbox/utils/paths.py`：跨平台虚拟路径组件和解析后的宿主归属校验。
- `agents/sandbox/translators`：明确虚拟路径与宿主挂载的映射。
- `SandboxMiddleware`：仅成功导出的产物注册下载。

## 保留的技术债

CLI Skill 命令分派、流式 UI 服务仍然较大；本轮优先修复数据与交付边界，没有为了行数指标重排这些文件。记忆 store/索引之间仍保留既有装饰器连接；检索前会额外校准外部写入造成的索引变化。完整类型检查、中文分词、持久化会话恢复和自动进化需要后续独立验收。
