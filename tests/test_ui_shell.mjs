// UI V2 shell and task-detail regression tests. Uses synthetic data only.
import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
import {test} from "node:test";
import vm from "node:vm";

const html = readFileSync(new URL("../web/index.html", import.meta.url), "utf8");
const scriptMatch = html.match(/<script>([\s\S]*?)<\/script>/);
assert.ok(scriptMatch, "the production page must contain its inline script");

function harness(tasks = [], confirm = () => true, projects = [], reviews = []) {
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
          "new-task-priority", "task-sort", "task-date-field", "calendar-granularity", "project-sort"]);
        elements.set(id, node(selects.has(id) ? "select" : "div"));
      }
      return elements.get(id);
    },
    createElement(tag) { return node(tag); }
  };
  const copied = [];
  const navigator = {clipboard: {writeText: async value => {copied.push(value);}}};
  const window = {confirm, addEventListener() {}};
  const fetch = async (path, options) => {
    if (options?.method === "POST") {
      writes.push({path, body: JSON.parse(options.body)});
      return {ok: true, json: async () => ({saved: true, task_id: "TASK-MOCK"})};
    }
    if (path === "/api/update/status") {
      return {ok: true, json: async () => ({version: "1.0.0", build_short: "abcdef0"})};
    }
    if (path === "/api/trash") return {ok: true, json: async () => ({tasks: [], retention_days: 30, warnings: []})};
    if (path === "/api/reviews") return {ok: true, json: async () => ({
      items: reviews, summary: {
        open_count: reviews.filter(item => ["pending","authorized","stale","failed","conflict"].includes(item.status)).length,
        authorized: reviews.filter(item => item.status === "authorized").length,
        applied: reviews.filter(item => item.status === "applied").length,
        dismissed: reviews.filter(item => item.status === "dismissed").length
      }, warnings: []
    })};
    assert.equal(path, "/api/tasks");
    return {ok: true, json: async () => ({tasks, projects, warnings: []})};
  };
  const api = vm.runInNewContext(scriptMatch[1] + "\n;({setActivePage, openTaskDetail, closeTaskDetail, refresh, renderTaskList, setTaskView, moveTaskPeriod, resetTaskPeriod, isoDayParts, projectCounts, openProjectTasks, matchesQuery, stepRow, documentPanel, legacyDocumentPanel, renderReviewDetail, renderReviewList, renderReviewSummary, loadReviews})", {
      document, window, navigator, fetch, Date, setInterval() {}
    }, {timeout: 2500});
  return {api, document, copied, writes, el: id => document.getElementById(id)};
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
    "page-tasks", "page-projects", "page-settings", "page-trash", "create-modal",
    "task-detail-drawer", "global-search-form"]) {
    assert.match(html, new RegExp('id="' + id + '"|class="' + id + '"'),
      "missing V2 shell element: " + id);
  }
  assert.match(html, /id="nav-overview"/);
  assert.match(html, /id="nav-tasks"/);
  assert.match(html, /id="nav-projects"/);
  assert.match(html, /id="nav-settings"/);
  assert.match(html, /id="nav-trash"/);
  assert.doesNotMatch(html, /id="open-trash"/);
  assert.doesNotMatch(html, /id="trash-modal"/);
});


