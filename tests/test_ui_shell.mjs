// UI V2 shell and task-detail regression tests. Uses synthetic data only.
import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
import {test} from "node:test";
import vm from "node:vm";

const html = readFileSync(new URL("../web/index.html", import.meta.url), "utf8");
const scriptMatch = html.match(/<script>([\s\S]*?)<\/script>/);
assert.ok(scriptMatch, "the production page must contain its inline script");

function harness(tasks = [], confirm = () => true) {
  const elements = new Map();
  const writes = [];
  function node(tag = "div") {
    const handlers = new Map();
    const item = {
      tag, handlers, children: [], textContent: "", className: "",
      disabled: false, hidden: false, multiple: false, selected: false,
      _value: "", append(...children) { this.children.push(...children); },
      replaceChildren(...children) { this.children = children; },
      addEventListener(type, handler) {
        if (!handlers.has(type)) handlers.set(type, []);
        handlers.get(type).push(handler);
      }
    };
    Object.defineProperty(item, "value", {
      get() {
        if (tag === "select") return item.children.find(child => child.selected)?.value ?? item._value;
        return item._value;
      },
      set(value) {
        item._value = value;
        if (tag === "select") {
          for (const child of item.children) child.selected = child.value === value;
        }
      }
    });
    Object.defineProperty(item, "selectedOptions", {
      get() { return tag === "select" ? item.children.filter(child => child.selected) : []; }
    });
    return item;
  }
  const document = {
    activeElement: null,
    getElementById(id) {
      if (!elements.has(id)) {
        const selects = new Set(["overview-owner", "query-project", "query-owner",
          "query-status", "query-date-field", "new-task-project", "new-task-related",
          "new-task-priority", "task-sort", "task-date-field"]);
        elements.set(id, node(selects.has(id) ? "select" : "div"));
      }
      return elements.get(id);
    },
    createElement(tag) { return node(tag); }
  };
  const window = {confirm, addEventListener() {}};
  const fetch = async (path, options) => {
    if (options?.method === "POST") {
      writes.push({path, body: JSON.parse(options.body)});
      return {ok: true, json: async () => ({saved: true, task_id: "TASK-MOCK"})};
    }
    if (path === "/api/update/status") {
      return {ok: true, json: async () => ({version: "1.0.0", build_short: "abcdef0"})};
    }
    assert.equal(path, "/api/tasks");
    return {ok: true, json: async () => ({tasks, projects: [], warnings: []})};
  };
  const api = vm.runInNewContext(scriptMatch[1] + "\n;({setActivePage, openTaskDetail, closeTaskDetail, refresh, renderTaskList, setTaskView, moveTaskPeriod, resetTaskPeriod, isoDayParts})", {
      document, window, fetch, Date, setInterval() {}
    }, {timeout: 2500});
  return {api, document, writes, el: id => document.getElementById(id)};
}

function sampleTask() {
  return {
    task_id: "TASK-UI-V2-001", title: "虚构演示任务：整理项目资料",
    status: "doing", revision: 1, conflict: false, conflict_fields: [],
    project_id: null, related_project_ids: [], owner: "演示负责人",
    priority: "high", due_date: "2026-11-05", planned_date: "2026-11-03",
    follow_up_date: null, steps: []
  };
}

test("V2 shell has distinct overview, tasks, projects and settings pages", () => {
  for (const id of ["app-shell", "sidebar", "app-topbar", "page-overview",
    "page-tasks", "page-projects", "page-settings", "create-modal",
    "task-detail-drawer", "global-search-form"]) {
    assert.match(html, new RegExp('id="' + id + '"|class="' + id + '"'),
      "missing V2 shell element: " + id);
  }
  assert.match(html, /id="nav-overview"/);
  assert.match(html, /id="nav-tasks"/);
  assert.match(html, /id="nav-projects"/);
  assert.match(html, /id="nav-settings"/);
});

test("page navigation changes the active workspace without writing task data", async () => {
  const page = harness([sampleTask()]);
  await page.api.refresh(true);
  assert.equal(page.el("page-overview").hidden, false);
  assert.equal(page.el("page-tasks").hidden, true);
  assert.equal(page.api.setActivePage("tasks", "all"), true);
  assert.equal(page.el("page-overview").hidden, true);
  assert.equal(page.el("page-tasks").hidden, false);
  assert.equal(page.el("topbar-context").textContent, "全部任务");
  assert.equal(page.writes.length, 0);
});

