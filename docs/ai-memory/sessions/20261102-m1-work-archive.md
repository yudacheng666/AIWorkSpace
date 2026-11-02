# 2026-11-02｜个人工作档案 M1 基础功能开发

## 任务背景
用户在 M0 架构检查后要求继续。目标是在不影响正在使用的 AIWorkSpace 2.0.0 的前提下，实现个人工作档案 M1 基础能力。

## 基线与隔离
- 仓库：yudacheng666/AIWorkSpace
- M1 分支：feat/20261102-m1-work-archive
- 基于 main SHA：fa51b0123aaac76ddff2064d34178e7cc6e3ab11
- VERSION：2.0.0（未修改）
- M0 设计 PR #14：仍为 Draft/未合并；M1 分支携带设计文档副本，不依赖 #14 合并。
- 未修改 main、未合并 PR、未部署、未访问真实 Drive/数据目录。

## 已实现
1. app.py
   - WORK_RECORD_ID / WORK_INBOX_ID、工作记录分类、日期/证据/行动关联校验。
   - 原始输入 capture 事件和标准工作记录 create/update 事件。
   - work_archive/inbox 与 work_archive/record_events 两个追加式事件目录。
   - capture_key 幂等重试；record event_id 重复冲突冻结；revision reducer。
   - GET /api/work-archive。
   - POST /api/work-archive/inbox。
   - POST /api/work-archive/records。
   - POST /api/work-archive/records/{record_id}/update，revision 冲突返回 409。
2. web/index.html
   - 独立工作档案导航与页面。
   - 全局快速记录弹窗，先保存原始输入。
   - 原始输入列表、工作记录时间线、关键词搜索、分类筛选。
   - 工作记录详情抽屉，支持标题、内容、分类、日期和项目编辑。
   - 工作记录编辑草稿保护。
3. 测试
   - tests/test_app.py：旧数据目录兼容、原文保存、追加更新、重复事件冲突、证据/行动引用校验、来源状态、HTTP 幂等、409、Host allowlist。
   - tests/test_ui_shell.mjs：导航、时间线/原始输入、快速记录、记录编辑 revision、搜索。
   - tests/test_updater.py：程序更新/回滚时 work_archive 原始文件字节保持不变。
4. 文档
   - README 增加数据结构、ChatGPT/Drive 整理流程、虚构 JSON 示例和备份边界。
   - REQUIREMENTS/DECISIONS/PROJECT_STATE 已更新。
   - PERSONAL_WORK_ARCHIVE_DESIGN.md 从 M0 设计延续并记录 M1 实施状态。

## 关键设计
- 工作记录=已发生事实；任务=未来独立交付；步骤=现有任务内部子行动。
- 原始输入不被 AI 结果覆盖；record.source_ids 关联 inbox_id。
- evidence_refs 只存 file_id/name/mime_type，不复制附件正文或保存私有 URL。
- action_links 指向现有 TASK/STEP ID。
- 不使用 OpenAI API 或任何模型 API。
- 沿用已验证的 Google Drive 双向通道，不重新验证基础可行性；新增数据类型的增量适配仍待测试。
- 当前 updater 只备份程序白名单，不备份 --data-dir；产品没有完整 data-dir 备份/恢复功能，README 已明确说明。

## 当前状态
- 代码和测试已提交到隔离分支。
- GitHub Actions 尚未获得此分支准确 SHA 的 CI 结果。
- 尚未做真实 Google Drive 新数据类型增量烟测。
- M1 尚未合入 main，也未部署到公司电脑。

## 下一步
1. 静态复核 app.py API 路由、工作记录 reducer、前端草稿保护和 Node harness。
2. 创建 Draft PR，确认 PR 的准确 head SHA。
3. 读取该 SHA 的 GitHub Actions Linux/Windows Python、Node UI 和 Windows updater E2E 结果；按失败项修复，不重复旧 SHA 已通过测试。
4. CI 通过后仅针对 work_archive 新目录/文件做 Drive 连接器增量适配烟测，不重跑 M1/M2 既有双向通道全套验收。
5. 保持 PR Draft/不合并，等待用户明确批准。
