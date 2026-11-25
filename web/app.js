"use strict";

const API = "/api/v1";
const state = {
  health: null,
  datasets: [],
  riskConfig: null,
  datasetId: null,
  workload: null,
  risk: null,
  workloadOffset: 0,
  workloadLimit: 20,
  workloadTotal: 0,
  workloadSearch: "",
  showAllWorkloads: false,
  policies: null,
  controllers: new Map(),
};

const el = (id) => document.getElementById(id);
const setHidden = (node, hidden) => node.classList.toggle("hidden", hidden);
const escapeHtml = (value) => String(value)
  .replaceAll("&", "&amp;")
  .replaceAll("<", "&lt;")
  .replaceAll(">", "&gt;")
  .replaceAll('"', "&quot;")
  .replaceAll("'", "&#039;");

function dataset() {
  return state.datasets.find((item) => item.dataset_id === state.datasetId) || null;
}

function riskInfo(level = state.risk) {
  return state.riskConfig?.risk_levels.find((item) => item.risk_level === level) || null;
}

function formatCount(value) {
  return Number(value).toLocaleString();
}

function formatNumber(value) {
  if (value === null || value === undefined || Number.isNaN(value)) return "not available";
  const abs = Math.abs(Number(value));
  if (abs >= 1000) return Number(value).toLocaleString(undefined, { maximumFractionDigits: 2 });
  if (abs >= 10) return Number(value).toLocaleString(undefined, { maximumFractionDigits: 2 });
  return Number(value).toLocaleString(undefined, { maximumFractionDigits: 4 });
}

function shortWorkloadName(value, max = 52) {
  if (!value || value.length <= max) {
    return value;
  }
  return `${value.slice(0, max)}…`;
}

function valueWithUnit(value, unit) {
  return value === null || value === undefined ? "not available" : `${formatNumber(value)} ${unit}`;
}

function pct(value) {
  return value === null || value === undefined ? "not available" : `${formatNumber(value)}%`;
}

function timestamp(us) {
  if (us === null || us === undefined) return "not available";
  return `${Number(us).toLocaleString()} μs`;
}

function apiErrorMessage(error) {
  if (error?.name === "AbortError") return null;
  return error?.message || "The API request failed.";
}

function startRequest(scope) {
  state.controllers.get(scope)?.abort();
  const controller = new AbortController();
  state.controllers.set(scope, controller);
  return controller;
}

async function fetchJson(path, { scope = null } = {}) {
  const controller = scope ? startRequest(scope) : null;
  let response;
  try {
    response = await fetch(path, { signal: controller?.signal, headers: { Accept: "application/json" } });
  } catch (error) {
    if (error.name === "AbortError") throw error;
    throw new Error("The TraceAdvisor API is unreachable. Start the FastAPI service and try again.");
  }
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(body?.error?.message || `Request failed with HTTP ${response.status}.`);
  }
  return body;
}

function showGlobalError(message) {
  const banner = el("global-banner");
  banner.textContent = message;
  setHidden(banner, !message);
}

function setLoading(name, active) {
  const node = el(`${name}-loading`);
  if (node) setHidden(node, !active);
}

function setInlineError(name, message) {
  const node = el(`${name}-error`);
  if (!node) return;
  node.textContent = message || "";
  setHidden(node, !message);
}

function renderHealth() {
  if (!state.health) return;
  el("health-summary").textContent = `Bundle: ${state.health.bundle_status} · schema ${state.health.bundle_schema_version}`;
  setHidden(el("development-banner"), state.health.bundle_status !== "development");
  if (state.health.status !== "ok") {
    showGlobalError("The recommendation bundle health check is not OK. Do not rely on displayed values.");
  }
}

function renderDatasetSelector() {
  const select = el("dataset-select");
  select.innerHTML = state.datasets.map((item) => `<option value="${escapeHtml(item.dataset_id)}">${escapeHtml(item.display_name)}</option>`).join("");
  select.disabled = false;
  select.value = state.datasetId;
  renderDatasetSummary();
}

function renderDatasetSummary() {
  const item = dataset();
  if (!item) return;
  const resources = item.resources.map((r) => `${r.resource}: ${r.label} (${r.unit})`).join(" · ");
  el("dataset-summary").innerHTML = `${escapeHtml(resources)}<br>${formatCount(item.population.test_runs)} test runs · ${formatCount(item.population.workloads)} workloads · min_runs ${formatCount(item.min_runs)}`;
}

