# Linux 运行环境记录模板

> 只有在真实 Linux 环境执行后再填写。本模板不是已完成证据。

## 基础环境

```bash
date
uname -a
cat /etc/os-release
python3 --version
which perf
which bpftrace
cat /proc/sys/kernel/perf_event_paranoid
```

## 权限记录

```bash
id
sudo -v
sudo sysctl kernel.perf_event_paranoid=1
```

## Mini-Drop 启动记录

```bash
python3 server.py --host 0.0.0.0 --port 8080
python3 agent.py --server http://127.0.0.1:8080 --agent-id linux-agent
```

截图要求：

- 终端显示 server started。
- 终端显示 agent 心跳或任务完成。
- 浏览器显示 Agent ONLINE、任务 DONE、状态迁移 reason。
