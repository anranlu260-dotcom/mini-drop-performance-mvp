# Mini-Drop proc 采集说明

当前 MVP 的 Agent 优先从 Linux `/proc/<pid>/stat`、`/proc/<pid>/status`、`/proc/<pid>/io` 读取 CPU、RSS 和 IO 字节变化。

如果运行环境不是 Linux，或目标 PID 不可读，Agent 会根据启动参数决定：

- `--allow-synthetic`：输出带 `source=synthetic-demo` 的确定性演示样本，用于 macOS 或课堂演示。
- 不带 `--allow-synthetic`：任务进入 `FAILED`，reason 写明 PID 不存在或不可读。

真实 Ubuntu 22.04 演示时，应关闭 synthetic fallback，并把采集器替换为 perf/eBPF/py-spy 等真实工具。