function renderRiskControls() {
  const item = dataset();
  const container = el("risk-controls");
  if (!item || !state.riskConfig) {
    container.innerHTML = "";
    return;
  }
  container.innerHTML = state.riskConfig.risk_levels.map((level) => {
    const mapping = level.policies[item.dataset_id];
    const checked = level.risk_level === state.risk;
    return `<button type="button" class="risk-option" role="radio" aria-checked="${checked}" data-risk="${escapeHtml(level.risk_level)}">
      <span class="risk-label">${escapeHtml(level.label)}${level.is_default ? " (default)" : ""}</span>
      <span class="risk-policy">${escapeHtml(mapping.policy)}</span>
      <span class="risk-description">${escapeHtml(level.description)}</span>
    </button>`;
  }).join("");
  container.querySelectorAll("[data-risk]").forEach((button) => {
    button.addEventListener("click", () => selectRisk(button.dataset.risk));
  });
}

function renderSelectionSummary() {
  const item = dataset();
  const risk = riskInfo();
  const rows = [
    ["Dataset", item?.display_name || "not selected"],
    ["Workload", state.workload?.display_name || "not selected"],
    ["Risk", risk ? `${risk.label} (${risk.policies[state.datasetId]?.policy || ""})` : "not selected"],
  ];
  el("selection-summary").innerHTML = rows.map(([k, v]) => `<div><dt>${escapeHtml(k)}</dt><dd>${escapeHtml(v)}</dd></div>`).join("");
}

async function loadWorkloads() {
  if (!state.datasetId) return;
  setLoading("choose", true);
  setInlineError("workload", null);
  el("workload-list").innerHTML = "";

  const params = new URLSearchParams({
    sort: "test_runs",
    limit: String(state.workloadLimit),
    offset: String(state.workloadOffset),
  });
  if (state.workloadSearch.trim()) params.set("search", state.workloadSearch.trim());
  if (!state.showAllWorkloads) params.set("has_history", "true");

  try {
    const body = await fetchJson(`${API}/datasets/${encodeURIComponent(state.datasetId)}/workloads?${params}`, { scope: "workloads" });
    state.workloadTotal = body.total;
    renderWorkloads(body);
  } catch (error) {
    const message = apiErrorMessage(error);
    if (message) {
      setInlineError("workload", message);
      state.workloadTotal = 0;
      renderWorkloads({ total: 0, items: [], offset: 0, limit: state.workloadLimit });
    }
  } finally {
    setLoading("choose", false);
  }
}

function renderWorkloads(body) {
  const list = el("workload-list");
  const total = body.total || 0;
  el("workload-count").textContent = `${formatCount(total)} matching workload${total === 1 ? "" : "s"}`;
  if (!body.items?.length) {
    list.innerHTML = `<div class="empty-state">No workloads match these filters. Many workloads have too little history; try “Show all workloads”.</div>`;
  } else {
    list.innerHTML = body.items.map((item) => {
      const selected = state.workload?.workload_id === item.workload_id;
      const fullDisplayName = item.display_name || item.workload_id;
      const fullWorkloadId = item.workload_id;
      return `<button type="button" class="workload-item${selected ? " selected" : ""}" data-workload="${escapeHtml(item.workload_id)}">
        <span>
          <span class="workload-title" title="${escapeHtml(fullDisplayName)}">${escapeHtml(shortWorkloadName(fullDisplayName))}</span><br>
          <span class="workload-meta" title="${escapeHtml(fullWorkloadId)}">${escapeHtml(shortWorkloadName(fullWorkloadId, 64))} · ${formatCount(item.test_run_count)} test runs · ${formatCount(item.scored_run_count)} scored runs</span>
        </span>
        <span class="badge ${item.latest_uses_history ? "history" : "fallback"}">${item.latest_uses_history ? "history" : "uses your request"}</span>
      </button>`;
    }).join("");
    list.querySelectorAll("[data-workload]").forEach((button, index) => {
      button.addEventListener("click", () => selectWorkload(body.items[index]));
    });
  }

  const start = total ? body.offset + 1 : 0;
  const end = Math.min(body.offset + body.limit, total);
  el("workload-page").textContent = `${formatCount(start)}–${formatCount(end)} of ${formatCount(total)}`;
  el("workload-prev").disabled = body.offset <= 0;
  el("workload-next").disabled = body.offset + body.limit >= total;
}

