const $ = (id) => document.getElementById(id);
const api = async (path, options = {}) => {
  const response = await fetch(`/api/v1${path}`, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  if (!response.ok) throw new Error(`${response.status} ${await response.text()}`);
  return response.status === 204 ? null : response.json();
};
let runId = null;
async function start() {
  try {
    const run = await api(`/works/${$("work").value}/analysis/reverse-outline`, {
      method: "POST", body: JSON.stringify({}),
    });
    runId = run.id;
    $("report").textContent = JSON.stringify(run, null, 2);
    poll();
  } catch (error) { $("report").textContent = `错误：${error.message}`; }
}
async function poll() {
  if (!runId) return;
  try {
    const run = await api(`/analysis/runs/${runId}`);
    $("report").textContent = JSON.stringify(run, null, 2);
    if (run.status === "queued" || run.status === "extracting") {
      setTimeout(poll, 2000);
    }
  } catch (error) { $("report").textContent = `错误：${error.message}`; }
}
async function loadOutline() {
  if (!runId) return $("message").textContent = "先运行分析";
  try {
    const draft = await api(`/analysis/runs/${runId}/outline`);
    $("content").value = JSON.stringify(draft.content, null, 2);
    $("message").textContent = `status=${draft.status}`;
  } catch (error) { $("message").textContent = `错误：${error.message}`; }
}
async function saveOutline() {
  if (!runId) return $("message").textContent = "先运行分析";
  try {
    const content = JSON.parse($("content").value);
    const draft = await api(`/analysis/runs/${runId}/outline`, {
      method: "PATCH", body: JSON.stringify({ content, status: "draft" }),
    });
    $("message").textContent = `已保存 ${draft.id}`;
  } catch (error) { $("message").textContent = `错误：${error.message}`; }
}
$("start").onclick = start;
$("outline").onclick = loadOutline;
$("save").onclick = saveOutline;
