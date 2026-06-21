# Mini-Drop 本地演示截图

这些截图来自本地运行的 `http://127.0.0.1:8080/`，用于证明 MVP 链路可以在本机跑通。

## 截图清单

1. `01-agent-task-done.png`
   - Web UI 已打开。
   - `screenshot-agent` 处于 `ONLINE`。
   - 任务 `task-1652f1ba48` 进入 `DONE`。
   - 审计日志记录 Agent 注册。

2. `02-task-detail-analysis.png`
   - 任务详情展示状态迁移：`PENDING -> RUNNING -> UPLOADING -> DONE`。
   - 每次状态迁移都有 reason。
   - 展示资源时间轴、采样热点聚合视图和热点建议。

3. `03-task-list-perf-failed-continuous.png`
   - 任务列表同时展示 `proc` 与 `perf` 两条主链路任务。
   - `proc` 任务关联 `Continuous Session` 并进入 `DONE`。
   - `perf` 任务进入 `FAILED`，reason 明确写出当前机器缺少 Linux perf：`perf unavailable: install linux-tools/perf and run on Linux`。
   - 这张图用于证明系统没有把本机无法运行的 perf 伪装成成功。

4. `04-agent-online-audit.png`
   - `evidence-agent` 处于 `ONLINE`。
   - 审计日志展示 Agent 注册、离线、恢复记录。
   - 新建任务区域展示 Web UI 的采集任务入口。

## 评审如何复现

导师不能直接访问提交人的 `127.0.0.1`。正确复现方式是在评审机器上解压本项目后执行：

```bash
cd mini_drop
python3 server.py --host 127.0.0.1 --port 8080
```

另开终端：

```bash
cd mini_drop
python3 agent.py --server http://127.0.0.1:8080 --agent-id reviewer-agent --allow-synthetic
python3 demo.py --server http://127.0.0.1:8080 --pid 999999 --duration 6 --sample-rate 1
```

然后在评审机器浏览器打开：

```text
http://127.0.0.1:8080/
```

截图证明的是“本地可复现 UI 和链路”，不是公网部署。

如果需要真实 Linux perf/eBPF 证据，请继续按 `linux_validation/linux_demo_checklist.md` 执行，并补充：

- `perf record` / `perf script` 输出。
- `import_perf_script.py` 生成的 `perf_analysis.json`。
- `bpftrace` IO latency 输出。
- Linux 内核版本和权限配置截图。
