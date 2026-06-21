# perf 采集输出模板

> 只有真实执行后再填写。本模板不是已完成证据。

## 目标进程

```bash
ps -p <PID> -o pid,ppid,comm,args
```

## 采集命令

```bash
bash linux_validation/perf_collect.sh <PID> 10 99 linux_validation/out
python3 import_perf_script.py linux_validation/out/perf.script.txt --out linux_validation/out/perf_analysis.json
```

## 需要保存的文件

- `linux_validation/out/perf.data`
- `linux_validation/out/perf.script.txt`
- `linux_validation/out/perf_analysis.json`

## 截图要求

- `perf record` 命令完整输出。
- `perf script` 前 30 行。
- `perf_analysis.json` 中 `summary.source_mode` 为 `perf-script-import`。
- Web 任务详情页或导入结果截图能看到热点函数名。
