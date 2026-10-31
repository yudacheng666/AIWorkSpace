// Regression tests for the real inline new-task form (no browser or dependencies needed).
import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
import {test} from "node:test";
import vm from "node:vm";

function mockWindow(confirm = () => true) {
  const listeners = new Map();
  return {
    window: {
      confirm,
      addEventListener(type, handler) {
        if (!listeners.has(type)) listeners.set(type, []);
        listeners.get(type).push(handler);
      }
    },
    fireBeforeUnload() {
      const event = {
        returnValue: undefined,
        defaultPrevented: false,
        preventDefault() { this.defaultPrevented = true; }
      };
      for (const handler of listeners.get("beforeunload") || []) handler(event);
      return {prevented: event.defaultPrevented, returnValue: event.returnValue};
    }
  };
}

const page = readFileSync(new URL("../web/index.html", import.meta.url), "utf8");
const match = page.match(/<script>([\s\S]*?)<\/script>/);
assert.ok(match, "web page must have an inline script");

function harness() {
  const elements = new Map();
  function mockElement() {
    const handlers = new Map();
    return {
      handlers,
      value: "",
      textContent: "",
      className: "",
      disabled: false,
      hidden: false,
      selectedOptions: [],
      append() {},
      replaceChildren() {},
      addEventListener(type, handler) { handlers.set(type, handler); },
    };
  }
  const document = {
    activeElement: null,
    getElementById(id) {
      if (!elements.has(id)) elements.set(id, mockElement());
      return elements.get(id);
    },
    createElement() { return mockElement(); },
  };
  let resolveResponse;
  const pendingResponse = new Promise(resolve => { resolveResponse = resolve; });
  const posted = [];
  const projectPosted = [];
  const updateCalls = [];
  const browser = mockWindow();
  const fetch = async (path, options) => {
    if (path === "/api/tasks" && options?.method === "POST") {
      posted.push(JSON.parse(options.body));
      return pendingResponse;
    }
    if (path === "/api/projects" && options?.method === "POST") {
      projectPosted.push(JSON.parse(options.body));
      return {ok: true, json: async () => ({saved: true, project_id: "PROJECT-MOCK-001"})};
    }
    if (path === "/api/update/status") {
      return {ok: true, json: async () => ({
        version: "1.0.0", build_short: "abcdef0", build_known: true, last_update: null
      })};
    }
    if (path === "/api/update/check") {
      updateCalls.push("check");
      return {ok: true, json: async () => ({
        version: "1.0.0", latest_version: "1.1.0",
        latest_commit: "a".repeat(40), latest_short: "aaaaaaa",
        latest_message: "test update", update_available: true
      })};
    }
    if (path === "/api/update/apply") {
      updateCalls.push(JSON.parse(options.body));
      return {ok: true, status: 202, json: async () => ({started: true})};
    }
    assert.equal(path, "/api/tasks");
    return {ok: true, json: async () => ({tasks: [], projects: [], warnings: []})};
  };
  vm.runInNewContext(match[1], {
    document, fetch, setInterval() {}, Date, window: browser.window
  }, {timeout: 2000});

  const input = document.getElementById("new-task-title");
  const message = document.getElementById("create-message");
  const submit = document.getElementById("create-submit");
  const form = document.getElementById("create-task");
  const type = (value) => {
    input.value = value;
    input.handlers.get("input")();
    form.handlers.get("input")?.();
  };
  const save = () => form.handlers.get("submit")({preventDefault() {}});
  const respond = (status = 201, payload = {saved: true, task_id: "TASK-MOCK-001"}) => {
    resolveResponse({ok: status >= 200 && status < 300, status,
                     json: async () => payload});
  };
  const projectInput = document.getElementById("new-project-name");
  const projectForm = document.getElementById("create-project");
  const createProject = () => projectForm.handlers.get("submit")({preventDefault() {}});
  return {type, save, respond, input, message, submit, posted, projectPosted,
          projectInput, createProject, document, updateCalls,
          beforeUnload: () => browser.fireBeforeUnload()};
}

test("a late success response must not erase a different draft", async () => {
  const page = harness();
  page.type("任务甲");
  const saving = page.save();
  assert.equal(page.posted.length, 1);
  assert.equal(page.posted[0].title, "任务甲");

  // User begins task B before request A responds.
  page.type("任务乙");
  page.respond();
  await saving;
  assert.equal(page.input.value, "任务乙");
  assert.match(page.message.textContent, /创建成功/);
  assert.match(page.message.textContent, /草稿已保留/);
  assert.equal(page.posted.length, 1, "draft B was not silently submitted");
  assert.equal(page.submit.disabled, false);
});

test("untouched input clears only after confirmed success", async () => {
  const page = harness();
  page.type("任务甲");
  const saving = page.save();
  page.respond();
  await saving;
  assert.equal(page.input.value, "");
  assert.equal(page.posted[0].title, "任务甲");
  assert.match(page.message.textContent, /创建成功/);
});

test("a draft edited and restored to the same text is still preserved", async () => {
  const page = harness();
  page.type("任务甲");
  const saving = page.save();
  page.type("任务乙");
  page.type("任务甲");
  page.respond();
  await saving;
  assert.equal(page.input.value, "任务甲");
  assert.match(page.message.textContent, /草稿已保留/);
});

test("failed create retains the current draft and reports uncertainty", async () => {
  const page = harness();
  page.type("任务甲");
  const saving = page.save();
  page.type("任务乙");
  page.respond(500, {error: "server unavailable"});
  await saving;
  assert.equal(page.input.value, "任务乙");
  assert.match(page.message.textContent, /创建结果未确认/);
  assert.equal(page.submit.disabled, false);
});

test("submit again during a pending request does not create duplicates", async () => {
  const page = harness();
  page.type("任务甲");
  const saving = page.save();
  page.type("任务乙");
  await page.save();
  assert.equal(page.posted.length, 1);
  page.respond();
  await saving;
  assert.equal(page.input.value, "任务乙");
});


