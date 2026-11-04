# AIWorkSpace 2.0.11：数据异常处理改为通知信箱

日期：2026-11-04

## 用户决定
现有“数据异常处理”界面过于复杂。当前页面没有内嵌 AI，也没有能力对各类数据冲突作通用、实质性的调整；因此改成普通用户易理解的“通知信箱”，以消息 ID 追踪为主。用户明确要求执行、测试，通过就合并。

## 设计与实现
- 导航和页面标题改为“通知信箱”，首页提醒入口同步调整。
- 移除技术统计卡片、任务/步骤聚合核查组、复杂双栏详情和所有页面修复操作。
- 每条异常独立作为一条消息，按来源时间倒序显示类型、状态、标题、摘要、关联任务/步骤和消息编号。
- 消息编号由现有 anomaly_id 确定性派生为 `MSG-YYMMDD-<12位大写十六进制>`；短编号在当前列表碰撞时扩展成完整 32 位哈希；没有可靠时间时日期段为 `SYS`。无新消息数据库或计数器。
- 详情默认折叠，只展示业务影响和建议；不显示原始 JSON、内部 ID、文件名、SHA-256 或英文校验错误。
- 刷新只调用现有只读 GET /api/reviews；不增加已读状态写入或业务数据写入。

## 后台和安全边界
- app.py、后端 API、事件 schema、review_events 审计链和现有授权/执行安全机制均未修改。
- 后端异常扫描和专门治理 API 保留；普通通知页面不再提供授权、执行修复或确认保留操作。
- 没有访问、迁移、修改或删除真实工作台/Google Drive 数据；没有部署公司 Windows 8770。

## 测试和发布
- 产品/测试 SHA：`d7c817713d86f27e654b2b882e2868f4f5a2b864`
- PR #34 Actions #41792421545：3/3 SUCCESS。Ubuntu/Windows Python 各 173 tests、Node UI 各 81 PASS；Windows Chromium 更新/回滚 3 PASS、工作台 UI E2E 11 PASS。
- 首轮 Node 测试因测试夹具未模拟 details.open 默认值失败；修正断言后以新 SHA 完整复验通过。
- PR #34 标准合并；merge SHA：`d7f703233a48dd22434a6f4e0c5221837610cdb4`。
- 合并后 main Actions #41792762895：3/3 SUCCESS，Ubuntu/Windows Python 各 173 tests、Node UI 各 81 PASS；Windows Chromium 更新/回滚 3 PASS、工作台 UI E2E 11 PASS。
- main/VERSION=2.0.11；开放 PR=0。
