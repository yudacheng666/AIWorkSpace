# 2026-11-11｜统一对象说明与工作记录类别

## 开发基线
- 仓库：`yudacheng666/AIWorkSpace`
- 基线 main：`9f98f1b11abe57ccf3c43d40aa43ad8b341afe62`
- 分支：`feature/20261111-unified-object-information`
- 最终产品／测试 SHA：`ad9e392d26ce91623551c5896b7a28ee616b4296`
- 候选版本：`2.10.0`
- 开始时 main 开放 PR：0；本次尚未合并、发布或部署。

## 用户确认的产品决策
- 项目、任务、步骤均有统一「说明」；说明是稳定背景，不是进展事件；总结时作为独立标注的 object_contexts 提供给 AI 理解背景，不计入工作事实或成果。
- 项目、任务、步骤共用同一 RECORD 记录入口，不增加独立记事本系统，不为记事或结论创建步骤。
- RECORD 类型：progress、communication、decision、note；旧记录缺省 progress。
- decision 的 content 保存背景／判断，outcome 保存结论；详情顶部按首次保存时间（created_at）投影最近一条有效决策为当前结论，旧决策保留为独立历史；补记发生日期或后续元数据更新不改变当前决策。decision 的 content/outcome/record_type 不允许原记录覆盖，更正或新判断必须新增 RECORD。
- note 纳入个人完整时间线；汇报版「只选重点」默认不推荐普通 note，仍可手动勾选。
- task↔step 转换保留说明；AI 整理仍由用户核对后写入。

## 已实施代码
- `app.py`：
  - 新增 `work_archive/object_detail_events/` 追加式说明事件，独立 revision、严格 schema、冲突冻结。
  - 说明投影到 project/task/step；通过已验证的转换事件映射在 task↔step 间继承；目标自身说明优先。
  - 新增 `POST /api/object-details`；不扩展旧 project/task/step 事件 schema，不改写既有事件。
  - RECORD 增加 `record_type`，旧数据默认 progress；类型进入报告来源、source_digest 和 ChatGPT 分析上下文。
- `web/index.html`：
  - 项目、任务、步骤详情均提供折叠说明编辑区。
  - 统一记录入口提供进展、沟通、决策／结论、记事；decision outcome 在详情顶部显示为当前结论。
  - 全局工作轨迹、项目阶段线和总结来源卡显示记录类型；汇报版重点推荐排除普通 note。
  - 说明草稿加入现有离开／刷新保护；并发或继承来源 revision 过期时停止写入。
- 测试：
  - `tests/test_work_records.py`：旧记录默认类型、类型校验、decision preview、说明 revision/冲突/隔离存储。
  - `tests/test_app.py`：task↔step 转换说明继承及继承来源 revision 过期保护。
  - `tests/test_unified_timeline_reports.py`：record_type 进入来源卡和 source_digest。
  - `tests/test_ui_shell.mjs`：快速记录类别、当前结论、说明编辑、转换继承 token、汇报默认选择。
  - `tests/test_task_id_drawer_windows_e2e.py`：新增真实 Windows Chromium 流程，验证说明、decision 记录、不自动完成任务、不创建额外步骤。

## 最终测试状态
- 最终产品／测试 SHA：`ad9e392d26ce91623551c5896b7a28ee616b4296`。
- [GitHub Actions #42959727208](https://github.com/yudacheng666/AIWorkSpace/actions/runs/42959727208) 第 2 次尝试 **3/3 SUCCESS**：
  - Ubuntu Python 308 项（33 skipped）通过；Node UI 128/128 PASS。
  - Windows Python 308 项（30 skipped）通过；Node UI 128/128 PASS。
  - Windows 真实应用／Chromium：更新回滚 3 项通过；工作台 E2E 27 项通过；隔离预览启动包检查通过。
- 新增关键回归在最终 SHA 均通过：decision reducer 不可变性、转换来源说明冲突冻结、真实 Chromium 说明与 decision 记录流程（不自动完成任务、不创建步骤）。
- 第 1 次尝试 Windows Python 的既有 `test_create_requires_json_content_type` 遇到 `WinError 10053`；只重跑失败的 Windows Python Job 后，第 2 次尝试通过。未为此修改无关业务代码。
- 开发过程中一次多文件顺序更新触发了多个中间 SHA 的 Actions；其中两个中间 UI 测试失败，原因是模拟 DOM 测试读取父节点 textContent 的断言方式错误，已改为读取实际文本节点。之后多文件修改改用一次 Git tree/commit；后续严格只核对最终 SHA，不复用中间 SHA 结果。

## 安全与发布边界
- 未读取、修改、迁移或上传真实 Google Drive 工作台数据。
- 未操作用户电脑的 8770 服务。
- 未修改 main、未合并 PR、未创建正式 Release。
- 用户未授权合并前保持 Draft PR；候选版本 2.10.0 不代表已发布。


## 最终安全边界与后续
- 公开差异已扫描；本次新增测试数据均为虚构示例，未提交用户真实采购事项、真实人员／公司信息、私有 Drive 链接或密钥。
- 未读取、修改、迁移或上传真实 Google Drive 工作台数据；未操作用户电脑的 8770 服务。
- PR #53 仍为 Draft / Open；main 未改变，未合并、未发布、未部署。
- 独立 Codex 探索性验收及真实双电脑 Google Drive 离线／晚同步仍 **NOT TESTED**。这是高风险持久化功能的剩余验收缺口，须在合并前补齐，或等待用户明确批准例外。