test("new task submission includes selected primary and related projects", async () => {
  const page = harness();
  const primary = page.document.getElementById("new-task-project");
  const related = page.document.getElementById("new-task-related");
  primary.value = "PROJECT-PRIMARY";
  related.selectedOptions = [{value: "PROJECT-RELATED"}];
  page.type("项目任务");
  const saving = page.save();
  assert.deepEqual(page.posted[0], {
    title: "项目任务",
    project_id: "PROJECT-PRIMARY",
    related_project_ids: ["PROJECT-RELATED"],
  });
  page.respond();
  await saving;
});

test("project creation sends only the project name", async () => {
  const page = harness();
  page.projectInput.value = "新项目";
  await page.createProject();
  assert.deepEqual(page.projectPosted, [{name: "新项目"}]);
});


// Exercise the actual task-edit form with project events missing from local sync.
// A small DOM stand-in maintains <select> selectedOptions as a browser would.
function taskEditHarness(task) {
  const elements = new Map();
  let confirmValue = true;
  const browser = mockWindow(() => confirmValue);
  function fakeElement(tag = "div") {
    const node = {
      tag, textContent: "", className: "", children: [], handlers: new Map(),
      disabled: false, selected: false, hidden: false, multiple: false,
      _value: "", append(...items) { this.children.push(...items); },
      replaceChildren(...items) { this.children = items; },
      addEventListener(type, handler) { this.handlers.set(type, handler); }
    };
    Object.defineProperty(node, "value", {
      get() { return this.tag === "select"
        ? (this.children.find(item => item.selected)?.value ?? "")
        : this._value; },
      set(next) {
        this._value = next;
        if (this.tag === "select") for (const item of this.children) {
          item.selected = item.value === next;
        }
      }
    });
    Object.defineProperty(node, "selectedOptions", {
      get() { return this.tag === "select"
        ? this.children.filter(item => item.selected) : []; }
    });
    return node;
  }
  const document = {
    activeElement: null,
    getElementById(id) {
      if (!elements.has(id)) elements.set(id, fakeElement());
      return elements.get(id);
    },
    createElement(tag) { return fakeElement(tag); }
  };
  const posted = [];
  const stepCreated = [];
  const stepUpdated = [];
  const stepReordered = [];
  let delayStepCreate = false;
  let resolveStepCreate;
  const pendingStepCreate = new Promise(resolve => { resolveStepCreate = resolve; });
  const fetch = async (path, options) => {
    if (path.includes("/steps/reorder") && options?.method === "POST") {
      stepReordered.push(JSON.parse(options.body));
      return {ok: true, json: async () => ({saved: true, revision: 1})};
    }
    if (path.includes("/steps/") && path.endsWith("/update") && options?.method === "POST") {
      stepUpdated.push({path, body: JSON.parse(options.body)});
      return {ok: true, json: async () => ({saved: true, revision: 2})};
    }
    if (path.endsWith("/steps") && options?.method === "POST") {
      stepCreated.push({path, body: JSON.parse(options.body)});
      if (delayStepCreate) return pendingStepCreate;
      return {ok: true, json: async () => ({saved: true, step_id: "STEP-" + "9".repeat(32)})};
    }
    if (path.endsWith("/update") && options?.method === "POST") {
      posted.push(JSON.parse(options.body));
      return {ok: true, json: async () => ({saved: true})};
    }
    assert.equal(path, "/api/tasks");
    return {ok: true, json: async () => ({tasks: [], projects: [], warnings: []})};
  };
  const {row} = vm.runInNewContext(match[1] + "\n;({row})", {
    document, fetch, setInterval() {}, Date, window: browser.window
  }, {timeout: 2000});
  const card = row({...task, steps: task.steps || [],
                    step_order_revision: task.step_order_revision ?? 0,
                    step_order_conflict: task.step_order_conflict ?? false,
                    step_order_candidates: task.step_order_candidates || []});
  const form = card.children.find(item => item.className === "task-form");
  assert.ok(form, "task edit form must exist");
  const [titleLabel, statusLabel, primaryLabel, relatedLabel] = form.children;
  const title = titleLabel.children[0];
  const status = statusLabel.children[0];
  const primary = primaryLabel.children[0];
  const related = relatedLabel.children[0];
  const metadata = form.children.find(item => item.className.includes("edit-meta"));
  assert.ok(metadata, "M3.2 metadata inputs must be part of the task form");
  const [owner, priority, due, planned, follow] =
    metadata.children.map(label => label.children[0]);
  const save = () => form.handlers.get("submit")({preventDefault() {}});
  const stepPanel = card.children.find(item => item.className === "steps-panel");
  return {title, status, primary, related, owner, priority, due, planned, follow,
          save, posted, card, stepPanel, stepCreated, stepUpdated, stepReordered,
          setConfirm(value) { confirmValue = value; },
          setDelayStepCreate(value) { delayStepCreate = value; },
          respondStepCreate() {
            resolveStepCreate({ok: true, json: async () => ({saved: true, step_id: "STEP-" + "9".repeat(32)})});
          },
          beforeUnload: () => browser.fireBeforeUnload()};
}

test("P2: changing title preserves unsynced primary and related project IDs", async () => {
  const primary = "PROJECT-" + "A".repeat(32);
  const related = "PROJECT-" + "B".repeat(32);
  const page = taskEditHarness({
    task_id: "TASK-TEST-PENDING", title: "原始名称", status: "todo",
    revision: 1, conflict: false, project_id: primary,
    related_project_ids: [related], project_name: null
  });
  assert.equal(page.primary.value, primary, "missing primary must remain selected");
  assert.deepEqual(page.related.selectedOptions.map(item => item.value), [related],
                   "missing related project must remain selected");
  page.title.value = "仅改标题";
  await page.save();
  assert.equal(page.posted.length, 1);
  assert.equal(page.posted[0].title, "仅改标题");
  assert.equal(Object.hasOwn(page.posted[0], "project_id"), false);
  assert.equal(Object.hasOwn(page.posted[0], "related_project_ids"), false);
});

