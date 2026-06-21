# Mini-Drop Linux 真实采集验证清单

当前 macOS 包内运行的是 MVP demo，不声称已完成真实 eBPF/perf 采集。若在 Ubuntu 22.04 或兼容 Linux 上补真实证据，按本清单执行并保存截图/日志。

## 1. 环境检查

```bash
uname -a
python3 --version
which perf
which bpftrace
cat /proc/sys/kernel/perf_event_paranoid
```

建议：

```bash
sudo sysctl kernel.perf_event_paranoid=1
```

## 2. 启动 Mini-Drop

```bash
cd Drop/mini_drop
docker compose up --build
```

浏览器打开：

```text
http://localhost:8080
```

## 3. 制造负载

CPU 负载：

```bash
python3 - <<'PY'
import time
end = time.time() + 60
x = 0
while time.time() < end:
    x = (x * 13 + 7) % 1000003
PY
```

IO 负载：

```bash
dd if=/dev/zero of=/tmp/mini-drop-io-test.bin bs=4M count=256 oflag=direct
rm -f /tmp/mini-drop-io-test.bin
```

## 4. perf 采集证据

找到目标 PID 后，优先通过 Mini-Drop 主链路验证：

```bash
python3 continuous_demo.py --server http://127.0.0.1:8080 --pid <pid> --collector perf --windows 1 --duration 10 --interval 10
```

也可以在 Web UI 中把采集器选为 `perf stack collector` 后下发任务。任务应进入：

```text
PENDING -> RUNNING -> UPLOADING -> DONE
```

如果缺少 `perf` 或权限不足，任务应进入 `FAILED`，reason 会写明 `perf unavailable` 或命令错误。

保留原始 perf 文件时执行：

```bash
bash linux_validation/perf_collect.sh <pid> 10 99 linux_validation/out
python3 import_perf_script.py linux_validation/out/perf.script.txt --out linux_validation/out/perf_analysis.json
ls -lh linux_validation/out
```

应保存：

- `linux_validation/out/perf.data`
- `linux_validation/out/perf.script.txt`
- `linux_validation/out/perf_analysis.json`
- 终端截图或日志

检查 `perf_analysis.json`，应能看到：

```json
"source_mode": "perf-script-import"
```

## 5. eBPF IO latency 证据

优先通过 Mini-Drop 主链路验证：

```bash
python3 continuous_demo.py --server http://127.0.0.1:8080 --pid <pid> --collector ebpf --windows 1 --duration 10 --interval 10
```

如果缺少 `bpftrace` 或权限不足，任务应进入 `FAILED`，reason 会写明 `bpftrace unavailable` 或权限问题。

也可以直接运行探针保存原始证据：

```bash
sudo bpftrace linux_validation/bpftrace_io_latency.bt
```

另一个终端执行 IO 负载，观察 histogram 分布变化。应保存：

- bpftrace 输出截图。
- 触发 IO 命令日志。

## 6. 交付说明

如果没有完成上述 Linux 验证，不要在答辩中说“eBPF 已真跑”。只能说当前实现了可运行 MVP，并准备了 Linux perf/eBPF 验证脚本，真实采集证据待 Linux 环境补齐。

真实执行后，把 `linux_validation/out/*_template.md` 复制成不带 `_template` 的文件并填写命令输出摘要，例如：

- `run_env_template.md` -> `run_env.md`
- `perf_output_template.md` -> `perf_output.md`
- `ebpf_output_template.md` -> `ebpf_output.md`
