"use strict";

// Headlines, articles, and drafts come from the web or an LLM, so everything
// is rendered as text through el(); nothing is inserted as HTML.

const POLL_MS = 1000;
const JOB_LABELS = {
  scrape: "Previewing headlines",
  headlines: "Generating drafts",
  event: "Drafting event post",
};

const $ = (id) => document.getElementById(id);
const state = { status: null, jobId: null, pollTimer: null, clockTimer: null, startedAt: null };

function el(tag, props = {}, ...children) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(props)) {
    if (key === "class") node.className = value;
    else if (key === "text") node.textContent = value;
    else if (key.startsWith("on")) node.addEventListener(key.slice(2), value);
    else if (key in node && key !== "list") node[key] = value;
    else node.setAttribute(key, value);
  }
  node.append(...children.filter((child) => child !== null && child !== undefined));
  return node;
}

function safeUrl(url) {
  try {
    const parsed = new URL(url);
    return ["http:", "https:"].includes(parsed.protocol) ? parsed.href : "";
  } catch {
    return "";
  }
}

function errorMessage(detail, fallback) {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail.map((item) => `${item.loc?.at(-1) ?? "field"}: ${item.msg}`).join("; ");
  }
  return detail?.message || fallback;
}

async function api(path, options = {}) {
  let response;
  try {
    response = await fetch(path, {
      ...options,
      headers: options.body ? { "Content-Type": "application/json" } : undefined,
    });
  } catch {
    throw Object.assign(new Error("The local server is not responding."), { offline: true });
  }
  const body = await response.json().catch(() => null);
  if (!response.ok) {
    const message = errorMessage(body?.detail, `Request failed (${response.status})`);
    throw Object.assign(new Error(message), { status: response.status, detail: body?.detail });
  }
  return body;
}

function showNotice(message, kind = "error") {
  const notice = $("notice");
  notice.textContent = message || "";
  notice.className = kind === "warn" ? "notice warn" : "notice";
  notice.hidden = !message;
}

// ── tabs ──────────────────────────────────────────────────────────────────

const tabs = ["headlines", "event", "saved"];

function selectTab(name, focus = false) {
  for (const tab of tabs) {
    const selected = tab === name;
    const button = $(`tab-${tab}`);
    button.setAttribute("aria-selected", String(selected));
    button.tabIndex = selected ? 0 : -1;
    $(`view-${tab}`).hidden = !selected;
    if (selected && focus) button.focus();
  }
  if (name === "saved") loadSavedFiles();
}

tabs.forEach((tab, index) => {
  const button = $(`tab-${tab}`);
  button.addEventListener("click", () => selectTab(tab));
  button.addEventListener("keydown", (event) => {
    const step = { ArrowRight: 1, ArrowLeft: -1 }[event.key];
    if (!step) return;
    event.preventDefault();
    selectTab(tabs[(index + step + tabs.length) % tabs.length], true);
  });
});

// ── status ────────────────────────────────────────────────────────────────

function creditHint() {
  const status = state.status;
  if (!status) return "";
  const count = Number($("count").value) || 0;
  const searches = status.web_search.configured
    ? Math.min(count, status.web_search.max_searches_per_run)
    : 0;
  const drafts = `${count} ${count === 1 ? "draft" : "drafts"}`;
  if (!searches) return `Uses LLM calls for ${drafts}. Web search is off.`;
  return `Uses up to ${searches} Tavily ${searches === 1 ? "search" : "searches"}, plus LLM calls for ${drafts}.`;
}

function renderStatus(status) {
  const service = (label, on) =>
    el("span", { class: `service ${on ? "on" : "off"}`, text: label });
  $("services").replaceChildren(
    service(status.llm.configured ? `LLM: ${status.llm.backend}` : "LLM: not configured", status.llm.configured),
    service(status.web_search.configured ? "Web search: on" : "Web search: off", status.web_search.configured),
  );
  $("credit-hint").textContent = creditHint();
  if (!status.llm.configured) {
    showNotice("No LLM is configured, so headline drafts cannot be written. Check your .env file.", "warn");
  }
}