async function selectDataset(datasetId) {
  state.datasetId = datasetId;
  state.workload = null;
  state.workloadOffset = 0;
  state.workloadSearch = "";
  el("workload-search").value = "";
  state.risk = state.riskConfig.default_risk_level;
  renderDatasetSelector();
  renderRiskControls();
  renderSelectionSummary();
  clearWorkloadViews();
  await Promise.all([loadWorkloads(), loadPolicies()]);
  renderAbout();
}

async function selectWorkload(workload) {
  state.workload = workload;
  renderSelectionSummary();
  el("workload-list").querySelectorAll(".workload-item").forEach((button) => {
    button.classList.toggle("selected", button.dataset.workload === workload.workload_id);
  });
  await loadWorkloadViews();
}

async function selectRisk(risk) {
  state.risk = risk;
  renderRiskControls();
  renderSelectionSummary();
  if (state.workload) await loadWorkloadViews();
}

function clearWorkloadViews() {
  for (const name of ["recommendation", "history"]) {
    setInlineError(name, null);
    setHidden(el(`${name}-content`), true);
    setHidden(el(`${name}-empty`), false);
    el(`${name}-empty`).textContent = "No workload selected.";
  }
}

async function loadWorkloadViews() {
  const workloadId = state.workload?.workload_id;
  if (!workloadId) return;
  const encodedDataset = encodeURIComponent(state.datasetId);
  const encodedWorkload = encodeURIComponent(workloadId);
  const query = `risk=${encodeURIComponent(state.risk)}`;

  setLoading("recommendation", true);
  setLoading("history", true);
  setInlineError("recommendation", null);
  setInlineError("history", null);
  setHidden(el("recommendation-content"), true);
  setHidden(el("history-content"), true);
  setHidden(el("recommendation-empty"), true);
  setHidden(el("history-empty"), true);

  const recPromise = fetchJson(`${API}/datasets/${encodedDataset}/workloads/${encodedWorkload}/recommendation?${query}`, { scope: "recommendation" });
  const historyPromise = fetchJson(`${API}/datasets/${encodedDataset}/workloads/${encodedWorkload}/history?${query}`, { scope: "history" });

  try {
    const rec = await recPromise;
    renderRecommendation(rec);
  } catch (error) {
    const message = apiErrorMessage(error);
    if (message) setInlineError("recommendation", message);
  } finally {
    setLoading("recommendation", false);
  }

  try {
    const history = await historyPromise;
    renderHistory(history);
  } catch (error) {
    const message = apiErrorMessage(error);
    if (message) setInlineError("history", message);
  } finally {
    setLoading("history", false);
  }
}

function basisMessage(resource, rule) {
  const basis = resource.basis || {};
  const count = basis.history_run_count;
  if (basis.type === "history") return `Based on ${formatCount(count)} earlier run${count === 1 ? "" : "s"}.`;
  if (basis.type === "request_fallback") return `Only ${formatCount(count)} earlier run${count === 1 ? "" : "s"} (needs ${formatCount(rule.min_runs)}): we keep your request.`;
  if (basis.type === "model") return "No request and no history: ML prediction only.";
  if (basis.type === "request") return "Original request policy.";
  return `Basis: ${basis.type || "not available"}.`;
}

