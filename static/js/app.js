const state = {
  notes: [],
  notebooks: [],
  query: "",
  importance: "",
  notebookId: "",
  sectionId: "",
  editingId: null,
};

const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => [...document.querySelectorAll(sel)];

function toast(msg) {
  const el = $("#toast");
  el.textContent = msg;
  el.classList.remove("hidden");
  clearTimeout(toast._t);
  toast._t = setTimeout(() => el.classList.add("hidden"), 2200);
}

async function api(path, opts = {}) {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json", ...(opts.headers || {}) },
    ...opts,
  });
  if (!res.ok) {
    let err = "Erro na requisicao";
    try {
      const data = await res.json();
      err = data.error || err;
    } catch (_) {}
    throw new Error(err);
  }
  const ct = res.headers.get("content-type") || "";
  if (ct.includes("application/json")) return res.json();
  return res;
}

function highlight(text, q) {
  const safe = escapeHtml(text || "");
  if (!q) return safe;
  const re = new RegExp(q.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"), "ig");
  return safe.replace(re, (m) => `<mark>${m}</mark>`);
}

function escapeHtml(s) {
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function linkify(text) {
  let html = escapeHtml(text || "");
  html = html.replace(/\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>');
  html = html.replace(/(^|[\s(])(https?:\/\/[^\s<]+)/g, '$1<a href="$2" target="_blank" rel="noopener">$2</a>');
  html = html.replace(/(^|[\s(])(www\.[^\s<]+)/g, '$1<a href="https://$2" target="_blank" rel="noopener">$2</a>');
  html = html.replace(/\b([\w.+-]+@[\w-]+\.[\w.-]+)\b/g, '<a href="mailto:$1">$1</a>');
  return html.replace(/\n/g, "<br>");
}

function excerpt(text) {
  return (text || "").replace(/\s+/g, " ").trim().slice(0, 140);
}

function formatDate(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" });
}

async function loadAll() {
  const [nb, notes] = await Promise.all([
    api("/api/notebooks"),
    api(notesUrl()),
  ]);
  state.notebooks = nb.notebooks || [];
  state.notes = notes.notes || [];
  renderNotebooks();
  renderCards();
  fillEditorNotebooks();
}

function notesUrl() {
  const p = new URLSearchParams();
  if (state.query) p.set("q", state.query);
  if (state.importance) p.set("importance", state.importance);
  if (state.notebookId) p.set("notebook_id", state.notebookId);
  const qs = p.toString();
  return "/api/notes" + (qs ? "?" + qs : "");
}

function renderNotebooks() {
  const list = $("#notebook-list");
  const counts = {};
  state.notes.forEach((n) => {
    counts[n.notebook_id] = (counts[n.notebook_id] || 0) + 1;
  });
  const allActive = !state.notebookId ? "active" : "";
  let html = `<button class="all-item ${allActive}" data-nb="">Todas as paginas</button>`;
  state.notebooks.forEach((nb) => {
    const open = state.notebookId === nb.id;
    html += `<div class="nb-item">
      <button class="nb-head ${open && !state.sectionId ? "active" : ""}" data-nb="${nb.id}">
        <span class="nb-dot" style="background:${nb.color || "#7719aa"}"></span>
        <span>${escapeHtml(nb.name)}</span>
        <span class="nb-count">${counts[nb.id] || 0}</span>
      </button>`;
    (nb.sections || []).forEach((sec) => {
      html += `<button class="sec-item ${state.sectionId === sec.id ? "active" : ""}" data-nb="${nb.id}" data-sec="${sec.id}">${escapeHtml(sec.name)}</button>`;
    });
    html += `<button class="add-sec" data-add-sec="${nb.id}">+ Secao</button></div>`;
  });
  list.innerHTML = html;
  list.querySelectorAll("[data-nb]").forEach((btn) => {
    btn.addEventListener("click", () => {
      state.notebookId = btn.dataset.nb || "";
      state.sectionId = btn.dataset.sec || "";
      refreshNotes();
    });
  });
  list.querySelectorAll("[data-add-sec]").forEach((btn) => {
    btn.addEventListener("click", async (e) => {
      e.stopPropagation();
      const name = prompt("Nome da secao:");
      if (!name) return;
      await api(`/api/notebooks/${btn.dataset.addSec}/sections`, {
        method: "POST",
        body: JSON.stringify({ name }),
      });
      toast("Secao criada");
      loadAll();
    });
  });
}

function filteredNotes() {
  let notes = state.notes;
  if (state.sectionId) notes = notes.filter((n) => n.section_id === state.sectionId);
  return notes;
}

function renderCards() {
  const notes = filteredNotes();
  const cards = $("#cards");
  const empty = $("#empty-state");
  const title = $("#workspace-title");
  const meta = $("#workspace-meta");
  let heading = "Todas as paginas";
  if (state.notebookId) {
    const nb = state.notebooks.find((n) => n.id === state.notebookId);
    heading = nb ? nb.name : heading;
    if (state.sectionId && nb) {
      const sec = (nb.sections || []).find((s) => s.id === state.sectionId);
      if (sec) heading = `${nb.name} / ${sec.name}`;
    }
  }
  if (state.query) heading = `Resultados para "${state.query}"`;
  title.textContent = heading;
  meta.textContent = `${notes.length} pagina${notes.length === 1 ? "" : "s"}`;
  if (!notes.length) {
    cards.innerHTML = "";
    empty.classList.remove("hidden");
    return;
  }
  empty.classList.add("hidden");
  cards.innerHTML = notes
    .map((n) => {
      const q = state.query;
      return `<article class="card" data-id="${n.id}">
        <div class="card-bar ${n.importance || "media"}"></div>
        <div class="card-body">
          <h3>${n.pinned ? '<span class="pin">*</span> ' : ""}${highlight(n.title, q)}</h3>
          <div class="card-excerpt">${highlight(excerpt(n.content), q)}</div>
        </div>
        <div class="card-foot">
          <span>${escapeHtml(n.notebook_name || "")} · ${escapeHtml(n.section_name || "")}</span>
          ${(n.tags || []).slice(0, 3).map((t) => `<span class="tag">#${escapeHtml(t)}</span>`).join("")}
          <span class="imp-badge ${n.importance}">${n.importance}</span>
        </div>
      </article>`;
    })
    .join("");
  cards.querySelectorAll(".card").forEach((el) => {
    el.addEventListener("click", () => openEditor(el.dataset.id));
  });
}

async function refreshNotes() {
  const data = await api(notesUrl());
  state.notes = data.notes || [];
  renderNotebooks();
  renderCards();
}

function fillEditorNotebooks() {
  const nbSel = $("#ed-notebook");
  const current = nbSel.value;
  nbSel.innerHTML = state.notebooks
    .map((n) => `<option value="${n.id}">${escapeHtml(n.name)}</option>`)
    .join("");
  if (current) nbSel.value = current;
  fillEditorSections();
}

function fillEditorSections() {
  const nb = state.notebooks.find((n) => n.id === $("#ed-notebook").value);
  const secSel = $("#ed-section");
  const current = secSel.value;
  secSel.innerHTML = ((nb && nb.sections) || [])
    .map((s) => `<option value="${s.id}">${escapeHtml(s.name)}</option>`)
    .join("");
  if (current) secSel.value = current;
}

function openDrawer() {
  $("#editor").classList.remove("hidden");
}
function closeDrawer() {
  $("#editor").classList.add("hidden");
  state.editingId = null;
}

function setPreview() {
  renderLinkEditor();
}

function editableLinks(content) {
  const found = [];
  const seen = new Set();
  const markdown = /\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g;
  let match;
  while ((match = markdown.exec(content))) {
    const raw = match[0];
    seen.add(raw);
    found.push({ raw, label: match[1], url: match[2] });
  }
  const plain = /https?:\/\/[^\s<>()\[\]]+|www\.[^\s<>()\[\]]+|\b[\w.+-]+@[\w-]+\.[\w.-]+\b/g;
  while ((match = plain.exec(content))) {
    const raw = match[0];
    if (seen.has(raw) || found.some((link) => link.url === raw || link.url.replace(/^https:\/\//, "") === raw)) continue;
    const url = raw.includes("@") && !raw.includes("://") ? `mailto:${raw}` : raw.startsWith("www.") ? `https://${raw}` : raw;
    found.push({ raw, label: raw, url });
  }
  return found;
}

function renderLinkEditor() {
  const links = editableLinks($("#ed-content").value);
  const box = $("#ed-links");
  if (!links.length) {
    box.innerHTML = '<p class="links-empty">Nenhum link nesta nota.</p>';
    return;
  }
  box.innerHTML = links.map((link, index) => `
    <div class="link-row" data-index="${index}">
      <a class="link-open" href="${escapeHtml(link.url)}" target="_blank" rel="noopener" title="Abrir link">Abrir</a>
      <div class="link-fields">
        <input class="link-label" value="${escapeHtml(link.label)}" aria-label="Texto do link">
        <input class="link-url" value="${escapeHtml(link.url)}" aria-label="Endereco do link">
      </div>
      <button class="icon-btn link-remove" title="Remover link">✕</button>
    </div>`).join("");
  box.querySelectorAll(".link-row").forEach((row) => {
    const link = links[Number(row.dataset.index)];
    row.querySelectorAll("input").forEach((input) => input.addEventListener("change", () => {
      const label = row.querySelector(".link-label").value.trim();
      const url = row.querySelector(".link-url").value.trim();
      if (!url) return;
      const replacement = label && label !== url ? `[${label}](${url})` : url.replace(/^mailto:/, "");
      const editor = $("#ed-content");
      editor.value = editor.value.replace(link.raw, replacement);
      setPreview();
    }));
    row.querySelector(".link-remove").addEventListener("click", () => {
      const editor = $("#ed-content");
      editor.value = editor.value.replace(link.raw, "");
      setPreview();
    });
  });
}

function openPreview() {
  $("#preview-title").textContent = $("#ed-title").value.trim() || "Sem titulo";
  $("#ed-preview").innerHTML = linkify($("#ed-content").value);
  $("#preview-modal").classList.remove("hidden");
}

async function openEditor(id) {
  fillEditorNotebooks();
  if (!id) {
    state.editingId = null;
    $("#ed-title").value = "";
    $("#ed-content").value = "";
    $("#ed-importance").value = "media";
    $("#ed-tags").value = "";
    $("#ed-due").value = "";
    $("#ed-pin").textContent = "Fixar";
    $("#ed-pin").dataset.pinned = "0";
    if (state.notebookId) $("#ed-notebook").value = state.notebookId;
    fillEditorSections();
    if (state.sectionId) $("#ed-section").value = state.sectionId;
    setPreview();
    openDrawer();
    $("#ed-title").focus();
    return;
  }
  const data = await api(`/api/notes/${id}`);
  const n = data.note;
  state.editingId = n.id;
  $("#ed-title").value = n.title || "";
  $("#ed-content").value = n.content || "";
  $("#ed-importance").value = n.importance || "media";
  $("#ed-tags").value = (n.tags || []).join(", ");
  $("#ed-due").value = (n.due || "").slice(0, 10);
  $("#ed-pin").dataset.pinned = n.pinned ? "1" : "0";
  $("#ed-pin").textContent = n.pinned ? "Fixada" : "Fixar";
  $("#ed-notebook").value = n.notebook_id || "";
  fillEditorSections();
  $("#ed-section").value = n.section_id || "";
  setPreview();
  openDrawer();
}

function gatherNote() {
  const nb = state.notebooks.find((n) => n.id === $("#ed-notebook").value);
  const sec = ((nb && nb.sections) || []).find((s) => s.id === $("#ed-section").value);
  return {
    id: state.editingId,
    title: $("#ed-title").value.trim() || "Sem titulo",
    content: $("#ed-content").value,
    importance: $("#ed-importance").value,
    tags: $("#ed-tags").value.split(/[,;]/).map((t) => t.trim()).filter(Boolean),
    notebook_id: $("#ed-notebook").value,
    section_id: $("#ed-section").value,
    notebook: nb ? nb.name : "Geral",
    section: sec ? sec.name : "Notas",
    due: $("#ed-due").value || null,
    pinned: $("#ed-pin").dataset.pinned === "1",
  };
}

async function saveNote() {
  const payload = gatherNote();
  if (payload.id) {
    await api(`/api/notes/${payload.id}`, { method: "PUT", body: JSON.stringify(payload) });
    toast("Pagina salva");
  } else {
    const data = await api("/api/notes", { method: "POST", body: JSON.stringify(payload) });
    state.editingId = data.note.id;
    toast("Pagina criada");
  }
  await loadAll();
}

function bindEvents() {
  let t;
  $("#search").addEventListener("input", (e) => {
    state.query = e.target.value;
    clearTimeout(t);
    t = setTimeout(refreshNotes, 120);
  });
  $$("#importance-filters .chip").forEach((chip) => {
    chip.addEventListener("click", () => {
      $$("#importance-filters .chip").forEach((c) => c.classList.remove("active"));
      chip.classList.add("active");
      state.importance = chip.dataset.imp || "";
      refreshNotes();
    });
  });
  $("#btn-refresh").addEventListener("click", async () => {
    const button = $("#btn-refresh");
    button.disabled = true;
    button.textContent = "Atualizando...";
    try {
      const data = await api("/api/import-folder", { method: "POST" });
      await loadAll();
      toast(data.imported ? `${data.imported} nota(s) carregada(s)` : "Interface atualizada");
    } catch (err) {
      toast(err.message);
    } finally {
      button.disabled = false;
      button.textContent = "Atualizar interface";
    }
  });
  $("#btn-new-page").addEventListener("click", () => openEditor(null));
  $("#btn-new-note").addEventListener("click", () => openEditor(null));
  $("#editor-close").addEventListener("click", closeDrawer);
  $("#ed-save").addEventListener("click", saveNote);
  $("#ed-content").addEventListener("input", setPreview);
  $("#ed-notebook").addEventListener("change", fillEditorSections);
  $("#ed-pin").addEventListener("click", () => {
    const on = $("#ed-pin").dataset.pinned !== "1";
    $("#ed-pin").dataset.pinned = on ? "1" : "0";
    $("#ed-pin").textContent = on ? "Fixada" : "Fixar";
  });
  $("#ed-delete").addEventListener("click", async () => {
    if (!state.editingId) return closeDrawer();
    if (!confirm("Excluir esta pagina?")) return;
    await api(`/api/notes/${state.editingId}`, { method: "DELETE" });
    closeDrawer();
    toast("Pagina excluida");
    loadAll();
  });
  $("#ed-preview-btn").addEventListener("click", openPreview);
  $("#preview-close").addEventListener("click", () => $("#preview-modal").classList.add("hidden"));
  $("#ed-add-link").addEventListener("click", () => {
    const editor = $("#ed-content");
    const url = prompt("Endereco do link:");
    if (!url) return;
    const label = prompt("Texto exibido (opcional):");
    const normalized = /^(https?:\/\/|mailto:)/i.test(url) ? url : `https://${url}`;
    editor.value += `${editor.value && !editor.value.endsWith("\n") ? "\n" : ""}${label ? `[${label}](${normalized})` : normalized}`;
    setPreview();
  });
  $("#ed-export").addEventListener("click", () => {
    if (!state.editingId) return toast("Salve a pagina primeiro");
    $("#ed-export-options").classList.toggle("hidden");
  });
  $$("[data-export]").forEach((button) => button.addEventListener("click", async () => {
    if (!state.editingId) return toast("Salve a pagina primeiro");
    $("#ed-export-options").classList.add("hidden");
    const format = button.dataset.export;
    try {
      if (window.pywebview && window.pywebview.api) {
        const result = await window.pywebview.api.save_note_export(state.editingId, format);
        if (result.ok) toast("Arquivo exportado");
        else if (!result.cancelled) toast(result.error || "Nao foi possivel exportar");
        return;
      }
      window.location = `/api/export/${state.editingId}.${format}`;
    } catch (err) {
      toast(err.message || "Nao foi possivel exportar");
    }
  }));
  $("#btn-import").addEventListener("click", () => $("#import-modal").classList.remove("hidden"));
  $("#import-cancel").addEventListener("click", () => $("#import-modal").classList.add("hidden"));
  $("#import-go").addEventListener("click", async () => {
    const file = $("#import-file").files[0];
    const notebook = $("#import-notebook").value || "Importados";
    try {
      if (file) {
        const fd = new FormData();
        fd.append("file", file);
        fd.append("notebook", notebook);
        const res = await fetch("/api/import-txt", { method: "POST", body: fd });
        const data = await res.json();
        toast(`${data.imported} nota(s) importada(s)`);
      } else {
        const text = $("#import-text").value;
        if (!text.trim()) return toast("Cole um texto ou escolha um arquivo");
        const data = await api("/api/import-txt", {
          method: "POST",
          body: JSON.stringify({ text, notebook, filename: "colar.txt" }),
        });
        toast(`${data.imported} nota(s) importada(s)`);
      }
      $("#import-modal").classList.add("hidden");
      $("#import-text").value = "";
      $("#import-file").value = "";
      await loadAll();
    } catch (err) {
      toast(err.message);
    }
  });
  $("#btn-new-notebook").addEventListener("click", () => $("#notebook-modal").classList.remove("hidden"));
  $("#nb-cancel").addEventListener("click", () => $("#notebook-modal").classList.add("hidden"));
  $("#nb-go").addEventListener("click", async () => {
    const name = $("#nb-name").value.trim();
    if (!name) return toast("Informe o nome");
    await api("/api/notebooks", {
      method: "POST",
      body: JSON.stringify({ name, color: $("#nb-color").value }),
    });
    $("#notebook-modal").classList.add("hidden");
    $("#nb-name").value = "";
    toast("Caderno criado");
    loadAll();
  });
  $$(".rail-btn[data-view]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      $$(".rail-btn").forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      if (btn.dataset.view === "search") $("#search").focus();
      if (btn.dataset.view === "report") openReport();
      if (btn.dataset.view === "home") {
        state.notebookId = "";
        state.sectionId = "";
        refreshNotes();
      }
    });
  });
  $("#report-close").addEventListener("click", () => $("#report-modal").classList.add("hidden"));
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
      closeDrawer();
      $("#import-modal").classList.add("hidden");
      $("#notebook-modal").classList.add("hidden");
      $("#report-modal").classList.add("hidden");
      $("#preview-modal").classList.add("hidden");
    }
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "s" && !$("#editor").classList.contains("hidden")) {
      e.preventDefault();
      saveNote();
    }
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "n") {
      e.preventDefault();
      openEditor(null);
    }
  });
}

async function openReport() {
  const s = await api("/api/stats");
  $("#report-stats").innerHTML = `
    <div class="stat-box"><b>${s.total}</b><span>Notas</span></div>
    <div class="stat-box"><b>${s.pinned}</b><span>Fixadas</span></div>
    <div class="stat-box"><b>${s.links}</b><span>Links</span></div>
    <div class="stat-box"><b>${s.by_importance.urgente}</b><span>Urgente</span></div>
    <div class="stat-box"><b>${s.by_importance.alta}</b><span>Alta</span></div>
    <div class="stat-box"><b>${s.by_importance.media}</b><span>Media</span></div>
    <div class="stat-box"><b>${s.by_importance.baixa}</b><span>Baixa</span></div>
  `;
  $("#report-modal").classList.remove("hidden");
}

bindEvents();
loadAll().catch((err) => toast(err.message));