$("count").addEventListener("input", () => {
  $("credit-hint").textContent = creditHint();
});

// ── draft reader ──────────────────────────────────────────────────────────

function wordCount(text) {
  const prose = text.replace(/https?:\/\/\S+/g, "").replace(/#\w+/g, "");
  return prose.trim() ? prose.trim().split(/\s+/).length : 0;
}

function draftPane(draft) {
  const url = safeUrl(draft.url);
  const pane = el("article", { class: "draft" }, el("h2", { text: draft.title }));
  if (draft.published) pane.append(el("p", { class: "draft-meta", text: draft.published }));

  if (!draft.drafted) {
    pane.append(el("p", { class: "callout fail", text: `No draft generated: ${draft.warning || "unknown reason"}` }));
    if (url) pane.append(sourceLink(url));
    return pane;
  }
  if (draft.warning) {
    pane.append(el("p", { class: "callout", text: `Review before posting: ${draft.warning}` }));
  }

  const count = el("span", { class: "word-count" });
  const updateCount = () => {
    const words = wordCount(draft.post);
    count.textContent = `${words} ${words === 1 ? "word" : "words"}`;
  };
  const editor = el("textarea", {
    class: "post",
    value: draft.post,
    "aria-label": "Post text",
    spellcheck: true,
    oninput: () => {
      draft.post = editor.value;
      updateCount();
    },
  });
  updateCount();

  const copy = el("button", {
    type: "button",
    class: "primary",
    text: "Copy post",
    onclick: async () => {
      try {
        await navigator.clipboard.writeText(editor.value);
        copy.textContent = "Copied";
      } catch {
        editor.select();
        copy.textContent = "Press Cmd+C";
      }
      setTimeout(() => { copy.textContent = "Copy post"; }, 1600);
    },
  });

  pane.append(editor, el("div", { class: "draft-actions" }, count, url ? sourceLink(url) : null, copy));
  if (draft.web_context) {
    pane.append(el("details", {},
      el("summary", { text: "Source notes" }),
      el("pre", { text: draft.web_context }),
    ));
  }
  return pane;
}

function sourceLink(url) {
  return el("a", { class: "action", href: url, target: "_blank", rel: "noopener noreferrer", text: "Open source" });
}

function storyMeta(draft) {
  const parts = [];
  if (draft.published) parts.push(draft.published);
  const meta = el("span", { class: "story-meta", text: parts.join("") });
  if (!draft.drafted) meta.append(parts.length ? " · " : "", el("span", { class: "fail", text: "Not generated" }));
  else if (draft.warning) meta.append(parts.length ? " · " : "", el("span", { class: "flag", text: "Review" }));
  return meta;
}

function renderReader(container, drafts) {
  const pane = el("div");
  const showDraft = (index) => {
    pane.replaceChildren(draftPane(drafts[index]));
    buttons.forEach((button, i) => button.setAttribute("aria-current", String(i === index)));
  };
  const buttons = drafts.map((draft, index) =>
    el("button", { type: "button", class: "story", onclick: () => showDraft(index) },
      el("span", { class: "story-number", text: String(index + 1) }),
      el("span", { class: "story-title", text: draft.title }),
      storyMeta(draft),
    ));

  const reader = el("div", { class: drafts.length > 1 ? "reader" : "reader single" });
  if (drafts.length > 1) {
    reader.append(el("ul", { class: "story-list" }, ...buttons.map((button) => el("li", {}, button))));
  }
  reader.append(pane);
  container.append(reader);
  showDraft(0);
}

function renderHeadlineTable(container, headlines) {
  const rows = headlines.map((item, index) => {
    const url = safeUrl(item.url);
    const title = url
      ? el("a", { href: url, target: "_blank", rel: "noopener noreferrer", text: item.title })
      : item.title;
    return el("tr", {},
      el("td", { class: "number", text: String(index + 1) }),
      el("td", {}, title),
      el("td", { class: "nowrap", text: item.source }),
      el("td", { class: "nowrap", text: item.published }),
      el("td", { class: "number", text: item.score.toFixed(1) }),
    );
  });
  const heading = el("tr", {},
    el("th", { class: "number", scope: "col", text: "Rank" }),
    el("th", { scope: "col", text: "Headline" }),
    el("th", { scope: "col", text: "Source" }),
    el("th", { scope: "col", text: "Published" }),
    el("th", { class: "number", scope: "col", text: "Score" }),
  );
  container.append(el("div", { class: "table-wrap" },
    el("table", {}, el("thead", {}, heading), el("tbody", {}, ...rows))));
}

// ── jobs ──────────────────────────────────────────────────────────────────

function setBusy(busy) {
  document.querySelectorAll("[data-run]").forEach((button) => { button.disabled = busy; });
}

function formatElapsed(ms) {
  const seconds = Math.max(0, Math.round(ms / 1000));
  return `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, "0")}`;
}

function renderJob(job) {
  const running = job.status === "running";
  const label = JOB_LABELS[job.kind];
  $("job").hidden = false;
  $("job").className = running ? "job" : `job ${job.status}`;
  $("job-spinner").hidden = !running;
  $("job-title").textContent = running
    ? label
    : job.status === "succeeded" ? `${label}: done` : `${label}: failed`;

  const lines = job.log.split("\n").map((line) => line.trim()).filter(Boolean);
  $("job-activity").textContent = job.error || (running ? lines.at(-1) || "" : "");

  const log = $("job-log");
  const atEnd = log.scrollHeight - log.scrollTop - log.clientHeight < 24;
  log.textContent = job.log;
  if (atEnd) log.scrollTop = log.scrollHeight;
}

function stopTracking() {
  clearTimeout(state.pollTimer);
  clearInterval(state.clockTimer);
  state.jobId = null;
  setBusy(false);
}

function showJobResult(job) {
  const result = job.result;
  if (!result) return;
  const target = job.kind === "event" ? $("event-results") : $("headline-results");
  target.replaceChildren();

  if (job.kind === "scrape") {
    if (!result.headlines.length) {
      target.append(el("p", { class: "empty", text: "No headlines matched in this period." }));
      return;
    }
    target.append(el("p", { class: "result-note", text: `${result.headlines.length} ranked headlines` }));
    renderHeadlineTable(target, result.headlines);
    return;
  }

  if (!result.drafts.length) {
    target.append(el("p", { class: "empty", text: "No headlines matched in this period, so no drafts were written." }));
    return;
  }
  const written = result.drafts.filter((draft) => draft.drafted).length;
  const savedNote = result.saved ? "Saved to the drafts folder." : "Not saved.";
  const note = job.kind === "event"
    ? savedNote
    : `${written} of ${result.drafts.length} drafts written. ${savedNote}`;
  target.append(el("p", { class: "result-note", text: note }));
  renderReader(target, result.drafts);
  // On narrow screens the event draft appears below the form.
  if (job.kind === "event") target.scrollIntoView({ block: "nearest" });
}

async function pollJob(jobId) {
  try {
    const job = await api(`/api/jobs/${jobId}`);
    if (job.id !== state.jobId) return;
    renderJob(job);
    if (job.status === "running") {
      state.pollTimer = setTimeout(() => pollJob(jobId), POLL_MS);
      return;
    }
    $("job-elapsed").textContent = formatElapsed(new Date(job.finished_at) - new Date(job.created_at));
    stopTracking();
    showJobResult(job);
    if (job.result?.saved) {
      savedFilesLoaded = false;
      if (!$("view-saved").hidden) loadSavedFiles();
    }
  } catch (error) {
    if (error.offline) {
      showNotice("Lost contact with the local server. Retrying…");
      state.pollTimer = setTimeout(() => pollJob(jobId), POLL_MS * 3);
      return;
    }
    stopTracking();
    $("job").hidden = true;
    showNotice(error.status === 404
      ? "The server restarted, so this job's progress was lost."
      : error.message);
    return;
  }
  if ($("notice").textContent.startsWith("Lost contact")) showNotice("");
}

function trackJob(job) {
  clearTimeout(state.pollTimer);
  clearInterval(state.clockTimer);
  state.jobId = job.id;
  state.startedAt = new Date(job.created_at);
  setBusy(true);
  renderJob(job);
  const tick = () => { $("job-elapsed").textContent = formatElapsed(Date.now() - state.startedAt); };
  tick();
  state.clockTimer = setInterval(tick, 1000);
  pollJob(job.id);
}

async function startJob(path, body) {
  showNotice("");
  setBusy(true);
  try {
    trackJob(await api(path, { method: "POST", body: body ? JSON.stringify(body) : undefined }));
  } catch (error) {
    setBusy(false);
    if (error.status === 409 && error.detail?.job_id) {
      trackJob(await api(`/api/jobs/${error.detail.job_id}`));
      showNotice("Another job is already running. Showing its progress.", "warn");
    } else {
      showNotice(error.message);
    }
  }
}

$("headline-form").addEventListener("submit", (event) => {
  event.preventDefault();
  startJob("/api/jobs/headlines", { count: Number($("count").value), save: $("headline-save").checked });
});

$("preview").addEventListener("click", () => startJob("/api/jobs/scrape"));

$("event-form").addEventListener("submit", (event) => {
  event.preventDefault();
  startJob("/api/jobs/event", {
    name: $("event-name").value,
    date: $("event-date").value,
    location: $("event-location").value,
    description: $("event-description").value,
    url: $("event-url").value,
    save: $("event-save").checked,
  });
});

// ── saved drafts ──────────────────────────────────────────────────────────

let savedFilesLoaded = false;

async function showSavedFile(name) {
  const target = $("saved-results");
  try {
    const file = await api(`/api/drafts/${encodeURIComponent(name)}`);
    if ($("saved-file").value !== name) return;
    target.replaceChildren();
    if (file.drafts.length) renderReader(target, file.drafts);
    else target.append(el("p", { class: "empty", text: "This file has no drafts." }));
  } catch (error) {
    target.replaceChildren(el("p", { class: "empty", text: error.message }));
  }
}

async function loadSavedFiles() {
  if (savedFilesLoaded) return;
  const select = $("saved-file");
  const target = $("saved-results");
  try {
    const files = await api("/api/drafts");
    savedFilesLoaded = true;
    select.replaceChildren(...files.map((file) => {
      const count = `${file.draft_count} ${file.draft_count === 1 ? "draft" : "drafts"}`;
      return el("option", { value: file.name, text: `${file.created || file.name} · ${file.title} · ${count}` });
    }));
    select.disabled = !files.length;
    if (files.length) await showSavedFile(files[0].name);
    else target.replaceChildren(el("p", { class: "empty", text: "No saved drafts yet. Generate some from the Headlines tab." }));
  } catch (error) {
    target.replaceChildren(el("p", { class: "empty", text: error.message }));
  }
}

$("saved-file").addEventListener("change", (event) => showSavedFile(event.target.value));

// ── start ─────────────────────────────────────────────────────────────────

async function init() {
  const today = new Date();
  today.setMinutes(today.getMinutes() - today.getTimezoneOffset());
  $("event-date").value = today.toISOString().slice(0, 10);
  $("headline-results").replaceChildren(
    el("p", { class: "empty", text: "Generate drafts, or preview this period's ranked headlines first." }),
  );

  try {
    const status = await api("/api/status");
    state.status = status;
    $("count").value = status.default_count;
    $("count").max = status.max_count;
    renderStatus(status);
    if (status.active_job_id) trackJob(await api(`/api/jobs/${status.active_job_id}`));
  } catch (error) {
    showNotice(error.message);
  }
}

init();
