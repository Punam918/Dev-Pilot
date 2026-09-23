"use strict";
const $ = (id) => document.getElementById(id);
const examples = {
  redis: {repo: "demo-redis", task: "Fix the default Redis hostname for separate Docker Compose containers. Preserve host overrides and validate the patch."},
  pagination: {repo: "demo-pagination", task: "Fix the pagination off-by-one error while preserving invalid-input checks."},
  normalize: {repo: "demo-normalize", task: "Fix username normalization for whitespace and Unicode case folding without altering the tests."}
};
let token = sessionStorage.getItem("devpilot-token") || "";
let runId = null;
let pending = null;
let poll = null;
let streamAbort = null;
let eventCount = 0;
let activityFilter = "all";
const terminal = new Set(["completed", "failed", "cancelled", "interrupted", "limit_reached"]);

function updateTaskCount() {
  $("task-count").textContent = `${$("task").value.length.toLocaleString()} / 4,000`;
}
function filterActivity() {
  let visible = 0;
  const entries = $("trace").querySelectorAll(".trace-event");
  entries.forEach((entry) => {
    const kind = entry.dataset.kind;
    entry.hidden = activityFilter === "tools" ? kind !== "tool_result" :
      activityFilter === "approvals" ? !kind.startsWith("approval_") : false;
    if (!entry.hidden) visible += 1;
  });
  $("trace").querySelector(".filter-empty")?.remove();
  if (entries.length && !visible) {
    const empty = document.createElement("p");
    empty.className = "filter-empty";
    empty.textContent = "No matching activity yet.";
    $("trace").append(empty);
  }
}

