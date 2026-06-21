# Linux Evidence Output Directory

这个目录用于保存真实 Linux 验证产物。当前提交包只放模板，不伪造运行结果。

建议补充的文件：

- `run_env.md`：Linux 版本、内核、权限、perf/bpftrace 可用性。
- `perf.data`：`perf record` 生成的二进制采样文件。
- `perf.script.txt`：`perf script` 导出的原始调用栈文本。
- `perf_analysis.json`：`import_perf_script.py` 生成的 Mini-Drop analyzer JSON。
- `ebpf_io_latency.log`：`bpftrace_io_latency.bt` 运行时的 IO latency 输出。
- 截图：终端命令、Web 任务详情页、Linux 权限检查。

如果没有真实执行，请保留模板，不要把模板改写成已完成证据。