function renderRecommendation(rec) {
  const container = el("recommendation-content");
  const sameNotice = rec.same_for_all_risk_levels
    ? `<div class="notice">Risk levels give the same answer for this workload until it has enough history.</div>`
    : "";

  const resources = rec.resources.map((resource) => `<article class="resource-card">
      <h3>${escapeHtml(resource.resource)}</h3>
      <div class="muted">${escapeHtml(resource.label)} · ${escapeHtml(resource.unit)}</div>
      <div class="metric-pair">
        <div class="metric-block"><span class="metric-label">Recommended</span><span class="metric-value" title="${escapeHtml(String(resource.recommended))}">${escapeHtml(valueWithUnit(resource.recommended, resource.unit))}</span></div>
        <div class="metric-block"><span class="metric-label">Original request</span><span class="metric-value" title="${escapeHtml(String(resource.request))}">${escapeHtml(valueWithUnit(resource.request, resource.unit))}</span></div>
      </div>
      <p class="basis"><span class="badge ${resource.basis.type === "history" ? "history" : "fallback"}">${escapeHtml(resource.basis.type)}</span> ${escapeHtml(basisMessage(resource, rec.rule))}</p>
    </article>`).join("");

  const evidenceRows = rec.policy_evidence.resources.map((metric) => `<tr>
    <th scope="row">${escapeHtml(metric.resource)} (${escapeHtml(metric.unit)})</th>
    <td>${escapeHtml(pct(metric.violation_pct))}</td>
    <td>${escapeHtml(valueWithUnit(metric.average_waste, metric.unit))}</td>
    <td>${metric.valid_violation_count === null ? "not available" : formatCount(metric.valid_violation_count)}</td>
  </tr>`).join("");

  const model = rec.rule.ml_model ? Object.entries(rec.rule.ml_model).map(([k, v]) => `${k}: ${v}`).join(", ") : null;
  container.innerHTML = `
    <div class="section-heading">
      <div><h3>${escapeHtml(rec.display_name)}</h3><div class="muted">${escapeHtml(rec.workload_id)} · ${escapeHtml(rec.policy)} · latest run ${escapeHtml(rec.latest_run.occurrence_id)}</div></div>
    </div>
    ${sameNotice}
    <div class="resource-grid">${resources}</div>
    <div class="rule-card">
      <h3>Rule</h3>
      <p>${escapeHtml(rec.rule.description)}</p>
      <p class="muted">min_runs: ${rec.rule.min_runs === null ? "not applicable" : formatCount(rec.rule.min_runs)}${rec.rule.safeguard_policy ? ` · safeguard: ${escapeHtml(rec.rule.safeguard_policy)}` : ""}${model ? ` · ML model: ${escapeHtml(model)}` : ""}</p>
    </div>
    <div class="evidence-card">
      <h3>Dataset-wide policy evidence</h3>
      <p class="muted">These metrics describe the selected policy across the dataset's final-test population; they are not specific to this workload.</p>
      <div class="table-wrap"><table>
        <thead><tr><th>Resource</th><th>Violation rate</th><th>Average waste</th><th>Valid rows</th></tr></thead>
        <tbody>${evidenceRows}</tbody>
      </table></div>
      ${rec.policy_evidence.any_resource ? `<p><strong>Any-resource violation:</strong> ${escapeHtml(pct(rec.policy_evidence.any_resource.violation_pct))} (${formatCount(rec.policy_evidence.any_resource.valid_violation_count)} valid rows)</p>` : ""}
    </div>
    <div class="source-card">
      <div class="source-line">bundle status=${escapeHtml(rec.bundle.bundle_status)} · dataset status=${escapeHtml(rec.bundle.dataset_status)} · source run=${escapeHtml(rec.bundle.source_run_id ?? "not available")} · checksum=${escapeHtml(rec.bundle.bundle_checksum)}</div>
    </div>`;
  setHidden(container, false);
}

function resourceSeries(history, resourceName) {
  return history.items.map((item) => {
    const resource = item.resources.find((r) => r.resource === resourceName);
    return {
      occurrence_id: item.occurrence_id,
      start_time_us: item.start_time_us,
      target_occurrence_id: item.target_occurrence_id,
      target_start_time_us: item.target_start_time_us,
      recommended: resource?.recommended ?? null,
      actual: resource?.actual ?? null,
      exceeded: resource?.exceeded ?? null,
      target_status: resource?.target_status ?? "not available",
      unit: resource?.unit ?? "",
      label: resource?.label ?? resourceName,
    };
  });
}

function finiteValues(values) {
  return values.filter((v) => v !== null && v !== undefined && Number.isFinite(Number(v))).map(Number);
}

function linePath(points, xScale, yScale, valueKey) {
  const parts = [];
  let open = false;
  for (const point of points) {
    const value = point[valueKey];
    if (value === null || value === undefined || !Number.isFinite(Number(value))) {
      open = false;
      continue;
    }
    const command = open ? "L" : "M";
    parts.push(`${command}${xScale(point.start_time_us).toFixed(2)},${yScale(Number(value)).toFixed(2)}`);
    open = true;
  }
  return parts.join(" ");
}

