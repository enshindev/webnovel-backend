/* World Studio — throwaway UI prototype. No framework, no persistence. */
const $ = (id) => document.getElementById(id);
const state = { workId: null, chapters: [], chapter: null, generationId: null, analysisRunId: null };

async function api(path, options = {}) {
  const headers = { ...(options.headers || {}) };
  if (!(options.body instanceof FormData) && options.body !== undefined) headers["Content-Type"] = "application/json";
  const response = await fetch(`/api/v1${path}`, { ...options, headers });
  const text = response.status === 204 ? "" : await response.text();
  if (!response.ok) throw new Error(`${response.status} ${text}`);
  return text ? JSON.parse(text) : null;
}
const setStatus = (text) => {
  $("status").textContent = String(text).replace(/<[^>]*>/g, " ").replace(/\s+/g, " ").slice(0, 160);
};
const text = (v) => typeof v === "string" ? v : JSON.stringify(v, null, 2);
const esc = (v) => String(v ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const badge = (value) => `<span class="tag ${value === "ready" || value === "succeeded" ? "good" : value === "failed" ? "bad" : "warn"}">${esc(value)}</span>`;

function renderItems(target, items, render) {
  const box = typeof target === "string" ? $(target) : target;
  box.innerHTML = "";
  if (!items || !items.length) { box.innerHTML = '<div class="muted">暂无数据</div>'; return; }
  for (const item of items) {
    const el = document.createElement("div");
    el.className = "card";
    el.innerHTML = render(item);
    box.appendChild(el);
  }
}

async function loadWorks() {
  try {
    const data = await api("/works?limit=50");
    const box = $("works"); box.innerHTML = "";
    for (const work of data.items) {
      const el = document.createElement("div"); el.className = "item";
      el.innerHTML = `<strong>${esc(work.title)}</strong><div class="meta">${esc(work.genre || "未设题材")} · ${esc(work.id)}</div>`;
      el.onclick = () => selectWork(work);
      box.appendChild(el);
    }
    if (!state.workId && data.items[0]) await selectWork(data.items[0]);
    setStatus("已连接后端");
  } catch (error) { setStatus("未连接后端：请先启动 API，再打开 /app/studio.html"); }
}

async function createWork(event) {
  event.preventDefault();
  try {
    const work = await api("/works", { method: "POST", body: JSON.stringify({ title: $("work-title").value, genre: $("work-genre").value || null }) });
    await loadWorks(); await selectWork(work);
  } catch (error) { setStatus(`创建作品失败：${error.message}`); }
}

async function selectWork(work) {
  state.workId = work.id; state.chapter = null; state.chapterId = null;
  $("current-work").textContent = `${work.title} · ${work.id}`;
  await Promise.all([loadChapters(), loadStory(), loadAnalysis(), loadLibrary(), loadUsage()]);
}

async function loadChapters() {
  if (!state.workId) return;
  try {
    const data = await api(`/works/${state.workId}/chapters`);
    state.chapters = data.items;
    const box = $("chapters"); box.innerHTML = "";
    for (const chapter of data.items) {
      const el = document.createElement("div"); el.className = "item";
      el.innerHTML = `<strong>第 ${chapter.number} 章 · ${esc(chapter.title)}</strong><div class="meta">${chapter.word_count} 字 · ${chapter.current_version_id ? "有正文" : "空章"}</div>`;
      el.onclick = () => selectChapter(chapter);
      box.appendChild(el);
    }
    if (state.chapter && !data.items.some((c) => c.id === state.chapter.id)) state.chapter = null;
  } catch (error) { setStatus(`加载章节失败：${error.message}`); }
}

async function createChapter() {
  try {
    await api(`/works/${state.workId}/chapters`, { method: "POST", body: JSON.stringify({ number: Number($("chapter-number").value), title: $("chapter-title").value, content: "" }) });
    await loadChapters();
  } catch (error) { setStatus(`创建章节失败：${error.message}`); }
}

async function selectChapter(chapter) {
  state.chapter = chapter; state.chapterId = chapter.id;
  $("chapter-meta").textContent = `第 ${chapter.number} 章 · lock_version=${chapter.lock_version}`;
  $("chapter-edit-title").value = chapter.title;
  if (chapter.current_version_id) {
    try {
      const version = await api(`/chapters/${chapter.id}/versions`);
      const current = version.items.find((v) => v.id === chapter.current_version_id);
      $("chapter-edit-content").value = current ? current.content : "";
    } catch (error) { $("chapter-edit-content").value = ""; }
  } else { $("chapter-edit-content").value = ""; }
}

async function saveChapter() {
  if (!state.chapter) return setStatus("先选择章节");
  try {
    const updated = await api(`/chapters/${state.chapter.id}`, { method: "PUT", body: JSON.stringify({ base_version: state.chapter.lock_version, title: $("chapter-edit-title").value, content: $("chapter-edit-content").value }) });
    $("chapter-message").textContent = `已保存 · version=${updated.current_version_id || "-"}`;
    await loadChapters(); state.chapter = state.chapters.find((c) => c.id === updated.id) || updated;
  } catch (error) { $("chapter-message").textContent = `保存失败：${error.message}`; }
}

async function startGeneration() {
  if (!state.chapter) return setStatus("先选择章节");
  try {
    const generation = await api(`/works/${state.workId}/generations`, {
      method: "POST", headers: { "Idempotency-Key": crypto.randomUUID() },
      body: JSON.stringify({ chapter_id: state.chapter.id, task_type: $("generation-task").value, instruction: $("generation-instruction").value || null, candidate_count: Number($("candidate-count").value) }),
    });
    state.generationId = generation.id;
    $("generation-meta").textContent = `generation=${generation.id} · ${generation.status}`;
    pollGeneration();
  } catch (error) { setStatus(`生成失败：${error.message}`); }
}

async function pollGeneration() {
  if (!state.generationId) return;
  try {
    const generation = await api(`/generations/${state.generationId}`);
    $("generation-meta").textContent = `generation=${generation.id} · ${generation.status}`;
    await loadDrafts();
    if (!["succeeded", "failed", "cancelled", "expired"].includes(generation.status)) setTimeout(pollGeneration, 1200);
  } catch (error) { setStatus(`轮询失败：${error.message}`); }
}

async function loadDrafts() {
  if (!state.generationId) return;
  try {
    const data = await api(`/generations/${state.generationId}/drafts`);
    const box = $("drafts"); box.innerHTML = "";
    for (const draft of data.items) {
      const card = document.createElement("div"); card.className = "card";
      card.innerHTML = `<div class="head"><strong>候选 ${draft.candidate_index + 1}</strong>${badge(draft.status)}</div><p>${esc((draft.content || "").slice(0, 1400) || "（生成中）")}</p>`;
      const accept = document.createElement("button"); accept.className = "tiny"; accept.textContent = "采纳";
      accept.onclick = async () => {
        try {
          await api(`/drafts/${draft.id}/accept`, { method: "POST", body: JSON.stringify({ base_version: state.chapter ? state.chapter.lock_version : 0 }) });
          await loadChapters(); setStatus("已采纳候选");
        } catch (error) { setStatus(`采纳失败：${error.message}`); }
      };
      card.appendChild(accept); box.appendChild(card);
    }
  } catch (error) { setStatus(`加载草稿失败：${error.message}`); }
}

async function streamGeneration() {
  if (!state.generationId) return setStatus("先生成");
  try {
    const response = await fetch(`/api/v1/generations/${state.generationId}/stream`);
    if (!response.ok) throw new Error(await response.text());
    const reader = response.body.getReader(); const decoder = new TextDecoder(); let buffer = ""; $("live-text").textContent = "";
    while (true) {
      const { value, done } = await reader.read(); if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const events = buffer.split("\n\n"); buffer = events.pop() || "";
      for (const raw of events) {
        const data = raw.match(/data: (.+)/)?.[1]; if (!data) continue;
        const payload = JSON.parse(data);
        if (payload.text) $("live-text").textContent += payload.text;
      }
    }
  } catch (error) { $("live-text").textContent = `流式连接失败：${error.message}`; }
}

function renderSimple(target, items, line) {
  const box = $(target); box.innerHTML = "";
  if (!items || !items.length) { box.innerHTML = '<div class="muted">暂无数据</div>'; return; }
  for (const item of items) { const div = document.createElement("div"); div.className = "card"; div.textContent = line(item); box.appendChild(div); }
}

async function loadStory() {
  if (!state.workId) return;
  try {
    const [events, knowledge, changes, relations, contradictions, foreshadows] = await Promise.all([
      api(`/works/${state.workId}/story-state/events?limit=50`),
      api(`/works/${state.workId}/story-state/knowledge?limit=50`),
      api(`/works/${state.workId}/story-state/entity-changes?limit=50`),
      api(`/works/${state.workId}/story-state/relations?limit=50`),
      api(`/works/${state.workId}/story-state/contradictions`),
      api(`/works/${state.workId}/foreshadows`),
    ]);
    renderSimple("story-events", events.items, (x) => `第 ${x.chapter_number} 章：${x.summary}`);
    renderSimple("story-knowledge", knowledge.items, (x) => `${x.character_name} · ${x.fact_key} = ${x.state}（第 ${x.chapter_number} 章）`);
    renderSimple("story-changes", changes.items, (x) => `${x.entity_name}.${x.field}：${text(x.before)} → ${text(x.after)}（第 ${x.chapter_number} 章）`);
    renderSimple("story-relations", relations.items, (x) => `${x.from_entity_id} → ${x.to_entity_id}（${x.relation_type}）`);
    renderSimple("story-contradictions", contradictions.items, (x) => `${x.severity} ${x.kind}：${x.message}`);
    renderSimple("story-foreshadows", foreshadows.items, (x) => `${x.status}：${x.description}`);
  } catch (error) { setStatus(`故事状态加载失败：${error.message}`); }
}

async function rebuildStory() {
  try { const result = await api(`/works/${state.workId}/story-state/rebuild`, { method: "POST", body: "{}" }); setStatus(`已排队 ${result.queued} 个重建任务`); }
  catch (error) { setStatus(`重建失败：${error.message}`); }
}

async function startAnalysis() {
  try {
    const run = await api(`/works/${state.workId}/analysis/reverse-outline`, { method: "POST", body: JSON.stringify({ chapter_range: { start: Number($("analysis-start").value || 1), end: Number($("analysis-end").value || 999) } }) });
    state.analysisRunId = run.id; $("analysis-run").textContent = `run=${run.id} · ${run.status}`;
    pollAnalysis();
  } catch (error) { $("analysis-result").textContent = `分析失败：${error.message}`; }
}

async function pollAnalysis() {
  if (!state.analysisRunId) return;
  try {
    const run = await api(`/analysis/runs/${state.analysisRunId}`);
    $("analysis-run").textContent = `run=${run.id} · ${run.status}`;
    const chapters = await api(`/analysis/runs/${run.id}/chapters`);
    const box = $("analysis-chapters"); box.innerHTML = "";
    for (const item of chapters) {
      const div = document.createElement("div"); div.className = "item";
      div.innerHTML = `<strong>${esc(item.chapter_id.slice(0, 8))}</strong> ${badge(item.status)} <span class="muted">confidence=${item.boundary_confidence ?? "-"} progress=${item.progress}%</span><div class="meta">${esc(item.summary || "无摘要")}</div>`;
      div.onclick = () => { $("analysis-chapter-id").value = item.chapter_id; };
      box.appendChild(div);
    }
    if (["queued", "extracting"].includes(run.status)) setTimeout(pollAnalysis, 1500);
  } catch (error) { $("analysis-run").textContent = `轮询失败：${error.message}`; }
}

async function splitAnalysisChapter() {
  try {
    const result = await api(`/analysis/runs/${state.analysisRunId}/chapters/${$("analysis-chapter-id").value}/split`, { method: "POST", body: JSON.stringify({ offset: Number($("split-offset").value) }) });
    $("analysis-result").textContent = JSON.stringify(result, null, 2);
  } catch (error) { $("analysis-result").textContent = `错误：${error.message}`; }
}
async function retryAnalysisChapter() {
  try {
    const result = await api(`/analysis/runs/${state.analysisRunId}/chapters/${$("analysis-chapter-id").value}/retry`, { method: "POST", body: "{}" });
    $("analysis-result").textContent = JSON.stringify(result, null, 2); pollAnalysis();
  } catch (error) { $("analysis-result").textContent = `错误：${error.message}`; }
}

async function loadLibrary() {
  try {
    const collections = await api(`/experiments/library/collections?work_id=${state.workId}`);
    const box = $("collections"); box.innerHTML = "";
    for (const c of collections) {
      const div = document.createElement("div"); div.className = "item"; div.textContent = `${c.name} · ${c.id}`;
      div.onclick = () => { $("collection-id").value = c.id; }; box.appendChild(div);
    }
    if (collections[0] && !$("collection-id").value) $("collection-id").value = collections[0].id;
  } catch (error) { $("library-result").textContent = `资料库不可用：${error.message}`; }
}
async function createCollection() {
  try { const c = await api("/experiments/library/collections", { method: "POST", body: JSON.stringify({ name: $("collection-name").value, work_id: state.workId }) }); $("collection-id").value = c.id; await loadLibrary(); }
  catch (error) { $("library-result").textContent = `创建失败：${error.message}`; }
}
async function uploadDocument() {
  const file = $("library-file").files[0]; if (!file) return;
  const form = new FormData(); form.append("collection_id", $("collection-id").value); form.append("file", file);
  try { const doc = await api("/experiments/library/documents", { method: "POST", body: form }); $("library-result").textContent = JSON.stringify(doc, null, 2); }
  catch (error) { $("library-result").textContent = `上传失败：${error.message}`; }
}
async function searchLibrary() {
  try { const result = await api("/experiments/library/search", { method: "POST", body: JSON.stringify({ query: $("library-query").value, limit: 8 }) }); $("library-result").textContent = JSON.stringify(result, null, 2); }
  catch (error) { $("library-result").textContent = `检索失败：${error.message}`; }
}

async function createExport() {
  try {
    const job = await api(`/works/${state.workId}/exports`, { method: "POST", body: JSON.stringify({ format: $("export-format").value }) });
    state.exportId = job.id;
    renderExports([job]);
    setStatus(`导出任务 ${job.id} · ${job.status}`);
    if (job.status === "queued" || job.status === "running") setTimeout(loadExports, 1200);
  } catch (error) { setStatus(`导出失败：${error.message}`); }
}
async function loadExports() {
  // export jobs have no list endpoint; keep the last job in local state
  if (!state.exportId) return;
  try { const job = await api(`/exports/${state.exportId}`); renderExports([job]); if (job.status === "queued" || job.status === "running") setTimeout(loadExports, 1200); }
  catch (error) { setStatus(`导出轮询失败：${error.message}`); }
}
function renderExports(jobs) {
  renderSimple("exports", jobs, (job) => `${job.format} · ${job.status} · ${job.id}${job.file_path ? " · 文件已生成" : ""}`);
}

async function loadUsage() {
  if (!state.workId) return;
  try { const summary = await api(`/works/${state.workId}/usage/summary`); $("usage-summary").textContent = text(summary); const entries = await api(`/works/${state.workId}/usage?limit=30`); renderSimple("usage-entries", entries.items, (x) => `${x.model} · ${x.task_type || "-"} · ${x.prompt_tokens}+${x.completion_tokens} tokens · ${x.cost.toFixed(4)} ${x.currency}`); }
  catch (error) { $("usage-summary").textContent = `用量加载失败：${error.message}`; }
}
async function loadOverview() {
  try { const overview = await api("/usage/overview?days=30"); $("usage-summary").textContent = text(overview); }
  catch (error) { $("usage-summary").textContent = `概览失败：${error.message}`; }
}

document.querySelectorAll("#tabs button").forEach((button) => {
  button.onclick = () => {
    document.querySelectorAll("#tabs button").forEach((b) => b.classList.remove("active"));
    document.querySelectorAll(".tab").forEach((p) => p.classList.remove("active"));
    button.classList.add("active"); $(`tab-${button.dataset.tab}`).classList.add("active");
  };
});
$("work-form").onsubmit = createWork;
$("create-chapter").onclick = createChapter;
$("save-chapter").onclick = saveChapter;
$("generate").onclick = startGeneration;
$("stream-generation").onclick = streamGeneration;
$("reload-drafts").onclick = loadDrafts;
$("load-story").onclick = loadStory;
$("rebuild-story").onclick = rebuildStory;
$("start-analysis").onclick = startAnalysis;
$("split-chapter").onclick = splitAnalysisChapter;
$("retry-chapter").onclick = retryAnalysisChapter;
$("create-collection").onclick = createCollection;
$("upload-document").onclick = uploadDocument;
$("search-library").onclick = searchLibrary;
$("create-export").onclick = createExport;
$("load-usage").onclick = loadUsage;
$("load-overview").onclick = loadOverview;

loadWorks();
