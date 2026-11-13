const state = { conversationId: null, briefId: null };
const $ = (id) => document.getElementById(id);
const api = async (path, options = {}) => {
  const response = await fetch(`/api/v1${path}`, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  if (!response.ok) throw new Error(`${response.status} ${await response.text()}`);
  return response.status === 204 ? null : response.json();
};
const setStatus = (text) => { $("status").textContent = text; };

async function loadConversations() {
  try {
    const data = await api("/experiments/assistant/conversations?limit=50");
    const list = $("conversations");
    list.innerHTML = "";
    for (const item of data) {
      const li = document.createElement("li");
      li.textContent = `${item.scope}/${item.mode} · ${item.title || item.id.slice(0, 8)}`;
      li.onclick = () => selectConversation(item);
      list.appendChild(li);
    }
    setStatus("已连接");
  } catch (error) { setStatus(`连接失败：${error.message}`); }
}
async function selectConversation(item) {
  state.conversationId = item.id;
  $("conversation-label").textContent = item.title || item.id;
  const messages = await api(`/experiments/assistant/conversations/${item.id}/messages?limit=50`);
  renderMessages(messages.items);
}
function renderMessages(messages) {
  const box = $("messages");
  box.innerHTML = "";
  for (const message of messages) {
    const div = document.createElement("div");
    div.className = message.role;
    div.textContent = `${message.role}: ${message.content}\n`;
    box.appendChild(div);
    for (const citation of message.citations || []) {
      const c = document.createElement("div");
      c.className = "citation";
      c.textContent = `↳ ${citation.source} ${citation.ref} ${citation.quote || ""}`;
      box.appendChild(c);
    }
  }
  box.scrollTop = box.scrollHeight;
}
async function sendMessage(event) {
  event.preventDefault();
  if (!state.conversationId) return setStatus("先选择会话");
  const content = $("message").value.trim();
  if (!content) return;
  $("message").value = "";
  const box = $("messages");
  const user = document.createElement("div"); user.className = "user"; user.textContent = `user: ${content}\n`; box.appendChild(user);
  const assistant = document.createElement("div"); assistant.className = "assistant"; assistant.textContent = "assistant: "; box.appendChild(assistant);
  try {
    const response = await fetch(`/api/v1/experiments/assistant/conversations/${state.conversationId}/messages/stream`, {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ content }),
    });
    if (!response.ok) throw new Error(await response.text());
    const reader = response.body.getReader(); const decoder = new TextDecoder(); let buffer = "";
    while (true) {
      const { value, done } = await reader.read(); if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const events = buffer.split("\n\n"); buffer = events.pop() || "";
      for (const raw of events) {
        const event = raw.match(/event: (.+)/)?.[1];
        const data = raw.match(/data: (.+)/)?.[1];
        if (!data) continue;
        const payload = JSON.parse(data);
        if (event === "delta") assistant.textContent += payload.text;
        if (event === "done") {
          for (const citation of payload.citations || []) {
            const c = document.createElement("div"); c.className = "citation";
            c.textContent = `↳ ${citation.source} ${citation.ref}`; box.appendChild(c);
          }
        }
        if (event === "error") assistant.textContent += `\n[错误] ${payload.error}`;
      }
    }
  } catch (error) { assistant.textContent += `\n[错误] ${error.message}`; }
}
async function createConversation(event) {
  event.preventDefault();
  try {
    const data = await api("/experiments/assistant/conversations", {
      method: "POST", body: JSON.stringify({ scope: $("scope").value, mode: $("mode").value, title: $("title").value }),
    });
    await loadConversations(); await selectConversation(data);
  } catch (error) { setStatus(`创建失败：${error.message}`); }
}
async function createDraft() {
  if (!state.conversationId) return setStatus("先选择会话");
  try {
    const nodes = JSON.parse($("nodes").value); const edges = JSON.parse($("edges").value);
    const draft = await api(`/experiments/assistant/conversations/${state.conversationId}/world-drafts`, {
      method: "POST", body: JSON.stringify({ summary: "", nodes, edges }),
    });
    $("draft").textContent = JSON.stringify(draft, null, 2);
  } catch (error) { $("draft").textContent = `错误：${error.message}`; }
}
async function createBrief() {
  if (!state.conversationId) return setStatus("先选择会话");
  try {
    const brief = await api(`/experiments/assistant/conversations/${state.conversationId}/briefs`, {
      method: "POST", body: JSON.stringify({
        premise: $("premise").value, genre: $("genre").value,
        title_candidates: $("titles").value.split(",").map((s) => s.trim()).filter(Boolean),
      }),
    });
    state.briefId = brief.id; $("brief").textContent = JSON.stringify(brief, null, 2);
  } catch (error) { $("brief").textContent = `错误：${error.message}`; }
}
async function createWork() {
  if (!state.briefId) return setStatus("先创建 Brief");
  try {
    const work = await api(`/experiments/assistant/briefs/${state.briefId}/create-work`, {
      method: "POST", headers: { "Idempotency-Key": crypto.randomUUID() }, body: "{}",
    });
    $("brief").textContent = `已开书：${work.work_id}`;
  } catch (error) { $("brief").textContent = `错误：${error.message}`; }
}
$("conversation-form").onsubmit = createConversation;
$("message-form").onsubmit = sendMessage;
$("create-draft").onclick = createDraft;
$("create-brief").onclick = createBrief;
$("create-work").onclick = createWork;
loadConversations();
