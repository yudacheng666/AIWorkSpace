// UI V2 shell and task-detail regression tests. Uses synthetic data only.
import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
import {test} from "node:test";
import vm from "node:vm";

const html = readFileSync(new URL("../web/index.html", import.meta.url), "utf8");
const scriptMatch = html.match(/<script>([\s\S]*?)<\/script>/);
assert.ok(scriptMatch, "the production page must contain its inline script");

function harness(tasks = [], confirm = () => true, projects = [], reviews = [], onPost = null) {
  const elements = new Map();
  const writes = [];
  function node(tag = "div") {
    const handlers = new Map();
    const item = {
      tag, handlers, children: [], textContent: "", className: "",
      disabled: false, hidden: false, multiple: false, selected: false,
      _value: "", attributes: new Map(),
      append(...children) { this.children.push(...children); },
      replaceChildren(...children) { this.children = children; },
      setAttribute(name, value) { this.attributes.set(name, String(value)); },
      getAttribute(name) { return this.attributes.get(name) ?? null; },
      contains(target) { return this === target || this.children.some(child => child.contains?.(target)); },
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
  const documentHandlers = new Map();
  const document = {
    activeElement: null,
    addEventListener(type, handler) {
      if (!documentHandlers.has(type)) documentHandlers.set(type, []);
      documentHandlers.get(type).push(handler);
    },
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
      const body = JSON.parse(options.body);
      writes.push({path, body});
      if (onPost) return onPost(path, body);
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
  const api = vm.runInNewContext(scriptMatch[1] + "\n;({setActivePage, openTaskDetail, closeTaskDetail, refresh, renderTaskList, setTaskView, moveTaskPeriod, resetTaskPeriod, isoDayParts, projectCounts, openProjectTasks, matchesQuery, stepRow, documentPanel, legacyDocumentPanel, taskSummaryRow, taskQuickField, updateTaskQuickField, renderNotificationList, loadNotifications, notificationIdFor, notificationRecommendation})", {
      document, window, navigator, fetch, Date, setInterval() {}
    }, {timeout: 2500});
  return {api, document, copied, writes,
    dispatchDocument(type, event) {
      for (const handler of documentHandlers.get(type) || []) handler(event);
    },
    el: id => document.getElementById(id)};
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

test("completed tasks stay at the end of the task list for every sort mode", async () => {
  const tasks = [
    {...sampleTask(),task_id:"TASK-DONE",title:"已完成任务",status:"done",due_date:"2026-11-01"},
    {...sampleTask(),task_id:"TASK-TODO",title:"待处理任务",status:"todo",due_date:"2026-11-08"},
    {...sampleTask(),task_id:"TASK-CONFLICT-DONE",title:"状态待核查任务",status:"done",
      conflict:true,due_date:"2026-11-02"},
    {...sampleTask(),task_id:"TASK-DOING",title:"进行中任务",status:"doing",due_date:"2026-11-03"}
  ];
  const page = harness(tasks);
  await page.api.refresh(true);
  assert.deepEqual(taskTitles(page),["待处理任务","状态待核查任务","进行中任务","已完成任务"],
    "completed tasks move to a final group; conflicted records are not treated as completed");

  for (const mode of ["due","priority","title"]) {
    page.el("task-sort").value = mode;
    page.api.renderTaskList();
    assert.equal(taskTitles(page).at(-1),"已完成任务",mode+" sort keeps completed tasks last");
  }

  page.el("task-sort").value = "project";
  page.api.renderTaskList();
  click(columnMenu(page,"due").actions.children[0]);
  click(columnMenu(page,"priority").actions.children[1]);
  assert.equal(taskTitles(page).at(-1),"已完成任务",
    "multi-column sort also keeps completed tasks last");
  assert.equal(page.writes.length,0,"sorting is display-only");
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

test("step document links are collapsed by default and remain editable when expanded", () => {
  const task = {...sampleTask(), revision: 8, document_links: [
    {title:"历史文档",url:"https://docs.google.com/document/d/SYNTHETIC/edit"}
  ]};
  const step = {step_id:"STEP-"+"B".repeat(32),revision:2,document_links: [
    {title:"步骤附件",url:"https://drive.google.com/file/d/SYNTHETIC_DOC/view"}
  ]};
  const page = harness([task]);
  const panel = page.api.documentPanel(task,step);
  assert.equal(panel.className,"doc-panel");
  const [toggle,body] = panel.children;
  assert.equal(toggle.tag,"button");
  assert.match(toggle.textContent,/1/);
  assert.equal(body.hidden,true,"step documents start collapsed");
  assert.equal(toggle.ariaExpanded,"false");
  assert.equal(body.children.filter(x=>x.className==="doc-row").length,1);
  assert.equal(body.children.filter(x=>x.className==="doc-add-form").length,1);
  toggle.handlers.get("click")[0]();
  assert.equal(body.hidden,false);
  assert.equal(toggle.ariaExpanded,"true");
  assert.match(toggle.className,/is-expanded/);
  toggle.handlers.get("click")[0]();
  assert.equal(body.hidden,true);

  const empty = page.api.documentPanel(task,{...step,document_links:[]});
  assert.equal(empty.children[1].hidden,true);
  assert.equal(empty.children[0].textContent,"添加文档");
  assert.equal(empty.children[1].children.filter(x=>x.className==="doc-row").length,0);
  assert.equal(empty.children[1].children.filter(x=>x.className==="doc-add-form").length,1);
  assert.doesNotMatch(JSON.stringify(empty),/未关联文档/,"steps without documents do not show an empty placeholder");
  const legacy = page.api.legacyDocumentPanel(task);
  assert.equal(legacy.className,"doc-panel legacy-doc-panel");
  assert.ok(JSON.stringify(legacy).includes("历史文档"));
  assert.equal(legacy.children.filter(x=>x.className==="doc-add-form").length,0);
  assert.match(html,/function legacyDocumentPanel\(task\)/);
  assert.doesNotMatch(html,/card\.append\(top, form, stepPanel\(task\), documentPanel\(task\)/);
  assert.equal(page.writes.length,0);
});

test("task title opens detail while the task ID below it copies independently", async () => {
  const task = {...sampleTask(),display_id:"T-261104-ABCDEF123456"};
  const page = harness([task]);
  await page.api.refresh(true);
  const summary = taskRows(page)[0];
  const main = summary.children[0];
  const title = main.children[0];
  const id = main.children[1];
  const feedback = main.children[2];
  assert.equal(title.tag,"button");
  assert.equal(title.className,"task-summary-title task-summary-title-open");
  title.handlers.get("click")[0]();
  assert.equal(page.el("task-detail-drawer").hidden,false);
  assert.equal(page.el("task-detail-title").textContent,task.title);
  assert.equal(page.api.closeTaskDetail(),true);
  assert.equal(page.el("task-detail-content").children.length,0);
  assert.equal(id.tag,"button");
  assert.equal(id.className,"task-summary-id task-summary-id-copy");
  await id.handlers.get("click")[0]();
  assert.deepEqual(page.copied,[task.display_id]);
  assert.equal(feedback.textContent,"已复制");
  assert.equal(feedback.hidden,false);
  assert.equal(page.el("task-detail-drawer").hidden,true,
    "copying the list ID must not open the task detail");
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

test("notification inbox shows stable message IDs, readable summaries and no repair controls", async () => {
  const guidance = {
    summary: "这条执行步骤记录中的步骤编号无法识别，系统不能确定它属于哪一个步骤。",
    impact: "这条记录没有被应用，原始记录仍保留；系统不会猜测目标步骤，也不会覆盖现有步骤。"
  };
  const reviews = [
    {
      anomaly_id: "ANOM-" + "A".repeat(32),
      category: "invalid_step_reference",
      title: "执行步骤记录中的步骤编号无法识别",
      status: "pending",
      task_id: "TASK-PRIVATE-TEST-ONLY",
      task_title: "虚构演示任务：整理设备资料",
      step_id: "STEP-PRIVATE-TEST-ONLY",
      recorded_step_title: "整理供应商图纸",
      source: {folder: "step_events", filename: "evt_private.json", sha256: "a".repeat(64)},
      reason: "invalid step_id PRIVATE_VALIDATOR_DETAIL",
      source_event: {action: "create", timestamp: "2026-11-04T08:00:00Z", raw_secret: "PRIVATE_RAW_JSON"},
      proposal: {private_proposal: "PRIVATE_PROPOSAL"},
      user_guidance: guidance
    },
    {
      anomaly_id: "ANOM-" + "B".repeat(32),
      category: "semantic_conflict",
      title: "任务数据存在版本冲突",
      status: "conflict",
      task_id: null,
      source: {folder: "workspace"},
      source_event: {timestamp: "2026-11-04T09:00:00Z"},
      user_guidance: {summary: "任务或步骤的数据版本存在差异，系统已暂停自动处理。"}
    }
  ];
  const page = harness([], () => true, [], reviews);
  await page.api.loadNotifications();
  const list = page.el("review-list");
  assert.equal(list.children.length, 2, "each original anomaly is shown as its own message");
  assert.match(treeText(list.children[0]), /任务数据存在版本冲突/,
    "newest messages appear first");
  assert.match(treeText(list.children[0]), /MSG-261104-B{12}/);
  assert.match(treeText(list.children[1]), /MSG-261104-A{12}/);
  assert.match(treeText(list.children[1]), /虚构演示任务：整理设备资料/);
  assert.match(treeText(list.children[1]), /步骤记录异常/);
  assert.match(treeText(list.children[1]), /待关注/);
  assert.doesNotMatch(treeText(list), /ANOM-|TASK-PRIVATE|STEP-PRIVATE|SHA-256|PRIVATE_RAW_JSON|PRIVATE_PROPOSAL|PRIVATE_VALIDATOR_DETAIL/);
  assert.equal(findTreeNode(list, node => node.tag === "button"), null,
    "the mailbox must not expose authorize, apply or dismiss controls");
  const details = findTreeNode(list.children[1], node => node.tag === "details");
  assert.ok(details, "read-only message details can be expanded");
  assert.notEqual(details.open, true, "message details are collapsed by default");
  assert.match(treeText(details), /影响：/);
  assert.match(treeText(details), /建议：/);
  assert.match(treeText(details), /不会猜测或自动改绑/);
  assert.equal(page.writes.length, 0, "loading notifications must not write business or review events");
});

test("notification message IDs remain stable across refreshes and the inbox is read-only", async () => {
  const item = {
    anomaly_id: "ANOM-" + "C".repeat(32),
    category: "step_update_position",
    title: "步骤记录需要留意",
    status: "pending",
    source_event: {timestamp: "2026-11-04T10:00:00Z"},
    source: {folder: "step_events"},
    user_guidance: {summary: "系统发现一条需要留意的步骤记录。"}
  };
  const page = harness([], () => true, [], [item]);
  await page.api.loadNotifications();
  const first = treeText(page.el("review-list"));
  await page.api.loadNotifications();
  const second = treeText(page.el("review-list"));
  assert.equal(first, second, "message IDs and contents are deterministic across refreshes");
  assert.equal(page.api.notificationIdFor(item), "MSG-261104-" + "C".repeat(12));
  assert.equal(page.writes.length, 0);
  assert.equal(page.el("review-total").textContent, "1 条消息");
  assert.equal(page.el("nav-reviews").title, "1 条待关注消息");
});


test("notification IDs expand to the full stable hash if short IDs collide", async () => {
  const prefix = "D".repeat(12);
  const reviews = [
    {anomaly_id: "ANOM-" + prefix + "A".repeat(20), category: "invalid_event",
      title: "第一条虚构提醒", status: "pending",
      source_event: {timestamp: "2026-11-04T10:00:00Z"}, source: {folder: "events"}},
    {anomaly_id: "ANOM-" + prefix + "B".repeat(20), category: "invalid_event",
      title: "第二条虚构提醒", status: "pending",
      source_event: {timestamp: "2026-11-04T10:01:00Z"}, source: {folder: "events"}}
  ];
  const page = harness([], () => true, [], reviews);
  await page.api.loadNotifications();
  const ids = page.el("review-list").children.map(node => {
    const match = treeText(node).match(/MSG-[A-Z0-9-]+/);
    return match?.[0];
  });
  assert.equal(new Set(ids).size, 2, "collision fallback must keep visible message IDs unique");
  assert.ok(ids.every(id => id.length === "MSG-261104-".length + 32));
});

test("notification inbox has a simple empty state and no exception statistics", async () => {
  const page = harness();
  await page.api.loadNotifications();
  assert.equal(page.el("review-list").children.length, 1);
  assert.match(treeText(page.el("review-list")), /目前没有新的系统消息/);
  assert.equal(page.el("review-total").textContent, "0 条消息");
  assert.equal(page.el("review-summary").children.length, 0,
    "the old technical exception statistic cards are removed");
  assert.equal(page.el("review-detail").children.length, 0,
    "the old complex two-panel detail layout is removed");
});

test("navigation presents a notification mailbox instead of a repair center", () => {
  assert.match(html, /id="nav-reviews"[\s\S]*?通知信箱/);
  assert.match(html, /<h1>通知信箱<\/h1>/);
  assert.match(html, /id="review-refresh">刷新消息/);
  assert.doesNotMatch(html, /数据异常处理|打开数据核查|确认并授权修复|执行已授权修复|确认保留，不写入/);
});

function taskQuickControl(row, field) {
  const editor = row.children.find(item => item.className?.includes("task-quick-editor--" + field));
  assert.ok(editor, "missing quick edit field " + field);
  return {editor, trigger:editor.children[0], menu:editor.children[1], feedback:editor.children[2]};
}
function chooseQuick(editor, label) {
  const option = editor.menu.children.find(item => item.textContent === label);
  assert.ok(option, "missing quick option " + label);
  return option.handlers.get("click")[0]();
}
const successReply = () => ({ok:true, status:200, json:async()=>({saved:true})});

test("task-list status and priority labels are accessible buttons with one-click menus", async () => {
  const page = harness([sampleTask()]);
  await page.api.refresh(true);
  const row = taskRows(page)[0];
  const status = taskQuickControl(row, "status");
  const priority = taskQuickControl(row, "priority");
  assert.equal(status.trigger.tag, "button");
  assert.equal(priority.trigger.tag, "button");
  assert.match(status.trigger.className, /status-pill.*task-quick-trigger/);
  assert.match(priority.trigger.className, /priority-pill.*task-quick-trigger/);
  assert.equal(status.trigger.textContent, "进行中");
  assert.equal(priority.trigger.textContent, "高");
  assert.equal(status.menu.hidden, true);
  status.trigger.handlers.get("click")[0]();
  assert.equal(status.menu.hidden, false);
  assert.deepEqual(status.menu.children.map(x => x.textContent), ["待处理", "进行中", "受阻", "已完成"]);
  priority.trigger.handlers.get("click")[0]();
  assert.equal(status.menu.hidden, true, "opening a second field closes the previous menu");
  assert.equal(priority.menu.hidden, false);
  page.dispatchDocument("keydown", {key:"Escape"});
  assert.equal(priority.menu.hidden, true);
  status.trigger.handlers.get("click")[0]();
  page.dispatchDocument("click", {target:row.children[0]});
  assert.equal(status.menu.hidden, true, "clicking outside closes a menu");
  assert.equal(page.el("task-detail-content").children.length, 0, "quick controls do not open task details");
  assert.equal(page.writes.length, 0, "opening/closing menus is read-only");
});

test("quick status and priority updates write only the changed field and the exact revision", async () => {
  const task = sampleTask();
  const page = harness([task], () => true, [], [], async (_path, body) => {
    Object.assign(task, {
      ...(body.status ? {status:body.status, manual_status:body.status} : {}),
      ...(body.priority ? {priority:body.priority} : {}),
      revision: task.revision + 1
    });
    return successReply();
  });
  await page.api.refresh(true);
  let row = taskRows(page)[0];
  let status = taskQuickControl(row,"status");
  status.trigger.handlers.get("click")[0]();
  await chooseQuick(status, "受阻");
  assert.equal(page.writes.length, 1);
  assert.equal(page.writes[0].path, "/api/tasks/TASK-UI-V2-001/update");
  assert.deepEqual(page.writes[0].body, {title:task.title, revision:1, status:"blocked"});
  assert.equal(taskQuickControl(taskRows(page)[0],"status").trigger.textContent, "受阻");
  row = taskRows(page)[0];
  const priority = taskQuickControl(row, "priority");
  priority.trigger.handlers.get("click")[0]();
  await chooseQuick(priority,"紧急");
  assert.deepEqual(page.writes[1].body, {title:task.title, revision:2, priority:"urgent"});
  assert.equal(page.writes.length, 2);
  assert.equal(taskQuickControl(taskRows(page)[0],"priority").trigger.textContent,"紧急");
  assert.equal(task.status,"blocked", "priority updates must not overwrite task status");
  assert.equal(page.el("task-detail-drawer").hidden,true);
  assert.equal(task.revision,3);
  assert.equal(taskQuickControl(taskRows(page)[0],"status").trigger.getAttribute("aria-expanded"),"false");
});

test("quick completion requires confirmation and can move tasks to completed-last group", async () => {
  const task = sampleTask();
  const later = {...sampleTask(), task_id:"TASK-UI-V2-002",title:"虚构未完成任务",revision:1};
  let approve = false, asks = 0;
  const page = harness([task,later], () => {asks++; return approve;}, [], [], async (_path, body) => {
    if (body.status) {task.status=body.status;task.manual_status=body.status;}
    task.revision++;
    return successReply();
  });
  await page.api.refresh(true);
  let status=taskQuickControl(taskRows(page)[0],"status");
  status.trigger.handlers.get("click")[0]();
  await chooseQuick(status,"已完成");
  assert.equal(asks,1);
  assert.equal(page.writes.length,0,"cancelled completion must not write");
  approve=true;
  status.trigger.handlers.get("click")[0]();
  await chooseQuick(status,"已完成");
  assert.equal(asks,2);
  assert.deepEqual(page.writes[0].body,
    {title:task.title,revision:1,status:"done",confirmed_done:true});
  assert.equal(taskRows(page).at(-1).children[0].children[0].textContent,task.title,
    "completed task stays last after refresh");
  const newStatus=taskQuickControl(taskRows(page).at(-1),"status");
  newStatus.trigger.handlers.get("click")[0]();
  await chooseQuick(newStatus,"待处理");
  assert.deepEqual(page.writes[1].body,
    {title:task.title,revision:2,status:"todo"},
    "reopening must not inherit completion confirmation");
});

test("quick controls preserve dirty drafts and refuse conflicts, incomplete rollups, same value, and busy writes", async () => {
  const task = sampleTask();
  const page = harness([task]);
  await page.api.refresh(true);
  const row=taskRows(page)[0];
  let priority=taskQuickControl(row,"priority");
  priority.trigger.handlers.get("click")[0]();
  await chooseQuick(priority,"高");
  assert.equal(page.writes.length,0,"selecting unchanged value must not create an event");

  page.api.openTaskDetail(task.task_id);
  const editor=page.el("task-detail-content").children[0];
  const form=editor.children.find(child=>child.className==="task-form");
  const title=form.children[0].children[0];
  title.value="未保存的虚构新标题";
  form.handlers.get("input")[0]();
  priority.trigger.handlers.get("click")[0]();
  await chooseQuick(priority,"紧急");
  assert.equal(page.writes.length,0);
  assert.match(priority.feedback.textContent,/未保存的草稿/);
  assert.equal(title.value,"未保存的虚构新标题");

  const conflicted={...task,task_id:"TASK-UI-V2-003",conflict:true};
  let status=taskQuickControl(page.api.taskSummaryRow(conflicted),"status");
  priority=taskQuickControl(page.api.taskSummaryRow(conflicted),"priority");
  assert.equal(status.trigger.disabled,true);
  assert.equal(priority.trigger.disabled,true);
  const unreliable={...task,status_rollup_incomplete:true};
  status=taskQuickControl(page.api.taskSummaryRow(unreliable),"status");
  priority=taskQuickControl(page.api.taskSummaryRow(unreliable),"priority");
  assert.equal(status.trigger.disabled,true,"incomplete parent/step rollup blocks status quick changes");
  assert.equal(priority.trigger.disabled,false,"priority may be changed separately");
});

test("quick status blocks 409 stale-revision writes and shows a local error without optimistic changes", async () => {
  const task=sampleTask();
  const page=harness([task],()=>true,[],[],async()=>({
    ok:false,status:409,json:async()=>({error:"task changed or has a conflict; refresh"})
  }));
  await page.api.refresh(true);
  const status=taskQuickControl(taskRows(page)[0],"status");
  status.trigger.handlers.get("click")[0]();
  await chooseQuick(status,"受阻");
  assert.equal(page.writes.length,1);
  assert.match(status.feedback.textContent,/已在别处更新或存在冲突/);
  assert.equal(status.trigger.textContent,"进行中");
  assert.equal(task.status,"doing");
  assert.equal(task.revision,1);
});