test("last refresh status lives in the sidebar footer, outside the task toolbar", async () => {
  const sidebarFooter = html.match(/<div class="sidebar-footnote">([\s\S]*?)<\/div>/);
  assert.ok(sidebarFooter, "sidebar footer exists");
  assert.match(sidebarFooter[1], /class="sync sidebar-refresh" id="sync"/);
  const sectionActions = html.match(/<div class="section-actions">([\s\S]*?)<\/div>/);
  assert.ok(sectionActions, "task toolbar exists");
  assert.doesNotMatch(sectionActions[1], /id="sync"/, "refresh feedback is not in the task toolbar");
  assert.match(html, /\.sidebar-refresh\s*\{[^}]*height:\s*16px/,
    "the sidebar indicator reserves a fixed line height to avoid layout shifts");
  const page = harness([sampleTask()]);
  await page.api.refresh(true);
  assert.match(page.el("sync").textContent, /^上次刷新 /);
  assert.equal(page.el("sync").title, page.el("sync").textContent);
  assert.equal(page.writes.length, 0);
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

test("trash uses a real sidebar page rather than a task-list button or modal", async () => {
  const page = harness([sampleTask()]);
  await page.api.refresh(true);
  page.el("nav-trash").handlers.get("click")[0]();
  assert.equal(page.el("page-trash").hidden, false);
  assert.equal(page.el("page-tasks").hidden, true);
  assert.equal(page.el("nav-trash").className, "nav-item is-active");
  assert.equal(page.el("topbar-context").textContent, "回收站");
  page.el("nav-tasks").handlers.get("click")[0]();
  assert.equal(page.el("page-trash").hidden, true);
  assert.equal(page.el("page-tasks").hidden, false);
  assert.equal(page.writes.length, 0, "navigation must not change task data");
});


function taskRows(page) {
  const host = page.el("tasks");
  return host.children.flatMap(item => item.className === "task-summary" ? [item] :
    item.className === "project-group" ? item.children.slice(1).filter(x => x.className === "task-summary") : []);
}
function taskTitles(page) {
  return taskRows(page).map(row => row.children[0].children[0].textContent);
}
function columnMenu(page, field) {
  const header = page.el("task-list-columns").children.find(item => item.columnField === field);
  assert.ok(header, "column header exists: " + field);
  const menu = header.children[1];
  return {
    header, menu,
    actions: menu.children.find(item => item.className === "task-column-menu-actions"),
    values: menu.children.find(item => item.className === "task-column-choice-list"),
    date: menu.children.find(item => item.className === "task-column-date"),
    footer: menu.children.filter(item => item.className === "task-column-menu-actions").at(-1)
  };
}
function click(node) { node.handlers.get("click")[0](); }
function pickValues(column, values) {
  for (const item of column.values.children) {
    item.children[0].checked = values.includes(item.children[1].textContent);
  }
  click(column.footer.children[0]);
}

test("list headings align with existing seven task-card fields without changing cards", async () => {
  const page = harness([sampleTask()]);
  await page.api.refresh(true);
  assert.match(html,/id="task-list-columns"/);
  assert.match(html,/class="task-list-columns"/);
  assert.match(html,/id="task-columns-clear"/);
  assert.equal(page.el("task-list-columns").children.length, 7);
  assert.deepEqual(page.el("task-list-columns").children.slice(0,6).map(c => c.children[0].children[0].textContent),
    ["任务／编号","项目","负责人","状态","优先级","截止日期"]);
  assert.equal(page.el("task-list-columns").children[6].textContent,"操作");
  assert.equal(taskRows(page).length,1);
  assert.equal(taskRows(page)[0].className,"task-summary");
  assert.equal(page.el("task-sort").tag,"select");
  assert.equal(page.el("task-legacy-sort-control").hidden,true);
  assert.equal(page.writes.length,0);
});

test("multi-column AND filters, multi-value OR, empty owner and case-insensitive title search", async () => {
  const tasks = [
    {...sampleTask(),task_id:"TASK-AAA",title:"甲方资料",owner:"张甲",status:"doing",priority:"high"},
    {...sampleTask(),task_id:"TASK-BBB",title:"乙方资料",owner:"张甲",status:"blocked",priority:"normal"},
    {...sampleTask(),task_id:"TASK-CCC",title:"丙方资料",owner:"李乙",status:"doing",priority:"high"},
    {...sampleTask(),task_id:"TASK-DDD",title:"无负责人",owner:null,status:"done",priority:"low"}
  ];
  const page = harness(tasks);
  await page.api.refresh(true);
  assert.equal(taskRows(page).length,4);
  pickValues(columnMenu(page,"owner"),["张甲"]);
  assert.equal(taskRows(page).length,2);
  pickValues(columnMenu(page,"status"),["进行中","受阻"]);
  assert.equal(taskRows(page).length,2,"same-column choices use OR");
  pickValues(columnMenu(page,"priority"),["高"]);
  assert.equal(taskRows(page).length,1,"columns combine via AND");
  assert.deepEqual(taskTitles(page),["甲方资料"]);
  const title = columnMenu(page,"title");
  const input = title.menu.children.find(item => item.tag==="input");
  input.value = "TASK-AAA";
  click(title.footer.children[0]);
  assert.deepEqual(taskTitles(page),["甲方资料"],"ID is searchable");
  assert.equal(page.el("query-result-count").textContent,"（1 / 4）");
  click(page.el("task-columns-clear"));
  assert.equal(taskRows(page).length,4);
  assert.equal(page.el("task-columns-clear").disabled,true);
  pickValues(columnMenu(page,"owner"),["未设置"]);
  assert.deepEqual(taskTitles(page),["无负责人"]);
  assert.equal(page.writes.length,0);
});

test("date range and blank-only filters work independently and reject reversed ranges", async () => {
  const tasks = [
    {...sampleTask(),task_id:"TASK-D1",title:"早期任务",due_date:"2026-11-02"},
    {...sampleTask(),task_id:"TASK-D2",title:"近期任务",due_date:"2026-11-09"},
    {...sampleTask(),task_id:"TASK-D3",title:"未排期任务",due_date:null}
  ];
  const page = harness(tasks); await page.api.refresh(true);
  let menu = columnMenu(page,"due");
  menu.date.children[0].children[0].value = "2026-11-05";
  menu.date.children[1].children[0].value = "2026-11-10";
  click(menu.footer.children[0]);
  assert.deepEqual(taskTitles(page),["近期任务"]);
  menu = columnMenu(page,"due");
  menu.date.children[0].children[0].value = "2026-11-20";
  menu.date.children[1].children[0].value = "2026-11-01";
  click(menu.footer.children[0]);
  assert.match(menu.menu.children.at(-1).textContent,/日期结束值不能早于起始值/);
  assert.deepEqual(taskTitles(page),["近期任务"],"invalid range retains prior valid filter");
  menu = columnMenu(page,"due");
  const blank = menu.menu.children.find(item=>item.className==="task-column-choice");
  blank.children[0].checked = true;
  click(menu.footer.children[0]);
  assert.deepEqual(taskTitles(page),["未排期任务"]);
  click(columnMenu(page,"due").footer.children[1]);
  assert.equal(taskRows(page).length,3);
  assert.equal(page.writes.length,0);
});

test("global multi-key sorting honors priority, direction, empty-last and deterministic ties", async () => {
  const tasks = [
    {...sampleTask(),task_id:"TASK-S1",title:"早期普通",due_date:"2026-11-01",priority:"normal"},
    {...sampleTask(),task_id:"TASK-S2",title:"晚期高",due_date:"2026-11-09",priority:"high"},
    {...sampleTask(),task_id:"TASK-S3",title:"晚期紧急",due_date:"2026-11-09",priority:"urgent"},
    {...sampleTask(),task_id:"TASK-S4",title:"无日期",due_date:null,priority:"urgent"}
  ];
  const page = harness(tasks); await page.api.refresh(true);
  click(columnMenu(page,"due").actions.children[0]);
  click(columnMenu(page,"priority").actions.children[1]);
  assert.deepEqual(taskTitles(page),["早期普通","晚期紧急","晚期高","无日期"]);
  assert.equal(page.el("tasks").children[0].className,"task-summary",
    "multi sort is global but preserves original task cards");
  assert.match(columnMenu(page,"due").header.children[0].children[1].textContent,/↑1/);
  assert.match(columnMenu(page,"priority").header.children[0].children[1].textContent,/↓2/);
  click(columnMenu(page,"priority").actions.children[3]);
  assert.deepEqual(taskTitles(page),["晚期紧急","无日期","晚期高","早期普通"]);
  assert.match(columnMenu(page,"priority").header.children[0].children[1].textContent,/↓1/);
  // Modifying the direction of an existing column must not change its precedence.
  click(columnMenu(page,"priority").actions.children[0]);
  assert.match(columnMenu(page,"priority").header.children[0].children[1].textContent,/↑1/);
  click(columnMenu(page,"priority").actions.children[2]);
  assert.equal(page.el("tasks").children[0].className,"task-summary");
  click(page.el("task-columns-clear"));
  assert.equal(page.el("tasks").children[0].className,"project-group",
    "original project sections return after clearing multi sort");
  assert.equal(page.writes.length,0);
});

test("column filters are list-only; board unchanged; rejected draft discard blocks sort", async () => {
  let approved = false;
  const tasks = [
    {...sampleTask(),task_id:"TASK-L1",status:"doing"},
    {...sampleTask(),task_id:"TASK-L2",status:"done",title:"已完成其他任务"}
  ];
  const page = harness(tasks,()=>approved); await page.api.refresh(true);
  pickValues(columnMenu(page,"status"),["进行中"]);
  assert.equal(taskRows(page).length,1);
  assert.equal(page.api.setTaskView("board"),true);
  assert.equal(page.el("task-list-columns").hidden,true);
  assert.equal(page.el("task-columns-clear").hidden,true);
  assert.equal(page.el("query-result-count").textContent,"（2 / 2）");
  assert.equal(page.api.setTaskView("list"),true);
  assert.equal(taskRows(page).length,1);
  page.api.openTaskDetail("TASK-L1");
  const form = page.el("task-detail-content").children[0].children.find(c=>c.className==="task-form");
  form.children[0].children[0].value = "尚未保存草稿";
  form.handlers.get("input")[0]();
  const before = columnMenu(page,"title").header.children[0].children[1].textContent;
  click(columnMenu(page,"title").actions.children[0]);
  assert.equal(columnMenu(page,"title").header.children[0].children[1].textContent,before);
  assert.equal(page.writes.length,0);
});


test("step delete is individually confirmed and posts the step revision, not the task revision", async () => {
  const task = {...sampleTask(), revision: 17, steps: []};
  const step = {step_id: "STEP-" + "A".repeat(32), task_id: task.task_id,
                title: "虚构可删除步骤", status: "doing", revision: 3, document_links: []};
  task.steps = [step];
  let accept = false;
  const page = harness([task], () => accept);
  const line = page.api.stepRow(task, step, 0, page.el("step-message"));
  assert.equal(line.className, "step-row");
  const actions = line.children[2];
  const del = actions.children[2];
  assert.equal(del.className, "step-delete");
  assert.equal(del.textContent, "删除");
  await del.handlers.get("click")[0]();
  assert.equal(page.writes.length, 0, "cancelled confirmation must not write any event");
  accept = true;
  await del.handlers.get("click")[0]();
  assert.equal(page.writes.length, 1);
  assert.equal(page.writes[0].path, "/api/tasks/" + task.task_id + "/steps/" + step.step_id + "/delete");
  assert.equal(page.writes[0].body.revision, 3);
  assert.equal(page.writes[0].body.confirmed_delete, true);
});

test("document attachments render per step; legacy task links remain read-only", () => {
  const task = {...sampleTask(), revision: 8, document_links: [
    {title:"历史文档",url:"https://docs.google.com/document/d/SYNTHETIC/edit"}
  ]};
  const step = {step_id:"STEP-"+"B".repeat(32),revision:2,document_links: [
    {title:"步骤附件",url:"https://drive.google.com/file/d/SYNTHETIC_DOC/view"}
  ]};
  const page = harness([task]);
  const panel = page.api.documentPanel(task,step);
  assert.equal(panel.className,"doc-panel");
  assert.ok(JSON.stringify(panel).includes("步骤附件"));
  assert.equal(panel.children.filter(x=>x.className==="doc-add-form").length,1);
  const legacy = page.api.legacyDocumentPanel(task);
  assert.equal(legacy.className,"doc-panel legacy-doc-panel");
  assert.ok(JSON.stringify(legacy).includes("历史文档"));
  assert.equal(legacy.children.filter(x=>x.className==="doc-add-form").length,0);
  assert.match(html,/function legacyDocumentPanel\(task\)/);
  assert.doesNotMatch(html,/card\.append\(top, form, stepPanel\(task\), documentPanel\(task\)/);
  assert.equal(page.writes.length,0);
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
  assert.equal(table.children[0].children[1].children.length, 42);
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

test("phase 2 Gantt isolates conflicted tasks from any assumed schedule", async () => {
  const task = {...sampleTask(), conflict: true,
    planned_date: dateInCurrentMonth(5), due_date: dateInCurrentMonth(12)};
  const page = harness([task]);
  await page.api.refresh(true);
  page.api.setTaskView("gantt");
  const table = page.el("tasks").children[1].children[0];
  assert.equal(table.children.length, 1, "no disputed date range should be plotted");
  assert.equal(page.el("tasks").children[2].children[1].children.length, 1);
  assert.equal(page.writes.length, 0);
});


test("V2 polishing: calendar and Gantt have direct sidebar navigation", async () => {
  const page = harness([sampleTask()]);
  await page.api.refresh(true);
  page.el("nav-calendar").handlers.get("click")[0]();
  assert.equal(page.el("page-tasks").hidden, false);
  assert.equal(page.el("tasks").className, "task-list is-calendar");
  assert.equal(page.el("tasks-page-title").textContent, "任务日历");
  assert.equal(page.el("topbar-context").textContent, "任务日历");
  assert.equal(page.el("nav-calendar").className, "nav-item is-active");
  page.el("nav-gantt").handlers.get("click")[0]();
  assert.equal(page.el("tasks").className, "task-list is-gantt");
  assert.equal(page.el("tasks-page-title").textContent, "日期甘特图");
  assert.equal(page.el("nav-gantt").className, "nav-item is-active");
  page.el("nav-board").handlers.get("click")[0]();
  assert.equal(page.el("tasks").className, "task-list is-board");
  page.el("nav-tasks").handlers.get("click")[0]();
  assert.equal(page.el("tasks").className, "task-list");
  assert.equal(page.el("topbar-context").textContent, "全部任务");
  assert.equal(page.writes.length, 0);
});

test("V2 polishing: calendar week toggle renders seven days and never changes task records", async () => {
  const page = harness([{...sampleTask(), due_date: dateInCurrentMonth(16)}]);
  await page.api.refresh(true);
  page.el("nav-calendar").handlers.get("click")[0]();
  assert.equal(page.el("tasks").children[2].children.length, 42);
  page.el("calendar-granularity").value = "week";
  page.el("calendar-granularity").handlers.get("change")[0]();
  assert.equal(page.el("tasks").children[2].children.length, 7);
  assert.equal(page.el("tasks").children[2].className, "calendar-grid is-week");
  const label = page.el("task-period-label").textContent;
  page.el("task-period-next").handlers.get("click")[0]();
  assert.notEqual(page.el("task-period-label").textContent, label);
  page.el("task-period-prev").handlers.get("click")[0]();
  assert.equal(page.el("task-period-label").textContent, label);
  page.el("calendar-granularity").value = "month";
  page.el("calendar-granularity").handlers.get("change")[0]();
  assert.equal(page.el("tasks").children[2].children.length, 42);
  assert.equal(page.writes.length, 0);
});

test("V2 polishing: filters remain accessible and Gantt uses legible horizontally scrollable dates", async () => {
  assert.match(html, /id="task-filter-disclosure"/);
  assert.match(html, /\.gantt-table \{min-width:1840px;\}/);
  assert.match(html, /repeat\(42,minmax\(36px,1fr\)\)/);
  assert.match(html, /is-week-start/);
  const page = harness([sampleTask()]);
  await page.api.refresh(true);
  page.el("nav-gantt").handlers.get("click")[0]();
  const dates = page.el("tasks").children[1].children[0].children[0].children[1].children;
  assert.equal(dates.length, 42);
  assert.ok(dates.some(d=>d.className.includes("is-week-start")));
  assert.equal(page.writes.length, 0);
});

test("stage3 project counts separate primary and related without duplicate",async()=>{
 const p="PROJECT-DEMO-1";
 const tasks=[{...sampleTask(),task_id:"A",project_id:p,related_project_ids:[p]},
 {...sampleTask(),task_id:"B",project_id:"OTHER",related_project_ids:[p],status:"blocked"}];
 const x=harness(tasks,()=>true,[{project_id:p,name:"虚构项目",revision:1,conflict:false}]);
 await x.api.refresh(true);
 assert.equal(x.api.projectCounts(p).primary,1);
 assert.equal(x.api.projectCounts(p).related,1);
 assert.equal(x.api.projectCounts(p).total,2);
 assert.equal(x.api.projectCounts(p).risk,1);
 assert.equal(x.writes.length,0);
});
test("stage3 project detail and task list link preserve task ID with no write",async()=>{
 const p="PROJECT-DEMO-1";
 const x=harness([{...sampleTask(),project_id:p}],()=>true,
  [{project_id:p,name:"虚构项目",revision:1,conflict:false}]);
 await x.api.refresh(true);
 x.api.setActivePage("projects");
 const card=x.el("project-list").children[0];
 card.children.find(c=>c.className==="project-card-actions").children[0].handlers.get("click")[0]();
 assert.equal(x.el("project-inspector").hidden,false);
 assert.equal(x.el("project-inspector").children[1].children.length,2);
 assert.equal(x.api.openProjectTasks(p),true);
 assert.equal(x.el("query-project").value,p);
 assert.equal(x.el("query-result-count").textContent,"（1 / 1）");
 assert.equal(x.writes.length,0);
});
test("stage3 project name draft cannot be discarded by navigation or auto refresh",async()=>{
 let consent=false;
 const x=harness([],()=>consent,[{project_id:"P",name:"虚构项目",revision:1,conflict:false}]);
 await x.api.refresh(true);x.api.setActivePage("projects");
 const card=x.el("project-list").children[0],input=card.children[0];
 input.value="未保存新名称";card.handlers.get("input")[0]();
 await x.api.refresh(false);
 assert.equal(x.el("project-list").children[0],card);
 assert.equal(x.api.setActivePage("tasks","all"),false);
 assert.equal(input.value,"未保存新名称");
 consent=true;assert.equal(x.api.setActivePage("tasks","all"),true);
 assert.equal(x.writes.length,0);
});
test("stage3 shows unresolved project references read only",async()=>{
 const x=harness([{...sampleTask(),project_id:"PROJECT-NOT-SYNCED"}]);
 await x.api.refresh(true);
 const card=x.el("project-list").children[0];
 assert.equal(card.children[0].disabled,true);
 assert.equal(x.api.projectCounts("PROJECT-NOT-SYNCED").primary,1);
 assert.equal(x.writes.length,0);
});


test("short display ID supports copy button, clickable ID and keyword search", async () => {
  const task = {...sampleTask(), display_id: "T-261102-ABCDEF123456"};
  const page = harness([task]);
  await page.api.refresh(true);
  page.api.setActivePage("tasks", "all");
  const list = page.el("tasks");
  const group = list.children[0];
  const summary = group.children[1];
  assert.ok(JSON.stringify(summary).includes("T-261102-ABCDEF123456"));
  page.api.openTaskDetail(task.task_id);
  assert.equal(page.el("task-detail-id").textContent, task.display_id);
  await page.el("task-id-copy").handlers.get("click")[0]();
  await page.el("task-detail-id").handlers.get("click")[0]();
  assert.deepEqual(page.copied, [task.display_id, task.display_id]);
  assert.equal(page.el("task-id-feedback").textContent, "已复制");
  assert.equal(page.api.matchesQuery(task, {keyword: "t-261102-abcdef123456"}), true);
  assert.equal(page.writes.length, 0);
});

test("clicking only drawer backdrop closes and respects unsaved edit confirmation", async () => {
  let discard = false;
  const page = harness([sampleTask()], () => discard);
  await page.api.refresh(true);
  page.api.setActivePage("tasks", "all");
  page.api.openTaskDetail("TASK-UI-V2-001");
  const backdrop = page.el("task-detail-drawer");
  const click = backdrop.handlers.get("click")[0];
  click({target: page.el("task-detail-content")});
  assert.equal(backdrop.hidden, false);
  const editor = page.el("task-detail-content").children[0];
  const form = editor.children.find(child => child.className === "task-form");
  form.children[0].children[0].value = "尚未保存的虚构草稿";
  form.handlers.get("input")[0]();
  click({target: backdrop});
  assert.equal(backdrop.hidden, false);
  discard = true;
  click({target: backdrop});
  assert.equal(backdrop.hidden, true);
  assert.equal(page.writes.length, 0);
});


function treeText(node) {
  return [node.textContent || "", ...(node.children || []).map(treeText)].join(" ");
}
function findTreeNode(node, predicate) {
  if (predicate(node)) return node;
  for (const child of node.children || []) {
    const found = findTreeNode(child, predicate);
    if (found) return found;
  }
  return null;
}

test("data review uses plain language and keeps raw event details collapsed", () => {
  const item = {
    anomaly_id: "ANOM-PRIVATE-TEST-ONLY",
    category: "invalid_step_reference",
    title: "执行步骤记录中的步骤编号无法识别",
    status: "pending",
    task_id: "TASK-PRIVATE-TEST-ONLY",
    task_title: "虚构演示任务：整理设备资料",
    step_id: "STEP-PRIVATE-TEST-ONLY",
    recorded_step_title: "整理供应商图纸",
    source: {folder: "step_events", filename: "evt_synthetic.json", sha256: "a".repeat(64)},
    source_present: true,
    reason: "invalid step_id",
    source_event: {action: "create", step_id: "bad-id", changes: {title: "整理供应商图纸"}},
    raw_excerpt: null,
    proposal: null,
    proposal_block_reason: "步骤编号格式不正确",
    can_authorize: false,
    can_apply: false,
    can_dismiss: true,
    user_guidance: {
      summary: "这条执行步骤记录中的步骤编号格式不正确，系统无法确认它属于哪一个步骤。",
      impact: "这条记录没有被应用，原始记录仍保留；系统不会猜测目标步骤，也不会覆盖任何现有步骤。",
      recommendation: "请核对关联任务中的步骤列表；若无法确认，选择确认保留，不写入。"
    }
  };
  const page = harness([], () => true, [], [item]);
  page.api.renderReviewDetail(item);
  const detail = page.el("review-detail");
  const allText = treeText(detail);
  assert.match(allText, /发生了什么/);
  assert.match(allText, /对工作台的影响/);
  assert.match(allText, /建议怎么处理/);
  assert.match(allText, /整理设备资料/);
  assert.match(allText, /确认保留，不写入/);
  assert.doesNotMatch(detail.children.map(child => child.textContent).join(" "), /ANOM-|SHA-256|invalid step_id|STEP-PRIVATE/);
  const technical = findTreeNode(detail, node => node.className === "review-technical");
  assert.ok(technical, "technical details are available for support");
  assert.ok(findTreeNode(technical, node => node.className === "review-code"),
    "raw JSON remains available inside collapsed technical details");
  assert.equal(findTreeNode(detail, node => node.tag === "button" && node.textContent === "确认并授权修复"), null,
    "an unidentifiable step reference must never offer automatic repair");
});



test("data review groups repeated records by task and step without merging their actions", async () => {
  const guidance = {
    summary: "这条记录需要核对。",
    impact: "系统没有自动修改任务或步骤。",
    recommendation: "请逐条核对。"
  };
  const reviews = [
    {
      anomaly_id: "ANOM-SYNTHETIC-1", category: "step_update_position",
      title: "步骤修改包含不允许的排序信息", status: "pending",
      task_id: "TASK-SYNTHETIC-1", task_title: "虚构采购任务",
      step_id: "STEP-SYNTHETIC-1", step_title: "收集供应商报价",
      source_event: {action: "update", timestamp: "2026-11-04T08:00:00Z"},
      source: {folder: "step_events"}, user_guidance: guidance
    },
    {
      anomaly_id: "ANOM-SYNTHETIC-2", category: "completion_confirmation_missing",
      title: "完成状态缺少用户明确确认", status: "pending",
      task_id: "TASK-SYNTHETIC-1", task_title: "虚构采购任务",
      step_id: "STEP-SYNTHETIC-1", step_title: "收集供应商报价",
      source_event: {action: "update", timestamp: "2026-11-04T08:01:00Z"},
      source: {folder: "step_events"}, user_guidance: guidance
    },
    {
      anomaly_id: "ANOM-SYNTHETIC-3", category: "step_update_position",
      title: "步骤修改包含不允许的排序信息", status: "pending",
      task_id: "TASK-SYNTHETIC-1", task_title: "虚构采购任务",
      step_id: "STEP-SYNTHETIC-2", step_title: "比较供应商报价",
      source_event: {action: "update", timestamp: "2026-11-04T08:02:00Z"},
      source: {folder: "step_events"}, user_guidance: guidance
    },
    {
      anomaly_id: "ANOM-SYNTHETIC-4", category: "invalid_event",
      title: "无法识别关联对象的异常记录", status: "pending",
      task_id: null, task_title: null, step_id: null,
      source_event: null, source: {folder: "workspace"}, user_guidance: guidance
    }
  ];
  const page = harness([], () => true, [], reviews);
  await page.api.loadReviews();
  const list = page.el("review-list");
  const groups = list.children.filter(node => node.className === "review-group");
  assert.equal(groups.length, 1, "only the two records for the same task and step should be grouped");
  assert.equal(list.children.length, 3, "other steps and unlinked records remain separate");
  assert.match(treeText(groups[0]), /虚构采购任务/);
  assert.match(treeText(groups[0]), /步骤：收集供应商报价/);
  assert.match(treeText(groups[0]), /共 2 条记录/);
  assert.match(treeText(groups[0]), /第 1 条/);
  assert.match(treeText(groups[0]), /第 2 条/);
  assert.equal(groups[0].children[1].children.length, 2,
    "each original anomaly remains independently selectable");
  assert.doesNotMatch(treeText(list), /TASK-SYNTHETIC|STEP-SYNTHETIC|ANOM-SYNTHETIC/);
});

test("data review summary cards count pending and authorized records separately", () => {
  const page = harness();
  page.api.renderReviewSummary({
    open_count: 5, pending: 2, stale: 1, failed: 0, conflict: 0,
    authorized: 2, applied: 3, dismissed: 4
  });
  const cards = page.el("review-summary").children;
  assert.equal(cards.length, 4);
  assert.equal(treeText(cards[0]).trim(), "3 待核对记录");
  assert.equal(treeText(cards[1]).trim(), "2 已授权待执行");
  assert.equal(treeText(cards[2]).trim(), "3 已修复并验证");
  assert.equal(treeText(cards[3]).trim(), "4 已确认保留");
});