test("P2: explicitly unassign primary without losing still-unsynced related project", async () => {
  const primary = "PROJECT-" + "C".repeat(32);
  const related = "PROJECT-" + "D".repeat(32);
  const page = taskEditHarness({
    task_id: "TASK-TEST-UNASSIGN", title: "演示任务", status: "todo",
    revision: 1, conflict: false, project_id: primary,
    related_project_ids: [related], project_name: null
  });
  page.primary.value = "";
  await page.save();
  assert.equal(page.posted.length, 1);
  assert.equal(page.posted[0].project_id, null,
               "explicit unassignment must be sent");
  assert.equal(Object.hasOwn(page.posted[0], "related_project_ids"), false,
               "unchanged unsynced related ID must not be cleared");
});


test("M3.2 create submits five independent fields", async () => {
  const page = harness();
  page.type("跟进测试事项");
  page.document.getElementById("new-task-owner").value = "员工甲";
  page.document.getElementById("new-task-priority").value = "high";
  page.document.getElementById("new-task-due").value = "2026-11-20";
  page.document.getElementById("new-task-planned").value = "2026-11-01";
  page.document.getElementById("new-task-follow").value = "2026-11-07";
  const pending = page.save();
  assert.deepEqual(page.posted[0], {
    title: "跟进测试事项", owner: "员工甲", priority: "high",
    due_date: "2026-11-20", planned_date: "2026-11-01",
    follow_up_date: "2026-11-07"
  });
  page.respond();
  await pending;
});

test("M3.2 create keeps changed owner and date drafts after late response", async () => {
  const page = harness();
  page.type("第一项");
  const owner = page.document.getElementById("new-task-owner");
  const nextFollow = page.document.getElementById("new-task-follow");
  owner.value = "员工甲";
  const pending = page.save();
  owner.value = "员工乙";
  nextFollow.value = "2026-11-04";
  page.respond();
  await pending;
  assert.equal(page.input.value, "第一项", "do not erase a draft changed while saving");
  assert.equal(owner.value, "员工乙");
  assert.equal(nextFollow.value, "2026-11-04");
  assert.match(page.message.textContent, /草稿已保留/);
  assert.equal(page.posted[0].owner, "员工甲");
});

test("M3.2 create clears unchanged metadata fields after confirmed save", async () => {
  const page = harness();
  page.type("待办");
  const owner = page.document.getElementById("new-task-owner");
  const priority = page.document.getElementById("new-task-priority");
  const date = page.document.getElementById("new-task-due");
  owner.value = "员工甲"; priority.value = "urgent"; date.value = "2026-11-03";
  const pending = page.save();
  page.respond();
  await pending;
  assert.equal(page.input.value, "");
  assert.equal(owner.value, "");
  assert.equal(priority.value, "normal");
  assert.equal(date.value, "");
});

test("M3.2 edit only follow-up date preserves other metadata and missing project refs", async () => {
  const primary = "PROJECT-" + "A".repeat(32);
  const related = "PROJECT-" + "B".repeat(32);
  const page = taskEditHarness({
    task_id: "TASK-M3-02-EDIT", title: "虚构事项", status: "todo",
    revision: 3, conflict: false, project_id: primary,
    related_project_ids: [related], owner: "员工甲", priority: "high",
    due_date: "2026-12-05", planned_date: "2026-11-01",
    follow_up_date: "2026-11-03"
  });
  page.follow.value = "2026-11-10";
  await page.save();
  assert.equal(page.posted.length, 1);
  const change = page.posted[0];
  assert.equal(change.follow_up_date, "2026-11-10");
  for (const field of ["owner", "priority", "due_date", "planned_date",
                       "project_id", "related_project_ids"]) {
    assert.equal(Object.hasOwn(change, field), false, field + " must be omitted");
  }
});

test("M3.2 edit can clear a date and owner without resetting priority", async () => {
  const page = taskEditHarness({
    task_id: "TASK-M3-02-CLEAR", title: "虚构任务", status: "todo",
    revision: 1, conflict: false, project_id: null,
    related_project_ids: [], owner: "员工乙", priority: "urgent",
    due_date: "2026-11-20", planned_date: null, follow_up_date: null
  });
  page.owner.value = "";
  page.due.value = "";
  await page.save();
  const change = page.posted[0];
  assert.equal(change.owner, null);
  assert.equal(change.due_date, null);
  assert.equal(Object.hasOwn(change, "priority"), false);
});

test("M3.2 legacy task title-only edit sends no new metadata fields", async () => {
  const page = taskEditHarness({
    task_id: "TASK-M3-02-LEGACY", title: "旧任务", status: "todo",
    revision: 1, conflict: false, project_id: null, related_project_ids: []
  });
  page.title.value = "编辑旧任务";
  await page.save();
  const change = page.posted[0];
  assert.equal(change.title, "编辑旧任务");
  for (const key of ["owner", "priority", "due_date", "planned_date", "follow_up_date"]) {
    assert.equal(Object.hasOwn(change, key), false, key + " should not be written");
  }
});


test("M3.3 adds a numbered step through the task-scoped endpoint", async () => {
  const page = taskEditHarness({
    task_id: "TASK-M3-03-ADD", title: "虚构任务", status: "todo",
    revision: 1, conflict: false, project_id: null, related_project_ids: [], steps: []
  });
  const addForm = page.stepPanel.children.find(item => item.className === "step-add-form");
  const input = addForm.children[0];
  input.value = "整理第一份资料";
  await addForm.handlers.get("submit")({preventDefault() {}});
  assert.equal(page.stepCreated.length, 1);
  assert.equal(page.stepCreated[0].path, "/api/tasks/TASK-M3-03-ADD/steps");
  assert.deepEqual(page.stepCreated[0].body, {title: "整理第一份资料"});
});

