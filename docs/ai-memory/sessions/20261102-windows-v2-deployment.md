# AIWorkSpace｜Windows V2.0.0 真实部署与人工核对

日期：2026-11-02

## 背景
GitHub main 已发布 UI V2.0.0，main merge SHA 为 `c279a976437bb8c1a493be3407a9de3767fa20cf`。用户在原公司 Windows 8770 工作台点击网页一键更新，期间曾遇到间歇性失败，最终报告更新成功。

## 真实 Windows 运行证据
用户在 Windows PowerShell 调用本机只读接口：
- `GET /api/update/status`：`version=2.0.0`。
- `build_short=fa51b01`。
- `build_commit=fa51b0123aaac76ddff2064d34178e7cc6e3ab11`，与当前 GitHub main HEAD 一致。
- `build_known=True`。
- `last_update.status=installed`，`last_update.version=2.0.0`，`last_update.commit=fa51b0123aaac76ddff2064d34178e7cc6e3ab11`，消息“更新安装成功。”。
- `last_update.updated_at=2026-11-02T03:59:21+00:00`。

结论：**公司 Windows 原 8770 服务已实际运行 V2.0.0，更新器记录为 installed。**

## 数据读取与用户人工确认
- `GET /api/tasks` 正常返回。
- 当前返回任务 2 条、项目 0 条。
- 用户随后明确确认：当前任务已人工查看，内容没有问题。
- 该人工确认记录为 **当前两条任务内容核对 PASS**。不外推为升级前后完整数据集一致，也不代表项目数据、Google Drive 同步或所有页面功能均通过。

## 更新故障排查
- 首次网页更新提示“无法连接 GitHub”；用户报告再次点击更新仍失败，随后又突然更新成功。
- Windows Python 3.15.0 对 GitHub API、RAW VERSION、ZIP 下载源的连通检查均 PASS。
- 进一步调用本机 `/api/update/check` 返回最新版本 2.0.0。
- 本地 `updater.check_latest_update` 返回 `2.0.0 / fa51b01`。
- 使用本地 updater 的完整 ZIP 读取函数下载成功，大小 149,371 bytes。
- 最终网页更新成功，随后状态接口明确返回 `installed`。
- **根因未知**：现有证据只说明故障具有间歇性，不能断言具体网络、代理、GitHub 登录或更新 helper 原因。更新功能不要求 GitHub 登录/Token，不能为此增加凭据。

## GitHub 自动化证据
准确 merge SHA `c279a976437bb8c1a493be3407a9de3767fa20cf` 的 [Actions #41382882228](https://github.com/yudacheng666/AIWorkSpace/actions/runs/41382882228) 全部成功：Ubuntu Python 103 + Node 58；Windows Python 103 + Node 58；Windows Chromium E2E 3 PASS。本轮没有重复执行同 SHA、同范围测试。

## 未验证事项
1. 升级前任务/项目数量的精确基线，未做逐条前后快照比较。
2. 当前项目数量为 0 是否符合用户预期。
3. 本次升级后 Google Drive 桌面同步状态及云端事件目录一致性。
4. 真实公司环境中其余 UI 页面和全部业务流程的完整人工验收。
5. 更新间歇性失败的具体根因。

## 本轮操作边界
仅更新项目 Markdown 记忆；未改产品代码、main 或真实业务数据；未重新执行更新；未重复 CI；未触发收费 Actions。
