from __future__ import annotations

import json
import math
from collections import defaultdict
from typing import Any


def build_analysis(task: dict[str, Any], samples: list[dict[str, Any]]) -> dict[str, Any]:
    """Build web-friendly analysis data from raw samples.

    This MVP emits a hotspot tree and timeline JSON. Demo samples use phase
    buckets; perf-script-import samples use imported stack frames.
    """
    if not samples:
        samples = [
            {"ts": 0, "cpu_pct": 0.0, "rss_mb": 0.0, "io_read_kb": 0.0, "io_write_kb": 0.0}
        ]

    cpu_values = [float(s.get("cpu_pct", 0.0)) for s in samples]
    rss_values = [float(s.get("rss_mb", 0.0)) for s in samples]
    avg_cpu = sum(cpu_values) / max(len(cpu_values), 1)
    max_cpu = max(cpu_values)
    max_rss = max(rss_values)

    source_mode = _source_mode(samples, task.get("collector", "proc"))
    stack_samples = [s for s in samples if isinstance(s.get("stack"), list) and s.get("stack")]
    if stack_samples:
        children, hotspots = _stack_hotspots(stack_samples)
    else:
        buckets = defaultdict(float)
        for idx, sample in enumerate(samples):
            cpu = float(sample.get("cpu_pct", 0.0))
            phase = ["user_work", "runtime", "syscall", "io_wait"][idx % 4]
            buckets[phase] += max(cpu, 1.0)

        children = [
            {
                "name": name,
                "value": round(value, 2),
                "children": [
                    {"name": f"{name}::sample_{i}", "value": round(value / 3 + math.sin(i + value), 2)}
                    for i in range(1, 4)
                ],
            }
            for name, value in sorted(buckets.items(), key=lambda item: item[1], reverse=True)
        ]

        hotspots = [
            {"name": child["name"], "self": child["value"], "hint": _advice(child["name"], child["value"], source_mode)}
            for child in children[:5]
        ]

    return {
        "task_id": task["id"],
        "pid": task["pid"],
        "summary": {
            "avg_cpu_pct": round(avg_cpu, 2),
            "max_cpu_pct": round(max_cpu, 2),
            "max_rss_mb": round(max_rss, 2),
            "sample_count": len(samples),
            "mode": task.get("collector", "proc"),
            "source_mode": source_mode,
        },
        "timeline": samples,
        "flamegraph": {"name": f"pid:{task['pid']}", "value": round(sum(cpu_values) or 1.0, 2), "children": children},
        "hotspots": hotspots,
        "diagnosis": _diagnose(avg_cpu, max_cpu, max_rss),
    }


def dumps_analysis(task: dict[str, Any], samples: list[dict[str, Any]]) -> str:
    return json.dumps(build_analysis(task, samples), ensure_ascii=False, indent=2)


def _source_mode(samples: list[dict[str, Any]], fallback: str) -> str:
    sources = {str(sample.get("source")) for sample in samples if sample.get("source")}
    if len(sources) == 1:
        return sources.pop()
    if len(sources) > 1:
        return "mixed"
    return fallback


def _stack_hotspots(samples: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    tree: dict[str, Any] = {"name": "root", "value": 0.0, "children": {}}
    stacks = defaultdict(float)
    for sample in samples:
        stack = [str(frame) for frame in sample.get("stack", []) if str(frame).strip()]
        if not stack:
            continue
        weight = float(sample.get("weight", sample.get("cpu_pct", 1.0)) or 1.0)
        stacks[";".join(stack)] += max(weight, 1.0)
        node = tree
        node["value"] += max(weight, 1.0)
        for frame in stack:
            node = node["children"].setdefault(frame, {"name": frame, "value": 0.0, "children": {}})
            node["value"] += max(weight, 1.0)

    children = [_freeze_tree(child) for child in tree["children"].values()]
    children.sort(key=lambda item: item["value"], reverse=True)
    hotspots = [
        {
            "name": name,
            "self": round(value, 2),
            "hint": "来自 perf script 导入的真实调用栈热点，可用于替换演示热点视图。",
        }
        for name, value in sorted(stacks.items(), key=lambda item: item[1], reverse=True)[:5]
    ]
    return children, hotspots


def _freeze_tree(node: dict[str, Any]) -> dict[str, Any]:
    children = [_freeze_tree(child) for child in node["children"].values()]
    children.sort(key=lambda item: item["value"], reverse=True)
    frozen = {"name": node["name"], "value": round(node["value"], 2)}
    if children:
        frozen["children"] = children
    return frozen


def _advice(name: str, value: float, source_mode: str = "synthetic-demo") -> str:
    if source_mode == "perf-script-import":
        return "来自 perf script 导入的调用栈热点，建议结合原始 perf.script.txt 追溯符号。"
    if "io" in name and value > 20:
        return "IO wait 占比较高，建议结合 eBPF block I/O 探针确认慢盘或队列抖动。"
    if "syscall" in name and value > 20:
        return "系统调用占比较高，建议检查锁竞争、网络读写或频繁小文件操作。"
    if "user" in name and value > 20:
        return "用户态计算占比较高，建议结合真实 perf 火焰图定位热点函数。"
    return "当前为演示聚合热点；真实 Linux 环境可用 perf script 导入调用栈数据。"


def _diagnose(avg_cpu: float, max_cpu: float, max_rss: float) -> list[str]:
    notes: list[str] = []
    if max_cpu >= 80:
        notes.append("CPU 峰值较高，优先查看火焰图顶部热点。")
    if avg_cpu >= 50:
        notes.append("平均 CPU 偏高，建议延长采样窗口确认是否持续。")
    if max_rss >= 1024:
        notes.append("RSS 超过 1GB，建议补充内存采样或对象分布分析。")
    if not notes:
        notes.append("未发现明显资源异常；当前结果可作为 baseline。")
    return notes