test("M3.3 keeps a new step draft typed while an earlier step is saving", async () => {
  const page = taskEditHarness({
    task_id: "TASK-M3-03-DRAFT", title: "父任务", status: "todo",
    revision: 1, conflict: false, project_id: null, related_project_ids: [], steps: []
  });
  const addForm = page.stepPanel.children.find(item => item.className === "step-add-form");
  const input = addForm.children[0];
  const message = page.stepPanel.children.find(item => item.className === "step-message");
  input.value = "正在保存的第一步";
  input.handlers.get("input")();
  page.setDelayStepCreate(true);
  const saving = addForm.handlers.get("submit")({preventDefault() {}});
  input.value = "新输入的第二步草稿";
  input.handlers.get("input")();
  page.respondStepCreate();
  await saving;
  assert.equal(input.value, "新输入的第二步草稿");
  assert.match(message.textContent, /草稿已保留/);
  assert.equal(page.stepCreated.length, 1);
});

test("M3.3 edits one step without touching its task or sibling steps", async () => {
  const page = taskEditHarness({
    task_id: "TASK-M3-03-EDIT", title: "父任务", status: "todo",
    revision: 4, conflict: false, project_id: null, related_project_ids: [],
    steps: [
      {step_id: "STEP-" + "A".repeat(32), title: "第一步", status: "todo",
       revision: 1, conflict: false, conflict_fields: []},
      {step_id: "STEP-" + "B".repeat(32), title: "第二步", status: "todo",
       revision: 1, conflict: false, conflict_fields: []}
    ]
  });
  const firstRow = page.stepPanel.children[1].children[0];
  const content = firstRow.children[1];
  const form = content.children.find(item => item.className === "step-edit-form");
  form.children[0].children[0].value = "第一步已修改";
  form.children[1].children[0].value = "doing";
  await form.handlers.get("submit")({preventDefault() {}});
  assert.equal(page.stepUpdated.length, 1);
  assert.match(page.stepUpdated[0].path, /STEP-A{32}\/update$/);
  assert.deepEqual(page.stepUpdated[0].body, {
    revision: 1, title: "第一步已修改", status: "doing"
  });
});

test("M3.3 completing a step requires explicit confirmation", async () => {
  const page = taskEditHarness({
    task_id: "TASK-M3-03-DONE", title: "父任务", status: "todo",
    revision: 1, conflict: false, project_id: null, related_project_ids: [],
    steps: [{step_id: "STEP-" + "C".repeat(32), title: "待确认步骤",
      status: "todo", revision: 1, conflict: false, conflict_fields: []}]
  });
  const form = page.stepPanel.children[1].children[0].children[1]
    .children.find(item => item.className === "step-edit-form");
  form.children[1].children[0].value = "done";
  page.setConfirm(false);
  await form.handlers.get("submit")({preventDefault() {}});
  assert.equal(page.stepUpdated.length, 0);
  page.setConfirm(true);
  await form.handlers.get("submit")({preventDefault() {}});
  assert.equal(page.stepUpdated.length, 1);
  assert.equal(page.stepUpdated[0].body.status, "done");
  assert.equal(page.stepUpdated[0].body.confirmed_done, true);
});

test("M3.3 moving a step submits the complete stable ID order and order revision", async () => {
  const a = "STEP-" + "D".repeat(32);
  const b = "STEP-" + "E".repeat(32);
  const page = taskEditHarness({
    task_id: "TASK-M3-03-ORDER", title: "父任务", status: "todo",
    revision: 1, conflict: false, project_id: null, related_project_ids: [],
    step_order_revision: 3, steps: [
      {step_id: a, title: "甲", status: "todo", revision: 1, conflict: false, conflict_fields: []},
      {step_id: b, title: "乙", status: "todo", revision: 1, conflict: false, conflict_fields: []}
    ]
  });
  const firstRow = page.stepPanel.children[1].children[0];
  const actions = firstRow.children[2];
  await actions.children[1].handlers.get("click")();
  assert.deepEqual(page.stepReordered, [{step_ids: [b, a], revision: 3}]);
});

test("M3.3 partial-sync order references disable reordering but preserve step editing", async () => {
  const a = "STEP-" + "A".repeat(32);
  const b = "STEP-" + "B".repeat(32);
  const page = taskEditHarness({
    task_id: "TASK-M3-03-PARTIAL-SYNC", title: "父任务", status: "todo",
    revision: 1, conflict: false, project_id: null, related_project_ids: [],
    step_order_incomplete: true, step_order_missing_ids: ["STEP-" + "C".repeat(32)],
    steps: [
      {step_id: a, title: "步骤甲", status: "todo", revision: 1, conflict: false, conflict_fields: []},
      {step_id: b, title: "步骤乙", status: "todo", revision: 1, conflict: false, conflict_fields: []}
    ]
  });
  const warning = page.stepPanel.children.find(item => item.className === "step-order-warning");
  assert.ok(warning, "partial synchronization must be visible to the user");
  assert.match(warning.textContent, /尚未同步/);
  const list = page.stepPanel.children.find(item => item.className === "step-list");
  const firstRow = list.children[0];
  const actions = firstRow.children[2];
  assert.equal(actions.children[0].disabled, true);
  assert.equal(actions.children[1].disabled, true);
  await actions.children[1].handlers.get("click")();
  assert.deepEqual(page.stepReordered, [], "incomplete order must not issue a POST");
  const form = firstRow.children[1].children.find(item => item.className === "step-edit-form");
  assert.equal(form.children[0].children[0].disabled, false,
               "partial order synchronization must not freeze step content editing");
});

test("M3.3 a conflicted step is frozen without freezing its sibling", () => {
  const page = taskEditHarness({
    task_id: "TASK-M3-03-CONFLICT", title: "父任务", status: "todo",
    revision: 1, conflict: false, project_id: null, related_project_ids: [],
    steps: [
      {step_id: "STEP-" + "F".repeat(32), title: "冲突步骤", status: "todo",
       revision: 1, conflict: true, conflict_fields: ["title"],
       conflict_candidates: [{changes: {title: "候选甲"}}, {changes: {title: "候选乙"}}]},
      {step_id: "STEP-" + "1".repeat(32), title: "正常步骤", status: "todo",
       revision: 1, conflict: false, conflict_fields: []}
    ]
  });
  const rows = page.stepPanel.children[1].children;
  const conflictedForm = rows[0].children[1].children.find(item => item.className === "step-edit-form");
  const normalForm = rows[1].children[1].children.find(item => item.className === "step-edit-form");
  assert.equal(conflictedForm.children[0].children[0].disabled, true);
  assert.equal(conflictedForm.children[2].disabled, true);
  assert.equal(normalForm.children[0].children[0].disabled, false);
  assert.equal(normalForm.children[2].disabled, false);
});