function svgLineChart(points, resourceName, unit) {
  const width = 920, height = 300, left = 64, right = 24, top = 24, bottom = 48;
  const xs = finiteValues(points.map((p) => p.start_time_us));
  const ys = finiteValues(points.flatMap((p) => [p.recommended, p.actual]));
  if (!xs.length || !ys.length) return `<div class="empty-state">No plottable values.</div>`;
  let minX = Math.min(...xs), maxX = Math.max(...xs);
  let minY = Math.min(...ys), maxY = Math.max(...ys);
  if (minX === maxX) { minX -= 1; maxX += 1; }
  if (minY === maxY) { minY -= 1; maxY += 1; }
  const yPad = (maxY - minY) * 0.08;
  minY -= yPad; maxY += yPad;
  const x = (v) => left + ((Number(v) - minX) / (maxX - minX)) * (width - left - right);
  const y = (v) => top + (1 - (Number(v) - minY) / (maxY - minY)) * (height - top - bottom);
  const ticks = [0, 0.25, 0.5, 0.75, 1];
  const grid = ticks.map((t) => {
    const yy = top + t * (height - top - bottom);
    const val = maxY - t * (maxY - minY);
    return `<line class="chart-grid" x1="${left}" y1="${yy}" x2="${width-right}" y2="${yy}"/><text class="chart-label" x="${left-8}" y="${yy+4}" text-anchor="end">${escapeHtml(formatNumber(val))}</text>`;
  }).join("");
  const recPath = linePath(points, x, y, "recommended");
  const actualPath = linePath(points, x, y, "actual");
  const recPoints = points.filter((p) => p.recommended !== null).map((p) => `<circle class="chart-point-rec" cx="${x(p.start_time_us)}" cy="${y(Number(p.recommended))}" r="4"><title>Recommendation run: ${escapeHtml(p.occurrence_id)} | start: ${escapeHtml(timestamp(p.start_time_us))} | recommended: ${escapeHtml(valueWithUnit(p.recommended, unit))}</title></circle>`).join("");
  const actualPoints = points.filter((p) => p.actual !== null).map((p) => `<circle class="${p.exceeded ? "chart-point-exceeded" : "chart-point-actual"}" cx="${x(p.start_time_us)}" cy="${y(Number(p.actual))}" r="5"><title>Recommendation run: ${escapeHtml(p.occurrence_id)} | recommendation start: ${escapeHtml(timestamp(p.start_time_us))} | target run: ${escapeHtml(p.target_occurrence_id ?? "not available")} | target start: ${escapeHtml(timestamp(p.target_start_time_us))} | actual: ${escapeHtml(valueWithUnit(p.actual, unit))}${p.exceeded ? " | exceeded recommendation" : ""}</title></circle>`).join("");
  return `<svg class="ta-chart" viewBox="0 0 ${width} ${height}" role="img" aria-label="${escapeHtml(resourceName)} recommendation and next-run actual history">
    ${grid}
    <line class="chart-axis" x1="${left}" y1="${height-bottom}" x2="${width-right}" y2="${height-bottom}"/>
    <line class="chart-axis" x1="${left}" y1="${top}" x2="${left}" y2="${height-bottom}"/>
    <path class="chart-rec" d="${recPath}"/>
    <path class="chart-actual" d="${actualPath}"/>
    ${recPoints}${actualPoints}
    <text class="chart-label" x="${left}" y="${height-14}">${escapeHtml(timestamp(minX))}</text>
    <text class="chart-label" x="${width-right}" y="${height-14}" text-anchor="end">${escapeHtml(timestamp(maxX))}</text>
  </svg>`;
}

