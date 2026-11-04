// Trash page visual and selection regression tests. All task data is synthetic.
import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
import {test} from "node:test";
import vm from "node:vm";

const html = readFileSync(new URL("../web/index.html", import.meta.url), "utf8");
const scriptMatch = html.match(/<script>([\s\S]*?)<\/script>/);
assert.ok(scriptMatch, "production page must contain its inline script");

function harness(tasks = []) {
  const elements = new Map();
  const writes = [];
  function node(tag = "div") {
    const handlers = new Map();
    const item = {
      tag, handlers, children: [], textContent: "", className: "",
      disabled: false, checked: false, hidden: false, value: "", type: "",
      attributes: {},
      append(...children) { this.children.push(...children); },
      replaceChildren(...children) { this.children = children; },
      addEventListener(type, handler) {
        if (!handlers.has(type)) handlers.set(type, []);
        handlers.get(type).push(handler);
      },
      setAttribute(name, value) { this.attributes[name] = String(value); }
    };
    return item;
  }
  const document = {
    getElementById(id) {
      if (!elements.has(id)) elements.set(id, node(id === "trash-retention" ? "select" : "div"));
      return elements.get(id);
    },
    createElement(tag) { return node(tag); },
    querySelectorAll(selector) {
      const rows = elements.get("trash-list")?.children || [];
      const picks = rows.flatMap(row => row.children.filter(child => child.className === "trash-pick"));
      if (selector.includes(":not(:disabled)")) return picks.filter(item => !item.disabled);
      if (selector.includes(":checked")) return picks.filter(item => item.checked);
      return picks;
    }
  };
  const window = {confirm: () => true, addEventListener() {}};
  const navigator = {clipboard: {writeText: async () => {}}};
  const fetch = async (path, options) => {
    if (path === "/api/trash") return {ok: true, json: async () => ({tasks, retention_days: 30, warnings: []})};
    if (options?.method === "POST") {
      writes.push({path, body: JSON.parse(options.body)});
      return {ok: true, json: async () => ({saved: true})};
    }
    return {ok: true, json: async () => ({tasks: [], projects: [], warnings: []})};
  };
  const api = vm.runInNewContext(
    scriptMatch[1] + "\n;({loadTrash, refreshTrashSelection})",
    {document, window, navigator, fetch, Date, setInterval() {}},
    {timeout: 2500}
  );
  return {api, writes, el: id => document.getElementById(id)};
}

const regularTask = {
  task_id: "TASK-TRASH-UI-001", title: "虚构任务：整理设备采购资料",
  revision: 2, trashed_at: "2026-11-04T08:30:00Z", conflict: false
};
const conflictedTask = {
  task_id: "TASK-TRASH-UI-002", title: "虚构任务：同步冲突示例",
  revision: 3, trashed_at: "2026-11-04T08:35:00Z", conflict: true
};

test("trash page uses the workspace stat cards, full-width panels and responsive action layout", () => {
  assert.match(html, /class="stats trash-stats"/);
  assert.match(html, /class="trash-card trash-settings-card"/);
  assert.match(html, /class="trash-card trash-list-card"/);
  assert.match(html, /class="trash-action trash-action--primary" id="trash-save-retention"/);
  assert.match(html, /class="trash-action trash-action--danger" id="trash-purge-selected" disabled/);
  assert.match(html, /\.trash-row:has\(\.trash-pick:checked\)/);
  assert.match(html, /@media\s*\(max-width:\s*520px\)/);
  assert.doesNotMatch(html, /max-width:\s*960px[^;]*\.trash-panel/);
});

test("trash summary, conflict locks and bulk selection stay in sync without writing data", async () => {
  const page = harness([regularTask, conflictedTask]);
  await page.api.loadTrash();
  const rows = page.el("trash-list").children;
  assert.equal(rows.length, 2);
  assert.equal(page.el("trash-stat-total").textContent, "2");
  assert.equal(page.el("trash-stat-restorable").textContent, "1");
  assert.equal(page.el("trash-stat-conflict").textContent, "1");
  assert.equal(page.el("trash-count").textContent, "2 项");
  assert.equal(page.el("trash-selection-count").textContent, "已选 0 项");
  assert.equal(page.el("trash-purge-selected").disabled, true);
  assert.equal(rows[1].children[0].disabled, true);
  assert.equal(rows[1].children[2].disabled, true);

  page.el("trash-select-all").handlers.get("click")[0]();
  assert.equal(rows[0].children[0].checked, true);
  assert.equal(rows[1].children[0].checked, false);
  assert.equal(page.el("trash-select-all").textContent, "取消全选");
  assert.equal(page.el("trash-selection-count").textContent, "已选 1 项");
  assert.equal(page.el("trash-purge-selected").disabled, false);

  page.el("trash-select-all").handlers.get("click")[0]();
  assert.equal(page.el("trash-selection-count").textContent, "已选 0 项");
  assert.equal(page.el("trash-purge-selected").disabled, true);
  rows[0].children[0].checked = true;
  rows[0].children[0].handlers.get("change")[0]();
  assert.equal(page.el("trash-selection-count").textContent, "已选 1 项");
  assert.equal(page.el("trash-purge-selected").disabled, false);
  assert.equal(page.writes.length, 0);
});

test("empty trash shows a designed empty state and disables bulk actions", async () => {
  const page = harness([]);
  await page.api.loadTrash();
  assert.equal(page.el("trash-list").children.length, 1);
  assert.equal(page.el("trash-list").children[0].className, "trash-empty");
  assert.equal(page.el("trash-stat-total").textContent, "0");
  assert.equal(page.el("trash-select-all").disabled, true);
  assert.equal(page.el("trash-purge-selected").disabled, true);
});