test("M3.3 an order conflict disables reorder but leaves step editing available", () => {
  const page = taskEditHarness({
    task_id: "TASK-M3-03-ORDER-CONFLICT", title: "父任务", status: "todo",
    revision: 1, conflict: false, project_id: null, related_project_ids: [],
    step_order_conflict: true, step_order_candidates: [{changes: {step_ids: []}}],
    steps: [
      {step_id: "STEP-" + "2".repeat(32), title: "正常步骤", status: "todo",
       revision: 1, conflict: false, conflict_fields: []},
      {step_id: "STEP-" + "3".repeat(32), title: "第二步", status: "todo",
       revision: 1, conflict: false, conflict_fields: []}
    ]
  });
  const list = page.stepPanel.children.find(item => item.className === "step-list");
  const firstRow = list.children[0];
  assert.equal(firstRow.children[2].children[0].disabled, true);
  assert.equal(firstRow.children[2].children[1].disabled, true);
  const form = firstRow.children[1].children.find(item => item.className === "step-edit-form");
  assert.equal(form.children[0].children[0].disabled, false);
});


 
// M3.4: exercise the real overview/query functions with a minimal browser-like DOM.
// The page must work entirely against GET /api/tasks without new write endpoints.
function overviewHarness(tasks, projects = [], allowWrites = false) {
  const elements = new Map();
  const posted = [];
  let confirmValue = true;
  const browser = mockWindow(() => confirmValue);
  function fakeNode(tag = "div") {
    const node = {
      tag, textContent: "", className: "", children: [], handlers: new Map(),
      disabled: false, selected: false, hidden: false, _value: "",
      append(...items) { this.children.push(...items); },
      replaceChildren(...items) { this.children = items; },
      addEventListener(type, handler) { this.handlers.set(type, handler); }
    };
    Object.defineProperty(node, "value", {
      get() {
        return this.tag === "select"
          ? (this.children.find(child => child.selected)?.value ?? "")
          : this._value;
      },
      set(value) {
        this._value = value;
        if (this.tag === "select") for (const child of this.children)
          child.selected = child.value === value;
      }
    });
    Object.defineProperty(node, "selectedOptions", {
      get() { return this.tag === "select" ? this.children.filter(child => child.selected) : []; }
    });
    return node;
  }
  const selectIds = new Set(["overview-owner", "query-project", "query-owner",
                             "query-status", "query-date-field",
                             "new-task-project", "new-task-related", "new-task-priority"]);
  const document = {
    activeElement: null,
    getElementById(id) {
      if (!elements.has(id)) elements.set(id, fakeNode(selectIds.has(id) ? "select" : "div"));
      return elements.get(id);
    },
    createElement: tag => fakeNode(tag)
  };
  const fetch = async (path, options) => {
    if (options?.method === "POST") {
      posted.push(path);
      if (!allowWrites) throw Error("overview must never write");
      const body = JSON.parse(options.body);
      const taskId = decodeURIComponent(path.split("/")[3] || "");
      const task = tasks.find(item => item.task_id === taskId);
      if (path.includes("/steps/") && path.endsWith("/update") && task) {
        const stepId = path.split("/steps/")[1].split("/")[0];
        const step = task.steps.find(item => item.step_id === stepId);
        if (step) Object.assign(step, body);
      } else if (path.endsWith("/steps") && task) {
        task.steps.push({step_id: "STEP-" + "A".repeat(32), title: body.title,
                         status: "todo", revision: 1, conflict: false});
      } else if (path.endsWith("/update") && task) {
        Object.assign(task, body);
      }
      return {ok: true, json: async () => ({
        saved: true, step_id: "STEP-" + "A".repeat(32), revision: 2
      })};
    }
    assert.equal(path, "/api/tasks");
    return {ok: true, json: async () => ({tasks, projects, warnings: []})};
  };
  const api = vm.runInNewContext(match[1] +
    "\n;({overviewDates, matchesOverview, matchesQuery, selectOverview, refresh, openTaskDetail})", {
      document, fetch, setInterval() {}, Date,
      window: browser.window
    }, {timeout: 2000});
  const el = id => document.getElementById(id);
  const submitQuery = () => el("task-query").handlers.get("submit")({preventDefault() {}});
  const resetQuery = () => el("query-reset").handlers.get("click")();
  return {api, el, posted, submitQuery, resetQuery, tasks, projects,
          setConfirm(value) { confirmValue = value; },
          beforeUnload: () => browser.fireBeforeUnload()};
}

function overviewTask(id, extras = {}) {
  return {
    task_id: id, title: "虚构任务" + id, status: "todo", revision: 1,
    conflict: false, owner: null, project_id: null, related_project_ids: [],
    steps: [], ...extras
  };
}

function openTaskEditor(page, taskId) {
  assert.equal(page.api.openTaskDetail(taskId), true, "task detail drawer should open");
  return page.el("task-detail-content").children[0];
}

test("M3.4 local dates include today and next 7 calendar days, including across year boundary", () => {
  const page = overviewHarness([]);
  const dates = page.api.overviewDates(new Date(2026, 11, 28, 23, 30));
  assert.equal(dates.today, "2026-12-28");
  assert.equal(dates.sevenDays, "2027-01-04");
});