test("task summary opens the existing revision-protected editor in a detail drawer", async () => {
  const page = harness([sampleTask()]);
  await page.api.refresh(true);
  const list = page.el("tasks");
  const group = list.children[0];
  const summary = group.children[1];
  const open = summary.children[summary.children.length - 1];
  assert.equal(open.textContent, "查看详情");
  open.handlers.get("click")[0]();
  assert.equal(page.el("task-detail-drawer").hidden, false);
  assert.equal(page.el("task-detail-title").textContent, "虚构演示任务：整理项目资料");
  const editor = page.el("task-detail-content").children[0];
  assert.equal(editor.className, "task");
  assert.ok(editor.children.some(child => child.className === "task-form"));
  assert.ok(editor.children.some(child => child.className === "steps-panel"));
  assert.equal(page.writes.length, 0);
  assert.equal(page.api.closeTaskDetail(), true);
  assert.equal(page.el("task-detail-drawer").hidden, true);
});

test("navigation cannot discard a dirty task draft when the user cancels", async () => {
  let allowDiscard = false;
  const page = harness([sampleTask()], () => allowDiscard);
  await page.api.refresh(true);
  page.api.setActivePage("tasks", "all");
  page.api.openTaskDetail("TASK-UI-V2-001");
  const editor = page.el("task-detail-content").children[0];
  const form = editor.children.find(child => child.className === "task-form");
  const title = form.children[0].children[0];
  title.value = "用户尚未保存的修改";
  form.handlers.get("input")[0]();
  assert.equal(page.api.setActivePage("projects"), false);
  assert.equal(page.el("task-detail-drawer").hidden, false);
  assert.equal(page.el("page-tasks").hidden, false);
  assert.equal(page.writes.length, 0);
  allowDiscard = true;
  assert.equal(page.api.setActivePage("projects"), true);
  assert.equal(page.el("task-detail-drawer").hidden, true);
  assert.equal(page.el("page-projects").hidden, false);
});


test("task creation modal opens and closes without writing task events", async () => {
  const page = harness([sampleTask()]);
  await page.api.refresh(true);
  page.el("open-create-task").handlers.get("click")[0]();
  assert.equal(page.el("create-modal").hidden, false);
  page.el("create-modal-close").handlers.get("click")[0]();
  assert.equal(page.el("create-modal").hidden, true);
  assert.equal(page.writes.length, 0);
});

test("global search applies the existing task query without creating or updating events", async () => {
  const page = harness([sampleTask()]);
  await page.api.refresh(true);
  page.el("global-search").value = "TASK-UI-V2";
  page.el("global-search-form").handlers.get("submit")[0]({preventDefault() {}});
  assert.equal(page.el("page-tasks").hidden, false);
  assert.equal(page.el("query-keyword").value, "TASK-UI-V2");
  assert.equal(page.writes.length, 0);
});

function dateInCurrentMonth(day) {
  const now = new Date();
  return String(now.getFullYear()) + "-" + String(now.getMonth() + 1).padStart(2,"0") +
    "-" + String(day).padStart(2,"0");
}

test("phase 2 status board groups conflicts separately and only opens task detail", async () => {
  const doing = sampleTask();
  const conflict = {...sampleTask(), task_id: "TASK-UI-CONFLICT", title: "冲突样本", conflict: true};
  const blocked = {...sampleTask(), task_id: "TASK-UI-BLOCKED", title: "阻塞样本", status: "blocked"};
  const page = harness([doing, conflict, blocked]);
  await page.api.refresh(true);
  assert.equal(page.api.setTaskView("board"), true);
  assert.equal(page.el("tasks").className, "task-list is-board");
  const note = page.el("tasks").children[0];
  const board = page.el("tasks").children[1];
  assert.match(note.textContent, /只读/);
  assert.equal(board.children.length, 5);
  assert.equal(board.children[1].children[1].children.length, 1);
  assert.equal(board.children[2].children[1].children.length, 1);
  assert.equal(board.children[4].children[1].children.length, 1);
  const card = board.children[4].children[1].children[0];
  card.handlers.get("click")[0]();
  assert.equal(page.el("task-detail-title").textContent, "冲突样本");
  assert.equal(page.writes.length, 0);
});

