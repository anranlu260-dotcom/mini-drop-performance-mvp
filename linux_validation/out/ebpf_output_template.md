# eBPF / bpftrace 输出模板

> 只有真实执行后再填写。本模板不是已完成证据。

## 探针命令

```bash
sudo bpftrace linux_validation/bpftrace_io_latency.bt | tee linux_validation/out/ebpf_io_latency.log
```

## 触发 IO 负载

```bash
dd if=/dev/zero of=/tmp/drop_io_test bs=1M count=512 oflag=direct
sync
rm -f /tmp/drop_io_test
```

## 需要保存的证据

- `linux_validation/out/ebpf_io_latency.log`
- bpftrace 终端截图。
- IO 负载触发终端截图。
- `uname -a` 和权限检查截图。

## 答辩口径

如果没有真实输出，不要说“eBPF 已接入系统”。可以说：“当前 MVP 没有伪造 eBPF 结果，Linux 目录提供 bpftrace 探针、触发负载和证据保存模板。”