test("M3.4 overview separates own work, other followups, near-due and risks without guessing owner", async () => {
  const tasks = [
    overviewTask("TASK-SELF", {owner: "虚构甲", planned_date: "2026-10-01"}),
    overviewTask("TASK-OTHER", {owner: "虚构乙", follow_up_date: "2026-10-02"}),
    overviewTask("TASK-OVERDUE", {due_date: "2026-10-01"}),
    overviewTask("TASK-BLOCKED", {status: "blocked"}),
    overviewTask("TASK-DONE", {status: "done", owner: "虚构甲", planned_date: "2026-10-01", due_date: "2026-10-01"}),
    overviewTask("TASK-CONFLICT", {conflict: true}),
    overviewTask("TASK-DUE", {due_date: "2026-10-31"}),
  ];
  const page = overviewHarness(tasks);
  await page.api.refresh(true);
  assert.equal(page.el("view-mine").disabled, true, "unconfigured identity must not imply user");
  assert.equal(page.el("view-followup-count").textContent, "—");
  const dates = {today: "2026-10-30", sevenDays: "2026-11-06"};
  assert.deepEqual(tasks.filter(t => page.api.matchesOverview(t, "mine", "虚构甲", dates)).map(t => t.task_id),
                   ["TASK-SELF"]);
  assert.deepEqual(tasks.filter(t => page.api.matchesOverview(t, "followup", "虚构甲", dates)).map(t => t.task_id),
                   ["TASK-OTHER"]);
  assert.deepEqual(tasks.filter(t => page.api.matchesOverview(t, "risk", "虚构甲", dates)).map(t => t.task_id),
                   ["TASK-OVERDUE", "TASK-BLOCKED", "TASK-CONFLICT"]);
  assert.deepEqual(tasks.filter(t => page.api.matchesOverview(t, "due", "虚构甲", dates)).map(t => t.task_id),
                   ["TASK-DUE"]);
  assert.equal(page.posted.length, 0);
});

test("M3.4 query matches stable task/step IDs, related projects and inclusive dates", () => {
  const page = overviewHarness([]);
  const task = overviewTask("TASK-ABCD-1234", {
    title: "整理材料", project_id: "PROJECT-MAIN",
    related_project_ids: ["PROJECT-RELATED"], status: "doing",
    owner: "虚构采购员", due_date: "2026-11-06",
    steps: [{step_id: "STEP-XYZ-1234", title: "核对附件"}]
  });
  const query = {keyword: "step-xyz", project: "PROJECT-RELATED",
    status: "doing", owner: "虚构采购员", dateField: "due_date",
    dateFrom: "2026-11-06", dateTo: "2026-11-06"};
  assert.equal(page.api.matchesQuery(task, query), true);
  assert.equal(page.api.matchesQuery(task, {...query, keyword: "附件"}), true);
  assert.equal(page.api.matchesQuery(task, {...query, keyword: "task-abcd"}), true);
  assert.equal(page.api.matchesQuery(task, {...query, keyword: "无关"}), false);
  assert.equal(page.api.matchesQuery(task, {...query, owner: "__none__"}), false);
  assert.equal(page.api.matchesQuery(task, {...query, project: "__none__"}), false);
  assert.equal(page.api.matchesQuery(task, {...query, dateFrom: "2026-11-07"}), false);
  assert.equal(page.api.matchesQuery(task, {...query, dateTo: "2026-11-05"}), false);
  assert.equal(page.api.matchesQuery({...task, conflict: true}, query), false,
               "conflicted task status must not be trusted");
  assert.equal(page.api.matchesQuery({...task, conflict: true}, {...query, status: "conflict"}), true);
});

test("M3.4 rendered query preserves input and applies filters only on explicit submit", async () => {
  const tasks = [
    overviewTask("TASK-ALPHA", {title: "虚构：紧急合同", owner: "员工甲"}),
    overviewTask("TASK-BETA", {title: "虚构：日常记录", owner: "员工乙"})
  ];
  const page = overviewHarness(tasks);
  await page.api.refresh(true);
  assert.equal(page.el("query-result-count").textContent, "（2 / 2）");
  page.el("query-keyword").value = "紧急";
  assert.equal(page.el("query-result-count").textContent, "（2 / 2）");
  page.submitQuery();
  assert.equal(page.el("query-result-count").textContent, "（1 / 2）");
  page.el("query-keyword").value = "   ";
  page.submitQuery();
  assert.equal(page.el("query-result-count").textContent, "（2 / 2）");
  assert.equal(page.posted.length, 0);
});

test("M3.4 invalid date range retains prior valid query and reset recovers all tasks", async () => {
  const page = overviewHarness([
    overviewTask("TASK-M34-A", {title: "A"}),
    overviewTask("TASK-M34-B", {title: "B"})
  ]);
  await page.api.refresh(true);
  page.el("query-keyword").value = "不存在";
  page.submitQuery();
  assert.equal(page.el("query-result-count").textContent, "（0 / 2）");
  page.el("query-keyword").value = "A";
  page.el("query-date-from").value = "2026-11-12";
  page.el("query-date-to").value = "2026-11-01";
  page.submitQuery();
  assert.match(page.el("query-message").textContent, /结束日期不得早于起始日期/);
  assert.equal(page.el("query-result-count").textContent, "（0 / 2）");
  page.resetQuery();
  assert.equal(page.el("query-result-count").textContent, "（2 / 2）");
  assert.equal(page.el("query-date-from").value, "");
  assert.equal(page.posted.length, 0);
});

test("M3.4 selected self owner remains local to UI and survives refresh without POST", async () => {
  const page = overviewHarness([
    overviewTask("TASK-M34-OWN", {owner: "虚构甲", planned_date: "2025-01-01"}),
    overviewTask("TASK-M34-OTHER", {owner: "虚构乙", follow_up_date: "2025-01-01"})
  ]);
  await page.api.refresh(true);
  page.el("overview-owner").value = "虚构甲";
  page.el("overview-owner").handlers.get("change")();
  assert.equal(page.el("view-mine").disabled, false);
  page.el("view-mine").handlers.get("click")();
  assert.equal(page.el("query-result-count").textContent, "（1 / 2）");
  await page.api.refresh(true);
  assert.equal(page.el("overview-owner").value, "虚构甲");
  assert.equal(page.el("query-result-count").textContent, "（1 / 2）");
  assert.equal(page.posted.length, 0);
});