test("phase 2 calendar renders 42 cells and distinguishes due, planned and followup dates", async () => {
  const due = dateInCurrentMonth(12);
  const planned = dateInCurrentMonth(9);
  const task = {...sampleTask(), due_date: due, planned_date: planned, follow_up_date: null};
  const noDate = {...sampleTask(), task_id: "TASK-UI-NODATE",
                   due_date: null, planned_date: null, follow_up_date: null};
  const page = harness([task, noDate]);
  await page.api.refresh(true);
  assert.equal(page.api.setTaskView("calendar"), true);
  assert.equal(page.el("task-date-tools").hidden, false);
  assert.equal(page.el("task-date-field-label").hidden, false);
  let grid = page.el("tasks").children[2];
  assert.equal(grid.className, "calendar-grid");
  assert.equal(grid.children.length, 42);
  const dueCell = grid.children.find(c => c.title?.startsWith(due + " ·"));
  assert.ok(dueCell);
  assert.equal(dueCell.children.length, 2);
  const undated = page.el("tasks").children[3];
  assert.match(undated.children[0].textContent, /未设置截止日期/);
  assert.equal(undated.children[1].children.length, 1);
  page.el("task-date-field").value = "planned_date";
  page.el("task-date-field").handlers.get("change")[0]();
  grid = page.el("tasks").children[2];
  const plannedCell = grid.children.find(c => c.title?.startsWith(planned + " ·"));
  assert.equal(plannedCell.children.length, 2);
  page.el("task-date-field").value = "follow_up_date";
  page.el("task-date-field").handlers.get("change")[0]();
  grid = page.el("tasks").children[2];
  assert.equal(grid.children.reduce((n,c) => n + c.children.length, 0), 42);
  assert.equal(page.el("tasks").children[3].children[1].children.length, 2);
  assert.equal(page.writes.length, 0);
});

test("phase 2 calendar retains an empty month grid and period buttons change the label", async () => {
  const page = harness([]);
  await page.api.refresh(true);
  page.api.setTaskView("calendar");
  assert.equal(page.el("tasks").children[2].children.length, 42);
  const before = page.el("task-period-label").textContent;
  page.el("task-period-next").handlers.get("click")[0]();
  const after = page.el("task-period-label").textContent;
  assert.notEqual(after, before);
  page.el("task-period-prev").handlers.get("click")[0]();
  assert.equal(page.el("task-period-label").textContent, before);
  assert.equal(page.writes.length, 0);
});

test("phase 2 Gantt shows independent date markers and preserves invalid or missing tasks", async () => {
  const planned = dateInCurrentMonth(5);
  const due = dateInCurrentMonth(12);
  const good = {...sampleTask(), planned_date: planned, due_date: due};
  const invalid = {...sampleTask(), task_id: "TASK-UI-INVALID",
                   planned_date: due, due_date: planned};
  const missing = {...sampleTask(), task_id: "TASK-UI-MISSING",
                   planned_date: null, due_date: null};
  const page = harness([good, invalid, missing]);
  await page.api.refresh(true);
  assert.equal(page.api.setTaskView("gantt"), true);
  assert.equal(page.el("task-date-field-label").hidden, true);
  const table = page.el("tasks").children[1].children[0];
  assert.equal(table.className, "gantt-table");
  assert.equal(table.children.length, 2);
  assert.equal(table.children[0].children[1].children.length, 28);
  const ganttRow = table.children[1];
  const classes = ganttRow.children[1].children.map(c => c.className);
  assert.ok(classes.some(c=>c.includes("is-planned")));
  assert.ok(classes.some(c=>c.includes("is-due")));
  assert.ok(classes.some(c=>c.includes("is-range")));
  assert.equal(page.el("tasks").children[2].children[1].children.length, 2);
  assert.equal(page.writes.length, 0);
});

test("phase 2 refuses view switching when an unsaved task draft cannot be discarded", async () => {
  let allowDiscard = false;
  const page = harness([sampleTask()], () => allowDiscard);
  await page.api.refresh(true);
  page.api.openTaskDetail("TASK-UI-V2-001");
  const form = page.el("task-detail-content").children[0].children
    .find(item => item.className === "task-form");
  const title = form.children[0].children[0];
  title.value = "未保存看板草稿";
  form.handlers.get("input")[0]();
  assert.equal(page.api.setTaskView("board"), false);
  assert.equal(page.el("tasks").className, "task-list");
  assert.equal(page.el("task-detail-content").children[0].children.find(x=>x.className==="task-form"), form);
  assert.equal(title.value, "未保存看板草稿");
  allowDiscard = true;
  assert.equal(page.api.setTaskView("board"), true);
  assert.equal(page.el("task-detail-drawer").hidden, true);
  assert.equal(page.el("tasks").className, "task-list is-board");
  assert.equal(page.writes.length, 0);
});

test("phase 2 accepts only genuine ISO calendar dates and does not infer missing values", async () => {
  const page = harness([]);
  await page.api.refresh(true);
  for (const bad of ["", "2026-02-30", "2026-13-01", "2026-00-01", "abc", null]) {
    assert.equal(page.api.isoDayParts(bad), null);
  }
  assert.ok(page.api.isoDayParts("2024-02-29"));
  assert.ok(page.api.isoDayParts("2026-11-05"));
});