function renderHistory(history) {
  const content = el("history-content");
  if (!history.items?.length) {
    el("history-empty").textContent = "No scored runs yet: this workload has not run again in the test period.";
    setHidden(el("history-empty"), false);
    return;
  }
  const resourceNames = history.items[0]?.resources.map((r) => r.resource) || [];
  const anyActual = resourceNames.some((name) => resourceSeries(history, name).some((p) => p.actual !== null));
  if (!anyActual) {
    el("history-empty").textContent = "No scored runs yet: this workload has not run again in the test period.";
    setHidden(el("history-empty"), false);
    return;
  }

  content.innerHTML = resourceNames.map((name) => {
    const points = resourceSeries(history, name);
    const first = points[0];
    const rows = points.map((p) => `<tr>
      <td>${escapeHtml(p.occurrence_id)}</td>
      <td>${escapeHtml(timestamp(p.start_time_us))}</td>
      <td>${escapeHtml(p.target_occurrence_id ?? "not available")}</td>
      <td>${escapeHtml(timestamp(p.target_start_time_us))}</td>
      <td>${escapeHtml(valueWithUnit(p.recommended, p.unit))}</td>
      <td>${escapeHtml(valueWithUnit(p.actual, p.unit))}</td>
      <td>${p.exceeded === null ? "not available" : (p.exceeded ? "yes" : "no")}</td>
      <td>${escapeHtml(p.target_status)}</td>
    </tr>`).join("");
    return `<article class="chart-card">
      <h3>${escapeHtml(name)} — ${escapeHtml(first.label)} (${escapeHtml(first.unit)})</h3>
      <div class="chart-legend"><span><span class="legend-swatch"></span>Recommendation</span><span><span class="legend-swatch actual"></span>Next-run actual</span><span><span class="legend-swatch exceeded"></span>Exceeded</span></div>
      <div class="chart-wrap">${svgLineChart(points, name, first.unit)}</div>
      <div class="table-wrap"><table>
        <caption class="muted">Accessible chart data. Null next-run usage is shown as not available and is never plotted as zero.</caption>
        <thead><tr><th>Recommendation occurrence</th><th>Recommendation start</th><th>Target occurrence</th><th>Target start</th><th>Recommended</th><th>Actual</th><th>Exceeded</th><th>Target status</th></tr></thead>
        <tbody>${rows}</tbody>
      </table></div>
    </article>`;
  }).join("");
  setHidden(content, false);
}

async function loadPolicies() {
  if (!state.datasetId) return;
  setLoading("policies", true);
  setInlineError("policies", null);
  el("policies-content").innerHTML = "";
  try {
    state.policies = await fetchJson(`${API}/datasets/${encodeURIComponent(state.datasetId)}/policies`, { scope: "policies" });
    renderPolicies();
  } catch (error) {
    state.policies = null;
    const message = apiErrorMessage(error);
    if (message) setInlineError("policies", message);
  } finally {
    setLoading("policies", false);
  }
}

function policyMetric(policy, resource) {
  return policy.resources.find((r) => r.resource === resource) || null;
}

function svgScatter(policies, resourceName, isAnyResource = false) {
  const points = policies.map((policy) => {
    const metric = isAnyResource ? policy.any_resource : policyMetric(policy, resourceName);
    return {
      policy: policy.policy,
      risk: policy.risk_levels,
      x: isAnyResource ? null : metric?.average_waste,
      y: metric?.violation_pct,
    };
  }).filter((p) => p.y !== null && p.y !== undefined && (isAnyResource || (p.x !== null && p.x !== undefined)));

  if (!points.length) return `<div class="empty-state">No comparable values are available.</div>`;
  const width = 920, height = 300, left = 70, right = 30, top = 24, bottom = 54;
  const xs = isAnyResource ? points.map((_, i) => i) : points.map((p) => Number(p.x));
  const ys = points.map((p) => Number(p.y));
  let minX = Math.min(...xs), maxX = Math.max(...xs), minY = Math.min(...ys), maxY = Math.max(...ys);
  if (minX === maxX) { minX -= 1; maxX += 1; }
  if (minY === maxY) { minY = Math.max(0, minY - 1); maxY += 1; }
  const x = (v) => left + ((Number(v) - minX) / (maxX - minX)) * (width - left - right);
  const y = (v) => top + (1 - (Number(v) - minY) / (maxY - minY)) * (height - top - bottom);
  const policyLabelOffsets = {
    request: { x: -8, y: -12 },
    mean: { x: 10, y: 10 },
    p90: { x: 0, y: -10 },
    p95: { x: -8, y: -12 },
    p99: { x: 0, y: -10 },
    ml: { x: 0, y: -10 },
    hybrid: { x: 10, y: 12 },
  };

  const circles = points.map((p, i) => {
    const xv = isAnyResource ? i : p.x;
    const risk = p.risk.length ? ` · risk: ${p.risk.join(", ")}` : "";
    const offset = policyLabelOffsets[String(p.policy).toLowerCase()] || { x: 0, y: -10 };
    return `<g><circle class="scatter-point${p.risk.length ? " risk" : ""}" cx="${x(xv)}" cy="${y(p.y)}" r="7"><title>${escapeHtml(p.policy)}${escapeHtml(risk)} · violation ${escapeHtml(pct(p.y))}${isAnyResource ? "" : ` · average waste ${escapeHtml(formatNumber(p.x))}`}</title></circle><text class="chart-label" x="${x(xv)+offset.x}" y="${y(p.y)+offset.y}" text-anchor="middle">${escapeHtml(p.policy)}</text></g>`;
  }).join("");
  return `<svg class="ta-chart" viewBox="0 0 ${width} ${height}" role="img" aria-label="Policy comparison for ${escapeHtml(resourceName)}">
    <line class="chart-axis" x1="${left}" y1="${height-bottom}" x2="${width-right}" y2="${height-bottom}"/>
    <line class="chart-axis" x1="${left}" y1="${top}" x2="${left}" y2="${height-bottom}"/>
    ${circles}
    <text class="chart-label" x="${(left+width-right)/2}" y="${height-12}" text-anchor="middle">${isAnyResource ? "Policies" : "Average waste"}</text>
    <text class="chart-label" transform="translate(16 ${(top+height-bottom)/2}) rotate(-90)" text-anchor="middle">Violation rate (%)</text>
  </svg>`;
}

