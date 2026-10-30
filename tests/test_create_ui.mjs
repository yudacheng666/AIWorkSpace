// Regression tests for the real inline new-task form (no browser or dependencies needed).
import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
import {test} from "node:test";
import vm from "node:vm";

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
  const fetch = async (path, options) => {
    if (path === "/api/tasks" && options?.method === "POST") {
      posted.push(JSON.parse(options.body));
      return pendingResponse;
    }
    if (path === "/api/projects" && options?.method === "POST") {
      projectPosted.push(JSON.parse(options.body));
      return {ok: true, json: async () => ({saved: true, project_id: "PROJECT-MOCK-001"})};
    }
    assert.equal(path, "/api/tasks");
    return {ok: true, json: async () => ({tasks: [], projects: [], warnings: []})};
  };
  vm.runInNewContext(match[1], {
    document, fetch, setInterval() {}, Date,
  }, {timeout: 2000});

  const input = document.getElementById("new-task-title");
  const message = document.getElementById("create-message");
  const submit = document.getElementById("create-submit");
  const form = document.getElementById("create-task");
  const type = (value) => {
    input.value = value;
    input.handlers.get("input")();
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
          projectInput, createProject, document};
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
  const fetch = async (path, options) => {
    if (path.endsWith("/update") && options?.method === "POST") {
      posted.push(JSON.parse(options.body));
      return {ok: true, json: async () => ({saved: true})};
    }
    assert.equal(path, "/api/tasks");
    return {ok: true, json: async () => ({tasks: [], projects: [], warnings: []})};
  };
  const {row} = vm.runInNewContext(match[1] + "\n;({row})", {
    document, fetch, setInterval() {}, Date, window: {confirm: () => true}
  }, {timeout: 2000});
  const card = row(task);
  const form = card.children.find(item => item.className === "task-form");
  assert.ok(form, "task edit form must exist");
  const [titleLabel, statusLabel, primaryLabel, relatedLabel] = form.children;
  const title = titleLabel.children[0];
  const status = statusLabel.children[0];
  const primary = primaryLabel.children[0];
  const related = relatedLabel.children[0];
  const save = () => form.handlers.get("submit")({preventDefault() {}});
  return {title, status, primary, related, save, posted};
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
