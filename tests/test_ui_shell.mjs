// UI V2 shell and task-detail regression tests. Uses synthetic data only.
import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
import {test} from "node:test";
import vm from "node:vm";

const html = readFileSync(new URL("../web/index.html", import.meta.url), "utf8");
const scriptMatch = html.match(/<script>([\s\S]*?)<\/script>/);
assert.ok(scriptMatch, "the production page must contain its inline script");

function harness(tasks = [], confirm = () => true, projects = [], reviews = [], onPost = null, work = {}) {
  const elements = new Map();
  const writes = [];
  function node(tag = "div") {
    const handlers = new Map();
    const item = {
      tag, handlers, children: [], textContent: "", className: "",
      focus() {},
      disabled: false, hidden: false, multiple: false, selected: false, checked: false,
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
          "new-task-priority", "task-sort", "task-date-field", "calendar-granularity", "project-sort",
          "work-record-project", "work-record-task", "work-record-type", "work-filter-project",
          "work-inbox-project", "work-split-source", "work-stage-project", "work-summary-period", "work-summary-project", "work-summary-audience",
          "work-link-target", "work-link-relation", "work-action-source",
          "work-task-convert-source", "work-portfolio-project"]);
        elements.set(id, node(selects.has(id) ? "select" : "div"));
      }
      return elements.get(id);
    },
    createElement(tag) { return node(tag); }
  };
  const copied = [];
  const navigator = {clipboard: {writeText: async value => {copied.push(value);}}};
  const window = {confirm, alert() {}, addEventListener() {}};
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
    if (path === "/api/work-records") return {ok: true, json: async () => ({records: work.records || [], task_completions: work.task_completions || [], warnings: []})};
    if (path === "/api/work-archive") return {ok: true, json: async () => ({
      inbox:work.inbox || [], summaries:work.summaries || [], warnings:[]})};
    if (path.startsWith("/api/work-archive/analysis-context?")) return {
      ok:work.analysis_error ? false : true,json:async()=>work.analysis_error
        ? {error:work.analysis_error} : (work.analysis_context || {prompt:"来源分析说明",record_count:0,completion_count:0})};
    if (path.startsWith("/api/work-archive/portfolio-context?")) return {
      ok:work.portfolio_error ? false : true,json:async()=>work.portfolio_error
        ? {error:work.portfolio_error} : (work.portfolio_context || {prompt:"成果来源说明",record_count:0})};
    if (path.startsWith("/api/work-archive/preview?")) return {
      ok:true,json:async()=>work.preview || {period:"daily",period_start:"2026-11-05",
        period_end:"2026-11-05",project_id:null,body:"工作总结底稿",
        source_record_ids:[],source_completion_ids:[],record_count:0,completion_count:0}};
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
  const api = vm.runInNewContext(scriptMatch[1] + "\n;({setActivePage, openTaskDetail, closeTaskDetail, refresh, renderTaskList, setTaskView, moveTaskPeriod, resetTaskPeriod, isoDayParts, projectCounts, openProjectTasks, matchesQuery, stepRow, taskToStepPanel, documentPanel, legacyDocumentPanel, taskSummaryRow, taskQuickField, updateTaskQuickField, renderCalendarView, renderGanttView, scheduleItems, renderNotificationList, loadNotifications, notificationIdFor, notificationRecommendation, loadWorkRecords, renderWorkRecords, editWorkRecord, saveWorkRecord, workFormSnapshot, loadWorkArchive, saveWorkInbox, renderWorkInbox, generateWorkSummary, saveWorkSummary, workSummarySnapshot, editWorkSummary, renderWorkOutcomes, populateWorkLinkTargets, populateWorkActionSources, copyActionAnalysisPrompt, previewWorkActions, applyWorkAction, resetWorkActionForm, workActionSnapshot, taskConvertSnapshot, populateTaskRecordSources, convertibleStandaloneTask, progressPanel, recordBelongsTo, objectDescriptionPanel, summaryRecordRecommended, workRecordTypeLabel})", {
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
  const firstSummary = page.el("task-list-columns").children[0].children[0];
  assert.equal(firstSummary.children[0].className, "task-column-label");
  assert.equal(firstSummary.children[1].className, "task-column-caret");
  assert.equal(firstSummary.children[1].textContent, "▾");
  assert.equal(firstSummary.children[2].className, "task-column-indicator");
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
  assert.match(columnMenu(page,"due").header.children[0].children[2].textContent,/↑1/);
  assert.match(columnMenu(page,"priority").header.children[0].children[2].textContent,/↓2/);
  click(columnMenu(page,"priority").actions.children[3]);
  assert.deepEqual(taskTitles(page),["晚期紧急","无日期","晚期高","早期普通"]);
  assert.match(columnMenu(page,"priority").header.children[0].children[2].textContent,/↓1/);
  // Modifying the direction of an existing column must not change its precedence.
  click(columnMenu(page,"priority").actions.children[0]);
  assert.match(columnMenu(page,"priority").header.children[0].children[2].textContent,/↑1/);
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
  const before = columnMenu(page,"title").header.children[0].children[2].textContent;
  click(columnMenu(page,"title").actions.children[0]);
  assert.equal(columnMenu(page,"title").header.children[0].children[2].textContent,before);
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
  const del = actions.children[3];
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



test("step date controls save all three task-equivalent date fields at the step revision", async () => {
  const task = {...sampleTask(),revision:12,steps:[]};
  const step = {step_id:"STEP-"+"A".repeat(32),task_id:task.task_id,title:"日期步骤",
    status:"doing",revision:4,planned_date:"2026-11-06",due_date:null,
    follow_up_date:"2026-11-09",document_links:[]};
  task.steps=[step];
  const page=harness([task]);
  const line=page.api.stepRow(task,step,0,page.el("step-message"));
  const form=line.children[1].children.find(x=>x.className==="step-edit-form");
  const dates=form.children.find(x=>x.className==="step-date-fields");
  assert.ok(dates);
  assert.equal(dates.children.length,3);
  assert.deepEqual(dates.children.map(x=>x.children[0].type),["date","date","date"]);
  dates.children[0].children[0].value="2026-11-07";
  dates.children[1].children[0].value="2026-11-08";
  await form.handlers.get("submit")[0]({preventDefault(){}});
  assert.equal(page.writes.length,1);
  assert.equal(page.writes[0].path,"/api/tasks/"+task.task_id+"/steps/"+step.step_id+"/update");
  assert.deepEqual(page.writes[0].body,{
    revision:4,planned_date:"2026-11-07",due_date:"2026-11-08"
  });
});

test("calendar and Gantt include step schedule items with the same date semantics as tasks", () => {
  const now=new Date();
  const today=[now.getFullYear(),String(now.getMonth()+1).padStart(2,"0"),
    String(now.getDate()).padStart(2,"0")].join("-");
  const task={...sampleTask(),due_date:today,planned_date:today,steps:[]};
  const step={step_id:"STEP-"+"B".repeat(32),task_id:task.task_id,title:"排期步骤",
    status:"doing",revision:1,due_date:today,planned_date:today,follow_up_date:today,
    document_links:[]};
  task.steps=[step];
  const page=harness([task]);
  const items=page.api.scheduleItems([task]);
  assert.deepEqual(Array.from(items, x=>x.kind),["task","step"]);
  const calendar=page.el("calendar-test");
  page.api.renderCalendarView([task],calendar);
  const grid=calendar.children[2];
  const stepButton=grid.children.flatMap(day=>day.children).find(x=>x.title?.includes(step.step_id));
  assert.ok(stepButton,"dated step appears in the selected calendar date field");
  assert.match(stepButton.textContent,/排期步骤/);
  const gantt=page.el("gantt-test");
  page.api.renderGanttView([task],gantt);
  const table=gantt.children[1].children[0];
  assert.equal(table.children.length,3,"header plus task and step rows");
  assert.match(table.children[2].className,/gantt-step-row/);
  assert.match(table.children[2].children[0].children[0].textContent,/排期步骤/);
});

test("task-to-step panel requires an eligible destination and posts both exact revisions", async () => {
  const parent={...sampleTask(),task_id:"TASK-PARENT-DEST",title:"目标父任务",steps:[],
    step_order_revision:2,manual_status:"todo"};
  const source={...sampleTask(),task_id:"TASK-LEAF-SOURCE",title:"待移动末级任务",
    revision:7,steps:[],child_task_ids:[],manual_status:"doing"};
  const page=harness([parent,source]);
  await page.api.refresh(true);
  const panel=page.api.taskToStepPanel(source);
  const select=panel.children[1].children[0];
  const button=panel.children[1].children[1];
  assert.equal(button.disabled,false);
  select.value=parent.task_id;
  await button.handlers.get("click")[0]();
  assert.equal(page.writes.length,1);
  assert.equal(page.writes[0].path,"/api/tasks/"+source.task_id+"/convert-to-step");
  assert.deepEqual(page.writes[0].body,{
    revision:7,target_parent_task_id:parent.task_id,
    target_step_order_revision:2,confirmed_move:true
  });
  const complex={...source,task_id:"TASK-COMPLEX",steps:[{
    step_id:"STEP-"+"C".repeat(32),title:"仍未完成的步骤"
  }]};
  const blocked=page.api.taskToStepPanel(complex);
  assert.equal(blocked.children[1].children[1].disabled,true);
  assert.match(blocked.children[2].textContent,/没有子任务、没有执行步骤/);
});

test("step-to-task action is explicit, preserves the step revision and requires confirmation", async () => {
  const task={...sampleTask(),steps:[]};
  const step={step_id:"STEP-"+"D".repeat(32),task_id:task.task_id,
    title:"升级步骤",status:"todo",revision:3,document_links:[]};
  task.steps=[step];
  const page=harness([task]);
  const line=page.api.stepRow(task,step,0,page.el("step-message"));
  const convert=line.children[2].children.find(x=>x.className==="step-convert");
  assert.equal(convert.textContent,"转为任务");
  await convert.handlers.get("click")[0]();
  assert.equal(page.writes.length,1);
  assert.equal(page.writes[0].path,"/api/tasks/"+task.task_id+"/steps/"+step.step_id+"/convert-to-task");
  assert.deepEqual(page.writes[0].body,{revision:3,confirmed_move:true});
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
  assert.equal(page.el("task-detail-drawer").hidden,true);
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
 const tasks=[{...sampleTask(),task_id:"A",project_id:p,related_project_ids:[p],due_date:"2099-12-31"},
 {...sampleTask(),task_id:"B",project_id:"OTHER",related_project_ids:[p],status:"blocked",due_date:"2099-12-31"}];
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
    summary: "系统无法确认这项操作对应任务中的哪一步，因此没有执行。",
    impact: "这项操作没有生效；任务“虚构演示任务：整理设备资料”中的现有步骤没有因此改变。",
    recommendation: "请打开任务“虚构演示任务：整理设备资料”的详情，查看执行步骤。若已有同名步骤，不要重复添加；若确实没有且仍需要，请通过任务详情正常新增。"
  };
  const reviews = [
    {
      anomaly_id: "ANOM-" + "A".repeat(32),
      category: "invalid_step_reference",
      title: "步骤操作未能确认目标",
      status: "pending",
      task_id: "TASK-PRIVATE-TEST-ONLY",
      task_title: "虚构演示任务：整理设备资料",
      step_id: "STEP-PRIVATE-TEST-ONLY",
      recorded_step_title: "整理供应商图纸",
      source: {folder: "step_events", filename: "evt_private.json", sha256: "a".repeat(64)},
      reason: "invalid step_id PRIVATE_VALIDATOR_DETAIL",
      source_event: {action: "create", timestamp: "2026-11-04T08:00:00Z", changes: {title: "整理供应商图纸"}, raw_secret: "PRIVATE_RAW_JSON"},
      proposal: null,
      proposal_block_reason: "记录引用的步骤编号无法识别。",
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
  assert.match(treeText(list.children[1]), /步骤操作异常/);
  assert.match(treeText(list.children[1]), /收到的操作：新增步骤「整理供应商图纸」/);
  assert.match(treeText(list.children[1]), /待关注/);
  assert.doesNotMatch(treeText(list), /ANOM-|TASK-PRIVATE|STEP-PRIVATE|SHA-256|PRIVATE_RAW_JSON|PRIVATE_PROPOSAL|PRIVATE_VALIDATOR_DETAIL/);
  const copyOnly = findTreeNode(list, node => node.tag === "button");
  assert.ok(copyOnly, "the mailbox must offer a safe ChatGPT handoff");
  assert.equal(copyOnly.textContent, "复制给 ChatGPT 核查",
    "the only mailbox action is a clipboard copy, not a data mutation");
  const details = findTreeNode(list.children[1], node => node.tag === "details");
  assert.ok(details, "read-only message details can be expanded");
  assert.notEqual(details.open, true, "message details are collapsed by default");
  assert.match(treeText(details), /对任务的影响：/);
  assert.match(treeText(details), /你可以怎么做：/);
  assert.match(treeText(details), /不要重复添加/);
  assert.doesNotMatch(treeText(list.children[1]), /这条记录|原始文件|原始记录|步骤编号/);
  const detailContent = findTreeNode(details, node => node.className === "inbox-message-detail-content");
  assert.ok(detailContent);
  assert.equal(detailContent.children.length, 2,
    "blocked messages show impact and one recommendation, not a duplicated block-reason paragraph");
  assert.equal((treeText(detailContent).match(/不要重复添加/g) || []).length, 1);
  assert.equal(page.writes.length, 0, "loading notifications must not write business or review events");
});



test("notification defer action explains the result without file jargon", async () => {
  const item = {
    anomaly_id: "ANOM-" + "C".repeat(32),
    category: "invalid_step_reference",
    title: "步骤操作未能确认目标",
    status: "pending",
    task_id: "TASK-SYNTHETIC-EXAMPLE",
    task_title: "虚构任务：整理资料",
    recorded_step_title: "虚构步骤：整理附件",
    action: "update",
    source_event: {action: "update"},
    source: {folder: "step_events", filename: "synthetic.json", sha256: "c".repeat(64)},
    source_present: true,
    can_dismiss: true,
    user_guidance: {
      summary: "系统无法确认这项操作对应任务中的哪一步，因此没有执行。",
      impact: "这项操作没有生效；现有任务和步骤保持不变。",
      recommendation: "请先核对步骤列表。"
    }
  };
  const page = harness([], () => true, [], [item]);
  await page.api.loadNotifications();
  const card = page.el("review-list").children[0];
  const defer = findTreeNode(card, node => node.className === "inbox-defer");
  assert.ok(defer);
  assert.equal(defer.children[0].textContent, "暂不处理这项操作");
  assert.match(treeText(defer), /只保存你的决定和备注/);
  assert.match(treeText(defer), /现有任务和步骤保持不变/);
  assert.doesNotMatch(treeText(defer), /原始文件|原始记录|底层问题/);
  const confirm = findTreeNode(defer, node => node.tag === "button");
  assert.equal(confirm.textContent, "确认暂不处理");
  assert.equal(page.writes.length, 0, "opening the defer panel must not write audit or business data");
});

test("task detail alignment and action buttons use the workspace visual system", () => {
  assert.match(html, /\.task-column-head > summary\s*\{[^}]*justify-content:flex-start/s);
  assert.match(html, /\.task-column-caret\s*\{[^}]*flex:0 0 auto/s);
  assert.match(html, /\.task-detail-content \.task-form\s*\{[^}]*align-items:\s*start/s);
  assert.match(html, /\.warning-open\s*\{[^}]*display:\s*inline-flex/s);
  assert.match(html, /\.recurrence-controls \.recurrence-toggle\s*\{[^}]*display:\s*inline-flex/s);
  assert.match(html, /"recurrence-toggle " \+ \(rule\.enabled \?/);
});

test("concurrent-write messages explain affected fields and copy a read-only handoff", async () => {
  const item = {
    anomaly_id: "ANOM-" + "E".repeat(32),
    category: "semantic_conflict",
    title: "同一任务的多次修改发生版本冲突",
    status: "pending",
    task_id: "TASK-SYNTHETIC-EXAMPLE",
    task_title: "虚构资料整理任务",
    concurrent_task_edit: true,
    source: {folder: "workspace"},
    reason: "TASK-SYNTHETIC-EXAMPLE: conflicting edits of revision 4",
    related_edits: [
      {event_id: "synthetic-1", changes: {priority: "high"}},
      {event_id: "synthetic-2", changes: {title: "虚构标题新版", due_date: "2026-11-05"}}
    ],
    user_guidance: {summary: "两条修改使用了同一个旧版本。", impact: "原始记录仍保留。", recommendation: "点击复制给 ChatGPT 核查。"}
  };
  const page = harness([], () => true, [], [item]);
  await page.api.loadNotifications();
  const list = page.el("review-list");
  assert.match(treeText(list), /虚构资料整理任务/);
  assert.match(treeText(list), /2 条修改发生了版本冲突/);
  assert.match(treeText(list), /优先级、任务名称、截止日期/);
  assert.match(treeText(list), /点击复制给 ChatGPT 核查/);
  const button = findTreeNode(list, node => node.tag === "button");
  assert.equal(button?.textContent, "复制给 ChatGPT 核查");
  for (const handler of button.handlers.get("click") || []) await handler();
  assert.equal(page.copied.length, 1);
  assert.match(page.copied[0], /TASK-SYNTHETIC-EXAMPLE/);
  assert.match(page.copied[0], /虚构标题新版/);
  assert.match(page.copied[0], /不要直接修改任何数据/);
  assert.equal(page.writes.length, 0, "clipboard handoff must never write business data");
});

test("successfully auto-merged edits are informational and never demand ChatGPT", async () => {
  const item = {
    anomaly_id: "ANOM-" + "F".repeat(32), category: "auto_merged",
    title: "已自动整合任务的独立修改", status: "auto_merged",
    task_id: "TASK-EXAMPLE", task_title: "虚构：资料任务",
    source_event: {timestamp: "2026-11-05T10:01:00Z"},
    source: {folder: "workspace_auto_merge"},
    user_guidance: {
      summary: "2 次修改涉及不同内容（优先级、截止日期），已自动整合，无需操作。",
      impact: "全部原始事件保持不变。", recommendation: "无需处理。"
    }
  };
  const page = harness([], () => true, [], [item]);
  await page.api.loadNotifications();
  const list = page.el("review-list");
  assert.match(treeText(list), /自动整合/);
  assert.match(treeText(list), /优先级、截止日期/);
  assert.match(treeText(list), /无需操作/);
  assert.equal(findTreeNode(list, node => node.tag === "button"), null,
    "auto-merged notices must not offer repair or copy controls");
  assert.equal(page.el("nav-reviews").title, "系统通知和数据提醒",
    "resolved notices must not create an attention-count badge");
  assert.equal(page.writes.length, 0);
});

test("bulk ChatGPT handoff copies every visible message in one read-only bundle", async () => {
  const reviews = [
    {
      anomaly_id: "ANOM-" + "1".repeat(32), category: "invalid_step_reference",
      title: "虚构：步骤编号无法识别", status: "pending",
      task_id: "TASK-SYNTHETIC-001", task_title: "虚构：设备资料任务",
      step_id: "STEP-BAD", recorded_step_title: "虚构：图纸整理",
      source: {folder: "step_events", filename: "evt_synthetic_invalid_step.json",
        sha256: "a".repeat(64)},
      event_id: "synthetic-invalid-step", source_present: true,
      source_event: {action: "update", timestamp: "2026-11-05T10:00:00Z",
        base_revision: 1, changes: {title: "虚构：图纸整理"}},
      user_guidance: {summary: "步骤编号无法识别。", impact: "原始记录保留。",
        recommendation: "请核对关联任务。"}
    },
    {
      anomaly_id: "ANOM-" + "2".repeat(32), category: "auto_merged",
      title: "虚构：两次修改已自动整合", status: "auto_merged",
      task_id: "TASK-SYNTHETIC-002", task_title: "虚构：另一个任务",
      source: {folder: "workspace_auto_merge"},
      user_guidance: {summary: "已自动整合，无需操作。", impact: "原始事件保留。",
        recommendation: "无需处理。"}
    }
  ];
  const page = harness([], () => true, [], reviews);
  await page.api.loadNotifications();
  const button = page.el("review-copy-all");
  assert.equal(button.disabled, false);
  assert.match(html, /id="review-copy-all" class="inbox-copy-all" disabled>复制全部消息给 ChatGPT 核查/);
  await button.handlers.get("click")[0]();
  assert.equal(page.copied.length, 1);
  const copied = page.copied[0];
  assert.match(copied, /message_count": 2/);
  assert.match(copied, /虚构：步骤编号无法识别/);
  assert.match(copied, /虚构：两次修改已自动整合/);
  assert.match(copied, /evt_synthetic_invalid_step.json/);
  assert.match(copied, /TASK-SYNTHETIC-001/);
  assert.match(copied, /请逐条核查/);
  assert.match(copied, /不要直接修改任何数据文件、删除或覆盖此前收到的变更信息/);
  assert.equal(page.writes.length, 0, "bulk clipboard handoff must not create review or business writes");
});

test("notification inbox exposes the full authorize then apply repair path", async () => {
  const item = {
    anomaly_id: "ANOM-" + "3".repeat(32), category: "step_update_position",
    title: "虚构：步骤修改需要核对", status: "pending",
    task_id: "TASK-SYNTHETIC-003", task_title: "虚构：设备资料任务",
    step_id: "STEP-" + "4".repeat(32), step_title: "虚构：整理图纸",
    source: {folder: "step_events", filename: "evt_synthetic_step_position.json",
      sha256: "c".repeat(64)},
    source_present: true, can_authorize: true, can_apply: false, can_dismiss: true,
    proposal: {
      target: {task_id: "TASK-SYNTHETIC-003", task_title: "虚构：设备资料任务",
        step_id: "STEP-" + "4".repeat(32), step_title: "虚构：整理图纸"},
      event: {action: "update", changes: {title: "虚构：整理并归档图纸"}},
      proposal_sha256: "d".repeat(64), requires_completion_confirmation: true,
      explanation: "按当前步骤版本重新生成合法更新。"
    },
    user_guidance: {summary: "步骤修改需要核对。", impact: "原始事件保留。",
      recommendation: "核对后再授权。"}
  };
  const page = harness([], () => true, [], [item], async (path, body) => {
    if (path.endsWith("/authorize")) {
      item.status = "authorized";
      item.can_authorize = false;
      item.can_apply = true;
      item.authorization_event_id = "review-auth-synthetic";
      return {ok:true,json:async()=>({saved:true,status:"authorized"})};
    }
    if (path.endsWith("/apply")) {
      item.status = "applied";
      item.can_apply = false;
      item.can_dismiss = false;
      return {ok:true,json:async()=>({saved:true,status:"applied"})};
    }
    throw new Error("unexpected review action " + path);
  });
  await page.api.loadNotifications();
  let card = page.el("review-list").children[0];
  assert.match(treeText(card), /虚构：整理并归档图纸/);
  assert.match(treeText(card), /我已核对上方的目标和修改/);
  assert.match(treeText(card), /我另外确认：这项任务\/步骤确实已经完成/);
  let checks = [];
  const collectChecks = node => {
    if (node.tag === "input" && node.type === "checkbox") checks.push(node);
    for (const child of node.children || []) collectChecks(child);
  };
  collectChecks(card);
  assert.equal(checks.length, 3, "proposal consent, completion consent and defer consent are separate");
  const authorize = findTreeNode(card, node => node.tag === "button" && node.textContent === "授权这项修复");
  assert.equal(authorize.disabled, true);
  checks[0].checked = true;
  checks[0].handlers.get("change")[0]();
  assert.equal(authorize.disabled, true, "completion cannot be inferred from general repair approval");
  checks[1].checked = true;
  checks[1].handlers.get("change")[0]();
  assert.equal(authorize.disabled, false);
  await authorize.handlers.get("click")[0]();
  assert.equal(page.writes.length, 1);
  assert.match(page.writes[0].path, /\/authorize$/);
  assert.equal(page.writes[0].body.source_sha256, "c".repeat(64));
  assert.equal(page.writes[0].body.proposal_sha256, "d".repeat(64));
  assert.equal(page.writes[0].body.confirm_completion, true);
  assert.equal(item.status, "authorized");
  card = page.el("review-list").children[0];
  assert.match(treeText(card), /虚构：整理并归档图纸/,
    "the approved repair preview must remain visible before execution");
  const apply = findTreeNode(card, node => node.tag === "button" && node.textContent === "执行修复");
  assert.ok(apply, "authorization must expose the separate execution step");
  await apply.handlers.get("click")[0]();
  assert.equal(page.writes.length, 2);
  assert.match(page.writes[1].path, /\/apply$/);
  assert.equal(page.writes[1].body.authorization_event_id, "review-auth-synthetic");
  assert.equal(page.writes[1].body.confirmed, true);
  assert.equal(item.status, "applied");
  assert.match(page.el("review-message").textContent, /修复已完成并核验/);
});

test("unsupported review can be explicitly recorded as keep-original without business write", async () => {
  const item = {
    anomaly_id: "ANOM-" + "5".repeat(32), category: "invalid_step_reference",
    title: "步骤操作未能确认目标", status: "pending",
    task_id: "TASK-SYNTHETIC-005", task_title: "虚构：步骤核对任务",
    source: {folder: "step_events", filename: "evt_synthetic_bad_step.json",
      sha256: "e".repeat(64)},
    source_present: true, can_authorize: false, can_apply: false, can_dismiss: true,
    proposal: null,
    user_guidance: {summary: "系统无法确认这项操作对应哪一步，因此没有执行。", impact: "现有任务和步骤保持不变。",
      recommendation: "请先核对任务详情中的步骤列表。"}
  };
  const page = harness([], () => true, [], [item], async (path, body) => {
    item.status = "dismissed";
    item.can_dismiss = false;
    return {ok:true,json:async()=>({saved:true,status:"dismissed"})};
  });
  await page.api.loadNotifications();
  const card = page.el("review-list").children[0];
  const defer = findTreeNode(card, node => node.tag === "details" && node.className === "inbox-defer");
  assert.ok(defer);
  const textarea = findTreeNode(defer, node => node.tag === "textarea");
  const consent = findTreeNode(defer, node => node.tag === "input" && node.type === "checkbox");
  const button = findTreeNode(defer, node => node.tag === "button");
  assert.equal(button.textContent, "确认暂不处理");
  assert.equal(button.disabled, true);
  textarea.value = "已核对现有步骤，无法确认要修改哪一步，决定暂不处理。";
  textarea.handlers.get("input")[0]();
  assert.equal(button.disabled, true, "a reason alone is not enough");
  consent.checked = true;
  consent.handlers.get("change")[0]();
  assert.equal(button.disabled, false);
  await button.handlers.get("click")[0]();
  assert.equal(page.writes.length, 1);
  assert.match(page.writes[0].path, /\/dismiss$/);
  assert.equal(page.writes[0].body.note, textarea.value);
  assert.equal(page.writes[0].body.confirmed, true);
  assert.equal(item.status, "dismissed");
  assert.equal(page.writes.length, 1, "only the review decision is written, not a task/step event");
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
  assert.match(html, /id="review-copy-all"/);
  assert.match(html, /复制全部消息给 ChatGPT 核查/);
  assert.match(html, /授权这项修复/);
  assert.match(html, /执行修复/);
  assert.match(html, /确认暂不处理/);
  assert.doesNotMatch(html, /数据异常处理|打开数据核查/);
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
  assert.equal(page.el("task-detail-content").children.length,0);
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


test("derived parent status menu permits confirmed completion but no manual override", async () => {
  const parent = {...sampleTask(), manual_status:"todo", status_source:"children",
    child_task_ids:["TASK-SYNTHETIC-CHILD-1"]};
  let approved = false;
  let confirms = 0;
  const page = harness([parent], () => {confirms++; return approved;}, [], [],
    async (_path, body) => {
      if (body.status === "done") {
        parent.manual_status = "done";
        parent.status_source = "user_confirmed";
        parent.status = "done";
      }
      parent.revision += 1;
      return successReply();
    });
  await page.api.refresh(true);
  const original = taskQuickControl(taskRows(page)[0], "status");
  original.trigger.handlers.get("click")[0]();
  assert.match(original.trigger.title, /下级进度自动计算/);
  assert.equal(original.menu.children.length, 2, "hint plus one deliberate completion action");
  assert.match(original.menu.children[0].textContent, /不支持直接覆盖/);
  assert.equal(original.menu.children[1].textContent, "确认完成任务");
  const blocked = await page.api.updateTaskQuickField(parent, "status", "blocked", original.feedback);
  assert.equal(blocked, false, "even programmatic attempts cannot override a derived parent");
  assert.match(original.feedback.textContent, /只能确认完成或重新打开/);
  assert.equal(page.writes.length, 0);
  await chooseQuick(original, "确认完成任务");
  assert.equal(confirms, 1);
  assert.equal(page.writes.length, 0, "declined completion cannot write");
  approved = true;
  original.trigger.handlers.get("click")[0]();
  await chooseQuick(original, "确认完成任务");
  assert.equal(confirms, 2);
  assert.deepEqual(page.writes[0].body, {
    title:parent.title, revision:1, status:"done", confirmed_done:true
  });
  assert.equal(parent.status, "done");
  assert.equal(parent.manual_status, "done");
  const completed = taskQuickControl(taskRows(page)[0], "status");
  completed.trigger.handlers.get("click")[0]();
  assert.equal(completed.menu.children[1].textContent, "重新打开（恢复自动联动）");
});

test("confirmed parent reopens with one explicit action and immediately resumes derived status", async () => {
  const parent = {...sampleTask(),status:"done",manual_status:"done",
    status_source:"user_confirmed", child_task_ids:["TASK-SYNTHETIC-CHILD-2"],
    revision:3, priority:"normal"};
  let allow = false;
  let confirms = 0;
  const page = harness([parent], () => {confirms++; return allow;}, [], [],
    async (_path, body) => {
      if (body.status === "todo") {
        parent.manual_status = "todo";
        parent.status = "blocked"; // Simulated child is blocked; server rollup wins.
        parent.status_source = "children";
      } else if (body.priority) parent.priority=body.priority;
      parent.revision += 1;
      return successReply();
    });
  await page.api.refresh(true);
  const status = taskQuickControl(taskRows(page)[0],"status");
  status.trigger.handlers.get("click")[0]();
  assert.equal(status.menu.children.length,2);
  assert.match(status.menu.children[0].textContent,/重新打开后/);
  assert.equal(status.menu.children[1].textContent,"重新打开（恢复自动联动）");
  await chooseQuick(status,"重新打开（恢复自动联动）");
  assert.equal(confirms,1);
  assert.equal(page.writes.length,0,"declined reopen must not create an event");
  allow=true;
  status.trigger.handlers.get("click")[0]();
  await chooseQuick(status,"重新打开（恢复自动联动）");
  assert.equal(confirms,2);
  assert.deepEqual(page.writes[0].body,{
    title:parent.title,revision:3,status:"todo"
  },"reopening saves manual todo without a completion marker");
  assert.equal(parent.status,"blocked","effective status is recalculated from child");
  assert.equal(parent.manual_status,"todo");
  assert.equal(taskQuickControl(taskRows(page)[0],"status").trigger.textContent,"受阻");
  const priority=taskQuickControl(taskRows(page)[0],"priority");
  priority.trigger.handlers.get("click")[0]();
  await chooseQuick(priority,"紧急");
  assert.deepEqual(page.writes[1].body,{
    title:parent.title,revision:4,priority:"urgent"
  });
  assert.equal(parent.status,"blocked","changing priority cannot affect a derived parent");
});

test("step-only aggregate follows the same safety gate and unreliable parents stay disabled", async () => {
  const step={step_id:"STEP-"+"A".repeat(32),title:"虚构采购步骤",status:"doing",revision:1};
  const parent={...sampleTask(),manual_status:"todo",status_source:"steps",steps:[step]};
  const page=harness([parent]);
  await page.api.refresh(true);
  const status=taskQuickControl(taskRows(page)[0],"status");
  status.trigger.handlers.get("click")[0]();
  assert.deepEqual(status.menu.children.filter(x=>x.tag==="button").map(x=>x.textContent),
    ["确认完成任务"]);
  const guard=await page.api.updateTaskQuickField(parent,"status","todo",status.feedback);
  assert.equal(guard,false);
  assert.equal(page.writes.length,0);
  const incomplete={...parent,status_rollup_incomplete:true};
  const guarded=page.api.taskSummaryRow(incomplete);
  assert.equal(taskQuickControl(guarded,"status").trigger.disabled,true);
  assert.equal(taskQuickControl(guarded,"priority").trigger.disabled,false);
  const cycle={...parent,parent_cycle:true};
  const cycleRow=page.api.taskSummaryRow(cycle);
  assert.equal(taskQuickControl(cycleRow,"status").trigger.disabled,true);
});


test("work record quick capture is separate from task creation and includes historical date", async () => {
  const h = harness();
  assert.equal(h.api.setActivePage("worklog"), true);
  await h.api.loadWorkRecords();
  h.el("work-record-content").value = "今天临时完成采购沟通";
  h.el("work-record-date").value = "2026-10-29";
  h.el("work-record-outcome").value = "交期确认";
  h.el("work-record-minutes").value = "45";
  await h.api.saveWorkRecord({preventDefault() {}});
  assert.equal(h.writes.length, 1);
  assert.equal(h.writes[0].path, "/api/work-records");
  assert.equal(h.writes[0].body.occurred_on, "2026-10-29");
  assert.equal(h.writes[0].body.duration_minutes, 45);
  assert.equal(h.writes[0].body.outcome, "交期确认");
  assert.ok(!("status" in h.writes[0].body));
  assert.equal(h.el("work-record-content").value, "");
  assert.equal(h.el("work-record-submit").disabled, false);
});

test("work timeline combines manual facts and read-only confirmed task completions without duplicate POST", async () => {
  const recordId = "RECORD-" + "A".repeat(32);
  const h = harness([sampleTask()], () => true, [], [], null, {
    records: [{record_id: recordId, display_id:"R-261105-AAAAAAAAAAAA",
      content:"供应商电话沟通", occurred_on:"2026-11-04", created_at:"2026-11-05T10:00:00Z",
      outcome:"确认交期", duration_minutes:30, project_id:null, task_id:null,
      conflict:false, revision:1}],
    task_completions: [{source_event_id:"done-00000001", task_id:"TASK-UI-V2-001",
      task_title:"虚构演示任务：整理项目资料", project_id:null, occurred_at:"2026-11-05T10:00:00Z"}]
  });
  h.api.setActivePage("worklog");
  await h.api.loadWorkRecords();
  assert.equal(h.el("work-record-list").children.length, 2);
  assert.match(h.el("work-record-count").textContent, /1 条工作记录 · 1 次任务完成/);
  assert.equal(h.writes.length, 0);
  h.el("work-filter-keyword").value = "电话沟通";
  h.api.renderWorkRecords();
  assert.equal(h.el("work-record-list").children.length, 1);
  h.el("work-filter-keyword").value = "";
  h.el("work-filter-from").value = "2026-11-05";
  h.api.renderWorkRecords();
  assert.equal(h.el("work-record-list").children.length, 1);
  h.el("work-filter-from").value = "";
  h.api.editWorkRecord(recordId);
  assert.equal(h.el("work-record-content").value, "供应商电话沟通");
  assert.equal(h.el("work-record-submit").textContent, "保存修改");
  h.el("work-record-content").value = "修改后的真实工作记录";
  await h.api.saveWorkRecord({preventDefault() {}});
  assert.equal(h.writes.length, 1);
  assert.equal(h.writes[0].path, "/api/work-records/" + recordId + "/update");
  assert.equal(h.writes[0].body.revision, 1);
});

test("work record save conflicts preserve current text and do not mutate tasks", async () => {
  const recordId = "RECORD-" + "B".repeat(32);
  const h = harness([sampleTask()], () => true, [], [], async () => ({
    ok: false, json: async () => ({error:"work record changed or conflicted; refresh"})
  }), {records:[{record_id:recordId, display_id:"R-261105-BBBBBBBBBBBB",
    content:"原工作内容", occurred_on:"2026-11-05", created_at:"2026-11-05T09:00:00Z",
    conflict:false, revision:2}]});
  await h.api.loadWorkRecords();
  h.api.editWorkRecord(recordId);
  h.el("work-record-content").value = "尚未保存的修正";
  await h.api.saveWorkRecord({preventDefault() {}});
  assert.equal(h.el("work-record-content").value, "尚未保存的修正");
  assert.match(h.el("work-record-message").textContent, /保存未成功/);
  assert.equal(h.writes.length, 1);
  assert.equal(h.writes[0].body.revision, 2);
});

test("work record save preserves edits typed while the request is in flight", async () => {
  let resolvePost;
  let confirmCalls = 0;
  const h = harness([], () => {confirmCalls++; return false;}, [], [], () =>
    new Promise(resolve => {resolvePost = resolve;}));
  h.api.setActivePage("worklog");
  await h.api.loadWorkRecords();
  h.el("work-record-content").value = "先提交的工作事实";
  h.el("work-record-date").value = "2026-11-04";
  h.el("work-record-form").handlers.get("input")[0]();
  const pending = h.api.saveWorkRecord({preventDefault() {}});
  assert.equal(h.el("work-record-cancel").disabled, true,
    "cancel cannot reset the submitted form while the write is pending");
  assert.equal(typeof resolvePost, "function");
  h.el("work-record-content").value = "保存期间继续输入的新草稿";
  h.el("work-record-form").handlers.get("input")[0]();
  assert.equal(h.api.setActivePage("tasks", "all"), false,
    "navigation waits until the in-flight write completes");
  resolvePost({ok:true, json:async()=>({saved:true, display_id:"R-261105-AAAAAAAAAAAA"})});
  await pending;
  assert.equal(h.el("work-record-content").value, "保存期间继续输入的新草稿");
  assert.match(h.el("work-record-message").textContent, /新输入仍保留为未保存草稿/);
  assert.equal(h.el("work-record-cancel").disabled, false);
  assert.equal(h.api.setActivePage("tasks", "all"), false,
    "the preserved draft remains protected after the first save completes");
  assert.equal(confirmCalls, 1);
});


test("work archive creates multiple task and step links with evidence while keeping a record separate from tasks", async () => {
  const stepId = "STEP-" + "B".repeat(32);
  const task = {...sampleTask(), steps:[{step_id:stepId,title:"核对交期",revision:1,status:"todo"}]};
  const h = harness([task]);
  await h.api.refresh(true);
  h.api.setActivePage("worklog");
  h.api.populateWorkLinkTargets();
  h.el("work-record-content").value = "处理临时交期问题";
  h.el("work-record-date").value = "2026-11-04";
  h.el("work-record-featured").checked = true;
  h.el("work-link-target").value = "task:" + task.task_id;
  h.el("work-link-relation").value = "progress_on";
  h.el("work-link-add").handlers.get("click")[0]();
  h.el("work-link-target").value = "step:" + task.task_id + ":" + stepId;
  h.el("work-link-relation").value = "result_of";
  h.el("work-link-add").handlers.get("click")[0]();
  h.el("work-evidence-title").value = "虚构会议纪要";
  h.el("work-evidence-url").value = "https://drive.google.com/file/d/fake/view";
  h.el("work-evidence-add").handlers.get("click")[0]();
  await h.api.saveWorkRecord({preventDefault() {}});
  assert.equal(h.writes.length,1);
  const saved = h.writes[0].body;
  assert.equal(h.writes[0].path,"/api/work-records");
  assert.equal(saved.action_links.length,2);
  assert.equal(saved.action_links[0].target_type,"task");
  assert.equal(saved.action_links[1].target_type,"step");
  assert.equal(saved.action_links[1].relation,"result_of");
  assert.equal(saved.evidence_links[0].title,"虚构会议纪要");
  assert.equal(saved.featured,true);
  assert.ok(!("status" in saved));
});

test("inbox raw note remains separate until user explicitly converts it to a work record", async () => {
  const inboxId = "INBOX-" + "B".repeat(32);
  const work = {inbox:[]};
  const h = harness([],()=>true,[],[],(path,body)=>{
    if(path === "/api/work-archive/inbox") {
      work.inbox.push({inbox_id:inboxId,content:body.content,occurred_on:body.occurred_on,
        revision:1,created_at:"2026-11-05T10:00:00Z",ignored:false,conflict:false});
      return {ok:true,json:async()=>({saved:true,inbox_id:inboxId})};
    }
    return {ok:true,json:async()=>({saved:true,display_id:"R-261105-EXAMPLE"})};
  },work);
  h.api.setActivePage("worklog");
  h.el("work-inbox-content").value = "临时会议讨论了流程问题";
  h.el("work-inbox-date").value = "2026-11-03";
  await h.api.saveWorkInbox({preventDefault() {}});
  assert.equal(h.writes.length,1);
  assert.equal(h.writes[0].path,"/api/work-archive/inbox");
  assert.equal(h.el("work-inbox-count").textContent,"1 条待整理");
  const card = h.el("work-inbox-list").children[0];
  const convert = card.children.find(child=>child.tag === "button" && child.textContent === "整理成工作记录");
  assert.ok(convert);
  convert.handlers.get("click")[0]();
  assert.equal(h.el("work-record-content").value,"临时会议讨论了流程问题");
  assert.equal(h.el("work-record-date").value,"2026-11-03");
  assert.equal(h.writes.length,1,"conversion preview does not silently write a task or record");
  await h.api.saveWorkRecord({preventDefault() {}});
  assert.equal(h.writes[1].path,"/api/work-records");
  assert.equal(h.writes[1].body.source_inbox_id,inboxId);
});

test("review generator submits source IDs and explicit confirmation without invoking an AI API", async () => {
  const recordId = "RECORD-" + "A".repeat(32);
  const preview = {period:"weekly",period_start:"2026-11-02",period_end:"2026-11-08",
    project_id:null,body:"# 周报（来源整理底稿）\n已记录工作事实",
    source_record_ids:[recordId],source_completion_ids:["demo-done-0001"],
    record_count:1,completion_count:1,source_digest:"a".repeat(64),
    record_sources:[{record_id:recordId,display_id:"R-261105-AAAAAAAAAAAA",
      occurred_on:"2026-11-05",content:"已记录工作事实",outcome:null,featured:false}],
    completion_sources:[{source_event_id:"demo-done-0001",occurred_at:"2026-11-05T08:00:00Z",
      task_title:"虚构任务"}]};
  const h = harness([],()=>true,[],[],null,{preview});
  h.api.setActivePage("worklog");
  h.el("work-summary-period").value = "weekly";
  h.el("work-summary-date").value = "2026-11-05";
  await h.api.generateWorkSummary();
  assert.equal(h.el("work-summary-body").value,preview.body);
  assert.equal(h.writes.length,0,"read-only generation never writes events");
  h.el("work-summary-body").value += "\n本人确认本周已经处理风险";
  h.el("work-summary-confirm").checked = true;
  await h.api.saveWorkSummary({preventDefault() {}});
  assert.equal(h.writes.length,1);
  assert.equal(h.writes[0].path,"/api/work-archive/summaries");
  assert.deepEqual(h.writes[0].body.source_record_ids,[recordId]);
  assert.deepEqual(h.writes[0].body.source_completion_ids,["demo-done-0001"]);
  assert.equal(h.writes[0].body.confirmed,true);
  assert.match(h.writes[0].body.body,/本人确认/);
});

test("work archive navigation protects all three unsaved editors", () => {
  let confirmCalls = 0;
  const h = harness([],()=>{confirmCalls++;return false;});
  h.api.setActivePage("worklog");
  h.el("work-inbox-content").value = "未保存的临时笔记";
  h.el("work-inbox-form").handlers.get("input")[0]();
  assert.equal(h.api.setActivePage("tasks","all"),false);
  assert.equal(h.el("work-inbox-content").value,"未保存的临时笔记");
  assert.equal(confirmCalls,1);
});


test("ChatGPT action prompt uses only selected record and explicit same-project task candidates", async () => {
  const rid = "RECORD-" + "A".repeat(32);
  const record = {record_id:rid, revision:3, display_id:"R-261105-AAAAAAAAAAAA",
    content:"供应商确认了本期报价，但后续还需核对质量协议",
    occurred_on:"2026-11-04",project_id:null,outcome:"初步报价确定"};
  const h = harness([sampleTask()],()=>true,[],[],null,{records:[record]});
  await h.api.refresh(true);
  await h.api.loadWorkRecords();
  h.el("work-action-source").value = rid;
  await h.api.copyActionAnalysisPrompt();
  assert.equal(h.copied.length,1);
  assert.match(h.copied[0],/供应商确认了本期报价/);
  assert.match(h.copied[0],/工作记录/);
  assert.match(h.copied[0],/record_revision/);
  assert.match(h.copied[0],/任务/);
  assert.match(h.copied[0],/不会自动/);
  assert.equal(h.writes.length,0,"copy is a manual handoff and must never write events");
});

test("reviewing structured AI proposals remains read-only until an explicit user confirmation", async () => {
  const rid="RECORD-"+"A".repeat(32);
  const record={record_id:rid,revision:1,display_id:"R-261105-AAAAAAAAAAAA",
    content:"原始会议已完成",occurred_on:"2026-11-04",project_id:null};
  const work={records:[record]};
  const review={record_id:rid,record_revision:1,project_id:null,proposals:[
    {title:"安排虚构质量核查",due_date:null,matches:[]}]};
  let allow=false;
  const h=harness([],()=>allow,[],[],(path,body)=>{
    if(path==="/api/work-archive/actions/preview")
      return {ok:true,json:async()=>review};
    return {ok:true,json:async()=>({saved:true,task_id:"TASK-NEW-ACTION"})};
  },work);
  await h.api.refresh(true);
  await h.api.loadWorkRecords();
  h.el("work-action-source").value=rid;
  const json={version:1,record_id:rid,record_revision:1,
    proposals:[{title:"安排虚构质量核查",due_date:null}]};
  h.el("work-action-json").value=JSON.stringify(json);
  await h.api.previewWorkActions();
  assert.equal(h.writes.length,1);
  assert.equal(h.writes[0].path,"/api/work-archive/actions/preview");
  assert.equal(h.el("work-action-list").children.length,1);
  assert.equal(h.el("work-action-list").children[0].children.at(-1).children[0].textContent,
               "确认新建待办");
  await h.api.applyWorkAction("create",review.proposals[0],null);
  assert.equal(h.writes.length,1,"declining confirmation must not create a task");
  allow=true;
  await h.api.applyWorkAction("create",review.proposals[0],null);
  assert.equal(h.writes.length,2);
  assert.equal(h.writes[1].path,"/api/work-archive/actions/create");
  assert.equal(h.writes[1].body.confirmed_create,true);
  assert.equal(h.writes[1].body.duplicate_reviewed,false);
  assert.ok(!("status" in h.writes[1].body),"AI imports cannot carry status=done");
  assert.match(h.el("work-action-message").textContent,/已新建待办/);
});

test("matched AI suggestions offer existing-task linkage rather than duplicate creation", async () => {
  const rid="RECORD-"+"A".repeat(32);
  const task=sampleTask();
  const matches=[{task_id:task.task_id,title:task.title,status:"doing",
    match_type:"same_title",score:1}];
  const review={record_id:rid,record_revision:1,project_id:null,
    proposals:[{title:task.title,due_date:null,matches}]};
  const work={records:[{record_id:rid,revision:1,display_id:"R-261105",
    content:"需要关联旧任务",occurred_on:"2026-11-04",project_id:null}]};
  const h=harness([task],()=>true,[],[],(path,body)=>{
    if(path==="/api/work-archive/actions/preview")
      return {ok:true,json:async()=>review};
    if(path==="/api/work-archive/actions/link")
      return {ok:true,json:async()=>({saved:true,revision:2})};
    throw Error("Unexpected request: "+path);
  },work);
  await h.api.refresh(true);
  await h.api.loadWorkRecords();
  h.el("work-action-source").value=rid;
  h.el("work-action-json").value=JSON.stringify({version:1,record_id:rid,
    record_revision:1,proposals:[{title:task.title,due_date:null}]});
  await h.api.previewWorkActions();
  const row=h.el("work-action-list").children[0];
  const allButtons=row.children.flatMap(child=>child.children || [])
    .filter(child=>child.tag==="button");
  assert.equal(allButtons.length,1);
  assert.match(allButtons[0].textContent,/关联已有/);
  await h.api.applyWorkAction("link",review.proposals[0],matches[0]);
  assert.equal(h.writes[1].path,"/api/work-archive/actions/link");
  assert.equal(h.writes[1].body.task_id,task.task_id);
  assert.equal(h.writes[1].body.confirmed_link,true);
  assert.equal(JSON.parse(h.el("work-action-json").value).record_revision,2,
               "successful link revises only the source snapshot, retaining remaining proposals");
});

test("invalid JSON does not submit a proposal; unsaved analysis is protected on navigation", async () => {
  const recordId="RECORD-"+"A".repeat(32);
  const h=harness([],()=>false,[],[],null,{records:[{record_id:recordId,
    content:"工作记录",revision:1,occurred_on:"2026-11-04",display_id:"R-TEST"}]});
  await h.api.loadWorkRecords();
  h.api.setActivePage("worklog");
  h.el("work-action-source").value=recordId;
  h.el("work-action-json").value="{bad json}";
  h.el("work-action-form").handlers.get("input")[0]();
  await h.api.previewWorkActions();
  assert.match(h.el("work-action-message").textContent,/不是有效 JSON/);
  assert.equal(h.writes.length,0);
  assert.equal(h.api.setActivePage("tasks","all"),false);
  assert.equal(h.el("work-action-json").value,"{bad json}");
});


test("task-to-record UI only proposes standalone tasks and preserves source fields on confirmation", async () => {
  const parent={...sampleTask(),task_id:"TASK-HAS-STEP",steps:[{step_id:"STEP-SIMULATED"}]};
  const recurrent={...sampleTask(),task_id:"TASK-RECUR",recurrence:{enabled:true}};
  const eligible={...sampleTask(),task_id:"TASK-SAFE-FINISHED-FACT",title:"误建的虚构沟通",steps:[]};
  const h=harness([parent,recurrent,eligible],()=>true,[],[],(path,body)=>{
    assert.equal(path,"/api/work-archive/tasks/"+eligible.task_id+"/convert-to-record");
    return {ok:true,json:async()=>({saved:true,display_id:"R-261106-TEST"})};
  });
  await h.api.refresh(true);
  const options=h.el("work-task-convert-source").children;
  assert.equal(options.length,2, "only the blank choice and standalone task can convert");
  assert.equal(options[1].value, eligible.task_id);
  h.el("work-task-convert-source").value=eligible.task_id;
  h.el("work-task-convert-date").value="2026-11-02";
  h.el("work-task-convert-content").value="会议已召开";
  h.el("work-task-convert-outcome").value="达成结果";
  h.el("work-task-convert-minutes").value="30";
  const submit=h.el("work-task-convert-form").handlers.get("submit")[0];
  await submit({preventDefault() {}});
  const saved=h.writes.find(x=>x.path.includes("convert-to-record"));
  assert.ok(saved);
  assert.equal(saved.body.revision,1);
  assert.equal(saved.body.confirmed_move,true);
  assert.equal(saved.body.content,"会议已召开");
  assert.equal(saved.body.duration_minutes,30);
  assert.equal(saved.body.occurred_on,"2026-11-02");
  assert.equal(Object.hasOwn(saved.body,"status"),false);
  assert.match(h.el("work-task-convert-message").textContent,/转换成功/);
});

test("cancelled task-to-record conversion does not POST and leaves the unsaved draft untouched", async () => {
  const eligible={...sampleTask(),task_id:"TASK-UNSAVED-FACT"};
  const h=harness([eligible],()=>false);
  await h.api.refresh(true);
  h.api.setActivePage("worklog");
  h.el("work-task-convert-source").value=eligible.task_id;
  h.el("work-task-convert-content").value="已有的工作事实";
  h.el("work-task-convert-date").value="2026-11-04";
  h.el("work-task-convert-form").handlers.get("input")[0]();
  assert.equal(h.api.setActivePage("tasks","all"),false, "unsaved form prevents navigation");
  await h.el("work-task-convert-form").handlers.get("submit")[0]({preventDefault() {}});
  assert.equal(h.writes.length,0);
  assert.equal(h.el("work-task-convert-content").value,"已有的工作事实");
});


test("ChatGPT weekly analysis copies only selected report sources and does not write", async () => {
  const recordId = "RECORD-" + "A".repeat(32);
  const ignoredId = "RECORD-" + "B".repeat(32);
  const preview = {
    period:"weekly",period_start:"2026-11-02",period_end:"2026-11-08",
    project_id:null,body:"全部周报来源",source_digest:"b".repeat(64),
    source_record_ids:[recordId,ignoredId],source_completion_ids:["evt-done-0001"],
    record_count:2,completion_count:1,
    record_sources:[
      {record_id:recordId,display_id:"R-261105-AAAAAAAAAAAA",
        occurred_on:"2026-11-05",content:"重要项目成果",outcome:"完成阶段成果",featured:true,
        project_name:"虚构采购项目",task_title:"报价审核",
        action_link_labels:[{label:"报价审核 / 核实供应商"}],
        evidence_links:[{title:"虚构报价附件",url:"https://drive.google.com/file/d/fiction/view"}]},
      {record_id:ignoredId,display_id:"R-261105-BBBBBBBBBBBB",
        occurred_on:"2026-11-05",content:"不应出现在汇报里的日常琐事",outcome:null,featured:false}
    ],
    completion_sources:[{source_event_id:"evt-done-0001",occurred_at:"2026-11-05T08:00:00Z",
      task_title:"已人工确认完成的工作"}]
  };
  const h=harness([],()=>true,[],[],null,{preview});
  await h.api.refresh(true);
  h.api.setActivePage("worklog");
  h.el("work-summary-period").value="weekly";
  h.el("work-summary-date").value="2026-11-05";
  h.el("work-summary-audience").value="report";
  await h.api.generateWorkSummary();
  assert.match(h.el("work-summary-source-count").textContent,/已选 2 \/ 3/);
  const importantInfo = h.el("work-summary-source-items").children[0].children[1].children[0].textContent;
  assert.match(importantInfo,/R-261105-AAAAAAAAAAAA/);
  assert.match(importantInfo,/虚构采购项目/);
  assert.match(importantInfo,/报价审核 \/ 核实供应商/);
  assert.match(importantInfo,/虚构报价附件/);
  h.el("work-summary-select-all").handlers.get("click")[0]();
  assert.match(h.el("work-summary-source-count").textContent,/已选 3 \/ 3/);
  assert.match(h.el("work-summary-body").value,/不应出现在汇报里的日常琐事/);
  h.el("work-summary-select-important").handlers.get("click")[0]();
  assert.match(h.el("work-summary-source-count").textContent,/已选 2 \/ 3/);
  assert.match(h.el("work-summary-body").value,/重要项目成果/);
  assert.doesNotMatch(h.el("work-summary-body").value,/不应出现在汇报里的日常琐事/);
  h.el("work-summary-select-none").handlers.get("click")[0]();
  assert.match(h.el("work-summary-source-count").textContent,/已选 0 \/ 3/);
  assert.doesNotMatch(h.el("work-summary-body").value,/重要项目成果/);
  h.el("work-summary-select-important").handlers.get("click")[0]();
  await h.el("work-summary-copy-sources").handlers.get("click")[0]();
  assert.match(h.copied.at(-1),/重要项目成果/);
  assert.doesNotMatch(h.copied.at(-1),/不应出现在汇报里的日常琐事/);
  assert.equal(h.writes.length,0,"report source handoff stays read-only");
});

test("featured achievement context copies only server-verified source data and surfaces conflict without writes", async () => {
  const projectId="PROJECT-"+"F".repeat(32);
  const h=harness([],()=>true,[{project_id:projectId,name:"虚构项目"}],[],null,{
    portfolio_context:{prompt:"精选成果资料：RECORD-0001",record_count:1}
  });
  await h.api.refresh(true);
  h.el("work-portfolio-project").value=projectId;
  await h.el("work-portfolio-copy").handlers.get("click")[0]();
  assert.equal(h.copied.at(-1),"精选成果资料：RECORD-0001");
  assert.match(h.el("work-portfolio-message").textContent,/已复制 1 条人工精选成果/);
  assert.equal(h.writes.length,0);
  const bad=harness([],()=>true,[],[],null,{portfolio_error:"featured source conflicted"});
  await bad.api.refresh(true);
  await bad.el("work-portfolio-copy").handlers.get("click")[0]();
  assert.equal(bad.copied.length,0);
  assert.match(bad.el("work-portfolio-message").textContent,/未复制成果来源/);
  assert.equal(bad.writes.length,0);
});

test("one step progress note belongs to step task and project timelines without task status writes", async () => {
  const projectId = "PROJECT-" + "A".repeat(32);
  const stepId = "STEP-" + "B".repeat(32);
  const taskId = "TASK-UI-PROGRESS";
  const task = {...sampleTask(),task_id:taskId,project_id:projectId,steps:[
    {step_id:stepId,task_id:taskId,title:"催报价",status:"todo",revision:1}
  ]};
  const fact = {record_id:"RECORD-"+"C".repeat(32),occurred_on:"2026-11-09",
    content:"已向供应商催促报价",project_id:projectId,task_id:taskId,
    action_links:[{target_type:"step",target_id:stepId,task_id:taskId,relation:"progress_on"}]};
  const h = harness([task],()=>true,[{project_id:projectId,name:"虚构采购"}],[],null,{records:[fact]});
  await h.api.refresh(true);
  await h.api.loadWorkRecords();
  assert.equal(h.api.recordBelongsTo(fact,{type:"step",task_id:taskId,step_id:stepId}),true);
  assert.equal(h.api.recordBelongsTo(fact,{type:"task",task_id:taskId}),true);
  assert.equal(h.api.recordBelongsTo(fact,{type:"project",project_id:projectId}),true);
  const panel = h.api.progressPanel({type:"step",project_id:projectId,task_id:taskId,step_id:stepId});
  const details = panel.children.find(x=>x.tag==="details");
  const form = details.children.find(x=>x.tag==="form");
  assert.ok(form,"step quick-record form exists");
  const contentLabel = form.children.find(x=>x.tag==="label" &&
    x.children.some(child=>child.tag==="textarea"));
  const textarea = contentLabel.children.find(x=>x.tag==="textarea");
  const date = form.children.find(x=>x.tag==="input");
  textarea.value = "新进展：供应商承诺核实货源";
  date.value = "2026-11-09";
  form.handlers.get("input")[0]();
  await form.handlers.get("submit")[0]({preventDefault(){}});
  const created = h.writes.find(x=>x.path==="/api/work-records");
  assert.ok(created,"quick progress writes to the single work record API");
  assert.equal(created.body.task_id,taskId);
  assert.equal(created.body.project_id,projectId);
  assert.equal(created.body.action_links[0].target_id,stepId);
  assert.equal(created.body.record_type,"progress");
  assert.equal(Object.hasOwn(created.body,"status"),false);
  assert.equal(Object.hasOwn(created.body,"confirmed_done"),false);
});

test("P3 one original note creates distinct reviewed work records with verified excerpts", async () => {
  const inboxId="INBOX-"+"A".repeat(32);
  const recordId="RECORD-"+"B".repeat(32);
  const digest="c".repeat(64);
  const source={inbox_id:inboxId,content:"上午核对虚构报价。\n下午确认虚构交期。",
    source_digest:digest,occurred_on:"2026-11-09",project_id:null,
    revision:1,processed_fragment_count:0,ignored:false,finished:false,conflict:false,
    created_at:"2026-11-09T08:00:00Z"};
  const saved={record_id:recordId,display_id:"R-261109-BBBBBBBBBBBB",
    content:"已核对虚构报价",revision:1,source_inbox_id:inboxId,
    occurred_on:"2026-11-09"};
  const h=harness([],()=>true,[],[],(path,body)=>{
    if(path==="/api/work-records")return {ok:true,json:async()=>({saved:true,record_id:recordId,
      display_id:saved.display_id,revision:1})};
    return {ok:true,json:async()=>({saved:true,revision:2})};
  },{inbox:[source],records:[saved]});
  await h.api.loadWorkArchive();
  h.el("work-split-source").value=inboxId;
  h.el("work-split-lines").handlers.get("click")[0]();
  const suggested=JSON.parse(h.el("work-split-json").value);
  assert.equal(suggested.facts.length,2);
  assert.equal(suggested.source_digest,digest);
  h.el("work-split-check").handlers.get("click")[0]();
  assert.equal(h.el("work-split-review").children.length,2);
  const first=h.el("work-split-review").children[0];
  const save=first.children.find(child=>child.tag==="button");
  await save.handlers.get("click")[0]();
  assert.equal(h.writes.length,1);
  assert.equal(h.writes[0].path,"/api/work-records");
  assert.equal(h.writes[0].body.source_inbox_id,inboxId);
  assert.equal(h.writes[0].body.source_fragment.excerpt,"上午核对虚构报价。");
  assert.equal(h.writes[0].body.source_fragment.occurrence,1);
  assert.equal(h.writes[0].body.source_fragment.source_digest,digest);
  assert.equal(Object.hasOwn(h.writes[0].body,"status"),false);
  assert.equal(Object.hasOwn(h.writes[0].body,"confirmed_done"),false);
  const rebuilt=h.el("work-split-review").children[0];
  assert.match(rebuilt.children[0].textContent,/已保存/);
  assert.equal(rebuilt.children.find(child=>child.tag==="button").disabled,true);
});

test("P3 rejects invented and overlapping quotes before any write and keeps follow-ups read-only", async () => {
  const inboxId="INBOX-"+"E".repeat(32),digest="e".repeat(64);
  const source={inbox_id:inboxId,content:"会议讨论了采购计划。\n后续核实供应商交期。",
    occurred_on:null,project_id:null,source_digest:digest,
    ignored:false,finished:false,conflict:false,revision:1};
  const h=harness([],()=>true,[],[],null,{inbox:[source]});
  await h.api.loadWorkArchive();
  h.el("work-split-source").value=inboxId;
  const plan={
    version:1,inbox_id:inboxId,source_digest:digest,
    facts:[{excerpt:"根本没说过的话",occurrence:1,
      content:"编造的工作完成",occurred_on:"2026-11-09",outcome:null}],
    follow_ups:[{title:"未来催供应商",due_date:null}]
  };
  h.el("work-split-json").value=JSON.stringify(plan);
  h.el("work-split-check").handlers.get("click")[0]();
  assert.match(h.el("work-split-message").textContent,/原文不存在/);
  assert.equal(h.writes.length,0);
  plan.facts=[{excerpt:"会议讨论了采购计划。",occurrence:1,
    content:"已开会讨论",occurred_on:null,outcome:null},
    {excerpt:"讨论了采购",occurrence:1,
    content:"重复同一事件",occurred_on:null,outcome:null}];
  h.el("work-split-json").value=JSON.stringify(plan);
  h.el("work-split-check").handlers.get("click")[0]();
  assert.match(h.el("work-split-message").textContent,/重叠原文/);
  plan.facts.pop();
  h.el("work-split-json").value=JSON.stringify(plan);
  h.el("work-split-check").handlers.get("click")[0]();
  assert.equal(h.el("work-split-review").children.length,2,"fact + future suggestion");
  const first=h.el("work-split-review").children[0];
  const save=first.children.find(child=>child.tag==="button");
  await save.handlers.get("click")[0]();
  assert.match(h.el("work-split-message").textContent,/补齐合法的发生日期/);
  assert.equal(h.writes.length,0);
  assert.match(h.el("work-split-review").children[1].textContent ||
    h.el("work-split-review").children[1].children.map(x=>x.textContent).join(""),
    /未来待办建议/);
});

test("integration: changing a split source cannot discard an unsaved reviewed draft", async () => {
  const a="INBOX-"+"A".repeat(32),b="INBOX-"+"B".repeat(32);
  const first={inbox_id:a,content:"虚构采购上午核对报价。",source_digest:"a".repeat(64),
    revision:1,occurred_on:"2026-11-09",ignored:false,finished:false,conflict:false};
  const second={...first,inbox_id:b,content:"虚构采购下午核对交期。",source_digest:"b".repeat(64)};
  const h=harness([],()=>false,[],[],null,{inbox:[first,second]});
  await h.api.loadWorkArchive();
  h.el("work-split-source").value=a;
  h.el("work-split-source").handlers.get("change")[0]();
  h.el("work-split-lines").handlers.get("click")[0]();
  h.el("work-split-check").handlers.get("click")[0]();
  const originalJson=h.el("work-split-json").value;
  assert.equal(h.el("work-split-review").children.length,1);
  h.el("work-split-source").value=b;
  h.el("work-split-source").handlers.get("change")[0]();
  assert.equal(h.el("work-split-source").value,a);
  assert.equal(h.el("work-split-json").value,originalJson);
  assert.equal(h.el("work-split-review").children.length,1);
  assert.equal(h.writes.length,0);
});

test("integration: edited AI plan must be re-reviewed before writing a fact", async () => {
  const inboxId="INBOX-"+"C".repeat(32);
  const source={inbox_id:inboxId,content:"虚构项目已核对报价。",source_digest:"c".repeat(64),
    revision:1,occurred_on:"2026-11-09",ignored:false,finished:false,conflict:false};
  const h=harness([],()=>true,[],[],null,{inbox:[source]});
  await h.api.loadWorkArchive();
  h.el("work-split-source").value=inboxId;
  h.el("work-split-lines").handlers.get("click")[0]();
  h.el("work-split-check").handlers.get("click")[0]();
  const oldCard=h.el("work-split-review").children[0];
  const oldSave=oldCard.children.find(node=>node.tag==="button");
  const payload=JSON.parse(h.el("work-split-json").value);
  payload.facts[0].content="虚构项目已经确认采购（尚未核实）";
  h.el("work-split-json").value=JSON.stringify(payload);
  h.el("work-split-json").handlers.get("input")[0]();
  await oldSave.handlers.get("click")[0]();
  assert.equal(h.writes.length,0);
  assert.match(h.el("work-split-message").textContent,/重新点击/);
  h.el("work-split-check").handlers.get("click")[0]();
  const freshSave=h.el("work-split-review").children[0].children.find(node=>node.tag==="button");
  await freshSave.handlers.get("click")[0]();
  assert.equal(h.writes.length,1);
  assert.equal(h.writes[0].body.content,payload.facts[0].content);
  assert.equal(Object.hasOwn(h.writes[0].body,"status"),false);
});

test("integration: previously saved inbox fragments are marked complete on reopen", async () => {
  const inboxId="INBOX-"+"D".repeat(32),savedId="RECORD-"+"A".repeat(32);
  const content="上午检查虚构报价。\n下午核对虚构交期。";
  const excerpt="上午检查虚构报价。";
  const source={inbox_id:inboxId,content,source_digest:"d".repeat(64),
    processed_fragment_count:1,
    processed_fragments:[{record_id:savedId,excerpt,occurrence:1,start:0,end:excerpt.length}],
    revision:1,occurred_on:"2026-11-09",ignored:false,finished:false,conflict:false};
  const h=harness([],()=>true,[],[],null,{inbox:[source]});
  await h.api.loadWorkArchive();
  h.el("work-split-source").value=inboxId;
  h.el("work-split-lines").handlers.get("click")[0]();
  h.el("work-split-check").handlers.get("click")[0]();
  const cards=h.el("work-split-review").children;
  assert.equal(cards.length,2);
  assert.match(cards[0].children[0].textContent,/已保存/);
  assert.equal(cards[0].children.find(x=>x.tag==="button").disabled,true);
  assert.equal(cards[1].children.find(x=>x.tag==="button").disabled,false);
  const untouched=cards[0].children.find(x=>x.tag==="button");
  await untouched.handlers.get("click")[0]();
  assert.equal(h.writes.length,0);
  const pending=cards[1].children.find(x=>x.tag==="button");
  await pending.handlers.get("click")[0]();
  assert.equal(h.writes.length,1);
  assert.equal(h.writes[0].body.source_fragment.excerpt,"下午核对虚构交期。");
});

test("P3 project stage timeline deduplicates project task and step records and copies source-only context", async () => {
  const projectId="PROJECT-"+"F".repeat(32);
  const taskId="TASK-UI-STAGE";
  const task={...sampleTask(),task_id:taskId,project_id:projectId,title:"虚构采购任务"};
  const firstId="RECORD-"+"A".repeat(32);
  const secondId="RECORD-"+"B".repeat(32);
  const unrelatedId="RECORD-"+"C".repeat(32);
  const work={
    records:[
      {record_id:firstId,display_id:"R-261109-AAAAAAAAAAAA",occurred_on:"2026-11-09",
        content:"已完成虚构设备现场核查",project_id:projectId},
      {record_id:secondId,display_id:"R-261108-BBBBBBBBBBBB",occurred_on:"2026-11-08",
        content:"已催促虚构供应商报价",task_id:taskId,project_id:null,
        action_links:[{target_type:"step",task_id:taskId,target_id:"STEP-"+"D".repeat(32),relation:"progress_on"}]},
      {record_id:secondId,display_id:"R-261108-BBBBBBBBBBBB",occurred_on:"2026-11-08",
        content:"已催促虚构供应商报价",task_id:taskId,project_id:null},
      {record_id:unrelatedId,occurred_on:"2026-11-09",content:"另一个不相关项目",project_id:"PROJECT-"+"E".repeat(32)}
    ],
    task_completions:[{source_event_id:"stage-completion-0001",occurred_at:"2026-11-09T06:00:00Z",
      task_title:"人工确认完成的虚构工作",project_id:projectId,task_id:taskId}]
  };
  const h=harness([task],()=>true,[{project_id:projectId,name:"虚构采购项目"}],[],null,work);
  await h.api.refresh(true);
  h.el("work-stage-project").value=projectId;
  h.el("work-stage-start").value="2026-11-01";
  h.el("work-stage-end").value="2026-11-09";
  await h.el("work-stage-show").handlers.get("click")[0]();
  assert.match(h.el("work-stage-message").textContent,/2 条独立工作事实、1 次人工任务完成/);
  assert.equal(h.el("work-stage-list").children.length,2);
  assert.equal(h.el("work-stage-copy").disabled,false);
  await h.el("work-stage-copy").handlers.get("click")[0]();
  const copied=h.copied.at(-1);
  assert.match(copied,/已完成虚构设备现场核查/);
  assert.match(copied,/已催促虚构供应商报价/);
  assert.match(copied,/stage-completion-0001/);
  assert.doesNotMatch(copied,/另一个不相关项目/);
  assert.equal(h.writes.length,0,"stage generation and export are strictly read-only");
  assert.equal(h.el("work-stage-report").disabled,false);
  h.el("work-stage-report").handlers.get("click")[0]();
  assert.equal(h.el("work-summary-period").value,"monthly");
  assert.equal(h.el("work-summary-date").value,"2026-11-09");
  assert.equal(h.el("work-summary-project").value,projectId);
  assert.equal(h.el("work-summary-audience").value,"report");
  assert.match(h.el("work-summary-message").textContent,/请点击.*生成来源底稿/);
  assert.equal(h.writes.length,0,"handoff is a filter change, not a save");
});

test("saved report reselects sources only after deliberate rebuild and appends one revision", async () => {
  const included = "RECORD-"+"A".repeat(32);
  const excluded = "RECORD-"+"B".repeat(32);
  const summaryId = "SUMMARY-"+"C".repeat(32);
  const preview = {
    period:"weekly",period_start:"2026-11-02",period_end:"2026-11-08",
    project_id:null,body:"# 全部旧来源",
    source_digest:"c".repeat(64),source_record_ids:[included,excluded],
    source_completion_ids:[],record_count:2,completion_count:0,
    record_sources:[
      {record_id:included,occurred_on:"2026-11-05",display_id:"R-261105-AAAAAAAAAAAA",
        content:"本周落实重要采购事项",outcome:"形成采购建议",featured:true},
      {record_id:excluded,occurred_on:"2026-11-05",display_id:"R-261105-BBBBBBBBBBBB",
        content:"不需要出现在汇报中的小事",outcome:null,featured:false}
    ],
    completion_sources:[]
  };
  const saved={summary_id:summaryId,revision:2,conflict:false,
    period:"weekly",period_start:"2026-11-02",period_end:"2026-11-08",
    project_id:null,body:"这是之前人工写的报告正文",audience:"report",
    confirmed:true,source_record_ids:[included,excluded],source_completion_ids:[],
    included_record_ids:[included],included_completion_ids:[],source_digest:"old-digest"};
  const h=harness([],()=>true,[],[],null,{preview,summaries:[saved]});
  await h.api.refresh(true);
  await h.api.loadWorkArchive();
  h.api.setActivePage("worklog");
  h.api.editWorkSummary(summaryId);
  assert.equal(h.el("work-summary-body").value,saved.body);
  assert.equal(h.el("work-summary-edit-sources").hidden,false);
  await h.el("work-summary-edit-sources").handlers.get("click")[0]();
  assert.equal(h.el("work-summary-body").value,saved.body,"opening source editor does not erase wording");
  assert.equal(h.el("work-summary-source-items").children.length,2);
  await h.api.saveWorkSummary({preventDefault() {}});
  assert.equal(h.writes.length,0,"cannot save stale body before reselect rebuild");
  await h.el("work-summary-rebuild").handlers.get("click")[0]();
  assert.match(h.el("work-summary-body").value,/本周落实重要采购事项/);
  assert.doesNotMatch(h.el("work-summary-body").value,/不需要出现在汇报中的小事/);
  await h.api.saveWorkSummary({preventDefault() {}});
  assert.equal(h.writes.length,1);
  assert.equal(h.writes[0].path,"/api/work-archive/summaries/"+summaryId+"/reselect");
  assert.equal(h.writes[0].body.revision,2);
  assert.equal(h.writes[0].body.confirmed_reselect,true);
  assert.equal(h.writes[0].body.confirmed,false);
  assert.equal(h.writes[0].body.source_digest,preview.source_digest);
  assert.deepEqual(h.writes[0].body.included_record_ids,[included]);
  assert.deepEqual(h.writes[0].body.source_record_ids,[included,excluded]);
  assert.equal(h.writes[0].body.body.includes("不需要出现在汇报中的小事"),false);
});

test("decision records surface the current conclusion and notes stay optional in report defaults", async () => {
  const task = sampleTask();
  const fact = {record_id:"RECORD-"+"D".repeat(32),display_id:"R-261111-DDDDDDDDDDDD",
    content:"评估是否向供应商转卖零件",outcome:"不卖",record_type:"decision",
    occurred_on:"2026-11-11",created_at:"2026-11-11T02:00:00Z",
    updated_at:"2026-11-11T02:00:00Z",task_id:task.task_id,project_id:null,conflict:false};
  const h = harness([task],()=>true,[],[],null,{records:[fact]});
  await h.api.loadWorkRecords();
  const panel = h.api.progressPanel({type:"task",task_id:task.task_id});
  assert.equal(panel.children[0].className,"current-conclusion");
  assert.equal(panel.children[0].children[1].textContent,"不卖");
  assert.equal(h.api.summaryRecordRecommended(fact),true);
  assert.equal(h.api.summaryRecordRecommended({record_type:"note",content:"临时想法"}),false);
  assert.equal(h.api.summaryRecordRecommended({record_type:"note",featured:true}),true);
  assert.equal(h.api.workRecordTypeLabel("communication"),"沟通");
  const details = panel.children.find(child=>child.tag==="details");
  const form = details.children.find(child=>child.tag==="form");
  const typeLabel = form.children.find(child=>child.tag==="label" &&
    child.children.some(input=>input.tag==="select"));
  const type = typeLabel.children.find(input=>input.tag==="select");
  const contentLabel = form.children.find(child=>child.tag==="label" &&
    child.children.some(input=>input.tag==="textarea"));
  const content = contentLabel.children.find(input=>input.tag==="textarea");
  const outcomeLabel = form.children.find(child=>child.tag==="label" &&
    child.children.some(input=>input.tag==="textarea" && input!==content));
  const outcome = outcomeLabel.children.find(input=>input.tag==="textarea");
  const date = form.children.find(child=>child.tag==="input");
  type.value = "decision";
  type.handlers.get("change")[0]();
  content.value = "评估是否向供应商转卖零件";
  outcome.value = "不卖";
  date.value = "2026-11-11";
  await form.handlers.get("submit")[0]({preventDefault(){}});
  const write = h.writes.find(item=>item.path==="/api/work-records");
  assert.ok(write);
  assert.equal(write.body.record_type,"decision");
  assert.equal(write.body.outcome,"不卖");
});

test("object descriptions save independently and inherited conversion descriptions use a revision token", async () => {
  const task = {...sampleTask(),description:"",description_revision:0};
  const h = harness([task],()=>true,[],[],async (path,body)=>({
    ok:true,json:async()=>({saved:true,revision:1,description:body.description})
  }));
  const panel = h.api.objectDescriptionPanel("task",task);
  const form = panel.children.find(child=>child.tag==="form");
  const textarea = form.children[0].children.find(child=>child.tag==="textarea");
  textarea.value = "背景：评估是否转卖零件";
  form.handlers.get("input")[0]();
  await form.handlers.get("submit")[0]({preventDefault(){}});
  assert.equal(h.writes[0].path,"/api/object-details");
  assert.equal(h.writes[0].body.object_type,"task");
  assert.equal(h.writes[0].body.object_id,task.task_id);
  assert.equal(h.writes[0].body.revision,0);
  assert.equal(task.description,"背景：评估是否转卖零件");
  assert.equal(task.description_revision,1);
  assert.equal(panel.children[0].textContent,"任务说明");

  const stepId = "STEP-"+"E".repeat(32);
  const step = {step_id:stepId,description:"原步骤说明",description_revision:0,
    description_inherited:true,description_inherited_from:"step|TASK-UI-V2-001|"+stepId,
    description_inherited_revision:2,conflict:false};
  const h2 = harness([],()=>true,[],[],async (path,body)=>({
    ok:true,json:async()=>({saved:true,revision:1,description:body.description})
  }));
  const stepPanel = h2.api.objectDescriptionPanel("step",step,"TASK-UI-V2-001");
  const stepForm = stepPanel.children.find(child=>child.tag==="form");
  stepForm.children[0].children.find(child=>child.tag==="textarea").value = "继承后调整的说明";
  await stepForm.handlers.get("submit")[0]({preventDefault(){}});
  assert.equal(h2.writes[0].body.inherited_from,step.description_inherited_from);
  assert.equal(h2.writes[0].body.inherited_revision,2);
  assert.equal(h2.writes[0].body.task_id,"TASK-UI-V2-001");
});

