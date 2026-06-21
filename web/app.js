const $ = (id) => document.getElementById(id);

async function api(path, options = {}) {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.error || "request failed");
  return data;
}

function fmtTime(ts) {
  return new Date(ts * 1000).toLocaleTimeString();
}

function statusClass(value) {
  return `status ${value ? String(value) : ""}`;
}

async function refresh() {
  const [{ agents, audits }, { tasks }, { sessions }] = await Promise.all([
    api("/api/agents"),
    api("/api/tasks"),
    api("/api/continuous/sessions"),
  ]);
  $("agents").innerHTML = renderAgents(agents);
  $("audits").innerHTML = renderAudits(audits);
  $("tasks").innerHTML = renderTasks(tasks);
  $("sessions").innerHTML = renderSessions(sessions);
}

function renderAgents(agents) {
  if (!agents.length) return `<p class="muted">暂无 Agent。启动 <code>python3 agent.py</code> 后会出现。</p>`;
  return `<table><thead><tr><th>ID</th><th>Host</th><th>状态</th><th>最后心跳</th></tr></thead><tbody>${agents.map(a => `
    <tr><td>${a.id}</td><td>${a.hostname}<br><span class="muted">${a.ip}</span></td><td><span class="${a.online ? "status online" : "status offline"}">${a.online ? "ONLINE" : "OFFLINE"}</span></td><td>${fmtTime(a.last_heartbeat)}</td></tr>
  `).join("")}</tbody></table>`;
}

function renderAudits(audits) {
  if (!audits.length) return `<p class="muted">暂无审计日志。</p>`;
  return `<table><thead><tr><th>时间</th><th>事件</th><th>内容</th></tr></thead><tbody>${audits.slice(0, 8).map(a => `
    <tr><td>${fmtTime(a.created_at)}</td><td>${a.kind}</td><td>${a.message}</td></tr>
  `).join("")}</tbody></table>`;
}

function renderTasks(tasks) {
  if (!tasks.length) return `<p class="muted">暂无任务。可以创建一个 PID=1 的 demo 任务。</p>`;
  return `<table><thead><tr><th>任务</th><th>PID</th><th>采集器</th><th>Session</th><th>状态</th><th>原因</th><th>操作</th></tr></thead><tbody>${tasks.map(t => `
    <tr><td>${t.id}</td><td>${t.pid}</td><td>${t.collector}</td><td>${t.session_id || "-"}</td><td><span class="${statusClass(t.status)}">${t.status}</span></td><td>${t.reason}</td><td><button onclick="loadTask('${t.id}')">查看</button></td></tr>
  `).join("")}</tbody></table>`;
}

function renderSessions(sessions) {
  if (!sessions.length) return `<p class="muted">暂无持续采样 session。可用 <code>python3 continuous_demo.py</code> 创建。</p>`;
  return `<table><thead><tr><th>Session</th><th>PID</th><th>采集器</th><th>窗口</th><th>状态</th><th>操作</th></tr></thead><tbody>${sessions.map(s => `
    <tr><td>${s.id}</td><td>${s.pid}</td><td>${s.collector}</td><td>${s.duration_sec}s / ${s.interval_sec}s</td><td><span class="${statusClass(s.status)}">${s.status}</span></td><td><button onclick="loadSessionWindow('${s.id}')">最近5分钟</button></td></tr>
  `).join("")}</tbody></table>`;
}

async function loadSessionWindow(id) {
  const now = Date.now() / 1000;
  const data = await api(`/api/continuous/window?session_id=${id}&from=${now - 300}&to=${now}`);
  $("taskDetail").innerHTML = `
    <h3>Continuous Window ${id}</h3>
    ${renderTasks(data.tasks)}
  `;
}

async function loadTask(id) {
  const data = await api(`/api/tasks/${id}`);
  $("taskDetail").innerHTML = renderTaskDetail(data);
}

function renderTaskDetail({ task, transitions, samples, analysis }) {
  return `
    <h3>${task.id} <span class="${statusClass(task.status)}">${task.status}</span></h3>
    <p class="muted">PID ${task.pid} · ${task.duration}s · ${task.sample_rate}Hz · ${task.reason}</p>
    <h3>状态迁移</h3>
    <table><thead><tr><th>时间</th><th>From</th><th>To</th><th>Reason</th></tr></thead><tbody>${transitions.map(t => `
      <tr><td>${fmtTime(t.created_at)}</td><td>${t.from_state || "-"}</td><td>${t.to_state}</td><td>${t.reason}</td></tr>
    `).join("")}</tbody></table>
    ${analysis ? renderAnalysis(analysis) : `<p class="muted">分析结果尚未生成。样本数：${samples.length}</p>`}
  `;
}

function renderAnalysis(analysis) {
  const maxCpu = Math.max(...analysis.timeline.map(s => s.cpu_pct), 1);
  return `
    <h3>资源时间轴</h3>
    <p>平均 CPU ${analysis.summary.avg_cpu_pct}% · 峰值 CPU ${analysis.summary.max_cpu_pct}% · 最大 RSS ${analysis.summary.max_rss_mb} MB</p>
    <div class="timeline">${analysis.timeline.map(s => `<div class="bar" title="${s.cpu_pct}%" style="height:${Math.max(2, s.cpu_pct / maxCpu * 110)}px"></div>`).join("")}</div>
    <h3>采样热点聚合视图</h3>
    <div class="flame">${analysis.flamegraph.children.map((c, i) => `<div class="frame" style="width:${Math.min(100, Math.max(18, c.value))}%;background:${["#2563eb","#059669","#d97706","#7c3aed"][i % 4]}">${c.name} · ${c.value}</div>`).join("")}</div>
    <h3>热点与建议</h3>
    <table><thead><tr><th>热点</th><th>Self</th><th>建议</th></tr></thead><tbody>${analysis.hotspots.map(h => `<tr><td>${h.name}</td><td>${h.self}</td><td>${h.hint}</td></tr>`).join("")}</tbody></table>
    <h3>归因摘要</h3>
    <ul>${analysis.diagnosis.map(d => `<li>${d}</li>`).join("")}</ul>
  `;
}

$("taskForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = new FormData(event.target);
  await api("/api/tasks", {
    method: "POST",
    body: JSON.stringify({
      pid: Number(form.get("pid")),
      duration: Number(form.get("duration")),
      sample_rate: Number(form.get("sample_rate")),
      collector: form.get("collector"),
    }),
  });
  await refresh();
});
$("refreshBtn").addEventListener("click", refresh);
setInterval(refresh, 5000);
refresh();
