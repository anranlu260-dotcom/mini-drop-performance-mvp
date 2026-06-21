# Mini-Drop 设计文档

提交人：陆安然

## 1. 架构

```text
Web UI -> Server(SQLite/API) <- Agent
                    |
                    v
                Analyzer
```

本实现把原 Drop 的 Web UI、Server、Agent、Analyzer 四个组件放在一个仓库中，降低复现成本。Server 用标准库 `http.server` 提供 API 和静态页面，SQLite 保存任务、状态迁移、审计、样本、continuous session 和分析结果。Agent 独立进程每 5 秒心跳，拉取任务后按 collector 路由采样 PID 并上报。Analyzer 在任务完成时把样本转成前端可展示 JSON。

## 2. 状态机

```text
PENDING
  |
  | Agent claim
  v
RUNNING
  |
  | samples uploaded
  v
UPLOADING
  |
  | analysis generated
  v
DONE

RUNNING -> FAILED
PENDING -> FAILED
```

每次状态迁移都会写入 `state_transitions` 表，字段包含 `from_state`、`to_state`、`reason` 和 `created_at`。这对应题目中“每次状态迁移必须落库并带 reason 字段”的要求。

## 3. Agent 心跳与审计

Agent 通过 `/api/agent/heartbeat` 上报 `agent_id`、hostname、IP 和版本。Server 后台每 5 秒扫描一次，超过 30 秒无心跳的 Agent 会被标记为 offline，并写入 `AGENT_OFFLINE` 审计日志。离线 Agent 再次心跳时写入 `AGENT_RECOVERED`。

## 4. 采样与分析

Linux 环境中，Agent 优先读取：

- `/proc/<pid>/stat`：计算 CPU 时间差。
- `/proc/<pid>/status`：读取 RSS。
- `/proc/<pid>/io`：读取读写字节差。

当前 macOS 工作区没有 `/proc` 和 perf/eBPF 权限，所以 demo 默认使用 `synthetic-demo` 样本，并在样本中写明原因。Agent 已提供 collector 路由：

- `proc`：读取 `/proc` 的 CPU/RSS/IO。
- `perf`：执行 `perf record -> perf script`，解析调用栈后上传 `perf-script-import` 样本。
- `ebpf`：执行 `bpftrace_io_latency.bt`，上传 bpftrace 输出摘要。
- `synthetic`：仅用于非 Linux 演示和端到端链路验证。

未在 Linux 上执行真实脚本前，本项目只能声明为可运行 MVP，不能声明完成真实 eBPF 采集。

Analyzer 输出：

- `timeline`：CPU/RSS/IO 时间序列。
- `flamegraph`：采样热点树。普通 demo 样本使用聚合阶段生成；`perf-script-import` 样本使用真实调用栈生成。
- `hotspots`：热点和建议。
- `diagnosis`：简单归因摘要。

## 5. 关键取舍

1. 不引入 FastAPI、React、PostgreSQL 等依赖，改用 Python 标准库和 SQLite，保证干净机器容易跑通。
2. 不在 macOS 上伪装真实 eBPF。文档明确说明当前是 synthetic demo，真实 Linux 演示需要补 eBPF 采集器和现场输出证据。
3. 前端不用构建工具，直接用 HTML/CSS/JS，减少 `npm install` 风险。
4. Analyzer 与 Server 同进程触发，避免引入任务队列；真实生产版应拆成独立 Job。
5. `perf` 和 `ebpf` 采集器如果缺少工具或权限会失败并写 reason，不静默回退为 synthetic。

## 6. AI 协作

AI 主要用于把题目拆成可实现 MVP：明确哪些能力必须真实落地，哪些能力需要在当前环境中降级说明。代码实现遵循可复现优先：状态机、审计、测试、文档比视觉复杂度更重要。

## 7. 性能自证

MVP 不追求高并发，但做了以下自证：

- SQLite WAL 模式支持 Server 和测试中的并发读写。
- Agent 分批上报样本，避免一次性大 payload。
- 前端 5 秒刷新，避免轮询过快。
- Analyzer 处理 JSON 样本，复杂度与样本数线性相关。
- Continuous Session 通过 `session_id` 关联任务，可以按 `from/to` 时间窗口查询最近采样片段。

## 8. 本地演示证据

`evidence/screenshots/` 保存了本地浏览器截图，证明当前 MVP 可以展示 Agent 在线、任务 DONE、状态迁移 reason 和分析结果。

这些截图不是公网访问证据。由于 `127.0.0.1` 只代表本机，导师需要在自己的评审机器上启动 server 和 agent 后访问同样的 URL 才能复现。

## 9. 如果再有 7 天

1. 在 Ubuntu 22.04 上执行 `linux_validation/perf_collect.sh`，保存 `perf.data`、`perf.script.txt` 和终端日志。
2. 执行 `python3 import_perf_script.py linux_validation/out/perf.script.txt --out linux_validation/out/perf_analysis.json`，保存导入后的 analyzer 结果。
3. 执行 `linux_validation/bpftrace_io_latency.bt`，现场触发 `dd`/`fio` IO 抖动并保存 histogram 输出。
4. 增加 py-spy 用户态 Python 采集器。
5. 把 Analyzer 拆成独立 worker，并把结果文件存到 MinIO。
6. 增加 LLM 归因工具调用约束，让模型只能读取 flamegraph、timeline 和 baseline。