function showError(error) {
  $("error").textContent = error.message || String(error);
  $("error").hidden = false;
}
function clearError() { $("error").hidden = true; }
async function api(path, options = {}) {
  const response = await fetch(path, {...options, headers: {"Authorization": `Bearer ${token}`, "Content-Type": "application/json", ...(options.headers || {})}});
  if (!response.ok) {
    let message = `HTTP ${response.status}`;
    try { const body = await response.json(); message = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail); } catch (_) { /* keep HTTP status */ }
    throw new Error(message);
  }
  return response;
}
async function connect() {
  clearError();
  token = $("token").value.trim() || token;
  if (!token) throw new Error("Paste the token printed by python -m devpilot token.");
  const config = await (await api("/api/config")).json();
  sessionStorage.setItem("devpilot-token", token);
  $("token").value = "";
  $("access-panel").hidden = true;
  $("connection-label").textContent = "Workspace connected";
  $("connection-dot").classList.add("connected");
  $("provider").textContent = config.provider === "demo" ? "Scripted replay" : config.model;
  $("runner").textContent = config.runner;
  $("version").textContent = config.version;
  $("demo-banner").hidden = config.provider !== "demo";
  $("runner-warning").hidden = config.runner !== "host-trusted";
  const data = await (await api("/api/repos")).json();
  $("repo").replaceChildren();
  for (const repo of data.repositories) {
    const option = document.createElement("option"); option.value = repo; option.textContent = repo; $("repo").append(option);
  }
  if (!data.repositories.length) throw new Error("No repositories found. Run python -m devpilot init, or copy your project into workspace/.");
  $("repo").disabled = false;
  $("model-check").disabled = false;
  if (data.repositories.includes("demo-redis")) $("repo").value = "demo-redis";
  if (!$("task").value) $("task").value = examples.redis.task;
  updateTaskCount();
  $("run").disabled = false;
  await refreshHistory();
  if (config.active_run) await selectRun(config.active_run);
}
async function refreshHistory() {
  const data = await (await api("/api/runs")).json();
  $("history").replaceChildren();
  for (const run of data.runs.slice(0, 6)) {
    const button = document.createElement("button"); button.className = "history-item";
    button.dataset.runId = run.id;
    button.textContent = run.repo;
    button.setAttribute("aria-current", String(run.id === runId));
    const sub = document.createElement("small"); sub.textContent = `${run.status.toUpperCase()} / ${run.id.slice(0, 8)}`;
    button.append(sub); button.addEventListener("click", () => selectRun(run.id).catch(showError));
    $("history").append(button);
  }
  if (!data.runs.length) {
    const empty = document.createElement("p"); empty.className = "history-empty";
    empty.textContent = "Your investigations will appear here."; $("history").append(empty);
  }
}
async function startRun() {
  clearError();
  $("run").disabled = true;
  try {
    const result = await (await api("/api/runs", {method: "POST", body: JSON.stringify({repo: $("repo").value, task: $("task").value, mode: $("mode").value})})).json();
    await selectRun(result.id);
  } catch (error) { $("run").disabled = false; throw error; }
}
async function selectRun(id) {
  if (streamAbort) streamAbort.abort();
  if (poll) clearInterval(poll);
  runId = id; pending = null; eventCount = 0;
  $("trace").replaceChildren(); $("event-count").textContent = "0 EVENTS";
  const waiting = document.createElement("div");
  waiting.className = "empty pending-empty";
  const waitingTitle = document.createElement("h3");
  waitingTitle.textContent = "Opening your investigation…";
  const waitingCopy = document.createElement("p");
  waitingCopy.textContent = "Activity will appear as each step is recorded.";
  waiting.append(waitingTitle, waitingCopy); $("trace").append(waiting);
  document.querySelectorAll(".history-item").forEach((item) => item.setAttribute("aria-current", String(item.dataset.runId === id)));
  await refreshRun();
  streamAbort = new AbortController();
  followEvents(id, streamAbort.signal).catch((error) => { if (error.name !== "AbortError") showError(error); });
  poll = setInterval(() => refreshRun().catch(showError), 800);
}
function addEvent(event) {
  if (event.kind === "model_request" || event.kind === "tool_requested") return;
  eventCount += 1; $("event-count").textContent = `${eventCount} EVENTS`;
  $("trace").querySelector(".pending-empty")?.remove();
  const node = document.createElement("div"); node.className = `trace-event ${event.kind}`;
  node.dataset.kind = event.kind;
  const details = document.createElement("details");
  const summary = document.createElement("summary");
  const title = document.createElement("span");
  const data = event.data;
  title.textContent = data.tool || event.kind.replaceAll("_", " ");
  const time = document.createElement("time"); time.textContent = new Date(event.created_at).toLocaleTimeString([], {hour12: false});
  summary.append(title, time); details.append(summary);
  const pre = document.createElement("pre");
  if (event.kind === "tool_result" && data.result && data.result.output !== undefined) {
    pre.textContent = `exit code: ${data.result.exit_code}\n${data.result.output}`;
    details.open = true;
  } else if (event.kind === "tool_result" && data.result && data.result.diff !== undefined) {
    pre.textContent = data.result.diff || "No changes."; details.open = true;
  } else { pre.textContent = JSON.stringify(data, null, 2); }
  details.append(pre); node.append(details); $("trace").append(node);
  filterActivity();
  if (event.kind === "approval_required") refreshRun().catch(showError);
  if (event.kind === "run_finished") { refreshRun().catch(showError); refreshHistory().catch(showError); }
}
async function followEvents(id, signal) {
  const response = await api(`/api/runs/${id}/events`, {signal});
  const reader = response.body.getReader(); const decoder = new TextDecoder(); let buffer = "";
  while (true) {
    const {value, done} = await reader.read(); if (done) break;
    buffer += decoder.decode(value, {stream: true});
    let split;
    while ((split = buffer.indexOf("\n\n")) >= 0) {
      const block = buffer.slice(0, split); buffer = buffer.slice(split + 2);
      const line = block.split("\n").find((part) => part.startsWith("data: "));
      if (line && block.includes("event: trace")) addEvent(JSON.parse(line.slice(6)));
    }
  }
  await refreshRun();
}
async function refreshRun() {
  if (!runId) return;
  const id = runId;
  const run = await (await api(`/api/runs/${id}`)).json();
  if (id !== runId) return;
  const done = terminal.has(run.status);
  $("run-status").textContent = run.status.replaceAll("_", " ").toUpperCase();
  $("run-status").className = "pill" + (run.status === "completed" ? " green" : run.status === "awaiting_approval" ? " amber" : run.status === "failed" ? " red" : "");
  $("run").disabled = !done; $("cancel").hidden = done;
  $("downloads").hidden = !done;
  const m = run.metrics || {};
  $("metric-tools").textContent = m.tool_calls ?? "--";
  $("metric-turns").textContent = m.model_turns ?? "--";
  $("metric-errors").textContent = m.tool_errors ?? "--";
  $("metric-time").textContent = m.wall_ms !== undefined ? `${(m.wall_ms / 1000).toFixed(1)}s` : "--";
  const v = run.verification || {};
  $("verification").classList.toggle("good", Boolean(v.verified));
  $("verified-title").textContent = v.verified ? "Final snapshot passed tests" : "Not verified";
  $("verified-copy").textContent = v.verified ? "Recorded exit code 0. The final snapshot matches the tested snapshot." : v.tests_executed ? `Last test exit code: ${v.last_exit_code}. No clean final-snapshot verification.` : "No successful test execution recorded for this snapshot.";
  $("verification").querySelector(".verify-icon").textContent = v.verified ? "✓" : "○";
  $("final").textContent = run.final || "The agent is collecting evidence. Watch the trace and review any approval request.";
  pending = run.pending_approval;
  $("approval").hidden = !pending;
  if (pending) {
    $("approval-title").textContent = pending.tool;
    $("approval-warning").textContent = pending.warning;
    $("approval-hash").textContent = `Snapshot: ${pending.snapshot_sha256.slice(0, 20)}... / Action: ${pending.arguments_sha256.slice(0, 20)}...`;
    $("approval-preview").textContent = pending.preview_diff || JSON.stringify(pending.arguments, null, 2) + "\n\nRun the fixed pytest command on this snapshot.";
    $("approve").disabled = false; $("deny").disabled = false;
  }
  if (done && poll) { clearInterval(poll); poll = null; }
}
async function decide(approved) {
  if (!pending || !runId) return;
  $("approve").disabled = true; $("deny").disabled = true;
  await api(`/api/runs/${runId}/approvals/${pending.id}`, {method: "POST", body: JSON.stringify({approved})});
  $("approval").hidden = true; pending = null;
  await refreshRun();
}
async function download(kind) {
  if (!runId) return;
  const response = await api(`/api/runs/${runId}/artifacts/${kind}`);
  const blob = await response.blob(); const url = URL.createObjectURL(blob);
  const link = document.createElement("a"); link.href = url;
  link.download = `devpilot-${runId.slice(0, 8)}.${kind === "patch" ? "patch" : kind === "trace" ? "json" : "md"}`;
  document.body.append(link); link.click(); link.remove(); setTimeout(() => URL.revokeObjectURL(url), 1000);
}
$("connect").addEventListener("click", () => connect().catch(showError));
$("token").addEventListener("keydown", (event) => { if (event.key === "Enter") connect().catch(showError); });
$("run").addEventListener("click", () => startRun().catch(showError));
$("cancel").addEventListener("click", () => { if (runId) api(`/api/runs/${runId}/cancel`, {method: "POST", body: "{}"}).then(refreshRun).catch(showError); });
$("approve").addEventListener("click", () => decide(true).catch(showError));
$("deny").addEventListener("click", () => decide(false).catch(showError));
$("model-check").addEventListener("click", async () => { try { const data = await (await api("/api/model/health")).json(); $("model-check-result").textContent = data.available ? data.mode || "Configured model is listed. Tool calling still requires a real run." : data.error || "Configured model was not listed."; } catch (error) { showError(error); } });
document.querySelectorAll("[data-example]").forEach((button) => button.addEventListener("click", () => { const e = examples[button.dataset.example]; $("task").value = e.task; updateTaskCount(); if ([...$("repo").options].some((o) => o.value === e.repo)) $("repo").value = e.repo; $("task").focus(); }));
document.querySelectorAll("[data-download]").forEach((button) => button.addEventListener("click", () => download(button.dataset.download).catch(showError)));
$("task").addEventListener("input", updateTaskCount);
$("task").addEventListener("keydown", (event) => {
  if ((event.ctrlKey || event.metaKey) && event.key === "Enter" && !$("run").disabled) {
    event.preventDefault(); startRun().catch(showError);
  }
});
document.querySelectorAll("[data-filter]").forEach((button) => button.addEventListener("click", () => {
  activityFilter = button.dataset.filter;
  document.querySelectorAll("[data-filter]").forEach((tab) => {
    const selected = tab === button;
    tab.classList.toggle("selected", selected);
    tab.setAttribute("aria-pressed", String(selected));
  });
  filterActivity();
}));
if (token) connect().catch((error) => { $("access-panel").hidden = false; showError(error); });
