# AIWorkSpace

个人 AI 工作台，先验证 **ChatGPT → Google Drive → 本地网页 → Google Drive → ChatGPT** 的任务闭环。不需要额外的 Google Cloud 项目、付费 API 或第三方 Python 库。

**当前阶段：** M1/M2/M3.1/M3.2/M3.3/M3.4 均已合入 `main`。M3.4 [PR #6](https://github.com/yudacheng666/AIWorkSpace/pull/6) 已于 2026-10-30 经用户批准 Squash 合并，合并提交 `5916744898ac3de1b82c4edf27c339ec9a0173c1`。固定产品/原测试 SHA `eb035c611a592cc01dc7b02138a4951b32a69036` 的 Linux/Windows CI 均 SUCCESS（224 PASS / 0 FAIL）；Codex 第四轮真实 Chromium 独立复验 PASS（已测范围），Node 定向 5 PASS，74 次整页刷新前后事件文件名及字节一致。当前新增独立功能阶段：内置软件更新中心 [Draft PR #7](https://github.com/yudacheng666/AIWorkSpace/pull/7)，Codex Linux 隔离独立验收 PASS；GitHub-hosted Windows Runner 使用真实 app.py + Chromium 完成网页一键更新/重启和失败回滚 E2E（2 PASS），双平台 CI 全部 SUCCESS。真实 GitHub main 下载/登记需合并后再隔离验证；公司 Windows 8770 未升级，真实 Drive 未访问，PR 尚未合并/部署。

## 软件更新中心（PR #7，尚未合并）

- 当前版本 `1.0.0` 与短 build SHA 会在页面显示；检查固定 GitHub main 的最新版后，可在网页中申请一键更新。
- 下载、校验、备份、安装、重启及失败回滚仅操作白名单程序文件；任务/项目/步骤事件数据目录不参与更新。
- [Codex Linux 独立验收](https://github.com/yudacheng666/AIWorkSpace/pull/7#issuecomment-6524335908) PASS（已测范围）；[CI #41073083681](https://github.com/yudacheng666/AIWorkSpace/actions/runs/41073083681) 的 GitHub-hosted Windows Runner 使用真实 app.py、updater helper 和 Chromium，完成一键更新成功及启动失败回滚 **2 PASS**，并上传[截图、Playwright trace、日志及数据哈希证据](https://github.com/yudacheng666/AIWorkSpace/actions/runs/41073083681/artifacts/12986271493)。此前 Windows helper mock 服务专项仍保留为单元级补充，不冒充网页 E2E。
- **发布限制**：Windows 隔离 E2E 只 mock 固定 GitHub 官方 API/raw/zipball 响应；PR #7 未合并前 `main` 不存在 `VERSION`，真实 main 下载/版本登记仍需合并后在隔离环境验证。公司 Windows 8770、真实 Drive、企业网络及长期运行尚未验证或部署。

## M3.4：首页工作总览与查询（已合入 main，尚未部署）

- 新的首页「工作总览」卡片直接从现有 `GET /api/tasks` 数据计算，不产生任务更新，也不在后台额外写入事件。
- 今日亲自处理：先在页面上从现有负责人名单选定“我”，仅统计该负责人名下**计划执行日期小于或等于今天**、且尚未完成和未冲突的任务；如果不选择本人，则显示“—”，不猜测身份。
- 跟进他人：选定“我”后，统计**有其他负责人、下次跟进日期已到**、且尚未完成和未冲突的任务。
- 七天内到期：截止日期从本地今天到含第 7 天，不含已经逾期、已完成或处于未裁决冲突的任务。逾期／受阻／冲突分类包括截止已过、状态受阻以及未裁决任务。
- 现有模型没有审批类型或“待审核/决策”标识；页面只显示**无法可靠自动统计**的提示，不伪造 0 条或套用优先级。
- 多条件查询支持任务/步骤的稳定编号与名称关键词、主要或关联项目、任务状态、负责人、三个日期字段之一的起止日期（含边界）；查询条件按“应用筛选”生效，可以清除。筛选只影响显示，不写事件、不会改变任务状态。
- 切换总览卡片、应用查询、清除筛选或手动刷新之前，若现有任务/步骤有未保存草稿，需要明确确认才会放弃；自动刷新则暂缓重绘，避免静默丢失输入。浏览器整页刷新、关闭或离开页面时，也通过原生 `beforeunload` 确认保护任务与步骤草稿；只有草稿确实未保存时才提示，保存成功或恢复干净状态后不提示。前两轮修复已通过双平台自动化回归。第三轮修复确保任务/步骤保存成功时，将 watcher 的 clean baseline 推进到该次成功提交的确切快照，并重新比较当前表单值；即使兄弟草稿阻止列表重绘，后续改回保存前旧值也会继续触发 beforeunload。保存请求期间产生的新输入也继续保持 dirty。最新双平台 CI 224 PASS；第四轮 Codex 独立 Chromium 复验 PASS（已测范围），Node 定向 5 PASS、74 次整页刷新事件文件完整性检查 PASS。前三轮发现的三项草稿保护 P2 均已修复并通过指定路径复验。筛选操作本身不保存任务。
- 目前全部在浏览器内计算和筛选；本地时钟、尚未同步/缺失的任务字段可能影响提示结果。没有远程访问、自动推送、身份认证或审批流程；用户选择“我的负责人”只保存在当前页面，不写入 Google Drive。**尚未测试**：公司 Windows 原生 M3.4、真实 Drive、Windows 原生 IME、其他浏览器、多客户端、长期/断电耐久性、远程访问/部署；物理键盘 F5 与关闭窗口未实测，整页离开保护以真实 Chromium `Page.reload` 验证。M3.4 合并不代表部署。

## 软件更新中心（开发中，尚未合并/部署）

- 工作台显示语义版本号（VERSION）与构建短 SHA；检查更新时读取固定公开仓库 yudacheng666/AIWorkSpace 的 main 最新 commit。
- 用户手动点击“检查更新”后，如有新构建，再点击“立即更新”。更新只从 GitHub 下载固定 commit 的 ZIP，不接受任意 URL、分支或用户输入的下载地址；不需要 GitHub Token、额外云服务或付费 API。
- 更新包只允许安装 app.py、updater.py、VERSION、web/index.html。压缩包会检查大小、CRC、路径穿越、符号链接、重复/缺失文件、commit 目录标识及 Python 语法；不执行远程任意脚本。
- 安装前将上述程序文件及本机版本元数据备份到用户目录下的独立备份位置；使用暂存目录和逐文件原子替换。启动新版本后验证本机 API 返回目标 commit；安装或启动失败时自动回滚旧程序。
- 更新通过独立 helper 等待旧服务退出，再安装并按原 --data-dir、端口重新启动。更新前若页面存在未保存任务/步骤草稿，网页会阻止更新，要求先处理草稿。
- **数据保护边界**：更新器检查程序目录与 --data-dir 不重叠；只写程序白名单及本机隐藏构建/更新状态文件，绝不读取、覆盖、删除或搬迁 events/、project_events/、step_events/。备份不放入数据目录。
- 初次从 GitHub ZIP 安装时没有本机登记的构建 SHA，版本区显示“未登记”；第一次检查会提示当前 main 构建可安装，点击更新后登记精确 commit。之后按本机 SHA 与 main SHA 判断是否需要更新。
- 当前 VERSION 为 1.0.0；每次 main 提交都以短 SHA 区分构建，语义版本号在正式产品版本变化时维护。仅检查更新，不会在后台自动下载或安装。
- 本功能合并并经独立验收前，仍按原方式运行当前版本；**不得把分支中的更新能力当成公司电脑已具备**。更新器实际 Windows 自动重启、文件锁、真实数据目录隔离和失败回滚，需在隔离虚构目录及 Windows 专项验收后才能用于公司电脑。

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
- M2 最初只接受任务名称；M3.1 增加项目关联；M3.2 增加可选负责人、优先级、截止/计划/跟进三个独立日期。浏览器不能伪造用户完成确认或指定任务 ID。
- 新任务作为独立 JSON 创建事件原子发布到现有 `events` 目录，原事件不覆盖；页面显示编号并刷新列表。
- 如果创建结果不明确，请先刷新并核查列表，避免盲目重复提交。

**状态与限制：** 本功能已合入 `main`，并在公司 Windows 电脑完成实际新建、刷新和 Drive 同步验证。ChatGPT 经已授权 Google Drive 连接器创建并上传 JSON 事件，也已实际同步至公司工作台并显示；目前使用临时 Google Doc → 导出 → 上传的连接器工作流，不是后台自动运行的实时 AI 服务。

## M3.1：项目与任务归属（PR #3 已合并）

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

## M3.2：任务管理字段（PR #4 已合并）

- 负责人：`owner`，自由文本（最多 100 字），可为空；空值在事件中表示 `null`。目前不引入成员名册、登录或团队权限。
- 优先级：`priority`，可选 `low`（低）、`normal`（普通，默认）、`high`（高）、`urgent`（紧急）。
- 三个互不混用的**日历日期**（YYYY-MM-DD，无时间与时区）：
  - `due_date`：任务必须完成的截止日期。
  - `planned_date`：计划开始处理/执行任务的日期。
  - `follow_up_date`：计划下次跟进或催办的日期。
- 日期均可留空（`null`），**不做任意日期的自动推断**。用户可独立修改或清除其中一个日期，不会改变其他日期，也不隐式修改任务状态。
- 新建与编辑网页均提供上述字段；只有实际设置/修改的字段才追加到 `events/` 中的新 JSON 事件，旧事件永不修改。
- 既有任务事件没有这些字段时，展示为「负责人未指定、普通优先级、三个日期未设置」，无需迁移。
- ChatGPT 可以在已授权情况下使用相同字段写入合法任务事件，但完成状态仍仅允许用户确认。编号执行步骤已在 M3.3 实现并合并；自动提醒、团队权限和综合仪表盘属于后续阶段。
- 事件示例（**虚构数据**）：

```json
{
  "version": 1,
  "event_id": "sample-m3-02-0001",
  "task_id": "TASK-M3-02-DEMO",
  "action": "create",
  "actor": "chatgpt",
  "base_revision": 0,
  "timestamp": "2026-10-30T00:00:00Z",
  "changes": {
    "title": "虚构项目跟进",
    "status": "todo",
    "owner": "员工甲",
    "priority": "high",
    "due_date": "2026-11-20",
    "planned_date": "2026-11-01",
    "follow_up_date": "2026-11-07"
  }
}
```

## M3.3：编号执行步骤（PR #5 已合并，尚未部署到公司电脑）

- 每项任务可拆分最多 100 个执行步骤；每一步有稳定编号 `STEP-<32位大写十六进制>`，与显示顺序分开保存。
- 步骤名称 1–200 字；状态沿用任务状态：`todo`（待处理）、`doing`（进行中）、`blocked`（受阻）、`done`（已完成）。
- 新建步骤时记录创建顺序；网页可用“上移/下移”调整顺序。顺序调整以一条包含完整步骤编号序列的事件保存，避免同时写多个步骤造成半完成排序。
- 如果当前排序事件引用了尚未同步到本机的 STEP ID，页面会提示等待同步并暂停排序；服务端也会拒绝不完整排序（HTTP 409）。缺失步骤同步后，原排序事件会自动恢复完整顺序，不需要重写历史。
- 每个步骤拥有独立 revision；编辑只追加该步骤的新事件，不改写父任务或其他步骤。并发同版本修改会冻结涉事步骤；顺序冲突只冻结排序，不冻结步骤内容读取/编辑。
- 步骤标记完成必须用户在网页明确确认；ChatGPT 可以新增步骤或更新非完成状态，不能自行将步骤设为已完成。
- 步骤事件写入数据目录的 `step_events/`，与任务 `events/`、项目 `project_events/` 分开。目录首次写入时自动创建；旧任务没有步骤时显示空列表，无需迁移。
- 不支持删除步骤或嵌套子步骤；不引入独立人员、审批、自动提醒或数据库。

步骤创建事件示例（虚构数据，位置从 1 开始）：

```json
{
  "version": 1,
  "event_id": "step-create-demo-0001",
  "task_id": "TASK-M3-03-DEMO",
  "step_id": "STEP-AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
  "action": "create",
  "actor": "chatgpt",
  "base_revision": 0,
  "timestamp": "2026-10-30T00:00:00Z",
  "changes": {
    "title": "整理第一份资料",
    "position": 1
  }
}
```

调整顺序事件示例（可由用户操作，或由 ChatGPT 在用户明确指令下写入；`actor` 为 `user` 或 `chatgpt`，`base_revision` 是该任务的步骤顺序修订号）：

```json
{
  "version": 1,
  "event_id": "step-order-demo-0001",
  "task_id": "TASK-M3-03-DEMO",
  "action": "reorder",
  "actor": "user",
  "base_revision": 0,
  "timestamp": "2026-10-30T00:00:00Z",
  "changes": {
    "step_ids": [
      "STEP-BBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB",
      "STEP-AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
    ]
  }
}
```

### ChatGPT 写入步骤事件的规则

- 写入前先读取当前任务及其 `steps`，确认父任务无冲突；不得根据旧对话猜测 revision 或现有顺序。
- 创建步骤：生成全新的 STEP ID 和 event ID，`base_revision=0`，`position=当前步骤数量+1`，写入 `step_events/evt_<event_id>.json`。
- 修改步骤：使用该步骤当前 revision，只写本次确实改变的 `title` 或非 `done` 状态；不写 `position`，不改父任务或兄弟步骤。
- 排序：仅在用户明确要求调整顺序时写入；使用当前 `step_order_revision`，`step_ids` 必须包含该任务全部现有 STEP ID 且各出现一次。
- `step_events/` 内所有事件的 `event_id` 必须唯一。相同 ID、相同内容的重复文件可忽略；相同 ID、不同内容必须冻结所有受影响的步骤/排序流，冲突变体不得作为有效 revision 应用。不得因为 `base_revision` 恰好连续，就接受复用 ID 的冲突事件。
- **ChatGPT 不得写入 `status: done`**。用户须在网页中亲自确认完成；`actor` 字段只是声明，不是身份认证。
- 如果父任务、步骤或顺序存在冲突，或 `step_order_incomplete=true`，不得从当前可见步骤拼出新的完整排序；先等待 Drive 同步并刷新。服务端拒绝未同步完成的排序，不允许静默丢弃隐藏 STEP ID。

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

历史 M2 CI 在 Linux/Windows 运行了 30 项 Python + 5 项 Node UI；M3.1 随后扩展了项目与任务关联回归。M3.2 新增负责人、优先级、日期校验/冲突/历史兼容/草稿保护测试，具体以 M3.2 PR 的最新固定 HEAD、CI 和独立验收结论为准。

- 代码：`app.py`、`web/index.html`；测试：`tests/test_app.py`。
- 无登录、无外网服务、无自动提醒、无多用户权限；M3.1/M3.2/M3.3 已合入 main，但合并不代表公司电脑的本机服务已升级。自动提醒、工作总览和高级查询仍属后续阶段。
- 首版的文件同步**不是实时数据库**。遇到 Drive 延迟、重复创建或并发修改可能需要刷新与人工核查。
- 不要将 API 密钥、凭证、个人资料、真实台账或 Google Drive 私有链接提交到此 Public 仓库。

## 项目文档和 AI 开发交接

- [确认过的需求](docs/REQUIREMENTS.md)
- [当前进展与下一步](docs/PROJECT_STATE.md)
- [重要决策](docs/DECISIONS.md)
- [AI 协作规则](AGENTS.md)
