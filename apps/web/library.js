const $ = (id) => document.getElementById(id);
const api = async (path, options = {}) => {
  const response = await fetch(`/api/v1${path}`, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  if (!response.ok) throw new Error(`${response.status} ${await response.text()}`);
  return response.status === 204 ? null : response.json();
};
async function createCollection() {
  try {
    const payload = { name: $("name").value };
    if ($("work").value) payload.work_id = $("work").value;
    const collection = await api("/experiments/library/collections", {
      method: "POST", body: JSON.stringify(payload),
    });
    $("collection-id").value = collection.id;
    $("collection").textContent = JSON.stringify(collection, null, 2);
  } catch (error) { $("collection").textContent = `错误：${error.message}`; }
}
async function upload() {
  const file = $("file").files[0];
  if (!file) return $("upload-result").textContent = "选择文件";
  const form = new FormData();
  form.append("collection_id", $("collection-id").value);
  form.append("file", file);
  try {
    const response = await fetch("/api/v1/experiments/library/documents", { method: "POST", body: form });
    if (!response.ok) throw new Error(await response.text());
    $("upload-result").textContent = JSON.stringify(await response.json(), null, 2);
  } catch (error) { $("upload-result").textContent = `错误：${error.message}`; }
}
async function search() {
  try {
    const result = await api("/experiments/library/search", {
      method: "POST", body: JSON.stringify({ query: $("query").value, limit: 8 }),
    });
    $("search-result").textContent = JSON.stringify(result, null, 2);
  } catch (error) { $("search-result").textContent = `错误：${error.message}`; }
}
$("create").onclick = createCollection;
$("upload").onclick = upload;
$("search").onclick = search;
