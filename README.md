# AIWorkSpace

个人 AI 工作台，先验证 **ChatGPT → Google Drive → 本地网页 → Google Drive → ChatGPT** 的任务闭环。不需要额外的 Google Cloud 项目、付费 API 或第三方 Python 库。

**当前阶段：** M1 与 M2 技术基线已合入 `main`（PR #2 squash commit `d31f0e2d`）。M3.1 项目结构与任务归属正在 PR #3 开发，尚未合并。当前仍是逐步扩展中的个人工作台，不是完整团队管理系统。

## 先在 Windows 运行

1. 安装 Google Drive 桌面版，确认你能在 Windows 文件资源管理器中看到同步文件夹。选择一个**不在 GitHub 仓库内**的个人数据目录，例如 `X:\\My Drive\\AIWorkSpaceData`（此处是示例路径，请换成你自己的）。
2. 在这个个人目录下建立 `events` 子文件夹，等待 Drive 同步。不要向公开 GitHub 提交这个目录内的任何数据。
3. 在已安装 Python 3 的 Windows 电脑上，进入下载的 `AIWorkSpace` 代码文件夹，运行：

   ```powershell
   python app.py --data-dir "X:\\My Drive\\AIWorkSpaceData"
   ```

4. 浏览器打开 `http://127.0.0.1:8770/`。初次没有事件文件时显示空任务列表，这是正常情况。

本地服务只监听 `127.0.0.1`，不提供公网访问。关闭运行窗口会停止网页服务；数据文件不会随之删除。

## M2：网页直接新建任务（PR #2 已合并）

打开本机工作台后，在页面顶部的「新建任务」输入名称，点击「创建任务」：
- 系统自动生成一个稳定的 `TASK-<UUID>` 编号；初始状态统一是「待处理」。
- 服务端只接受任务名称，不能通过浏览器新建接口伪造用户完成确认、指定任务 ID 或写入其他字段。
- 新任务作为独立 JSON 创建事件原子发布到现有 `events` 目录，原事件不覆盖；页面显示编号并刷新列表。
- 如果创建结果不明确，请先刷新并核查列表，避免盲目重复提交。

**状态与限制：** 本功能已合入 `main`，并在公司 Windows 电脑完成实际新建、刷新和 Drive 同步验证。ChatGPT 经已授权 Google Drive 连接器创建并上传 JSON 事件，也已实际同步至公司工作台并显示；目前使用临时 Google Doc → 导出 → 上传的连接器工作流，不是后台自动运行的实时 AI 服务。

## M3.1：项目与任务归属（PR #3 开发中，未合并）

- 项目作为轻量独立记录，拥有稳定的 `PROJECT-<UUID>` 编号；支持创建和重命名，不提供删除，避免误删关联。
- 项目事件追加保存到数据目录的 `project_events/`；每次修改新增 JSON，不覆盖旧事件。
- 任务可设置一个主要所属项目及多个关联项目；没有项目的任务保留在“未归类 / 收件箱”。
- 网页按主要项目分组显示任务；可创建/重命名项目，并在任务新建或编辑时设置主要项目和关联项目。
- 旧版任务事件没有项目字段时继续作为未归类任务读取，不要求迁移或改写旧 JSON。
- 若任务事件先于其项目事件同步到本机，任务仍显示，同时提示项目引用尚未同步/需核查。

ChatGPT 创建项目时，先向 `project_events/` 写入独立项目创建事件，再写入引用该项目 ID 的任务事件。项目创建事件示例：

```json
{
  "version": 1,
  "event_id": "project-event-0001",
  "project_id": "PROJECT-AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
  "action": "create",
  "actor": "chatgpt",
  "base_revision": 0,
  "timestamp": "2026-10-30T00:00:00Z",
  "changes": {
    "name": "虚构项目名称"
  }
}
```

任务事件的 `changes` 可选包含 `project_id` 和 `related_project_ids`。项目名称修改通过相同项目 ID 的新 update 事件完成，`base_revision` 使用当前项目 revision。

## 第一次双向测试

1. 让 ChatGPT 使用你已授权的 **Google Drive 连接器**，在同一个云端 `AIWorkSpaceData/events` 目录创建一个独立的 `.json` 任务事件文件。每次事件的文件名、`event_id` 都必须唯一。**禁止把真实任务放在本仓库。**
2. 等待 Google Drive 桌面版把文件同步到 Windows，网页点击“刷新任务”后应看到新事项。
3. 在网页改任务名称或状态，点击“保存修改”；应用会追加新的事件文件，**不覆盖以前的事件文件**。
4. 等待新的文件同步回 Google Drive，再让 ChatGPT 读取云端事件文件，核对最新任务状态。ChatGPT 不会在后台自动读取，需要在对话中明确触发。

首次虚构创建事件示例（保存为一个独立的 `.json` 文件）：

```json
{
  "version": 1,
  "event_id": "demo-event-0001",
  "task_id": "TASK-DEMO-001",
  "action": "create",
  "actor": "chatgpt",
  "base_revision": 0,
  "timestamp": "2026-10-27T00:00:00Z",
  "changes": {
    "title": "虚构：安排一次阅读",
    "status": "todo"
  }
}
```

允许的状态：`todo`（待处理）、`doing`（进行中）、`blocked`（受阻）、`done`（已完成）。任务只允许用户在网页明确确认后设为已完成。同一任务的同一版本出现两次修改时，页面提示冲突并停止自动覆盖，需人工处理。当前部署目标是单台公司 Windows 电脑；不把第二台电脑测试列为本阶段门槛。

## 自测与边界

```powershell
python -m unittest discover -s tests -v
node --test tests/test_create_ui.mjs
```

M2 的 CI 在 Linux 和 Windows 分别运行 30 项 Python 测试与 5 项 Node UI 回归测试；其中包含新建任务、并发/输入验证、后续草稿保留和 UTF-8 BOM 读取。正式验收以 PR 的最新代码和 CI 为准。

- 代码：`app.py`、`web/index.html`；测试：`tests/test_app.py`。
- 无登录、无外网服务、无自动提醒、无多用户权限；M3.1 项目结构仍在 PR #3 开发中。负责人、优先级、截止/计划/跟进日期、执行步骤、工作总览和搜索仍属于后续阶段。
- 首版的文件同步**不是实时数据库**。遇到 Drive 延迟、重复创建或并发修改可能需要刷新与人工核查。
- 不要将 API 密钥、凭证、个人资料、真实台账或 Google Drive 私有链接提交到此 Public 仓库。

## 项目文档和 AI 开发交接

- [确认过的需求](docs/REQUIREMENTS.md)
- [当前进展与下一步](docs/PROJECT_STATE.md)
- [重要决策](docs/DECISIONS.md)
- [AI 协作规则](AGENTS.md)
