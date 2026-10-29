# AIWorkSpace

个人 AI 工作台，先验证 **ChatGPT → Google Drive → 本地网页 → Google Drive → ChatGPT** 的任务闭环。不需要额外的 Google Cloud 项目、付费 API 或第三方 Python 库。

**当前是首版候选。Windows 网页启动、Drive 双向同步、ChatGPT 读回、网页刷新及服务重启均已由用户实测通过。冲突界面修复后，GitHub Actions 完整自动化测试为 16 PASS / 0 FAIL；最新冲突界面仍待 Windows 复测。**

## 先在 Windows 运行

1. 安装 Google Drive 桌面版，确认你能在 Windows 文件资源管理器中看到同步文件夹。选择一个**不在 GitHub 仓库内**的个人数据目录，例如 `X:\\My Drive\\AIWorkSpaceData`（此处是示例路径，请换成你自己的）。
2. 在这个个人目录下建立 `events` 子文件夹，等待 Drive 同步。不要向公开 GitHub 提交这个目录内的任何数据。
3. 在已安装 Python 3 的 Windows 电脑上，进入下载的 `AIWorkSpace` 代码文件夹，运行：

   ```powershell
   python app.py --data-dir "X:\\My Drive\\AIWorkSpaceData"
   ```

4. 浏览器打开 `http://127.0.0.1:8770/`。初次没有事件文件时显示空任务列表，这是正常情况。

本地服务只监听 `127.0.0.1`，不提供公网访问。关闭运行窗口会停止网页服务；数据文件不会随之删除。

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

允许的状态：`todo`（待处理）、`doing`（进行中）、`blocked`（受阻）、`done`（已完成）。任务只允许用户在网页明确确认后设为已完成。跨设备出现同一版本的两次修改时，页面提示冲突并停止自动覆盖，需人工处理。

## 自测与边界

```powershell
python -m unittest discover -s tests -v
```

- 代码：`app.py`、`web/index.html`；测试：`tests/test_app.py`。
- 无登录、无外网服务、无自动提醒、无多用户权限；这只是首个可验证的任务闭环。
- 首版的文件同步**不是实时数据库**。遇到 Drive 延迟、重复创建或并发修改可能需要刷新与人工核查。
- 不要将 API 密钥、凭证、个人资料、真实台账或 Google Drive 私有链接提交到此 Public 仓库。

## 项目文档和 AI 开发交接

- [确认过的需求](docs/REQUIREMENTS.md)
- [当前进展与下一步](docs/PROJECT_STATE.md)
- [重要决策](docs/DECISIONS.md)
- [AI 协作规则](AGENTS.md)
