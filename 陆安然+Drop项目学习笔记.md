# Drop 项目学习笔记

提交人：陆安然

## 一、我对 Drop 项目的理解

我理解的 Drop 不是一个单纯展示 CPU、内存曲线的监控面板，而是一个面向性能问题定位的一站式诊断系统。它的核心闭环是：

```text
用户在 Web 上下发采样任务
        ↓
Server 保存任务并维护状态机
        ↓
Agent 领取任务并对目标 PID 采样
        ↓
Analyzer 将原始采样数据转成时间线、热点和诊断结果
        ↓
Web 展示任务状态、资源变化、热点分布和分析结论
```

所以这个题目的重点不只是“页面能不能显示结果”，而是系统能不能把一次性能诊断任务完整跑通：任务下发、Agent 心跳、状态迁移、采样上报、分析生成、结果查看，每个环节都要有明确的数据流和可复现证据。

## 二、我复刻的范围

我实现的是 Mini-Drop MVP，保留了 Drop 的 Web UI、Server、Agent、Analyzer 四个主要组件，但为了让评审可以在干净机器上快速跑通，项目采用单仓库、Python 标准库和 SQLite 实现。

当前已经实现的部分包括：

- Web UI：可以创建采样任务，查看 Agent、审计日志、任务列表、任务详情和 continuous session。
- Server：提供 HTTP API，负责任务创建、任务领取、样本上传、结果查询、Agent 心跳和离线检测。
- Agent：独立进程运行，定期向 Server 上报心跳，领取任务后按 collector 类型执行采样。
- Analyzer：把采样数据转换成资源时间线、热点聚合、诊断建议和前端可展示的 JSON。
- Store：使用 SQLite 保存任务、状态迁移、审计日志、Agent 信息、采样数据、分析结果和 continuous session。
- Collector 路由：实现了 `proc`、`perf`、`ebpf`、`synthetic` 四类采集器入口。
- 测试：覆盖任务状态机、Agent 离线恢复、API、collector、perf script 解析和端到端流程。

## 三、我是怎么实现的

项目入口主要分成几个文件：

- `server.py`：启动 Web Server，同时提供静态页面和 API。前端访问 `/api/tasks` 创建任务，Agent 访问 `/api/tasks/claim` 领取任务，完成后通过 `/api/tasks/<id>/samples` 上传样本。
- `agent.py`：模拟真实 Drop Agent 的工作方式。它会先注册并持续心跳，然后循环向 Server 拉取任务。拿到任务后，根据任务里的 `collector` 字段选择对应采集器。
- `mini_drop/store.py`：封装 SQLite 数据库操作。任务状态从 `PENDING` 到 `RUNNING`、`UPLOADING`、`DONE` 或 `FAILED`，每次变化都会写入 `state_transitions` 表，并记录 reason。
- `mini_drop/analyzer.py`：把 Agent 上传的样本转成前端需要的分析结果。普通 proc 样本会生成 CPU/RSS/IO 时间线和热点聚合；如果导入 `perf script`，会优先用真实调用栈生成热点树。
- `mini_drop/collectors/procfs.py`：Linux 下读取 `/proc/<pid>/stat`、`/proc/<pid>/status`、`/proc/<pid>/io`，得到 CPU、RSS 和 IO 数据。
- `mini_drop/collectors/perf.py`：Linux 下调用 `perf record` 和 `perf script`，把调用栈采样结果交给 analyzer。
- `mini_drop/collectors/ebpf.py`：Linux 下调用 bpftrace 脚本，采集 block IO latency 分布。
- `web/app.js`：前端轮询 API，展示 Agent 状态、审计日志、任务列表、任务详情、资源时间线和热点视图。

整个实现里我最重视的是状态机和证据链。比如 Agent 领取任务后，任务不会直接变成 DONE，而是按顺序进入 `RUNNING -> UPLOADING -> DONE`。如果采集器缺工具或权限不足，任务会进入 `FAILED`，并在 reason 里写清楚失败原因，例如 `perf unavailable: install linux-tools/perf and run on Linux`。

## 四、过程中遇到的问题

第一个问题是本地开发环境是 macOS，不能真实运行 Linux 的 `/proc`、perf 和 eBPF。这个问题如果处理不好，很容易把 demo 做成“看起来能跑，实际上采集是假的”。所以我没有把 synthetic 样本包装成真实采集，而是在 README 和设计文档里明确说明：

