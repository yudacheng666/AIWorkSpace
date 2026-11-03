
# 2026-11-03 数据治理闭环开发记录

## 用户目标
补齐“异常发现 → 人工核查 → 明确授权 → 合法写入 → 结果追踪”整套数据治理闭环。起因：工作台仅显示若干项“需要核查”，没有核查入口。

## 开发基线与边界
- 正式 main（合并前）：8f713526f00370d5c8db518d6fa855b7a3f58885 / VERSION 2.0.4；用户已授权 PR #23 正式集成，候选 VERSION 提升为 2.0.5。
- 继续在 PR #23 步骤删除/步骤级文档候选之上开发；不修改 main，不合并，不升级公司电脑，不接触真实 Drive/任务数据。
- 本次只用 GitHub 中的虚构测试数据和标准 Actions runner。工作档案继续暂停。
- 用户于 2026-11-03 回复“授权”，批准 PR #23 正式集成到 GitHub main；不包含真实 Windows/Drive 部署或自动修复六项真实异常。

## 设计决策
1. 扫描 events/、project_events/、step_events/、settings_events/；同时把 workspace 读取器的冲突/引用缺失/同步等待转成异常条目。
2. 异常 ID 由 source folder + filename + 原始文件 SHA-256 确定。原始异常文件永远只读保留；不会移动到 quarantine，不覆盖、不删除。
3. 追加式 review_events/ 保存 authorize / applied / dismissed / stale / failed。每个异常使用独立 review revision；相同 revision 并发决定冻结为 conflict。
4. 人工授权和业务写入是两个不同按钮/HTTP 请求。授权只保存批准事件；执行时再次验证 source hash、proposal hash、目标存在/冲突/current revision 和原有 validator。使用新 event ID 追加合法事件；结果回执记录目标 event ID、SHA-256、revision。
5. 原始 source 文件变化、目标 revision 变化、授权预览变化时授权失效。已应用结果再次检查目标文件；缺失需重新授权，hash/内容变化冻结为冲突。重复执行使用同一个批准 event_id，按文件内容幂等验证。
6. 仅自动建议无歧义的修复：任务 trash/restore actor/revision；step update 剔除非法 position 并保留合法字段；task/step completion 在二次明确确认后写入 confirmed_done。Purge、损坏 JSON、缺失目标、其他未知项目/设置异常不自动修复，只能记录人工核查结论或走专门界面。
7. Google Drive 同步来的授权不会在另一设备自动执行；仍需本机用户明确点击执行。actor=user 是审计字段，不是强身份认证；服务继续只允许本机 Host/Origin。

## 文件改动
- app.py：数据源扫描、稳定 anomaly ID、review event validator/reducer、repair proposal、授权/执行/结果验证 API、已处理结果回查。
- web/index.html：侧栏“数据核查”入口、异常清单、原始事件、修复预览、授权/执行分离、处理轨迹和状态 badge。
- tests/test_data_governance.py：15 项合成 Python 测试。
- tests/test_task_id_drawer_windows_e2e.py：新增真实 Chromium 数据治理流程测试。
- README.md、REQUIREMENTS.md、PROJECT_STATE.md、DECISIONS.md 更新。

## 发布批准
- PR #23 纳入正式发布；main 当前 2.0.4，因此将候选 VERSION 提升为 2.0.5。
- 版本变更后的准确 SHA 必须重新运行 GitHub Actions；原代码 SHA 的 PASS 不可代替 RC CI。

## 测试状态
- **最终产品/测试 SHA：`cc8913083a8ef4616358fa81e4b0f899feb06526`**；[GitHub Actions #41591071040](https://github.com/yudacheng666/AIWorkSpace/actions/runs/41591071040) **3/3 SUCCESS，0 FAIL**。
- Ubuntu：Python 151 total，139 PASS / 12 SKIP；Node 68 PASS / 0 FAIL。
- Windows：Python 151 total，141 PASS / 10 SKIP；Node 68 PASS / 0 FAIL。
- Windows Chromium：升级/回滚 3 PASS；真实工作台任务/步骤 E2E 7 PASS，包含新增治理流程“发现→查看原始事件→授权但不写入→单独执行→校验结果回执、原始文件字节保持不变”。
- 新增 15 项 Python 治理专项测试全部通过，覆盖 lifecycle/step position/completion 修复、只读异常发现、源 hash 和目标 revision 变化、并发授权、Drive 同步授权不自动执行、设置异常、结果缺失/篡改与幂等追踪。
- 目标测试覆盖：只读发现；授权不写入；合法写入；完成二次确认；restore；非法 position 清理；设置事件只读核查；源变更/目标 revision 变化；并发审查冲突；同步授权不自动执行；结果缺失重新授权；结果篡改冲突；原始文件 SHA 不变；真实 Chromium 浏览器流程。
- 真实双电脑 Google Drive 同步和公司 Windows 8770 仍 NOT TESTED。

## 后续
1. **自动化闭环开发和准确 SHA CI 已完成，3/3 PASS。**
2. 保持 PR #23 Draft，不合并、不部署；等待用户审阅并另行审批。
3. 真实双电脑 Google Drive 同步与公司 Windows 8770 仍 NOT TESTED；需单独安排非生产演练。