test("M3.4 filter changes and refresh never silently discard unsaved task edits", async () => {
  const page = overviewHarness([
    overviewTask("TASK-ONE", {title: "原始任务"}),
    overviewTask("TASK-TWO", {title: "另一项任务"})
  ]);
  await page.api.refresh(true);
  const group = page.el("tasks").children[0];
  const card = group.children[1];
  const form = card.children.find(item => item.className === "task-form");
  const titleInput = form.children[0].children[0];
  titleInput.value = "还没有保存的修改";
  form.handlers.get("input")();
  page.setConfirm(false);

  page.el("view-risk").handlers.get("click")();
  assert.equal(page.el("query-result-count").textContent, "（2 / 2）",
               "declined navigation must not change visible task list");
  assert.equal(page.el("tasks").children[0].children[1], card,
               "same edit DOM must remain mounted");
  assert.equal(titleInput.value, "还没有保存的修改");

  page.el("query-keyword").value = "不匹配";
  page.submitQuery();
  assert.equal(page.el("query-result-count").textContent, "（2 / 2）");
  await page.api.refresh(false);
  assert.equal(page.el("tasks").children[0].children[1], card,
               "background refresh must not discard dirty draft");
  assert.match(page.el("sync").textContent, /尚未保存/);
  assert.equal(page.posted.length, 0);

  page.setConfirm(true);
  page.submitQuery();
  assert.equal(page.el("query-result-count").textContent, "（0 / 2）",
               "explicitly confirmed navigation may replace the edit DOM");
});

test("M3.4 new step drafts are also protected from view switching", async () => {
  const page = overviewHarness([overviewTask("TASK-STEP-DRAFT")]);
  await page.api.refresh(true);
  const card = page.el("tasks").children[0].children[1];
  const panel = card.children.find(item => item.className === "steps-panel");
  const addForm = panel.children.find(item => item.className === "step-add-form");
  const input = addForm.children[0];
  input.value = "新增草稿尚未保存";
  addForm.handlers.get("input")();
  page.setConfirm(false);
  page.el("view-risk").handlers.get("click")();
  assert.equal(page.el("tasks").children[0].children[1], card);
  assert.equal(input.value, "新增草稿尚未保存");
  assert.equal(page.posted.length, 0);
});


test("M3.4 browser reload prompts for an unsaved new-task form, but not after reset or save", async () => {
  const page = harness();
  assert.equal(page.beforeUnload().prevented, false, "clean page must not prompt");
  page.type("尚未保存的新任务");
  const blocked = page.beforeUnload();
  assert.equal(blocked.prevented, true);
  assert.equal(blocked.returnValue, "", "beforeunload must request the native browser prompt");

  page.type("已保存的新任务");
  const saving = page.save();
  page.respond();
  await saving;
  assert.equal(page.beforeUnload().prevented, false, "successful save and form reset remove the prompt");
});

test("M3.4 new-task form clears beforeunload when every field returns to its original value", () => {
  const page = harness();
  const form = page.document.getElementById("create-task");
  const cases = [
    ["new-task-title", "虚构标题", ""],
    ["new-task-project", "PROJECT-FAKE-001", ""],
    ["new-task-related", [{value: "PROJECT-FAKE-002"}], []],
    ["new-task-owner", "虚构负责人", ""],
    ["new-task-priority", "high", ""],
    ["new-task-due", "2030-02-03", ""],
    ["new-task-planned", "2030-02-04", ""],
    ["new-task-follow", "2030-02-05", ""]
  ];
  const setField = (id, value) => {
    const field = page.document.getElementById(id);
    if (id === "new-task-related") field.selectedOptions = value;
    else field.value = value;
    form.handlers.get(
      ["new-task-project", "new-task-related", "new-task-priority"].includes(id)
        ? "change" : "input"
    )();
  };

  assert.equal(page.beforeUnload().prevented, false);
  for (const [id, changed, original] of cases) {
    setField(id, changed);
    assert.equal(page.beforeUnload().prevented, true, id + " must mark the form dirty");
    setField(id, original);
    assert.equal(page.beforeUnload().prevented, false,
                 id + " restored to its original value must clear the dirty flag");
  }

  for (const [id, changed] of cases) setField(id, changed);
  assert.equal(page.beforeUnload().prevented, true,
               "multiple changed fields must request browser confirmation");
  for (const [id, , original] of cases) setField(id, original);
  assert.equal(page.beforeUnload().prevented, false,
               "restoring every field must clear the form dirty flag");

  setField("new-task-owner", "虚构负责人");
  setField("new-task-due", "2030-02-03");
  setField("new-task-owner", "");
  assert.equal(page.beforeUnload().prevented, true,
               "one remaining changed field must continue to protect the form");
  setField("new-task-due", "");
  assert.equal(page.beforeUnload().prevented, false,
               "restoring the last changed field must clear protection");
});