function renderPolicies() {
  const body = state.policies;
  const item = dataset();
  if (!body || !item) return;
  const resourceNames = item.resources.map((r) => r.resource);
  const cards = resourceNames.map((name) => {
    const unit = item.resources.find((r) => r.resource === name)?.unit || "";
    const rows = body.policies.map((policy) => {
      const m = policyMetric(policy, name);
      const risk = policy.risk_levels.length ? policy.risk_levels.map((level) => `<span class="badge risk">${escapeHtml(riskInfo(level)?.label || level)}</span>`).join("") : "—";
      return `<tr><th scope="row">${escapeHtml(policy.policy)}</th><td>${risk}</td><td>${escapeHtml(pct(m?.violation_pct))}</td><td>${escapeHtml(valueWithUnit(m?.average_waste, unit))}</td><td>${m?.valid_violation_count === null || m?.valid_violation_count === undefined ? "not available" : formatCount(m.valid_violation_count)}</td></tr>`;
    }).join("");
    return `<article class="chart-card">
      <h3>${escapeHtml(name)} (${escapeHtml(unit)})</h3>
      <div class="chart-wrap">${svgScatter(body.policies, name)}</div>
      <div class="table-wrap"><table><thead><tr><th>Policy</th><th>Risk level</th><th>Violation rate</th><th>Average waste</th><th>Valid rows</th></tr></thead><tbody>${rows}</tbody></table></div>
    </article>`;
  });

  const hasAny = body.policies.some((policy) => policy.any_resource !== null);
  if (hasAny) {
    const rows = body.policies.map((policy) => `<tr><th scope="row">${escapeHtml(policy.policy)}</th><td>${policy.risk_levels.map((level) => escapeHtml(riskInfo(level)?.label || level)).join(", ") || "—"}</td><td>${escapeHtml(pct(policy.any_resource?.violation_pct))}</td><td>${policy.any_resource?.valid_violation_count === null || policy.any_resource?.valid_violation_count === undefined ? "not available" : formatCount(policy.any_resource.valid_violation_count)}</td></tr>`).join("");
    cards.push(`<article class="chart-card"><h3>Any-resource violation</h3><p class="muted">Google only. Alibaba does not publish this combined metric.</p><div class="chart-wrap">${svgScatter(body.policies, "any resource", true)}</div><div class="table-wrap"><table><thead><tr><th>Policy</th><th>Risk level</th><th>Violation rate</th><th>Valid rows</th></tr></thead><tbody>${rows}</tbody></table></div></article>`);
  }
  el("policies-content").innerHTML = cards.join("");
}

async function loadHybridRule(datasetId) {
  const params = new URLSearchParams({ has_history: "true", sort: "test_runs", limit: "1", offset: "0" });
  let page = await fetchJson(`${API}/datasets/${encodeURIComponent(datasetId)}/workloads?${params}`);
  if (!page.items.length) {
    params.delete("has_history");
    page = await fetchJson(`${API}/datasets/${encodeURIComponent(datasetId)}/workloads?${params}`);
  }
  const workload = page.items[0];
  if (!workload) return null;
  return fetchJson(`${API}/datasets/${encodeURIComponent(datasetId)}/workloads/${encodeURIComponent(workload.workload_id)}/recommendation?risk=restrictive`);
}

