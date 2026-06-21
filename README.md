# Mini-Drop 性能诊断系统 MVP

提交人：陆安然

本项目是对 Drop 一站式性能分析平台的最小可运行复刻。它保留 Web UI + Server + Agent + Analyzer 四组件架构，但用单仓库和 Python 标准库实现，便于在干净环境中快速跑通。

## 能力范围

- Web UI 指定 PID、采样时长、采样率并创建任务。
- Server 负责任务状态机、Agent 心跳、离线判断、审计日志和静态页面。
- Agent 每 5 秒心跳，拉取任务后按 `collector` 路由到 `proc`、`perf`、`ebpf` 或 `synthetic` 采集器。
- Analyzer 生成前端可展示的 timeline、热点列表和采样热点聚合 JSON；如果导入 `perf script` 文本，会优先使用真实调用栈生成热点树。
- Continuous Session 支持创建持续采样会话，并按最近时间窗口查询关联任务。
- 任务状态迁移：`PENDING -> RUNNING -> UPLOADING -> DONE / FAILED`，每次迁移都落库并带 reason。
- Agent 30 秒无心跳判离线，恢复时写审计日志。
- 测试覆盖正常路径、PID 异常、Agent 离线审计等端到端路径。

## 当前取舍

当前工作区是 macOS，不能真实运行 Linux perf/eBPF。MVP 因此采用：

- Linux 上优先读取 `/proc/<pid>/stat`、`status`、`io`。
- 非 Linux 或 PID 不可读时，默认使用带 `source=synthetic-demo` 的确定性演示样本。
- `perf` 采集器会在 Linux 上执行 `perf record -> perf script -> stack sample -> Analyzer`。
- `ebpf` 采集器会在 Linux 上调用 `bpftrace_io_latency.bt` 并上传输出摘要。
- 如果评审机器没有 `perf` / `bpftrace` 或权限不足，任务会进入 `FAILED`，reason 写明缺少的工具或权限，不再静默伪装成功。

如果在 Ubuntu 22.04 演示真实采集，建议关闭 synthetic fallback。为避免把 demo 包装成真实完成，本包新增 `linux_validation/`：

- `perf_collect.sh`：真实 `perf record` / `perf script` 采集命令。
- `bpftrace_io_latency.bt`：最小 block IO latency eBPF 探针。
- `linux_demo_checklist.md`：Linux 现场验证清单。
- `out/*_template.md`：真实运行后需要补充的环境、perf、eBPF 证据模板。

同时提供 `import_perf_script.py`，用于把 Linux 上生成的 `perf.script.txt` 转为 Mini-Drop analyzer JSON：

```bash
python3 import_perf_script.py linux_validation/out/perf.script.txt --out linux_validation/out/perf_analysis.json
```

未在 Linux 上执行这些脚本前，不应声称“eBPF 已真跑”或“真实火焰图已完成”。

## 本地运行

```bash
cd Drop/mini_drop
python3 server.py --host 127.0.0.1 --port 8080
```

另开一个终端：

```bash
cd Drop/mini_drop
python3 agent.py --server http://127.0.0.1:8080
```

浏览器打开：

```text
http://127.0.0.1:8080
```

说明：`127.0.0.1` 是本机地址，导师不能直接访问提交人的本地页面。评审时应在导师自己的机器上按本节命令运行，然后打开导师机器上的 `http://127.0.0.1:8080` 复现。

创建 demo 任务：

```bash
python3 demo.py --server http://127.0.0.1:8080
```

## Docker 运行

```bash
docker compose up --build
```

然后打开：

```text
http://localhost:8080
```

## Make 命令

```bash
make test
make coverage
make demo
python3 continuous_demo.py --server http://127.0.0.1:8080 --pid 1
make package
```

创建持续采样 session：

```bash
python3 continuous_demo.py --server http://127.0.0.1:8080 --pid 1 --collector proc --windows 3 --duration 5 --interval 5
```

如果在 Linux 上验证 perf 主链路：

```bash
python3 continuous_demo.py --server http://127.0.0.1:8080 --pid <PID> --collector perf --windows 1 --duration 10 --interval 10
```

## Linux 权限要求

MVP 的 `/proc` 采样通常不需要特权，但如果扩展到 perf/eBPF：

- Ubuntu 22.04 或兼容 Linux 内核。
- `kernel.perf_event_paranoid <= 1` 或给采集二进制配置 `cap_perfmon`。
- eBPF 需要 `CAP_BPF` / `CAP_PERFMON` / `CAP_SYS_ADMIN`，Docker 中需 `privileged: true` 或细粒度 capability。
- 若采集宿主机 PID，容器需要 `pid: host`。

## 目录结构

```text
mini_drop/
├── server.py                 # HTTP API + 静态页面 + 离线扫描
├── agent.py                  # Agent 心跳、拉任务、采样、上报
├── demo.py                   # 创建 demo 任务
├── mini_drop/
│   ├── store.py              # SQLite 状态机、审计、样本、分析结果
│   ├── analyzer.py           # timeline / 热点聚合 JSON / 归因建议
│   ├── perf_importer.py      # perf script 文本导入为 analyzer 样本
│   └── collectors/           # proc/perf/eBPF/synthetic 采集器路由
├── web/                      # 前端页面
├── tests/                    # 单测和端到端测试
├── linux_validation/          # Linux 真实采集脚本和证据模板
├── import_perf_script.py      # perf.script.txt -> analysis JSON
├── docker-compose.yml
├── Dockerfile
└── design.md
```

## 验证

```bash
python3 -m unittest discover -s tests -v
python3 coverage_check.py
```

当前测试包含：

- 状态迁移 reason 落库。
- Agent offline / recovered 审计。
- 正常端到端任务生成 DONE 和 analysis。
- 非法 PID 进入 FAILED。
- API 触发离线审计。
- perf-script 栈样本进入 analyzer 后生成真实调用栈热点树。
- `perf script` 文本可以解析为 Mini-Drop 样本。
- `perf` / `ebpf` 采集器缺工具时任务进入 FAILED 并写清 reason。
- Continuous Session API 可以按时间窗口查询关联任务。

## 演示截图证据

本包包含本地演示截图：

- `evidence/screenshots/01-agent-task-done.png`
- `evidence/screenshots/02-task-detail-analysis.png`

截图展示 Agent 在线、任务 DONE、状态迁移 reason、资源时间轴、采样热点聚合视图和热点建议。截图只作为本地演示证据；真正评审仍应按 README 命令在评审机器上复现。导师不能访问提交人电脑上的 `127.0.0.1`，所以提交包内保留截图和复现命令，而不是提交本地链接。

`coverage_check.py` 统计核心业务逻辑（Store、Analyzer、perf importer、collectors）覆盖率；HTTP Server 和 Agent 长驻入口通过端到端测试验证，不纳入核心覆盖率分母。