test("M3.4 browser reload prompts for dirty task and step edits, and clears after successful saves", async () => {
  const task = overviewTask("TASK-BEFOREUNLOAD", {
    title: "原始任务标题",
    steps: [{
      step_id: "STEP-" + "B".repeat(32), title: "原始步骤内容",
      status: "todo", revision: 1, conflict: false
    }]
  });
  const page = overviewHarness([task], [], true);
  await page.api.refresh(true);
  assert.equal(page.beforeUnload().prevented, false, "clean task and step forms must not prompt");

  let card = openTaskEditor(page, task.task_id);
  let taskForm = card.children.find(item => item.className === "task-form");
  let taskTitle = taskForm.children[0].children[0];
  taskTitle.value = "未保存的任务标题";
  taskForm.handlers.get("input")();
  const taskBlocked = page.beforeUnload();
  assert.equal(taskBlocked.prevented, true);
  assert.equal(taskBlocked.returnValue, "");

  taskTitle.value = "原始任务标题";
  taskForm.handlers.get("input")();
  assert.equal(page.beforeUnload().prevented, false,
               "reverting the task editor to its clean snapshot removes the prompt");

  taskTitle.value = "已保存的任务标题";
  taskForm.handlers.get("input")();
  await taskForm.handlers.get("submit")({preventDefault() {}});
  assert.equal(page.beforeUnload().prevented, false,
               "successful task save clears the dirty editor before rerender");

  card = page.el("task-detail-content").children[0];
  let panel = card.children.find(item => item.className === "steps-panel");
  let stepList = panel.children.find(item => item.className === "step-list");
  let stepRow = stepList.children.find(item => item.className === "step-row");
  let stepForm = stepRow.children[1].children.find(item => item.className === "step-edit-form");
  let stepTitle = stepForm.children[0].children[0];
  stepTitle.value = "未保存的步骤内容";
  stepForm.handlers.get("input")();
  assert.equal(page.beforeUnload().prevented, true,
               "editing an existing step must request browser confirmation");

  stepTitle.value = "原始步骤内容";
  stepForm.handlers.get("input")();
  assert.equal(page.beforeUnload().prevented, false,
               "reverting the step editor to its clean snapshot removes the prompt");

  stepTitle.value = "已保存的步骤内容";
  stepForm.handlers.get("input")();
  await stepForm.handlers.get("submit")({preventDefault() {}});
  assert.equal(page.beforeUnload().prevented, false,
               "successful step save clears the dirty editor before rerender");

  card = page.el("task-detail-content").children[0];
  panel = card.children.find(item => item.className === "steps-panel");
  const addForm = panel.children.find(item => item.className === "step-add-form");
  const addInput = addForm.children[0];
  addInput.value = "未保存的新增步骤";
  addForm.handlers.get("input")();
  assert.equal(page.beforeUnload().prevented, true,
               "a new step draft must also request browser confirmation");

  addInput.value = "";
  addForm.handlers.get("input")();
  assert.equal(page.beforeUnload().prevented, false,
               "clearing the new step input removes the prompt");

  addInput.value = "已保存的新增步骤";
  addForm.handlers.get("input")();
  await addForm.handlers.get("submit")({preventDefault() {}});
  assert.equal(page.beforeUnload().prevented, false,
               "successful step creation clears the dirty editor before rerender");
});


test("M3.4 successful task save advances the clean baseline in the detail drawer", async () => {
  const task = overviewTask("TASK-SAVED-A", {title: "保存前标题X"});
  const page = overviewHarness([task], [], true);
  await page.api.refresh(true);
  const card = openTaskEditor(page, task.task_id);
  const form = card.children.find(node => node.className === "task-form");
  const title = form.children[0].children[0];

  title.value = "保存成功的新标题Y";
  form.handlers.get("input")();
  await form.handlers.get("submit")({preventDefault() {}});
  assert.equal(task.title, "保存成功的新标题Y", "the server has persisted Y");
  assert.equal(page.beforeUnload().prevented, false,
               "successful save should establish a clean persisted baseline");

  const refreshedCard = page.el("task-detail-content").children[0];
  const refreshedForm = refreshedCard.children.find(node => node.className === "task-form");
  const refreshedTitle = refreshedForm.children[0].children[0];
  refreshedTitle.value = "保存前标题X";
  refreshedForm.handlers.get("input")();
  assert.equal(page.beforeUnload().prevented, true,
               "reverting to the pre-save value is a new unsaved edit against persisted Y");
  assert.equal(refreshedTitle.value, "保存前标题X",
               "the new draft remains present until the user chooses whether to leave");
});

test("M3.4 successful step save advances the clean baseline in the detail drawer", async () => {
  const task = overviewTask("TASK-STEP-SAVED", {
    title: "步骤所属任务",
    steps: [{step_id: "STEP-SAVED-BASELINE", title: "保存前步骤X",
             status: "todo", revision: 1, conflict: false}]
  });
  const page = overviewHarness([task], [], true);
  await page.api.refresh(true);
  const card = openTaskEditor(page, task.task_id);
  const panel = card.children.find(node => node.className === "steps-panel");
  const stepRow = panel.children.find(node => node.className === "step-list")
    .children.find(node => node.className === "step-row");
  const stepForm = stepRow.children[1].children.find(node => node.className === "step-edit-form");
  const stepTitle = stepForm.children[0].children[0];

  stepTitle.value = "保存成功的新步骤Y";
  stepForm.handlers.get("input")();
  await stepForm.handlers.get("submit")({preventDefault() {}});
  assert.equal(task.steps[0].title, "保存成功的新步骤Y");
  assert.equal(page.beforeUnload().prevented, false,
               "successful step save should establish a clean persisted baseline");

  const refreshedCard = page.el("task-detail-content").children[0];
  const refreshedPanel = refreshedCard.children.find(node => node.className === "steps-panel");
  const refreshedRow = refreshedPanel.children.find(node => node.className === "step-list")
    .children.find(node => node.className === "step-row");
  const refreshedForm = refreshedRow.children[1].children.find(node => node.className === "step-edit-form");
  const refreshedTitle = refreshedForm.children[0].children[0];
  refreshedTitle.value = "保存前步骤X";
  refreshedForm.handlers.get("input")();
  assert.equal(page.beforeUnload().prevented, true,
               "reverting to the pre-save value remains an unsaved edit");
});

test("update center displays the installed version and checks the fixed latest build", async () => {
  const page = harness();
  await new Promise(resolve => setImmediate(resolve));
  assert.match(page.document.getElementById("app-version").textContent, /v1\.0\.0/);
  assert.match(page.document.getElementById("app-version").textContent, /abcdef0/);

  await page.document.getElementById("check-update").handlers.get("click")();
  assert.deepEqual(page.updateCalls, ["check"]);
  assert.equal(page.document.getElementById("apply-update").hidden, false);
  assert.equal(page.document.getElementById("apply-update").disabled, false);
  assert.match(page.document.getElementById("update-message").textContent, /1\.1\.0/);
});

test("update UI never starts while a task draft is unsaved", async () => {
  const page = harness();
  await new Promise(resolve => setImmediate(resolve));
  page.type("保留的虚构任务草稿");
  await page.document.getElementById("check-update").handlers.get("click")();
  await page.document.getElementById("apply-update").handlers.get("click")();
  assert.deepEqual(page.updateCalls, ["check"]);
  assert.match(page.document.getElementById("update-message").textContent, /先保存或处理未保存/);
});