- macOS 本地只能验证系统链路和 UI 展示。
- Linux 上才可以验证真实 `/proc`、perf、eBPF 采集。
- 如果缺少 `perf` 或 `bpftrace`，任务必须失败并写明 reason，不能静默回退成假数据。

第二个问题是火焰图。真实火焰图应该来自 perf/eBPF/py-spy 等调用栈采样，而不是手工拼一个图。为避免误导，我把前端表述调整为采样热点聚合视图；同时提供 `import_perf_script.py`，可以把 Linux 上生成的 `perf.script.txt` 导入成 analyzer 能识别的调用栈样本。

第三个问题是 continuous profiling。题目要求的是常驻低频采样、时间窗口切片和历史回放。当前 MVP 实现了 continuous session 和最近窗口查询，但还没有做到生产级的长期低开销采样，所以我在文档里把它归为 MVP 能力，而不是夸大成完整 Drop 级别的 continuous profiling。

## 五、测试和验证

我为这个项目补了单元测试和端到端测试，主要验证这些点：

- 创建任务后状态机是否正确迁移。
- 每次状态迁移是否带 reason 落库。
- Agent 心跳、离线、恢复是否会写审计日志。
- 正常任务是否能从创建到 DONE 并生成分析结果。
- 非法 PID 或缺少工具时，任务是否进入 FAILED。
- perf script 文本是否可以解析成调用栈样本。
- Analyzer 是否能根据 perf stack 生成热点树。
- Continuous Session 是否能按时间窗口查到关联任务。

本地验证命令是：

```bash
python3 -m unittest discover -s tests -v
python3 coverage_check.py
```

当前项目也提供：

```bash
docker compose up --build
make demo
python3 continuous_demo.py --server http://127.0.0.1:8080 --pid 1
```

这些命令用于证明项目可以在干净环境中启动、创建任务、运行 Agent、生成结果。

## 六、Linux 真实验证计划

因为 Drop 的关键是真实性能采集，最终还需要在 Ubuntu 22.04 或类似 Linux 机器上补充真实证据。我准备按下面流程补：

1. 记录运行环境：

```bash
uname -a
cat /etc/os-release
which perf
which bpftrace
cat /proc/sys/kernel/perf_event_paranoid
```

2. 启动项目：

```bash
docker compose up --build
```

3. 用 stress-ng、dd 或 fio 制造负载：

```bash
stress-ng --cpu 1 --timeout 60s
dd if=/dev/zero of=/tmp/drop_io_test bs=1M count=512 oflag=direct
```

4. 验证 perf：

```bash
python3 continuous_demo.py --server http://127.0.0.1:8080 --pid <PID> --collector perf --windows 1 --duration 10 --interval 10
```

5. 验证 eBPF：

```bash
sudo bpftrace linux_validation/bpftrace_io_latency.bt
python3 continuous_demo.py --server http://127.0.0.1:8080 --pid 1 --collector ebpf --windows 1 --duration 10 --interval 10
```

6. 保存 Web 截图、终端日志、perf 输出、bpftrace 输出和视频演示。

## 七、我对这个项目的反思

这个项目目前最有价值的部分是把 Drop 的基本工程链路跑通了：Web 下发任务、Server 维护状态、Agent 执行采样、Analyzer 生成结果、前端展示诊断信息。它能体现我对性能诊断系统组件边界和数据流的理解。

但它还不是完整的 Drop 复刻。真正完整的版本必须把 perf/eBPF 放到主链路里，在 Linux 上真实采到调用栈、IO 延迟和调度事件，并且能在 Web 上看到负载变化前后的对比。当前项目更准确的定位是“可运行的 Mini-Drop MVP + Linux 真实采集补证路径”。

如果再给我 7 天，我会优先做四件事：

1. 在 Ubuntu 上补齐真实 perf/eBPF 运行日志和截图。
2. 把 perf 采集结果转换成标准 collapsed stack，并接入真正 flamegraph。
3. 把 Analyzer 从 Server 进程中拆成独立 worker。
4. 增加一个简单的 LLM 归因模块，但限制它只能读取 timeline、hotspot 和状态迁移证据，避免凭空判断。