async function renderAbout() {
  if (!state.health || !state.datasets.length) return;
  const container = el("about-content");
  container.innerHTML = `<p class="muted">Loading dataset rules…</p>`;
  const ruleResults = await Promise.all(state.datasets.map(async (item) => {
    try { return [item.dataset_id, await loadHybridRule(item.dataset_id)]; }
    catch { return [item.dataset_id, null]; }
  }));
  const rules = Object.fromEntries(ruleResults);

  const datasetCards = state.datasets.map((item) => {
    const rule = rules[item.dataset_id]?.rule;
    const resources = item.resources.map((r) => `<li><strong>${escapeHtml(r.resource)}</strong>: ${escapeHtml(r.label)} · ${escapeHtml(r.unit)} — ${escapeHtml(r.description)}</li>`).join("");
    const caveats = item.caveats.map((c) => `<li>${escapeHtml(c)}</li>`).join("");
    return `<article class="about-card">
      <h3>${escapeHtml(item.display_name)}</h3>
      <p>${escapeHtml(item.evaluation_scope)}</p>
      <ul>${resources}</ul>
      <p><strong>Hybrid rule:</strong> ${rule ? escapeHtml(rule.description) : "not available"}</p>
      <p><strong>History threshold:</strong> ${formatCount(item.min_runs)} earlier run${item.min_runs === 1 ? "" : "s"} before history-based policies stop falling back to the request. ${formatCount(item.population.workloads_with_history_latest)} of ${formatCount(item.population.workloads)} workloads have a latest recommendation that uses history in this bundle; workloads below the threshold may keep the original request instead.</p>
      <details><summary>Dataset caveats</summary><ul>${caveats}</ul></details>
    </article>`;
  }).join("");

  container.innerHTML = `
    <div class="notice">The final test is a one-time historical replay, not a live cluster. Recommendations are compared with the next observed run when a target exists.</div>
    <div class="about-grid">${datasetCards}</div>
    <div class="source-card">
      <h3>Bundle provenance</h3>
      <p class="source-line">status=${escapeHtml(state.health.bundle_status)} · schema=${escapeHtml(state.health.bundle_schema_version)} · export commit=${escapeHtml(state.health.export_commit ?? "not available")} · checksum=${escapeHtml(state.health.bundle_checksum)}</p>
    </div>`;
}

function wireEvents() {
  el("dataset-select").addEventListener("change", (event) => selectDataset(event.target.value));
  el("show-all-workloads").addEventListener("change", (event) => {
    state.showAllWorkloads = event.target.checked;
    state.workloadOffset = 0;
    loadWorkloads();
  });
  let searchTimer = null;
  el("workload-search").addEventListener("input", (event) => {
    clearTimeout(searchTimer);
    searchTimer = setTimeout(() => {
      state.workloadSearch = event.target.value;
      state.workloadOffset = 0;
      loadWorkloads();
    }, 250);
  });
  el("workload-prev").addEventListener("click", () => {
    state.workloadOffset = Math.max(0, state.workloadOffset - state.workloadLimit);
    loadWorkloads();
  });
  el("workload-next").addEventListener("click", () => {
    state.workloadOffset += state.workloadLimit;
    loadWorkloads();
  });
  el("workload-page-size").addEventListener("change", (event) => {
    state.workloadLimit = Math.min(200, Math.max(1, Number(event.target.value) || 20));
    state.workloadOffset = 0;
    loadWorkloads();
  });
}

async function boot() {
  wireEvents();
  try {
    const [health, datasets, risks] = await Promise.all([
      fetchJson(`${API}/health`),
      fetchJson(`${API}/datasets`),
      fetchJson(`${API}/risk-levels`),
    ]);
    state.health = health;
    state.datasets = datasets.datasets;
    state.riskConfig = risks;
    state.datasetId = state.datasets[0]?.dataset_id || null;
    state.risk = risks.default_risk_level;
    renderHealth();
    el("workload-search").disabled = false;
    el("show-all-workloads").disabled = false;
    if (!state.datasetId) throw new Error("The API returned no datasets.");
    await selectDataset(state.datasetId);
  } catch (error) {
    const message = apiErrorMessage(error);
    if (message) showGlobalError(message);
    el("health-summary").textContent = "API unavailable";
  }
}

document.addEventListener("DOMContentLoaded", boot);
