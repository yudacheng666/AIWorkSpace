# AIWorkSpace｜当前项目状态

## 2026-11-06：2.7.0 Draft PR #44 准确 SHA CI PASS；尚未发布

- **准确代码/测试 SHA**：`26eeaef7b7030707ddf6e24a7992cd078b4e36e9`，GitHub Actions [#42126735310](https://github.com/yudacheng666/AIWorkSpace/actions/runs/42126735310) **3/3 SUCCESS**。Ubuntu Python 243 tests（26 SKIP）、Windows Python 243 tests（24 SKIP）；Node 两端各 109 PASS/0 FAIL；Windows 原生 Chromium 更新/回滚 3 PASS，工作台 UI 21 PASS（含总结与成果库来源编号及证据剪贴板只读核验）。
- **前次失败及处理**：第一轮新 Python 测试错误地仅要求提示出现字面词“不得”，而正确实现使用同义的“不要编造”；已改为检查明确的禁止虚构业绩提示；产品代码未因这条测试文案断言而改变。新精确 SHA 完整 CI 通过。
- **现阶段链路**：#40（2.3 补记）→ #41（2.4 档案与来源总结底稿）→ #42（2.5 衍生待办）→ #43（2.6 历史误建任务转记录）→ #44（2.7 来源可追溯 ChatGPT 总结及成果材料交接），**五个 PR 均应保持 Draft**，待用户集中体验与明确合并授权。
- **距离正式完成仍差**：真正的 ChatGPT 深度语义自动分析/职业报告应用内生成尚未建设；本机网页没有模型 API（按用户零付费要求，现为人工复制粘贴）；真实公司 Windows 8770、Google Drive 双电脑离线/重连、旧客户端兼容及生产迁移 NOT TESTED；main 仍正式 2.2.0，不能把 CI 当作已部署可体验。最后完整体验、回归、依赖顺序批准合并及发布仍待执行。

## 2026-11-06：2.7.0 来源可追溯 AI 分析交接（新 Draft 候选）

- **承接与规则**：继续从已在准确 SHA 测试通过的 Draft #43（2.6.0，产品 SHA `f24ba1a00087555c5b1541a9061aebbe7567dc3b`、Actions #42125093085 3/3 SUCCESS）开发；原链路 #40→#41→#42→#43 全部未合并，最新 main 仍正式 v2.2.0。新分支 `feat/20261106-work-analysis-handoff`，候选 VERSION 2.7.0。
- **新增两个只读出口**：`GET /api/work-archive/analysis-context` 严格使用日/周/月已有 summary 底稿的相同 RECORD IDs 和人工确认完成 event IDs，附工作内容、成果/工时、来源任务和证据链接；`GET /api/work-archive/portfolio-context` 仅选人工 featured 成果，项目可筛选。冲突/缺失/无来源/超出 30000 字符等均拒绝，不沉默遗漏。
- **界面**：工作总结增加「复制含来源的 ChatGPT 分析说明」，成果库增加项目范围和「复制成果证据供 ChatGPT 整理」。点击只读取本机数据、复制剪贴板，由用户主动粘贴给 ChatGPT 分析、核对并用现有手工总结保存流程回写；无内嵌 AI、无付费 API、无自动写事件、无伪造成果。
- **代码与测试**：app.py、web/index.html、tests/test_work_analysis_handoff.py、tests/test_ui_shell.mjs 和 Windows 真实 Chromium E2E；需求、设计、决策、README 同步。**本阶段尚未完成准确 SHA 的 CI 验收，不可继承 2.6 PASS。**
- **发布安全**：开发分支 / Draft、虚构测试数据，不合并 main、不操作真实 Drive、不开启后台服务或模型 API；公司 Windows 8770、双机离线/重连与真实业务材料仍 NOT TESTED。用户要求全部阶段完成后集中体验反馈。

## 2026-11-06：v2.6.0 Draft PR #43 已通过准确 SHA 自动化（待集中体验与授权合并）

- **PR**：[Draft #43](https://github.com/yudacheng666/AIWorkSpace/pull/43)，依赖 #40→#41→#42；仍 **Open/Draft**，不合并、不部署。
- **产品与测试 SHA**：`f24ba1a00087555c5b1541a9061aebbe7567dc3b`，[GitHub Actions #42125093085](https://github.com/yudacheng666/AIWorkSpace/actions/runs/42125093085) **3/3 SUCCESS**。Ubuntu Python 237 tests（25 预期 SKIP），Windows Python 237 tests（23 预期 SKIP），Node 每平台 107 PASS/0 FAIL，Windows 真实 Chromium 更新回滚 3 PASS、工作台 E2E 20 PASS（含 task→record 人工确认、取消不写入、单事件、旧任务原文件字节保留及晚到编辑冻结转换）。
- **失败处理**：首次新增 Node 测试的 VM 导出字符串含非法换行，已修；新增转换表单未加入页面导航草稿保护，在测试捕获后已修；上述准确 SHA 全套重测通过。旧失败 SHA 不能代替最终证据，Codex 不重复跑同环境。
- **仍未验收**：公司 Windows 8770、真实 Google Drive 双电脑断网/重连及版本混用、生产数据迁移和外部自动 AI 分析。正式 main 仍为 2.2.0。用户要求工作记录各阶段完成后一并集中体验，待后续授权再按 #40→#41→#42→#43 顺序审核合并。

## 2026-11-06：2.6.0 误建任务转为事实工作记录（累计候选，尚未合并）

- **开发前检查**：已按 AGENTS.md 读取 README、REQUIREMENTS、PROJECT_STATE、DECISIONS、WORK_RECORDS_DESIGN 并核对当前 main SHA \`4bff94987a9cf45df2a3fd3acafdefb79bdedefd\`、正式 VERSION 2.2.0、现有 Draft PR #40（2.3）→ #41（2.4）→ #42（2.5）与精确 Actions 证据；三项尚未合并，用户要求全部阶段完工再集中体验。
- **基线与开发分支**：基于 #42 HEAD \`6fd208ba26ada7ce5b25b4adeabf9f632810865d\`，新建 \`feat/20261106-work-task-to-record\`；统一候选 VERSION=2.6.0，保留 #40→#41→#42→本 PR 的依赖，**绝不能脱离前三项直接发布到 main**。
- **本阶段代码**：任务到记录转换为一份不可覆盖的 \`work_archive/task_record_events/\` 事件；task 原有事件字节不变，靠 source revision/指纹与目标约束在只读投影中隐藏旧任务、显示新 RECORD，并保留原任务 ID。晚到源任务修改、相同来源多转换、记录 ID 冲突或坏文件时拒绝激活并显示核查告警，原任务可见。界面加转换入口/明确二次确认/发生日期/事实成果/耗时，保留草稿与 409，遵循本机 Host/Origin 限制。
- **代码与测试文件**：app.py、web/index.html、tests/test_task_record_conversion.py；设计/需求/决策/README 更新。既有 #42 Actions \`#42022478232\` 在产品 SHA \`7cb663881bc6c9b67f193cb0548ae0700831baba\` 3/3 SUCCESS，但**不等于 2.6 新代码已验收**。
- **测试状态**：以本 PR 准确 SHA 的 Actions 为准；新的 Python 合同/HTTP/故障及源事件不可变测试将进入标准 Ubuntu/Windows、Node 与 Windows Chromium CI。未取得 CI 结果前状态 **NOT TESTED**，不得沿用 #42 的 PASS。
- **未触碰真实用户资料**：未操作公司 Windows 8770，没有更改真实 Google Drive 数据，未合并主分支，未使用 Work/付费 API。真正双电脑 Drive 离线-重连、版本混用与断电数据同步 **NOT TESTED**。
- **后续方向**：本阶段精确 SHA CI、缺陷定向修复并回写结论；另行规划 ChatGPT 主动分析日报/周报与可追溯职业成果报告，而不在无模型 API 的本机页面假装自动分析。待所有阶段完成，再按用户安排集中体验并审批依赖 PR 合并。

## 2026-11-05：2.5.0 工作记录衍生待办审核候选 CI PASS（Draft PR #42）

- 用户指示继续下一阶段文档、代码、测试，不在各子阶段反复人工体验。按 AGENTS.md 审计 main=2.2.0 / SHA 4bff94987a9cf45df2a3fd3acafdefb79bdedefd；PR #40、#41 均 Draft 未合并。此分支 feat/20261105-work-action-review 从 PR #41 精确 HEAD 3ee098df8798a0209b14a9338b2e237ea9b32b1c 派生。
- 2.5.0 候选实现：工作记录选择与向 ChatGPT 复制分析上下文、严格 JSON 导入、候选建议预览及同项目文字相似查重、逐条明确新建待办或关联已有任务。后端创建任务采用一个 task create 事件，source_work_record:{record_id,revision} 可审计，status 默认 todo；已有任务关联采用工作记录 action_links 单次更新。
- 增量测试：新 tests/test_work_action_review.py 的 API、schema、防重复、来源版本与原始事件保护；tests/test_ui_shell.mjs 补充人工审核/草稿/拒绝路径；Windows 真实 Chromium E2E 覆盖复制、JSON 预览、取消确认、用户新建及重复阻断。
- **CI 验收**：准确产品/测试 SHA `7cb663881bc6c9b67f193cb0548ae0700831baba` 的 [GitHub Actions #42022478232](https://github.com/yudacheng666/AIWorkSpace/actions/runs/42022478232) **3/3 SUCCESS**。Ubuntu Python 223 tests（24 预期 SKIP），Windows Python 223 tests（22 预期 SKIP），Node UI 每端 105 PASS/0 FAIL，Windows 真实 Chromium updater/rollback 3 PASS、工作台端到端 19 PASS。新增行为覆盖：错误 JSON/越权状态字段拒绝、只读分析预览、同名和疑似重复检查、显式用户新建/关联、旧 source revision 409、任务 provenance 单事件、取消不写入、原始业务事件字节不变、已衍生任务改名后仍防止原建议重复创建及草稿保护。
- **初轮问题及修复**：初轮 Node 有 1 项提示文本断言失败（复制的 ChatGPT 说明缺少“不会自动”的直白表述），其余 Python 和 Windows Chromium 通过；已把明确说明补到产品提示，在新准确 SHA 上执行三组完整 CI，均 PASS，未让 Codex 重跑已由 Actions 证明的同环境测试。
- **进一步加固**：审计发现仅依赖任务当前标题查重，会让已重命名的来源任务可能重复创建。新增只读遍历原始合法 task create 事件的同源同原始标题保护，以及对应 HTTP 回归；实际产品/测试 SHA 和 CI 已更新为最终加固版本。
- **发布与未测范围**：正式 main 仍为 2.2.0；PR #40/#41/#42 均 Draft，不合并 main、不安装公司 Windows 8770、不改真实 Google Drive。高风险双设备断网/重连、历史误分类 task→record 的原子转换、ChatGPT 连接器真实双向写回仍为 NOT TESTED/NOT IMPLEMENTED。完成全部约定阶段后再统一人工体验。


## 2026-11-05：2.4.0 工作档案完整组合候选验收通过（Draft PR #41）

- 用户指示“继续推进新文档的编写代码的开发和测试，等这个功能全都完成之后一起体验反馈”。本轮不要求用户分阶段下载或体验，先完成独立候选与准确 SHA CI。
- 正式 main 基线为 2.2.0 / SHA 4bff94987a9cf45df2a3fd3acafdefb79bdedefd。已通过测试的工作记录 PR #40 HEAD 63455d03e9c7af73154fcee538c2775aa76bcfe6 保持 Draft；后续分支 feat/20261105-work-archive-completion 从其 HEAD 创建，在 Draft PR #41 集成。
- 新产品逻辑：原文待整理收件箱及同来源去重、同条工作记录多任务/步骤进展与成果关联、受限制的 Google Drive 证据 URL、精选成果库、任务详情关联记录反查、日报周报月报的来源底稿与 SUMMARY 追加事件（含来源验证、修订及人工核对）。
- **准确产品/测试 SHA 2c16b37c02c4b566869ecd9a75ceaf10e73110e8**：[GitHub Actions #42009472610](https://github.com/yudacheng666/AIWorkSpace/actions/runs/42009472610) 3/3 SUCCESS。Ubuntu Python 215 tests（23 预期 skip），Windows Python 215 tests（21 预期 skip），Node 每端 101 PASS/0 FAIL，Windows 真实 Chromium 更新/回滚 3 PASS、工作台 UI E2E 18 PASS。新增 tests/test_work_archive_complete.py、Node 交互专项及真实 Windows Chromium 原文→多关联工作记录→来源周报→任务反查。准确 SHA CI 已验证原任务数据不可变、重复来源拒绝、并发 revision 保护、来源对照与草稿安全。
- **初轮缺陷已修复**：候选首次 CI 中缺省 action_links 被解释为 None 导致两个 Python HTTP 用例失败；另一个 Windows E2E 用了 textarea 文本节点断言而不是 value。已针对准确 SHA 修复并重新运行三平台完整 CI，当前全部 SUCCESS。没有重复派 Codex 跑已在相同 SHA/平台通过的自动化。
- **边界与下一步**：新增使用手册与 ChatGPT 协同文档。工作台无内嵌 AI、不会后台自动分析或替用户完成任务。真实 Windows 8770 和 Google Drive 公司数据未操作；两台电脑离线/重连及混合版本 NOT TESTED。PR #40/#41 均 Draft，正式 main 仍 2.2.0。待用户集中体验后再申请合并和真实部署独立授权。


## 2026-11-05：2.3.0 工作记录补记与轨迹候选（最终准确 SHA CI 已通过，待审批合并）

- **用户最新指示**：“按分析推进，做文档，开发，测试，汇报”。基于 main 精确 SHA `4bff94987a9cf45df2a3fd3acafdefb79bdedefd`（正式 2.2.0，开发开始时开放 PR=0）创建 `feat/20261105-work-records`；历史工作档案 PR #14 已关闭且未合并，仅参考其 M0 设计，不恢复旧代码。
- **产品实现**：顶部「＋ 补记工作」、侧栏「工作记录」页面；工作内容和实际发生日期必填（可回填），系统另存实际录入时间；项目/已有任务/成果/分钟数可选。支持按发生日期、项目、关键词筛选、修改历史记录、短编号 R-、草稿保护。工作事实不设置 todo/doing/blocked/done。
- **数据安全**：独立 `data-dir/work_archive/record_events/` 追加式 JSON；内部 RECORD ID 与短显示编号分离；严格 schema（拒绝未知事件字段及任何任务状态字段）、原子文件发布、revision/409、并发冲突冻结。任务已确认完成事件只读投影，不复制成工作记录、不改变任务/步骤/项目历史。更新期间用户继续输入的新草稿以已提交快照为基线保留；保存中阻止离页并禁用取消，避免静默丢失。旧任务/project/step 原始数据未迁移或改写。
- **设计与文档**：新增 `docs/WORK_RECORDS_DESIGN.md`；同步更新 `REQUIREMENTS.md`、`DECISIONS.md`、`PROJECT_STATE.md` 和 README。第一阶段不含自动 AI 总结、历史误分类批量转换、多对多步骤关联和职业档案，留待后续阶段；不使用付费模型 API。
- **最终产品/测试 SHA**：`6e3287b567f565df7d8e385af6bcc6b7eebbc777`。GitHub Actions [#41987809633](https://github.com/yudacheng666/AIWorkSpace/actions/runs/41987809633) **3/3 SUCCESS**：Ubuntu Python 208 tests（22 预期 SKIP）、Windows Python 208 tests（20 预期 SKIP），两端 Node 各 **97 PASS / 0 FAIL**；Windows 原生 Chromium updater/rollback **3 PASS**、工作台 UI E2E **17 PASS**。新增回归覆盖事件顶层未知字段/状态字段拒绝、保存期间继续输入保留草稿、阻止保存中离页、补记过去日期、编辑后原事件字节不变。准确 SHA 上无失败。
- **测试去重与修复经过**：初始候选 SHA `fcced72f3088b02f131953b3ff2e6b1256b0eaad` 的 [Actions #41983154279](https://github.com/yudacheng666/AIWorkSpace/actions/runs/41983154279) 曾 3/3 SUCCESS；代码复审另发现保存中的草稿竞争窗口和事件 envelope 未拒绝未知字段，因此增加修复与专项测试，并在最终 SHA 重新运行完整 CI。只报告最终准确 SHA 作为交付验收，不再重复 Codex 全套自动化。
- **风险与边界**：测试仅用虚构数据。真实两电脑 Google Drive 离线/重连、并发及版本混用仍 **NOT TESTED**；公司 Windows 8770 未安装，未修改真实 Google Drive 工作资料。所有共享 data-dir 客户端必须统一升级后再创建新格式记录。
- **发布审批**：用户本次只授权设计、文档、开发、测试和汇报，未授权合并或部署；[PR #40](https://github.com/yudacheng666/AIWorkSpace/pull/40) 保持 Draft，正式 `main/VERSION=2.2.0` 不变，等待单独发布授权。

## 2026-11-05：2.2.0 已正式发布 — 步骤排期互转 + 周期任务

- **用户授权**：明确要求“合并发布”。按 AGENTS.md 审计所有开放 PR，仅 #37（2.1.0 步骤日期/任务与步骤互转）和依赖它的 #38（2.2.0 周期任务）；无其他开放 PR。合并顺序先 #37 后 #38，不跳过依赖，不重复合并已吸收变更。
- **精确合并**：[PR #37](https://github.com/yudacheng666/AIWorkSpace/pull/37) 由 HEAD `735bc71e940b60e0055a33dffc9e0ba381705ac5` 正常 Merge 至 main，merge SHA `e6987a2a933d374346e3b70587c71933aca92ab2`（main/VERSION=2.1.0）；[PR #38](https://github.com/yudacheng666/AIWorkSpace/pull/38) 从旧依赖分支调整 base 至 main，确认无冲突并从 Draft 转 Ready 后正常 Merge，HEAD `dce8bafb05fba51355b3cbe54c6268e6faae8b4a`，merge SHA `b8ae95699d442b2efc73798bf9bfb3b8c887a28e`，main/VERSION=2.2.0。再次核实两 PR merged，开放 PR=0。
- **候选 CI 证据**：#37 HEAD 的 [Actions #41967001515](https://github.com/yudacheng666/AIWorkSpace/actions/runs/41967001515) 3/3 SUCCESS；#38 产品/测试 SHA `f0c47fe536d2696f27175e8b9413049ee4945c15` 的 [Actions #41977504669](https://github.com/yudacheng666/AIWorkSpace/actions/runs/41977504669) 3/3 SUCCESS；#38 后续 HEAD 与产品/测试 SHA 的差异仅为 README.md、PROJECT_STATE.md、DECISIONS.md 三份 Markdown 记忆文档。
- **合并后 main 回归**：2.1.0 合并 SHA `e6987a2a933d374346e3b70587c71933aca92ab2` 对应 [Actions #41978238908](https://github.com/yudacheng666/AIWorkSpace/actions/runs/41978238908) 3/3 SUCCESS；2.2.0 合并 SHA `b8ae95699d442b2efc73798bf9bfb3b8c887a28e` 对应 [Actions #41978365376](https://github.com/yudacheng666/AIWorkSpace/actions/runs/41978365376) **3/3 SUCCESS**。2.2.0 主分支 Ubuntu/Windows Python 各运行 198 tests（分别 21/19 预期 SKIP），Node 各 93 PASS，Windows 原生 Chromium 更新/回滚 3 PASS，工作台 E2E 16 PASS。
- **发布内容**：执行步骤日期进入日历、甘特图；步骤与末级任务互转并保护原始事件；周期任务按固定开始日每 N 天/周/月/年重复，本期明确完成显示已完成、下期计算恢复待办，用户可明确“彻底结束循环”后再次“恢复循环”。当前周期计划/截止分别取周期开始/结束日，历史完成事件不覆盖；第一版周期任务限定无步骤/子任务的末级任务。
- **部署及风险边界**：仅 GitHub 正式 main 发布；未自动更新公司 Windows 8770，未修改真实 Google Drive 工作台任务数据。真实两电脑 Google Drive 离线—重连、版本混用、并发数据同步 **NOT TESTED**；使用 2.1/2.2 新事件与转换操作前，应先让所有共享同一 Drive 数据目录的客户端统一升级至 2.2.0，备份数据，避免旧版写入。用户本次“合并发布”不等于授权实际本机部署或直接更改真实事件。
- **下一步**：实际使用前先备份，并在所有共享数据目录的电脑统一升级；对复杂转换/周期任务至少补充真实 Drive 离线/重连增量验收，不重复运行已在 CI 同准确 SHA 通过的全套自动化。

## 2026-11-05：2.2.0 周期性任务候选开发（未合并）

- **需求**：可设置每天／每周／每月／每年重复与间隔，本周期人工确认完成后列入已完成；下一周期在读取时重新显示为待办；明确确认彻底结束后不再重复，后续可以恢复原循环。
- **项目规则复核**：开始前已阅读 AGENTS.md、README.md、docs/REQUIREMENTS.md、docs/PROJECT_STATE.md、docs/DECISIONS.md；核对 main SHA `2c1a50e32fa068db274d4fef18898f07f59984a5`（正式 VERSION 2.0.13），并审计开放 PR：#37 是 2.1.0 步骤日期/任务转换候选，已通过既有 CI 但尚未获合并批准。新分支 `feat/20261105-recurring-tasks` 基于 #37 HEAD `735bc71e940b60e0055a33dffc9e0ba381705ac5` 开发，不能跳过其依赖直接合并 main。
- **实现**：事件校验增加 `recurrence`（频率／间隔／起始日／enabled）与 `recurrence_status_period`；按固定锚点计算当前日历周期，周/月/年切换无需后台写文件。当前期人工完成保留 `confirmed_done` 与所属周期；跨期投影恢复待办，历史原始事件不删。通过独立 revision/409 保护的循环配置／结束／恢复 API 操作，结束附带 `confirmed_end` 审计；网页任务详情操作、列表周期标识、日历/甘特和总览虚拟日期联动。仅支持不含步骤和子任务的末级任务，旧客户端混用不安全。
- **准确 CI 结果（已通过）**：产品与测试 SHA `f0c47fe536d2696f27175e8b9413049ee4945c15`，GitHub Actions [#41977504669](https://github.com/yudacheng666/AIWorkSpace/actions/runs/41977504669) **3/3 SUCCESS**；Ubuntu/Windows Python 各执行 198 项测试（其中各有 21/19 项预期跳过），Node UI 各 93/93 PASS；Windows 实际 Chromium 更新/回滚 3 PASS、工作台 E2E 16 PASS（新增周期任务启用→完成→彻底结束→恢复，以及周期排期字段的真实浏览器验证）。首轮周期专项均 PASS；旧“文档折叠” E2E 因异步刷新后错误收折面板而失败，已将测试改为等待持久化后的文档数，再按当前展开状态操作；在上述准确 SHA 完整复验通过。
- **测试范围**：新增虚构数据 Python 单测与 HTTP 测试，覆盖月底闰年、周期切换、人工完成、永久结束与恢复、确认、版本冲突及下级限制。提交后须按最新准确 SHA 的 GitHub Actions Ubuntu/Windows Python + Node 与 Windows Chromium 验收；真实两台电脑离线重连同步及公司 8770 环境 **NOT TESTED**。
- **发布边界**：PR #37 未合并，2.2.0 候选亦不得直接合入 main；本次未修改真实 Google Drive 任务或用户电脑程序。下一步依据准确 SHA CI 修复缺陷，保留与 #37 的依赖及用户合并审批。
 
## 2026-11-05：2.1.0 候选已通过完整 CI — 步骤日期及任务/步骤双向转换（待合并）

- **用户需求与执行方式**：步骤增加与任务一致的日期并纳入日历/甘特；支持步骤升级为所属任务的子任务，末级任务移动为另一任务的步骤。用户要求直接在当前对话通过 GitHub 执行，不使用 Work；尚未批准合并。
- **基线与候选**：main 基线 SHA `2c1a50e32fa068db274d4fef18898f07f59984a5`（VERSION 2.0.13）；开发分支 `feat/20261105-step-dates-and-conversion`，[PR #37](https://github.com/yudacheng666/AIWorkSpace/pull/37)，候选 VERSION 2.1.0。最终产品与测试准确 SHA `a77bec7df2ce9098a72d3462179fcd9518a4a1b1`。
- **步骤排期**：步骤采用与现有任务一致的 `planned_date`、`due_date`、`follow_up_date`（YYYY-MM-DD；当前任务不含小时分钟）；步骤详情可编辑或清空日期，后端严格校验合法日期、revision 与追加式步骤事件。日历按三种日期展示任务和步骤并可打开对应步骤；甘特只用计划与截止两日期绘制时间窗，未排期、逆序或冲突项目单独展示。
- **任务/步骤转换**：步骤→任务默认成为原任务的子任务；任务→步骤需用户明确指定目标父任务，且只支持无活动/回收站子任务、无活动步骤、无异常的末级任务。两者均需人工确认。日期、状态、标题、文档保留；原任务的负责人、优先级、项目关联作为受控元数据保存，供回转恢复。
- **追加式数据治理**：使用独立 `conversion_events/` 的单文件转换提交记录；源 task/step 文件不覆盖、不删除，记录源 revision、SHA-256 指纹和目标字段。只在源/目标/父任务可验证时激活转换并隐藏源；未同步则保留源隐藏目标；源晚到修改则冻结转换，保留源和警告。转换目标删除后源不复活。
- **新增关键修正**：修复云端转换文件乱序时的拓扑排序漏洞，保证多轮相互转换按真正依赖顺序解析；校验目标标题、状态、日期、文档和保留元数据与真实源一致，阻止改写转换日志伪造已完成、文档或负责人。测试新增三阶段逆序文件链、目标内容篡改、元数据篡改。
- **CI 首轮与回归**：首轮 SHA `27e588d231e3a3cad7a5aa6c9844fd583c863555` 的 Actions #41964602891 失败：Node DOM 测试选错表单层级/跨 VM 数组比较，真实 Chromium 异步保存尚未完成时断言。修复测试定位及持久化轮询、在真实浏览器关闭抽屉后切换视图，并进一步加固转换状态机，最终准确 SHA `a77bec7df2ce9098a72d3462179fcd9518a4a1b1` 的 [Actions #41966545453](https://github.com/yudacheng666/AIWorkSpace/actions/runs/41966545453) **3/3 SUCCESS**：Ubuntu/Windows Python 各运行 186 tests（含预期 SKIP），Node UI 各 93 PASS/0 FAIL；Windows 真实 app.py + Chromium updater/rollback 3 PASS、工作台 UI 15 PASS，其中新增步骤日期、日历甘特、双向转换往返与原始事件字节不变。准确 SHA 未更改产品/测试代码。
- **限制与下一步**：不触碰真实 Google Drive 或公司 Windows 8770。2.1.0 新增日期事件与 conversion ledger，旧版客户端不识别；**所有同步同一数据目录的电脑先升级到 2.1.0 后再执行转换**。真实双电脑离线/重连与冲突演练未在 GitHub-hosted Runner 等价验证，须作为后续高风险增量验收。当前正式 main 仍 2.0.13，PR #37 未合并；等待用户明确合并授权。

## 2026-11-04：2.0.13 已正式发布 — 派生父任务快捷状态保护

- **用户批准**：修复任务列表的父任务快捷状态覆盖问题。拥有有效子任务或执行步骤的任务，未完成时只提供“确认完成任务”，已人工完成时只提供“重新打开（恢复自动联动）”，操作均需人工确认。普通无下级任务仍支持四种状态快捷切换，优先级独立。
- **正式合并**：从 main `ad503bfa1fd89f81e7956a000a61ede4f09f68d9`（VERSION 2.0.12）开发；[PR #36](https://github.com/yudacheng666/AIWorkSpace/pull/36) 准确产品/测试 HEAD `b37330e24019a743630b8604ead37ec17ec17587` 通过验收后 Draft→Ready、GitHub 标准 Merge，merge SHA `0bd1c811417e7c5251138f3dedd12c793890b090`；`main/VERSION=2.0.13`，开放 PR=0。
- **实际修复**：仅变更 `web/index.html`，不更改后端 app.py/事件 schema/原父子递归汇总逻辑。派生父任务无法通过列表按钮写入会被计算覆盖的待处理/进行中/受阻人工值；人工完成仍明确确认、合法追加 `confirmed_done=true`。已完成父任务的重新打开确认后只追加 `status=todo`（无 completed 标记），刷新后可自动显示待处理、进行中或受阻，依下级实际状态而定。
- **安全**：草稿保护、冲突/缺失/父子环路/步骤不完整禁用、准确 revision/409 和不可覆盖事件链均保留；不扫描/迁移/写入真实用户任务或 Google Drive。
- **新增定向回归**：Node UI shell 3 项，验证派生任务按钮防覆盖、完成确认/取消、重新打开/取消、恢复下级受阻以及步骤汇总/环路保护。Windows 真实 app.py + Chromium 1 项，以隔离虚构数据验证父子任务联动、保存事件结构、revision、优先级独立、已完成置底及原事件字节不变。
- **PR 自动化验收**：[Actions #41821750877](https://github.com/yudacheng666/AIWorkSpace/actions/runs/41821750877) 对产品/测试 SHA `b37330e24019a743630b8604ead37ec17ec17587` **3/3 SUCCESS**。Ubuntu/Windows Python 各执行 176 tests（含预期 SKIP），Node UI 各 89 PASS / 0 FAIL；Windows Chromium 更新/回滚 3 PASS、工作台 UI E2E 14 PASS。
- **合并后 main 复验**：[Actions #41822077475](https://github.com/yudacheng666/AIWorkSpace/actions/runs/41822077475) 对 merge SHA `0bd1c811417e7c5251138f3dedd12c793890b090` **3/3 SUCCESS**，覆盖同样 Ubuntu/Windows Python+Node 与 Windows 真实 Chromium 范围。
- **部署边界**：GitHub 正式版本发布不代表 Windows 本机已经升级；公司 Windows 8770 未部署、实际 Google Drive/任务数据未修改。后续本机升级应在独立备份/回滚保障下进行。

## 2026-11-04：2.0.12 已正式发布 — 任务列表状态/优先级快捷切换

- **需求**：任务列表状态与优先级文字徽标改为按钮，点击弹出四项选项并保存，保留原任务卡片及表头筛选排序。
- **基线/发布**：从 2.0.11 main SHA `0a718be5234a046d7ed15e5a82c90312321539fa` 开发；[PR #35](https://github.com/yudacheng666/AIWorkSpace/pull/35) 最终产品/测试 SHA `7d6dc3a61439d0b93d4d1d64dbb9fb41598fcd4c`，通过完整验收后 Draft→Ready、GitHub 标准 Merge，merge SHA `8172f8eee501923cb1230ffc35ec7d5af7a2f56e`，`main/VERSION=2.0.12`；开放 PR=0。
- **产品实现**：仅改动 `web/index.html`，状态/优先级各四项。点击标签按钮展开选项、菜单互斥并可点外部/Escape 收起；当前值不写入；修改通过原有 `/api/tasks/{task_id}/update`，只提交原 title、准确 revision 和用户明确改变的一个字段。已完成需明确确认，取消不写；冲突任务两个字段均禁用，状态联动信息不可靠时禁用状态快改；未保存草稿阻止快捷操作，409 失败不乐观改状态。服务端刷新后延续完成任务置底与字段排序。窄屏两组按钮可见。
- **安全范围**：`app.py`、任务事件 schema、原始数据、后台审计规则均未改变；不新增 API、数据库或自动业务写入。公司 Windows 8770 和真实 Google Drive 未由本轮更新/操作。
- **自动化范围**：新增 Node UI shell 5 条快捷操作回归；Windows 真实 app.py + Chromium E2E 新增 2 条覆盖实际持久化、旧 revision/409、人工完成确认与取消、冲突禁用、手机窄屏和原事件不可覆盖。
- **候选验收**：[PR GitHub Actions #41818398711](https://github.com/yudacheng666/AIWorkSpace/actions/runs/41818398711)，准确 SHA `7d6dc3a61439d0b93d4d1d64dbb9fb41598fcd4c` **3/3 SUCCESS**。Ubuntu/Windows Python 各运行 175 tests（含设计性 SKIP），Node 各 86 PASS / 0 FAIL；Windows Chromium updater 3 PASS，工作台 UI E2E 13 PASS。
- **合并后复验**：[main GitHub Actions #41818715644](https://github.com/yudacheng666/AIWorkSpace/actions/runs/41818715644)，准确 merge SHA `8172f8eee501923cb1230ffc35ec7d5af7a2f56e` **3/3 SUCCESS**，同样的 175 Python tests（含预期 SKIP）、86 Node PASS，3 updater 与 13 UI Chromium PASS。
- **首轮修正证据**：首轮 Linux/Windows Node 失败为历史 mock DOM 缺少 button setAttribute 与新测试误判抽屉默认 hidden；第二轮仅残余一处新测试断言错误；均已修正并在最终准确 SHA 完整重测 PASS，产品写入行为本身的 Windows 真实 Chromium E2E 各轮均通过。
- **下一步**：公司电脑如需使用 2.0.12，应在真实环境先备份，再从网页软件更新中心升级；GitHub Merge 不等于本机已升级，真实 Drive/任务数据操作独立授权。

## 2026-11-04：2.0.11 已正式发布 — 数据异常处理改为通知信箱

- **用户决定**：现有“数据异常处理”界面过于复杂，且当前页面没有内嵌 AI 或通用冲突修复能力；改为简洁的“通知信箱”，明确只负责告知，不假装能在此处解决冲突。
- **正式合并**：[PR #34](https://github.com/yudacheng666/AIWorkSpace/pull/34) 已标准 Merge。合并 SHA `d7f703233a48dd22434a6f4e0c5221837610cdb4`，`main/VERSION=2.0.11`。PR 最终 HEAD `f4c68beace8b0c83d2276bdac860350a78bebd1d`；测试后只增加 README、PROJECT_STATE、DECISIONS 文档，没有产品或测试代码变化。
- **界面实现**：侧栏“异常处理”改名“通知信箱”；移除技术统计卡片、任务/步骤聚合核查组、复杂双栏详情、原始 JSON/内部编号/哈希/英文错误展示，以及授权/执行/确认保留等修复操作。采用全宽消息列表，每条异常独立显示类型、状态、标题、摘要、可靠时间及已识别任务/步骤；详情折叠显示影响与建议；空状态简洁。首页提醒及侧栏待关注数字指向通知信箱。
- **消息编号**：由现有稳定 `anomaly_id` 的 32 位十六进制部分确定性派生为 `MSG-YYMMDD-<12位大写十六进制>`；若当前消息列表短编号碰撞，则扩展为完整 32 位哈希；来源无可靠时间时使用 `SYS` 日期段。不新增消息数据库/计数器；同一异常刷新后编号稳定，源文件内容变化生成新异常编号。
- **后台与数据边界**：只调用现有只读 `GET /api/reviews`；`app.py`、API、事件 schema、review_events 审计链、原始事件、授权/执行安全校验均未修改。后端数据扫描和专门治理 API 保留，但不再暴露在普通通知页面。未读写或删除任何真实工作台/Google Drive 数据。
- **PR 验收**：[GitHub Actions #41792421545](https://github.com/yudacheng666/AIWorkSpace/actions/runs/41792421545) 对产品/测试 SHA `d7c817713d86f27e654b2b882e2868f4f5a2b864` **3/3 SUCCESS**：Ubuntu/Windows Python 各 173 tests、Node UI 各 81 PASS；Windows 真实 app.py + Chromium 更新/回滚 3 PASS、工作台 UI E2E 11 PASS。
- **合并后 main 复验**：[GitHub Actions #41792762895](https://github.com/yudacheng666/AIWorkSpace/actions/runs/41792762895) 对 merge SHA `d7f703233a48dd22434a6f4e0c5221837610cdb4` **3/3 SUCCESS**；Ubuntu/Windows Python 各 173 tests、Node UI 各 81 PASS；Windows Chromium 更新/回滚 3 PASS、工作台 UI E2E 11 PASS。
- **首轮失败及修正**：首次 CI 的 Node 测试夹具未模拟 DOM 的 `details.open` 默认值，导致 1 条断言失败；修正测试夹具断言后，在新准确 SHA 上完整复测通过。没有为追求通过而修改产品安全规则。
- **合并后状态**：开放 PR=0。GitHub 代码已正式发布；公司 Windows 8770 未升级，真实 Google Drive/任务数据未读取、写入或删除。后续部署须另行按备份/回滚流程授权。


## 2026-11-04：2.0.10 已正式发布 — 任务列表与步骤文档交互优化

- **用户需求**：步骤文档增加折叠按钮；任务名称点击打开详情；任务 ID 点击复制；已完成任务自动排到任务列表末尾。
- **基线**：正式 main SHA `726da94e1817cd910665d5fb984bd3f02c26f8c1`，`VERSION=2.0.9`。分支 `feat/20261104-task-list-usability`，候选 `VERSION=2.0.10`。不改 app.py、事件 schema、API、任务 revision 或真实工作台数据。
- **设计**：步骤文档默认收起，有文档显示数量、无文档显示“添加文档”；展开后仍用原 Google Drive 链接和步骤 revision/409 表单。任务标题改为可聚焦按钮，仍调用原 openTaskDetail；短编号在列表中可点击复制，显示局部状态反馈，不打开抽屉。无冲突且 status=done 的任务放在列表末尾独立“已完成”组；列多字段、截止日期、优先级和标题排序均保持已完成置底，冲突任务留在普通分组；看板/日历/甘特图不改变。
- **测试计划**：Node UI shell 增加文档折叠/空文档入口、标题点击、编号复制、默认/字段/多字段排序覆盖；Windows 真实 app.py + Chromium 增加列表复制与标题直达、步骤文档展开/收起实测。沿用既有 Python/Node 双平台和 Windows updater/UI E2E CI；不重复 Codex 已覆盖的 CI 范围。
- **准确产品/测试 SHA**：`b0adfae15ce70065f25bada16af8305402fea6c9`；[GitHub Actions #41783935135](https://github.com/yudacheng666/AIWorkSpace/actions/runs/41783935135) **3/3 SUCCESS**：
  - Ubuntu Python：173 total / 157 PASS / 16 SKIP；Node：79 PASS / 0 FAIL。
  - Windows Python：173 total / 159 PASS / 14 SKIP；Node：79 PASS / 0 FAIL。
  - Windows 真实 app.py + Chromium：更新/回滚 3 PASS；工作台 UI E2E 11 PASS，覆盖任务名称打开、列表 ID 剪贴板复制、步骤文档折叠/展开/关联、完成任务在默认/字段/多字段排序中置底，以及排序不写任务事件。
- **正式合并**：用户于 2026-11-04 明确批准最新合并。PR #33 Draft→Ready 后以 GitHub 标准 Merge 合入 main；产品/测试准确 SHA `b0adfae15ce70065f25bada16af8305402fea6c9` 的 Actions #41783935135 3/3 SUCCESS。最终 PR HEAD `31a720d0f226bedb98653fb224cb9450a98aa389` 相对该已测 SHA 仅包含 README、PROJECT_STATE、DECISIONS 三个 Markdown 文件的记忆追记，无产品/测试代码变化；最终 HEAD 对应 Actions #41784404642 SUCCESS。合并 SHA `0ec256205bf47a7ee36ae74d3a638a3bb71ef44b`，已回读确认 `main/VERSION=2.0.10`；PR #33 merged，当前开放 PR=0。当前连接器未返回合并后 main push CI，故不宣称该项已核实。
- **安全边界**：仅更改网页展示与自动化测试；不扫描、修改或重排真实任务数据，不自动把任务写成 done，不改任何事件文件。

## 2026-11-04：2.0.9 已正式发布，所有遗漏 PR 已审计归档

- **用户授权**：要求检查所有未合并 PR、修复遗漏并一并合并，随后明确批准补入。此次发布的是仍有效的原 PR #20 父子任务状态联动与 #22 刷新状态位置，原始老分支基线落后，故在最新 main 2.0.8 重新集成为 [PR #31](https://github.com/yudacheng666/AIWorkSpace/pull/31)，不是直接硬合旧分支。
- **发布前准确 HEAD**：`d71456401e886b53c0f96ba76fbe03c040311186`。[Actions #41780863683](https://github.com/yudacheng666/AIWorkSpace/actions/runs/41780863683) **3/3 SUCCESS**：Ubuntu Python/Node、Windows Python/Node、Windows 真实 app.py + Chromium 更新回滚和工作台 UI E2E 全通过。
- **正式合并**：PR #31 Draft → Ready → GitHub 标准 Merge，merge SHA `a1f681f9fb18982870741484a4d717979e1bb77d`；读取验证 main VERSION=**2.0.9**。[合并后 main CI #41781106338](https://github.com/yudacheng666/AIWorkSpace/actions/runs/41781106338) **3/3 SUCCESS**；新版本已在 GitHub 发布，不代表公司电脑已自动更新。
- **核心修复**：用户指定的显式上级任务关系支持多级联动；有步骤/子任务受阻则上层受阻，有 doing/done 则上层进行中，全部完成需人工确认；冲突/环路冻结计算，自动汇总不生成上级写入/不推进 revision，非状态编辑不污染原人工状态。最后刷新状态位于侧栏底部，不再挤占任务列表工具栏。
- **遗留 PR 清理**：#20/#22 代码内容已被 #31 吸收并关闭旧 PR；#19 旧回收站 UI 已被 2.0.8 #29/#30 取代；#14 工作档案按用户先前要求仍暂停，旧 M0 文档 PR 关闭归档；#13 是 2.0.0 历史部署记忆、#8 为 1.0.0 实时源 QA，#16 为 2.0.0→2.0.1 真实公开源安装/回滚的 QA-only 单次留证。#8/#13/#14/#16/#19/#20/#22 共 7 个未合并旧 PR 均已单独说明并关闭，保留历史证据；**不是声称全部 merged**。其中 #20/#22 的有效产品功能已由 #31 正式合并。全仓库 31 个 PR 已逐项核对，当前开放 PR **0**。
- **安全界限**：未访问或修改公司 Windows 8770、Google Drive 真实任务数据、事件或 review_events；未自动修复现有异常或执行回收站清除。GitHub 代码升级到 2.0.9 后仍需用户在软件内检查更新决定是否安装；继续保留此前的数据治理人工授权与回滚保护。
- **文档收口**：本条和 README/DECISIONS 的发布结果属于纯 Markdown 追记，记录已完成的独立准确 HEAD 测试和合并后 CI；不改变 2.0.9 产品代码或测试文件。

## 2026-11-04：2.0.9 候选 — 补齐遗漏的父子状态联动与刷新状态布局

- **用户要求**：全面盘点未合并 PR，补齐此前遗漏且仍有效的修复。本轮确认 PR #20（父子任务状态联动）与 PR #22（刷新状态移至侧栏底部）仍未进入正式 main；用户现明确要求一并执行。
- **当前基线**：GitHub main SHA db6115d9bdecf028d651f5495d92f1b5732c1144，VERSION=2.0.8。新集成分支 release/20261104-v2.0.9-parent-rollup-refresh 从该准确 SHA 派生；统一候选 VERSION=2.0.9。
- **旧 PR 为什么不能直接合并**：#20 以 68a3212360fed942ccf2dbfca97afd8f4e224bd3 为基线，较当前 main 落后 92 个提交；#22 以 8f713526f00370d5c8db518d6fa855b7a3f58885 为基线，落后 87 个提交。两个旧分支都与当前 main diverged、mergeable=false；其旧 CI 只证明旧基线。
- **父子状态联动整合**：保留 PR #20 已审阅的核心实现：明确 parent_task_id、递归步骤/子任务状态、冲突/缺失/环路冻结、全部完成仍需人工确认、人工 done 不自动撤销、无合成父事件/无 revision 推进、非状态编辑不覆盖 manual_status。已将其代码补丁移植到 2.0.8 当前 app.py；网页实现与 2.0.8 当前步骤级文档、数据异常处理和回收站代码做兼容整合，不回退新功能。
- **刷新状态整合**：将 #sync 唯一状态节点从任务工具栏移至侧栏底部，刷新状态通过 setRefreshStatus 同步文本与 title；保留原刷新频率、读取状态、草稿保护和数据读写行为。
- **测试**：移植 PR #20 的 parent rollup Python/Node/Windows Chromium 用例和 PR #22 的刷新位置 Node/Windows Chromium 用例。以本集成分支最终准确 SHA 的 GitHub Actions 为准；不沿用旧 Actions #41455699276/#41576050443 的旧基线 PASS。
- **其余开放 PR 处置**：#19 已由 2.0.8 的 #29/#30 取代；#14 工作档案继续暂停；#13 是 2.0.0 历史部署记录；#8 是 1.0.0 时代 QA。它们不作为本次产品功能合并内容，待本次集成验证后分别关闭/归档并保留说明。#20/#22 旧 PR 在新集成 PR 完成后标记为已由新 PR 取代。
- **发布边界**：新集成 PR 先以 Draft 验收；CI 通过后按用户本轮“一并合并”的授权完成 GitHub 合并。不得将 GitHub 合并视为公司 Windows 8770 实机部署、Google Drive 数据写入或真实任务自动修复授权。

## 2026-11-04：2.0.8 组合发布完成（数据异常处理 + 回收站视觉）

- **授权与范围**：用户明确要求“PR #28/#29 一起合并到 2.08”，统一语义版本实际为 `2.0.8`；包含两项 UI/交互改善，不包含 PR #20 父子任务状态联动、PR #22 刷新状态位置或旧 PR #19，工作档案继续暂缓。
- **集成方式**：以 2.0.7 main `c4817668730de6631c86877e93571bd5d4456e15` 为共同基线，创建包含 PR #28 HEAD `ec816c1d0eac5822a50b6e6ade05c8eabadedf7b` 和 PR #29 HEAD `97dea4f5f1b32ebfcd16881a5726bc1933c4cb53` 的双父合并提交；组合 SHA `742efa1ce8b0b0625c99b6b6b3594c5932ec3131`。
- **组合 SHA 验收**：[GitHub Actions #41775916301](https://github.com/yudacheng666/AIWorkSpace/actions/runs/41775916301) **3/3 SUCCESS**：Ubuntu Python 162 tests（含设计性 SKIP）、Node 74 PASS/0 FAIL；Windows Python 162 tests（含设计性 SKIP）、Node 74 PASS/0 FAIL；Windows 真实 app.py + Chromium 更新/回滚 3 PASS、工作台 UI E2E 7 PASS，包含数据核查流程和回收站恢复/批量删除。
- **正式发布**：[集成 PR #30](https://github.com/yudacheng666/AIWorkSpace/pull/30) 经 Draft → Ready、GitHub 标准 Merge 合入 main，合并 SHA `8c15b999c5a23ca1a49b03a89e35291922367e0b`，`main/VERSION=2.0.8`。GitHub 自动将已被集成的 PR #28/#29 标记为 merged。合并后 main push 的 [Actions #41776122516](https://github.com/yudacheng666/AIWorkSpace/actions/runs/41776122516) **3/3 SUCCESS**，与发布前的组合 CI 分开核验。
- **安全与待办边界**：本轮没有访问公司真实 Windows `127.0.0.1:8770`，没有启动软件网页升级，没有操作 Google Drive 真实任务/步骤/review_events；数据异常修复仍必须由用户先核查/授权、再明确执行；回收站的永久删除、revision 和墓碑保护保持原行为。下一步仅由用户自行在工作台检查更新并决定升级，GitHub 代码发布不代表设备自动更新。
- **维护方式**：本段仅为合并后的 Markdown 记忆回执，不修改产品/测试或 VERSION，不重复触发 CI；以上产品验证 SHA 仍以合并提交及准确测试运行记录为准。


## 2026-11-04：用户批准 PR #28 + #29 统一合入 2.0.8

- 用户明确指示“一起合并到2.08”，本次仅包含数据异常处理页面 #28 与回收站主页视觉 #29，不包括父子任务联动 #20、刷新状态位置 #22 或旧回收站 PR #19。
- 从已通过独立 CI 的 PR #28 和 #29 精确 HEAD 派生组合发布分支 `release/20261104-v2.0.8-review-trash`，使用双父提交保留两套开发与测试历史，按 29 的精确补丁整合到 28，保留 `VERSION=2.0.8`。
- 对组合提交执行 GitHub Actions 3 项标准 job：Linux Python/Node、Windows Python/Node、Windows 真实 app.py+Chromium 更新/回滚及 UI。用户授权在验证全部通过且未见数据安全缺口后正常合并 GitHub main；不执行真实 Windows 8770 升级、Google Drive 真实数据读写、用户现有异常自动修复。
- 历史候选状态见下文。以组合最终 SHA 对应 Actions 的真实结论和合并后 main SHA 为发布权威证据；禁止沿用两个独立 PR 的 CI 冒充组合测试。


## 2026-11-04：回收站界面统一主页视觉（开发完成，等待用户体验与发布审批）

- **用户反馈**：正式工作台回收站仍是窄容器、原生按钮和简单列表，与工作总览视觉割裂；用户明确要求修复并统一主页界面。
- **开发记忆规则已复核**：本轮完整读取 AGENTS.md、README.md、REQUIREMENTS.md、PROJECT_STATE.md、DECISIONS.md；以 GitHub main、实际代码和准确 SHA 为准。GitHub Actions 为默认测试主力，ChatGPT 开发维护测试；不重复 Codex 已覆盖用例，不合并 main、不部署公司 Windows 8770、不访问真实 Drive 数据。
- **历史原因**：旧回收站视觉 PR #19（分支 `feat/20261102-trash-polish`，HEAD `e40b80b055856e06037c80d8d979f20ff5178e7a`）仍为 Draft，且相对当前 main 已不可合并（mergeable=false）；其 CSS/测试从未进入正式 main。旧 PR 的 Actions #41453008757 只证明旧分支当时的测试范围，不证明当前正式版本已包含 UI。
- **当前基线**：main SHA `c4817668730de6631c86877e93571bd5d4456e15`，`VERSION=2.0.7`。新分支 `fix/20261104-trash-ui-alignment` 从该 main 精确派生；不修改 VERSION，不覆盖 PR #28 的数据异常处理候选，不触碰真实业务数据。
- **实现**：PR #29（[回收站界面统一主页视觉](https://github.com/yudacheng666/AIWorkSpace/pull/29)）使用与工作总览一致的统计卡片、全宽白色面板、蓝色主操作、次级恢复按钮和危险删除描边；自动清理与已删除任务分区；增加已删除/可恢复/冲突统计、任务行元数据、空状态、实时选择数量和安全禁用；移动端自适应。保留 0/7/30/90 天、默认 30 天、到期在下次访问时执行、恢复/彻底删除确认和原 API/事件模型。
- **最终产品/测试 SHA**：`7d55390582ee6a639ffe7a93b1da97eb2ee87565`；[GitHub Actions #41775067629](https://github.com/yudacheng666/AIWorkSpace/actions/runs/41775067629) **3/3 SUCCESS**：
  - Ubuntu Python：161 total / 149 PASS / 12 SKIP；Node：71 PASS / 0 FAIL。
  - Windows Python：161 total / 151 PASS / 10 SKIP；Node：71 PASS / 0 FAIL。
  - Windows 真实 app.py + Chromium：更新/回滚 3 PASS；工作台 UI E2E 7 PASS，包含回收站统计、卡片分区、按钮样式、全选/取消、禁用危险操作及恢复/彻底删除原流程。
- **测试职责**：CI 已覆盖本次新增 Node 与 Windows Chromium 路径，未重复派发 Codex 跑相同测试。自动化证明结构和交互，不替代用户对最终视觉效果的体验确认。
- **当前状态**：PR #29 Draft / Open，未合并 main、未发布；PR #19 保留历史，不自动关闭或合并。CI 通过不等于发布授权；公司 Windows 8770、Google Drive 实际数据和自动更新均不在本轮范围。测试后的项目记忆提交仅修改 Markdown，不改变上述产品/测试 SHA。

## 2.0.7 正式发布回执

2026-11-04 用户明确授权“合并，发布”。PR #27 最终 HEAD `ca9ba2acb377c265f6df175a1aff1426dcd152e1` 的 [Actions #41767021531](https://github.com/yudacheng666/AIWorkSpace/actions/runs/41767021531) 全部 SUCCESS（Linux、Windows、Windows Chromium 更新/回滚及 UI 回归）。已通过 GitHub 普通 merge 正式合入 main，merge SHA `dae9c5fcf1797c44ded1ecc569039902c09912a7`，VERSION=2.0.7。合并后 main CI 尚未独立核实；公司 Windows 未由本轮升级，真实 Drive 数据未操作。

## 2026-11-04：2.0.7 更新检查网络容错修复（用户已批准发布）

- 基线 main `f63e717c6684815a9aea532eaad225aa7f912f10`，VERSION 2.0.6；用户报告已安装 2.0.4 的更新检查间歇失败。代码确认原请求仅一次尝试且所有网络错误折叠为同一提示；公司网络实际 DNS/代理/限流根因未取得日志，不作确定归因。
- 增加每请求最多 3 次、0.5/1 秒退避；仅瞬时网络及 HTTP 408/500/502/503/504 重试；证书错误、限流、代理认证及其他永久 HTTP 错误即时解释。保留 urllib 系统/环境代理及 TLS 校验。固定 commit 的 raw VERSION 网络失败后可使用官方 contents API 读取同一 commit；安全校验错误不降级。不使用缓存冒充在线检查，不改变安装包/备份/回滚/数据安全约束。
- 本地 Linux 更新器定向 25 PASS / 2 Windows-only SKIP，新增 8 项网络故障注入。[PR #27](https://github.com/yudacheng666/AIWorkSpace/pull/27) 产品/测试 SHA `297997540dbdaeb4906d98b4fb1e94869bb125e1` 的 [Actions #41766281412](https://github.com/yudacheng666/AIWorkSpace/actions/runs/41766281412) 已核实 3/3 SUCCESS：Linux Python 149 PASS/12 SKIP + Node 68 PASS，Windows Python 151 PASS/10 SKIP + Node 68 PASS，Windows 真实 Chromium 更新/回滚 3 PASS + UI E2E 7 PASS。未升级真实 Windows 8770，未操作真实 Drive 数据，未修改正式版本号，未合并 main。
- 用户于 2026-11-04 明确要求“合并，发布”，已授权 PR #27 正常合并与 GitHub 发布；候选 VERSION 已设为 2.0.7。用户同时反馈稍后再次点击检查可连通，支持间歇失败现象，但不能据此认定具体网络根因。
- 下一步：核对 2.0.7 最终提交的 Linux/Windows/Chromium CI 全部成功后，通过 GitHub 普通 merge 发布至 main。合并回执以 PR #27 merged 状态及 merge SHA 为准；公司电脑尚未升级，真实企业网络未实测，不操作真实 Drive 数据。

## 2026-11-03：既有异常事件已通过用户授权的 Google Drive 数据层修复

- 用户明确授权修复真实工作台中的既有异常，包括有据可查的重复任务归并、非法生命周期动作及步骤更新/完成事件；**真实业务内容、用户身份、原始文件名、任务编号、私有链接及备份位置不写入公开仓库**，审计详情仅保存在用户自己的数据存储中。
- 本轮先只读核对云端原始事件的来源、精确 revision 和目标状态，创建包含 **66 个原始事件**的恢复快照并上传至用户私有 Drive；确认没有新增并发写入后，按原修订顺序追加 **6 条合法业务事件**（1 条用户授权回收站事件、5 条执行步骤状态/标题修复）。
- 为 6 个异常分别写入 authorize 与 applied 共 **12 条核查审计事件**，来源原件全部保留；6 条业务事件及 12 条审计事件均通过云端回读、字节一致性/散列、目标 revision 与事件流顺序验证。云端回放检查：六项对应审计记录为 applied，未解决的目标事件流冲突 0；重复项不再属于正常任务列表。
- **测试边界**：这里是 Google Drive 数据层读写/回读及本地离线重放检查，**不是**公司 Windows 8770 实机网页验收。Windows 同步、应用新版本、网页刷新后的显示，以及其它设备 Drive 延迟同步仍 **NOT VERIFIED**。原始无效文件不会被静默删除，系统通过已验证的核查状态区分已处理和待处理。
- 本轮补充 AGENTS.md 的云端直写前校验、用户确认/角色、非法 position、revision/冲突、回读与审计规则，防止今后经连接器绕过应用 validator 而重复产生无效事件；未修改产品 Python/JS、正式 VERSION 或真实业务资料至 GitHub。
- **下一步**：用户的工作台同步并升级到 2.0.6 后，检查数据核查待处理数量和任务列表；若与云端结果不一致，再针对实际同步/版本原因排查，禁止重复执行同一条已写入合法事件。



## 2026-11-03：2.0.6 已正式发布至 GitHub main（PR #24）

- **用户发布授权**：2026-11-03 用户明确要求“遵守项目规则，发布最新版本”，本轮按此前已经隔离开发、验收通过的最新 PR #24（2.0.6）执行正式发布；不包括未获批准的 PR #19/#20/#22 或工作档案。
- **准确 RC 验收**：产品/测试最终 PR HEAD `352c7f3854a72ed5a28343a248bdbd658ff17ddb`，[Actions #41599009901](https://github.com/yudacheng666/AIWorkSpace/actions/runs/41599009901) 3/3 SUCCESS（Ubuntu Python 141 PASS/12 SKIP + Node 68 PASS；Windows Python 143 PASS/10 SKIP + Node 68 PASS；Windows Chromium 更新/回滚 3 PASS + 工作台 UI E2E 7 PASS）。最终 HEAD 相对合并前 main ahead 6 / behind 0；提交差异检查未发现新增密钥、真实台账或公司业务文件。
- **发布动作核验**：PR #24 Draft → Ready → GitHub 标准 Merge，返回 merged=true；合并 SHA `2fca238e8e1fd635161d1b0f3a52961e8d982f67`。已重新读取 `main` HEAD 与 `main/VERSION=2.0.6`、PR CLOSED/MERGED。合并后 push [Actions #41609836093](https://github.com/yudacheng666/AIWorkSpace/actions/runs/41609836093) 已独立核实 3/3 SUCCESS（Ubuntu Python、Windows Python、Windows Chromium）；与合并前 PR 的 3/3 SUCCESS 分别记录。
- **修复范围**：防止同一目标异常跨修订号乱序重放；高于当前修订号的候选不提供授权；旧任务 trash 不自动重基到更新后的任务；步骤已人工完成则不重复制造完成动作。原始异常证据不删除、不自动修复。
- **发布边界**：本次发布仅改变 GitHub main；未访问或升级真实 Windows `127.0.0.1:8770`，未写入真实 Google Drive 或 review_events。真实双设备同步及六项异常的人工逐项核查/授权仍待后续单独执行；不得把 GitHub 发布当作本地部署。
- **下一步**：首先核验合并后 Actions 最终状态，再由用户在实际工作台检查更新并自主决定是否应用；实际部署前保存草稿、确认备份，部署后查看数据核查建议但不自动执行修复。历史 PR #19/#20/#22 若恢复须基于当前 main 重新合并/定版及准确 SHA 回归。



## 2026-11-03：数据核查修复顺序保护（2.0.6 发布前候选记录）

- 2.0.5 正式版本已由 PR #23 合并进入 main，merge SHA `f137fd6cd400b23c7878b4cd514ff27b94d88c92`；合并后 [Actions #41595962365](https://github.com/yudacheng666/AIWorkSpace/actions/runs/41595962365) 3/3 SUCCESS。当前候选分支从该 main 派生，VERSION 提升为 2.0.6。
- 对 2.0.5 的核查建议流程做只读数据场景复核时，发现同一目标存在连续非法事件（base_revision 2、3）时，若先处理后一个，可能把较早标题覆盖到较新状态；旧 lifecycle trash 若基于旧任务 revision，也不应重放到更新后的任务。
- 修复策略：高于当前目标 revision 的异常不提供授权，提示先处理前序异常；同一目标异常按 task/step 与 base_revision 升序展示；任务 trash 源 revision 与当前 revision 不一致时禁止自动重放，须从当前任务的正常操作入口重新发起；对低于当前 revision 且允许人工重审的候选，预览明确说明按当前 revision 重建。
- 新增合成测试：连续步骤异常必须按 revision 顺序授权/执行，后一个事件在前一个完成前不可授权；过期 task trash 只能人工核查不写入。原始异常文件保持不变。
- 最终候选 SHA：`49ac4c3f27adceba63fd942fbcd79af0e955fe76`；[Actions #41598685352](https://github.com/yudacheng666/AIWorkSpace/actions/runs/41598685352) **3/3 SUCCESS，0 FAIL**。Ubuntu Python 153 total / 141 PASS / 12 SKIP、Node 68 PASS；Windows Python 153 total / 143 PASS / 10 SKIP、Node 68 PASS；Windows Chromium 更新/回滚 3 PASS、工作台 E2E 7 PASS。新增 2 项专项测试全部通过。
- 该修复只保护后续授权/执行，不会扫描、修改或自动处理真实 Drive 数据。2.0.5 main 未改变；PR #24 保持 Draft，等待用户另行批准后才可合并。
- 真实 Windows 8770 尚未升级；真实异常仍只读检查，任何写入仍需逐项人工确认。

## 2026-11-03：异常发现 → 人工核查 → 明确授权 → 合法写入 → 结果追踪（PR #23 / 2.0.5 已发布）

- 用户要求补齐完整数据治理闭环，起因是首页仅提示“6 项需要核查”，没有可进入的核查页面。此前示例包含：任务 lifecycle 缺少用户 actor/有效 revision、step update 使用 revision 0 或非法 position、step completion 缺少显式确认。
- 正式发布：用户授权 PR #23 后已正常合并进入 main，merge SHA `f137fd6cd400b23c7878b4cd514ff27b94d88c92`，`VERSION=2.0.5`。2.0.5 RC SHA `4d2f27e632821ee4f914f1ad1b60215a98371aa1` 的 Actions #41595613734 与合并后 main Actions #41595962365 均 3/3 SUCCESS。
- 实现：新增独立侧栏“数据核查”页面；只读扫描 task/project/step/settings 事件和 workspace 语义警告，生成基于来源目录、文件名、原始 SHA-256 的稳定异常编号，完整展示原始证据、原因、修复预览、核查轨迹。首页提示不再截断异常清单。
- 追加式 review_events/ 流保存人工 authorize/dismissed/stale/failed/applied 事件；原始异常源文件始终保留、不移动、不覆盖。授权与执行严格分离；修复时重新验证源 SHA、当前 task/step revision、冲突状态、proposal SHA 和既有 validator；合法事件使用新 ID/actor=user 追加，成功回执记录目标事件 ID、文件 SHA 与结果 revision。每次展示 applied 都重新检查目标结果文件完整性；缺失可重新授权，hash/内容变化冻结冲突。
- 支持无歧义修复的范围：lifecycle trash/restore；step update 中剔除非法 position 并保留合法字段；task/step completion 在二次明确确认后写入 confirmed_done。purge、格式损坏、目标缺失、其他项目/设置异常不猜测、不自动写入，只能人工记录“不写入”或使用专门业务界面。
- 多设备安全：Google Drive 同步的授权事件只代表审计记录，不会自动执行；另一设备仍须本机人工确认执行。相同 anomaly revision 并发决定冻结冲突。JSON actor 字段不是强身份认证；服务仍仅允许本机 Host/Origin。
- 自动化测试新增 tests/test_data_governance.py 15 项 Python API/数据层测试和 Windows Chromium 真实网页 E2E；包括原文件 hash 保持、授权不写入、合法写入、完成二次确认、restore、settings anomaly、同步授权不自动执行、并发审查冲突、源/目标 revision 变化、回执缺失/篡改、幂等追踪。**产品逻辑准确 SHA `cc8913083a8ef4616358fa81e4b0f899feb06526` 的 Actions #41591071040：3/3 SUCCESS，0 FAIL。** Ubuntu Python 151 total / 139 PASS / 12 SKIP、Node 68 PASS；Windows Python 151 total / 141 PASS / 10 SKIP、Node 68 PASS；Windows Chromium 升级/回滚 3 PASS、真实 UI E2E 7 PASS（含治理闭环）。新增 15 项治理专项 Python 测试全部通过。
- 自动化结果：Ubuntu Python 151 total / 139 PASS / 12 SKIP、Node 68 PASS；Windows Python 151 total / 141 PASS / 10 SKIP、Node 68 PASS；Windows Chromium 更新/回滚 3 PASS、工作台 UI E2E 7 PASS；15 项治理专项 Python 测试全部通过。
- 发布边界：合并只改变 GitHub main；未升级公司 Windows 8770。真实 Drive 数据只做了只读检查，没有创建 review_events、授权、写入或覆盖任何真实事件。真实双电脑 Drive 同步仍未独立验收。工作档案仍暂停。
- 下一步：当前独立 2.0.6 候选修复同一目标异常的修订顺序保护，需通过准确 SHA CI 并另行获得用户合并批准；真实异常的任何写入仍需逐项人工授权。


## 2026-11-03：步骤删除与步骤级关联文档（独立候选）

- 用户新增两项需求：“步骤增加删除功能”“文档链接关联到步骤级别，而不是任务级别”。前置核对正式 main SHA `8f713526f00370d5c8db518d6fa855b7a3f58885`、VERSION=2.0.4；PR #19（回收站 UI）、#20（父子任务状态联动）、#22（刷新位置）均仍 Draft，本轮不合并也不覆盖。
- 实现采用新独立分支 `feat/20261103-step-delete-step-documents`：步骤删除追加 `delete` 墓碑并从展示/状态/顺序中隐藏；删除前必须用户确认并检查步骤 revision 与排序/同步冲突；不擦除历史文件、不清除 Google Drive 原文件。文档链接改为按步骤独立存储、读写及版本保护；所有新链接只通过步骤 API。
- 数据兼容：旧任务事件中 `document_links` 原样保留并只读展示，用户自行按需重新关联至具体步骤；旧任务级写接口返回 410，不自动迁移，不凭项目名称推断关系。步骤删除后的引用仅隐藏、历史保留；未授权合并前不接触真实数据。
- 测试目标：定向 Python 事件/HTTP（合法删除、确认、版本冲突、并发、迟到旧事件、顺序状态、历史链接、非法 URL）、Node 步骤按钮/草稿/文档区域、Windows 原生 Chromium 从网页创建步骤→关联文档→删除步骤→数据验证；准确 SHA 的 GitHub Actions CI 为准，完成前不得称 PASS。更高风险双电脑真实 Drive 延迟同步仍为 NOT TESTED，后续独立验收只补 CI 未覆盖项。


## 2026-11-03：PR #21 用户批准、准备 2.0.4 正式发布（待最终准确 SHA CI）

- **批准范围**：用户明确“批准”上一轮任务列表列筛选/多字段排序 PR #21 的发布；仅批准此 PR 正常合并到 GitHub main，不包含 [PR #19](https://github.com/yudacheng666/AIWorkSpace/pull/19) 回收站 UI 和 [PR #20](https://github.com/yudacheng666/AIWorkSpace/pull/20) 父子任务状态联动，也不授权任何本地 Windows 8770 / Google Drive 实际升级。
- **发布版本**：原 main `68a3212360fed942ccf2dbfca97afd8f4e224bd3` 的 `VERSION=2.0.3`，PR #21 原 UI/测试 SHA `1c446820c53e4f6c5c892fb3a1c4f52e1368dec8` 的 [Actions #41566900915](https://github.com/yudacheng666/AIWorkSpace/actions/runs/41566900915) 3/3 PASS。因网页更新依赖统一版本号，本独立批准的 PR #21 候选升级为 `VERSION=2.0.4`，并更正 README 项目状态及追加本决策。最终 2.0.4 RC 必须以**新准确 SHA** 的 GitHub CI 为准，不使用旧 SHA 冒充。
- **未合并分支协调**：PR #19 预占了 2.0.4 RC 但尚未批准，保留 Draft；PR #21 先发布 2.0.4 后 PR #19 必须重新基于新的 main 定版为后续版本并回归，PR #20 同理，不强行互相覆盖。
- **当前状态**：PR #21 待最终 RC CI 和正常 merge；禁止提前写合并成功。项目其它功能/代码和真实设备不变。


## 2026-11-03：任务列表字段标题与联合筛选/多字段排序（隔离开发候选）

- **需求定稿**：用户明确要求“Excel 式筛选排序”，**绝不改成 Excel 风格表格**。保持现有任务卡片、状态徽标、整体 UI 不变；顶部新增字段标题行，列内下拉菜单可做多选筛选、关键字、截止日期区间、升降序与多字段排序优先级，提供各列/全部清理。
- **开发基线**：正式 main `68a3212360fed942ccf2dbfca97afd8f4e224bd3`、VERSION 2.0.3；[PR #19](https://github.com/yudacheng666/AIWorkSpace/pull/19) 回收站视觉 2.0.4 RC 和 [PR #20](https://github.com/yudacheng666/AIWorkSpace/pull/20) 父子任务联动仍是独立 Draft、未合并；本轮不更改它们及 main。先从正式 main 派生独立分支，稍后合并按顺序核对冲突。
- **实现边界**：仅展示层过滤/排序，不写数据事件、不变更任务 API、revision、项目关联或草稿；与原先全局筛选 AND 组合，列表视图之外不适用列条件。项目分组仅在全局多键排序时临时展平以保证跨项目排序，原任务卡片完全保留。
- **验收门槛**：新增 Node 定向测试覆盖多列 AND、同列多值 OR、日期范围/空白、空值排序稳定性、排序优先级与清除、其他视图隔离、无 POST，以及 Chromium 真实界面交互（条件选择、排序、详情可打开）；准确 SHA 的 GitHub Actions CI 才能证明通过。用户批准前不合并、不发布、不操作真实 Windows/Drive；工作档案继续暂停。


## 2026-11-02：回收站左侧导航独立页面（2.0.3 RC 候选，正式 main 仍为 2.0.2）

- **用户要求**：回收站入口置于左侧导航标签，不再是“全部任务”页面上的独立按钮。先遵守 AGENTS.md、REQUIREMENTS.md、PROJECT_STATE.md、DECISIONS.md 的持久化规则，核对 2.0.2 main 和合并 PR #17，工作档案 PR #14 继续暂停。
- **隔离开发**：从正式 `main` SHA `8e299ce832a2adb143e45b13882ed1d6b2a4e928` 派生 `feat/20261102-trash-sidebar-page`；不修改 main、不操作 Windows 8770 或 Google Drive 真实任务。UI 基线在分支保持 `VERSION=2.0.2` 通过 CI，现准备独立 `2.0.3 RC`：仅 PR 分支改为 `VERSION=2.0.3`，正式 main 仍为 2.0.2。
- **产品变化**：左下系统导航新增“回收站”，点击进入独立工作区页面，具有导航高亮和顶部当前位置；移除任务列表原按钮及回收站弹窗，将原恢复、勾选永久删除、清空周期等控件移入页面。继续使用既有 API 和事件逻辑，沿用切换页面时的草稿保护。
- **UI 基线验证**：新增 Node 页面导航测试，调整 Windows 真实 Chromium 原有恢复/彻底删除 E2E；准确代码 SHA `1245bbbe6c2d1a56cbf66d18044a9ed8248509ed` 的 [Actions #41450315589](https://github.com/yudacheng666/AIWorkSpace/actions/runs/41450315589) **3/3 SUCCESS**：Ubuntu Python 115 PASS/9 SKIP，Windows Python 117 PASS/7 SKIP，各端 Node UI 61 PASS；Windows 真 app.py + Chromium 共 7 PASS。详见 [PR #18 测试证据](https://github.com/yudacheng666/AIWorkSpace/pull/18#issuecomment-6577973397)。
- **发布候选准入**：2026-11-02 继续按统一版本规划，在同一 Draft PR #18 提升分支 `VERSION=2.0.3`；README 与项目记忆同步标示历史/当前状态。新的准确 RC SHA 和 3 组 CI **尚待执行/核实**，不借用上一 SHA 的 PASS。下一步核验 RC CI 与合并适配；未经用户明确批准不合并、发布或部署，也不默认安排 Codex 重复测试。

## 2026-11-02：用户批准，AIWorkSpace 2.0.2 已正式合并 GitHub main（不等于工作电脑已升级）

- **用户授权**：用户明确回复“批准”2.0.2 GitHub 合并。ChatGPT 先核对 PR #17 HEAD 与准确 RC SHA 的提交差异、`main` 基线、`VERSION` 和 Actions 证据。执行范围仅 GitHub PR 转 Ready + 普通合并，**未授权也未执行真实 Windows 8770 / Google Drive 数据部署、删除、同步或升级**。
- **成功合并**：[PR #17](https://github.com/yudacheng666/AIWorkSpace/pull/17) 从 Draft 转 Ready for review 后以 `merge_method=merge` 正常合并，GitHub 返回 `merged=true`，准确合并 SHA **`bfb741bbb9da943f1d63241a9f8b85df008e0b4a`**；合并前 HEAD **`ba6ce308992ecea157a92c5fe146034e9bbc9dd9`**。重复读取 `main` HEAD 为合并 SHA，`compare(merge,main)` 无额外差异，PR 为 CLOSED / MERGED。
- **正式仓库语义版本**：`main/VERSION=2.0.2`。三个功能是任务回收站（恢复、到期清理配置、手动彻底删除）、执行步骤状态联动任务有效状态（全部完成时仍须人工确认任务完成）、关联多个 Google Drive 文档链接（不复制文件，AI 读取取决于原文档和连接器权限）。工作档案功能仍暂停，不操作 PR #14。
- **准确 RC 测试证据**：产品和测试代码 RC SHA **`faa092d2d9359171f53a01d3f7145197e6412a28`**，[Actions #41443451302](https://github.com/yudacheng666/AIWorkSpace/actions/runs/41443451302) **3/3 SUCCESS**：Ubuntu Python 115 PASS/9 SKIP + Node 60 PASS；Windows Python 117 PASS/7 SKIP + Node 60 PASS；Windows 真 app.py + Chromium 更新器 3 PASS、任务 UI 4 PASS。RC 测试 SHA 之后只更新三份 docs Markdown，产品/测试代码无改动。
- **合并后主干 push CI 状态**：`main` 合并 SHA **`bfb741bbb9da943f1d63241a9f8b85df008e0b4a`** 对应的 `push` 工作流 **NOT VERIFIED**。现有 GitHub 连接器 `fetch_commit_workflow_runs` 仅返回 `pull_request` 关联的运行，不能以该接口结果空列表认定无 CI 或认定 CI PASS。已通过的 RC 测试与合并后 push 测试必须严格区分。
- **尚未测试**：真实两台电脑 Google Drive 云端同步、私人文档实际访问权限、真实任务数据长期运行与正式升级均未独立验证；不可把虚构同步 PASS 当作真实服务验收。同步来的永久删除墓碑会逻辑隐藏任务但不得擅自物理清空另一电脑的文件；云端历史版本、备份不能承诺物理擦除。
- **下一步**：用户可在工作电脑网页中先检查更新并自主选择 2.0.2 一键升级；升级前保留真实数据备份并确认草稿已保存，升级后核对任务总数、原数据、回收站、步骤状态和 Drive 链接。用户还没宣布真实电脑完成升级，不能宣称已部署。测试继续 ChatGPT + GitHub Actions 优先，不默认重复 Codex。


## 2026-11-02：统一版本 2.0.2 正式发布候选（RC）已准备，GitHub CI 3/3 PASS，等待用户批准合并

- **状态**：[PR #17](https://github.com/yudacheng666/AIWorkSpace/pull/17) 已完成 RC 版本与说明，分支 `VERSION=2.0.2`，仍 **Draft / OPEN / 未合并 / 未部署**；正式 `main/VERSION=2.0.1`，用户已反馈实际 Windows 工作台升级 2.0.1 成功（非本机独立验证）。工作档案 PR #14 继续暂停。
- **准确 RC 产品/测试 SHA**：`faa092d2d9359171f53a01d3f7145197e6412a28`；[GitHub Actions #41443451302](https://github.com/yudacheng666/AIWorkSpace/actions/runs/41443451302) **3/3 SUCCESS**。Ubuntu Python 124 total / 115 PASS / 9 SKIP，Node 60 PASS；Windows Python 124 total / 117 PASS / 7 SKIP，Node 60 PASS；Windows app.py + 真 Chromium 更新/回滚 E2E 3 PASS、任务界面 E2E 4 PASS。0 FAIL。
- **RC 首次失败与修复**：旧测试 `tests/test_app.py::test_update_status_reports_local_version_without_network` 曾把版本值硬编码 `2.0.1`，`VERSION` 从 2.0.1 升为 2.0.2 后，[Actions #41443192582](https://github.com/yudacheng666/AIWorkSpace/actions/runs/41443192582) 的 Linux/Windows 各 1 FAIL。修复为从仓库 `VERSION` 文件读取预期值，确保语义版本后续再更新无需修改测试魔数；准确 SHA `faa092d` 完整三组 CI 已通过。该轮未修改三项功能的产品逻辑。
- **已实现需求**：任务回收站（删除、恢复、选中彻底删除、0/7/30/90 天周期）及永久删除墓碑；步骤聚合任务有效状态（全部完成后仅提示用户亲自确认）；任务保存最多 20 个 Google Drive/Docs/Sheets/Slides 链接、跨设备打开、AI 使用现有连接器访问取决于权限。跨设备**虚构数据模拟**已在前序 SHA `5e995c7d2ef67bc4039cc91bba65e3e6d0bceba2` 的 [Actions #41430588371](https://github.com/yudacheng666/AIWorkSpace/actions/runs/41430588371) PASS，RC 正常回归也通过。
- **仍为 NOT TESTED**：两台真实电脑经 Google Drive 服务的掉线/重连和历史版本、真正 Drive 文档权限、公司生产数据及长时间运行。同步来的墓碑只逻辑隐藏，不因此物理删除另一电脑现存文件；本机可确认永久删除或到期清理，但不保证跨副本物理抹除。
- **执行流程**：保留 ChatGPT 开发/自测 + GitHub Actions 准确 SHA 测试；不默认 Codex 复跑已有 PASS 范围。当前无新增需重复 CI 的代码改动。下一步：用户确认 RC 功能范围及未测风险后**明确批准 GitHub 合并**；PR 解除 Draft 后可使用普通 merge 将已通过的 2.0.2 合并 main，核查合并 SHA/main VERSION。实际电脑更新依旧是用户在工作台手动触发，ChatGPT 不操作实际 Windows/Drive 数据。


## 2026-11-02：2.0.2 回收站／步骤状态／Drive 引用已实现，准确 SHA CI PASS（未发布）

- **需求来源**：用户确认实际 Windows 工作台 2.0.1 网页一键升级成功，并明确要求下一版实现任务删除与回收站、执行步骤与任务状态联动、Google Drive 文档关联。实际升级成功是用户反馈，非本轮独立设备核验。
- **隔离范围**：[Draft PR #17](https://github.com/yudacheng666/AIWorkSpace/pull/17)，分支 `feat/20261102-v202-trash-step-rollup-drive-links`，正式 `main/VERSION=2.0.1` 未修改；2.0.2 仅为后续发布目标，未合并、未部署，工作档案继续暂停。
- **实现状态**：
  - 任务详情删除→回收站、恢复、勾选彻底删除；自动清理周期 0（关闭）／7／30／90 天，默认 30 天，程序下一次访问任务列表或回收站时惰性触发，关闭程序期间不执行定时清理。任务 lifecycle 状态与保留周期采用独立追加式事件；跨设备同步回来的旧任务文件因永久删除标记而保持不可见。
  - 本机通过确认操作或本机设置的到期周期清理历史事件文件前，先保存不可逆删除标记；**仅接收另一台设备的删除标记不会擅自物理清理本机历史文件**。其他 Google Drive 历史版本、设备副本及备份不保证物理清除。
  - 非冲突且完整同步的步骤推导有效任务状态：受阻优先，其余有 doing/done 则 doing，全部 todo 则 todo；全部步骤 done 仍仅提示用户亲自确认任务完成，不自动写 done，也不更改原任务事件状态/修订号。
  - 任务可关联最多 20 个经校验的官方 HTTPS Google Drive/Docs/Sheets/Slides 链接，显示/打开/取消关联，不复制文件或改动权限。AI 实际读取依赖用户已授权 Google Drive 连接器和文件访问权限，不保证仅凭链接即可读取。
- **已通过的准确产品/测试 SHA**：`9d25552e9899f27150899a12ab3be48e22b158c1`， [GitHub Actions #41430035182](https://github.com/yudacheng666/AIWorkSpace/actions/runs/41430035182) **3/3 SUCCESS**：Ubuntu Python 123 total，114 PASS / 9 SKIP，Node 60 PASS；Windows Python 123 total，116 PASS / 7 SKIP，Node 60 PASS；Windows 真 Chromium 原更新 E2E 3 PASS、任务交互 E2E 4 PASS（其中本次新增 2 条）。此前浏览器 E2E 提示隐藏和保存时序错误均已定向修复，未绕过 CSP 或缩减业务断言。
- **最新额外两设备仿真**：后续新增针对延迟同步的双设备回归时，旧断言错误要求第二设备自动删除本地事件，已改为“旧事件不会让任务复活，远端 purge 标记不会擅自物理清除本机历史”。最新代码/测试 SHA `5e995c7d2ef67bc4039cc91bba65e3e6d0bceba2`，**[Actions #41430588371](https://github.com/yudacheng666/AIWorkSpace/actions/runs/41430588371) 已对准确 SHA 完成 3/3 SUCCESS**；Ubuntu Python 124 total / 115 PASS / 9 SKIP、Node 60 PASS，Windows Python 124 total / 117 PASS / 7 SKIP、Node 60 PASS，Windows 真实 Chromium 原更新链路 3 PASS、任务交互 4 PASS。新增两设备延迟文件同步回归 PASS；不代表真实 Google Drive 服务端/两台电脑已测试，不能沿用前一 SHA 冒充新 SHA PASS。
- **仍未验收的范围**：真实跨电脑 Google Drive 同步、异步断网/同步历史、不同账户的实际 Drive 文档权限、公司真实任务文件、生产升级及长时运行均 NOT TESTED。此类高风险缺口先评估现有测试与必要的定向独立验收；禁止自动合并、升级、对真实数据操作。
- **下一步**：准确 SHA 自动化 CI 已 PASS。按既定 D021 针对删除/同步及真实 Drive 文件权限的高风险缺口决定必要的增量独立验收；在用户明确批准前不修改正式 VERSION、不合并 main、不部署真实电脑，继续采用 CI-first 去重策略。


## 2026-11-02：用户确认 2.0.1 网页实际一键更新成功；2.0.2 三项任务增强开发中

- 用户直接反馈：公司本地工作台 **2.0.1 网页内置自动更新成功**。这是用户实际操作反馈，尚未由 ChatGPT 独立读取本地 8770 当前文件哈希/Drive 数据，不将其写成独立实机安全验收。
- **新增三项已确认需求**：① 任务删除进回收站、可恢复、自动清空周期及勾选彻底删除；② 执行步骤状态自动联动任务有效状态，仍禁止自动确认任务完成；③ 任务关联 Google Drive 文档链接，人可跨电脑打开，AI 仅通过已有权限的连接器读取，不复制全部文档到工作台数据文件夹。见 `docs/REQUIREMENTS.md` §9 和 `docs/DECISIONS.md` D-20261102-UI-07。
- **独立开发分支**：`feat/20261102-v202-trash-step-rollup-drive-links`，从 `main` SHA `6845b34bb36f97beccada3eb4690cf0ef0270490` 派生；候选统一版本暂定 **2.0.2**，正式 `main/VERSION` 仍为 **2.0.1**。
- **当前未验收**：已写入 app.py 和 web/index.html 的草案（任务 lifecycle/墓碑与留存、步骤有效状态、Drive 文档引用、回收站界面），以及新建 `tests/test_v202_features.py` 虚构数据用例；**尚未按 SHA 执行完整 GitHub Actions/Windows Chromium、跨电脑同步，不宣称 PASS**。需要先 CI 验证和必要高风险独立定向验收；不要升级真实 2.0.1。
- **删除安全边界**：永久 purge 前必须先写不可撤销墓碑，再尽量清除本机事件副本；Google Drive 其他副本/历史/备份不能自动保证物理擦除。自动清空采用访问时惰性执行，服务关闭时不会运行；可能需要用户后续确认是否升级为服务器定时维护。
- **工作档案**：继续暂停，PR #14、独立分支不修改；不合并或部署本候选。


## 2026-11-02：2.0.1 真实 GitHub 发布源 / 旧版→新版 Windows 隔离验证 PASS

- **正式发布版本仍是 2.0.1**：[PR #15](https://github.com/yudacheng666/AIWorkSpace/pull/15) 已合并，正式 merge SHA `7d1a0f2c8cf8135b78a43108f666d750538d6a18`；本轮真实源测试读取到 GitHub `main` **`31963c3c48c9d9cd95663c971a55cb3bb9b108f6`**，公开 raw VERSION **`2.0.1`**。
- **定向 Windows 验收**：[QA-only PR #16](https://github.com/yudacheng666/AIWorkSpace/pull/16) / [Actions #41425066853](https://github.com/yudacheng666/AIWorkSpace/actions/runs/41425066853)，准确 QA HEAD **`749beb40f3748617356861a6919c2f75dd9f4167`**；GitHub-hosted 标准 Windows Runner 单项 **SUCCESS / 1 PASS / 0 FAIL**，未重复之前已通过的全套 CI。
- **新增实际验证范围**：直接从 GitHub 官方发布仓库下载 2.0.0 旧 main SHA `fa51b0123aaac76ddff2064d34178e7cc6e3ab11` 的真实四个程序文件；通过公开 GitHub main API/raw VERSION/zipball 检查和安装 2.0.1；在临时 Windows 程序目录备份旧版、校验新包、执行安装、随机 loopback 端口启动 app 并验证版本与 build SHA、核对虚构 events/project_events/step_events 的 SHA-256 不变；随后从实际备份恢复旧版 2.0.0，并核验程序 SHA-256、无已登记 build 及数据 SHA-256 完全不变。
- **独立风险互补**：既有发布候选 [Actions #41421749629](https://github.com/yudacheng666/AIWorkSpace/actions/runs/41421749629) 在真实 Windows Chromium + 固定 GitHub mock 环境对网页一键更新成功、失败时自动回滚、原端口和 data-dir 不变已有 PASS。本轮只补真实官方 GitHub 下载/真实旧版安装与备份恢复；**真实官方源 + 浏览器一键更新 + 失败注入的端到端组合路径并未作为一个合并场景同时运行**，不能越界推定。
- **QA 证据**：artifact `qa-v201-real-public-source`（ID `13130903143`），[PR #16 评论记录](https://github.com/yudacheng666/AIWorkSpace/pull/16#issuecomment-6574287190)。PR #16 已 **CLOSED / NOT MERGED**；专用 QA 分支不影响 main 2.0.1 产品代码。
- **仍未核实**：合并 SHA `7d1a0f2c8cf8135b78a43108f666d750538d6a18` 对应 `main` 的 push CI 最终状态，因现有 GitHub 连接器 `fetch_commit_workflow_runs` 仅查询 PR 关联运行；不能写成 push CI PASS 或 FAIL。实际公司 Windows 设备、Google Drive 双向同步、正式程序升级和长时间运行均 **NOT TESTED / NOT DEPLOYED**。
- **授权边界与下一步**：用户只授权继续隔离验证；未授权正式公司电脑操作。工作档案 M1 继续暂停；下一步如要升级真实工作台，先确认本机运行版本、安装/数据目录与备份，再取得单独部署批准。继续遵守准确 SHA 和不重复 Codex/CI 规则。


## 2026-11-02：AIWorkSpace 2.0.1 已由用户批准并合并 GitHub main（正式部署仍未授权）

- **用户批准范围**：2026-11-02 用户已明确批准把通过 CI 的 PR #15 合并到 `main`；用户随后在 GitHub 将 PR 从 Draft 转为 Ready for review。批准范围仅 GitHub 代码合并，不包含公司 Windows 正式机器或真实 Google Drive 数据的升级/更改。
- **实际 GitHub 合并**：[PR #15](https://github.com/yudacheng666/AIWorkSpace/pull/15) 已 **MERGED / CLOSED**，通过 GitHub 原生普通 `merge` 保留 PR 分支提交历史；准确合并 SHA **`7d1a0f2c8cf8135b78a43108f666d750538d6a18`**。合并前 PR HEAD `5ee54db89a3f5d86e04815d54046250a1cface51`。再次读取 `main` HEAD 与 `compare(7d1a0f2,main)` 均一致，差异 0。
- **正式 GitHub 代码版本**：`main/VERSION=2.0.1`，`app.py`、`web/index.html` 和测试来自通过验收的 2.0.1 RC；内部 task_id 和原 JSON 事件 schema 不变。用户可在 GitHub main 获取 2.0.1，但不等于工作电脑已经安装 2.0.1。
- **合并前 CI 证据**：准确 RC 产品/测试代码 SHA `97ca50d74641fcb8ae2f232a95651ab7c50fbcd0` 的 [Actions #41421749629](https://github.com/yudacheng666/AIWorkSpace/actions/runs/41421749629) **3/3 SUCCESS**：Ubuntu Python 100 PASS / 7 SKIP + Node 60 PASS；Windows Python 102 PASS / 5 SKIP + Node 60 PASS；Windows 真 app.py/Chromium 既有更新回滚和 UI E2E 3 PASS、新增 2 PASS。该 SHA 后至被合并 PR HEAD 仅修改 `README.md`、`docs/DECISIONS.md`、`docs/PROJECT_STATE.md`、本 session（Markdown），产品/测试代码未改。
- **合并后 CI 状态**：`main` push 对应准确合并 SHA `7d1a0f2c8cf8135b78a43108f666d750538d6a18` 的 Actions 完成状态 **NOT VERIFIED**。当前 GitHub 连接器 `fetch_commit_workflow_runs` 只枚举 `pull_request` 事件，不返回 `push` 运行；不能把该接口空列表写作“没有运行”，也不能冒用合并前 PASS 作为 post-merge PASS。应通过 [GitHub Actions 工作流页面](https://github.com/yudacheng666/AIWorkSpace/actions/workflows/tests.yml) 核对该 SHA 的 push CI 并补记。
- **项目隔离**：工作档案 M1 开发仍暂停，工作档案 PR #14 及独立分支保留，不操作；没有部署 8770、没有读写真实公司 Drive 任务数据、没有触发真实电脑更新。CI 继续遵循 D021：GitHub Actions 优先，Codex 不重复已在准确 SHA/范围通过的测试。
- **下一步**：核实合并 SHA 的 `main` push CI 证据；随后在公司电脑外安排一次 Windows 隔离部署/从旧版升级预演（安全备份、回滚、端口与 data-dir 保护），获用户真实环境部署授权后再操作真实工作台。工作档案待用户重新安排。


## 2026-11-02：用户已批准 2.0.1 合并，但 GitHub Draft 状态尚未解除（BLOCKED）

- **用户审批**：2026-11-02 用户在 RC 验收结果及下一步“合并 PR #15 到 main”的上下文中回复“批准”，明确授权 **仅合并 PR #15**；并未授权公司电脑实际升级、Google Drive 数据操作或工作档案恢复开发。
- **前置条件已满足**：2.0.1 RC 产品/测试准确 SHA `97ca50d74641fcb8ae2f232a95651ab7c50fbcd0`，对应 [GitHub Actions #41421749629](https://github.com/yudacheng666/AIWorkSpace/actions/runs/41421749629) 3/3 SUCCESS。其后到 PR 最新代码仅修改 Markdown 文档；`main` 原 SHA `fa51b0123aaac76ddff2064d34178e7cc6e3ab11`，版本 2.0.0。合并目标为版本 2.0.1，优先普通 `merge` 保留原 PR 历史。
- **实际阻塞**：PR #15 仍是 **Draft**。GitHub 连接器的 `mark_pull_request_ready_for_review` 操作被当前平台安全检查阻止；随后原生 GitHub merge API 带 `expected_head_sha` 请求得到 HTTP 405 `Pull Request is still a draft`。**没有合并，main 未变化，不能将用户“批准”写为已发布或 CI post-merge PASS**。
- **最小下一步**：需要在 [PR #15](https://github.com/yudacheng666/AIWorkSpace/pull/15) 网页点击一次 **Ready for review** 解除 Draft。之后按最新 PR HEAD 再次核实产品/测试 SHA、`main`、CI，执行已批准的普通 Git merge，核验 main 精确 SHA 与 push CI；不要求用户重复批准合并。
- **严格边界**：不得通过强制改写 main、伪造 merge、重复创建 PR 或部署真实机器来绕过 Draft 校验。工作档案继续暂停。


## 2026-11-02：2.0.1 正式发布候选（RC）完成并通过完整免费 CI，等待用户合并批准

- **授权范围**：用户批准制作 2.0.1 正式发布候选并测试；**未授权合并 `main`、公司电脑升级或真实 Google Drive 数据操作**。工作档案 M1 继续暂停，PR #14 / M1 分支没有修改。
- **PR**：[Draft PR #15](https://github.com/yudacheng666/AIWorkSpace/pull/15)，开发分支 `feat/20261102-v2-0-1-task-ids-drawer`，`main` 仍为 `fa51b0123aaac76ddff2064d34178e7cc6e3ab11`，`main/VERSION=2.0.0`。
- **2.0.1 发布候选的完整产品/测试 SHA**：`97ca50d74641fcb8ae2f232a95651ab7c50fbcd0`。正式发布候选 `VERSION=2.0.1`，对应 `tests/test_app.py` 的服务版本状态断言由 2.0.0 改为 2.0.1；未修改其他产品逻辑或数据事件 schema。
- **准确 SHA 正式 CI**：[GitHub Actions run #41421749629](https://github.com/yudacheng666/AIWorkSpace/actions/runs/41421749629) **SUCCESS / 3 of 3 jobs**（公开仓库标准免费 Ubuntu / Windows runner）：
  - Ubuntu Python 3.12：107 total，**100 PASS / 7 SKIP / 0 FAIL**；Node 22：**60 PASS / 0 FAIL**。
  - Windows Python 3.12：107 total，**102 PASS / 5 SKIP / 0 FAIL**；Node 22：**60 PASS / 0 FAIL**。
  - Windows 真 `app.py` + Chromium：原有更新回滚及 UI E2E **3 PASS**，2.0.1 新增编号复制与抽屉草稿保护 E2E **2 PASS**，**0 FAIL**。
- **去重**：此前 2.0.1 功能完整回归 [run #41420159188](https://github.com/yudacheng666/AIWorkSpace/actions/runs/41420159188) 已通过；RC 只追加版本状态断言和 `VERSION`，没有额外重复派 Codex 验收。CI 的 Skip 为 Windows/Linux 环境选择型测试跳过，不伪装为 PASS。
- **完成界限**：这是 GitHub 仓库内 **RC READY / CI PASS**，**不是 main 发布**，亦非正式工作台一键更新或真实 Drive 数据验证。Windows 实际电脑升级、Google Drive 实际同步、长期运行等**NOT TESTED / NOT DEPLOYED**。
- **下一步**：保持 PR #15 Draft；由用户审阅并明确批准合并到 main 后，按既定发布流程合并并复核 main 精确 SHA。实际电脑升级另行独立授权；工作档案继续暂停。本记忆更新仅 Markdown，不影响 RC 的受测产品和测试代码 SHA。


## 2026-11-02：2.0.1 GitHub Actions 免费 CI 验收通过（待发布批准）

- **用户测试指令**：用户指出 Actions 在公开仓库可免费运行，要求恢复执行仓库既定 D021：准确 SHA 的 GitHub Actions CI 为默认验证，Codex 不重复跑同范围。已核实仓库 Public，`.github/workflows/tests.yml` 仅使用 `ubuntu-latest` 与 `windows-latest` 标准 GitHub 托管 runner，不使用计费 larger runner。
- **Draft PR**：[PR #15](https://github.com/yudacheng666/AIWorkSpace/pull/15)，`feat/20261102-v2-0-1-task-ids-drawer` 对 `main`，尚未合并；与工作档案 PR #14 / M1 功能分支隔离。
- **精确 CI 产品/测试 SHA**：`65126022808bc0af1847d67dd999ea7f6e31dee9`。[Actions #41420159188](https://github.com/yudacheng666/AIWorkSpace/actions/runs/41420159188)：**SUCCESS，3/3 jobs**。
- **Ubuntu Python 3.12**：`Ran 107 tests`，**100 PASS / 7 SKIP / 0 FAIL**；Node 22：**60 PASS / 0 FAIL**。
- **Windows Python 3.12**：`Ran 107 tests`，**102 PASS / 5 SKIP / 0 FAIL**；Node 22：**60 PASS / 0 FAIL**。
- **Windows 真实 app + Chromium**：原有更新/回滚和 UI E2E **3 PASS**；本次新增任务短编号复制/抽屉遮罩/未保存草稿保护 Chromium E2E **2 PASS**。独立测试使用随机本地端口、临时虚构 data-dir，测试后检查事件文件哈希不变。
- **失败及根因**：上一 SHA `73840f58a13195ad4daa6b4ec3bad710dd8d2229` 的 [Actions #41419903019](https://github.com/yudacheng666/AIWorkSpace/actions/runs/41419903019) 中，新增复制测试因测试脚本 `page.wait_for_function` 触发产品 CSP 的 `unsafe-eval` 禁止而 ERROR；不是产品复制/草稿保护逻辑的已确认缺陷。仅将该测试改为 CSP 兼容的 Playwright locator wait，提交 `65126022808bc0af1847d67dd999ea7f6e31dee9`，不放松 CSP 或改变产品代码。最新准确 SHA 全绿。
- **测试覆盖与去重**：已经有完整 Linux/Windows 常规回归与实际 Windows Chromium 定向 E2E，因此**无需 Codex 重复验收相同路径**；本轮不做公司真实 Google Drive、Windows 正式安装/一键升级、其他浏览器或生产数据验收，这些属于未来独立部署门槛。
- **版本与安全**：`VERSION` 仍是 `2.0.0`，`2.0.1` 是下一候选发布版本；不合并、不部署、不改 `main` 和工作档案分支，也不接触真实业务数据。此记忆更新是文档-only，不使已通过的产品/测试代码 SHA 失效。
- **下一步**：PR #15 保持 Draft，向用户提交结果与发布候选审阅；获得明确批准并确认版本号处理后才考虑合入 main/安排正式部署。工作档案仍暂停。


## 2026-11-02：V2.0.1 任务编号与抽屉操作优化开发中（工作档案暂停）

### 2026-11-02 本轮隔离验证（对前述开发状态的增量更新）

- **产品与测试源码 HEAD**：`187e097ecfd414b0c8fd1c7bf615be74daae748d`；此后只更新了 Markdown 项目记忆，`app.py` blob `8954614469261816b55a74ede3a4abfc72bb599e`、`web/index.html` blob `8558a60d1c0a44423b90f829f5c69cf074d7633c`、`tests/test_ui_shell.mjs` blob `98c88e8cb9c4467d908ae7fc63598d25b9ebab59`。
- **V8 沙箱 JavaScript 执行 PASS（22/22）**：直接用 GitHub 连接器取得本分支真实网页内嵌 JS 和 `tests/test_ui_shell.mjs`；在可执行 V8 沙箱中加载真实页面脚本，使用该测试文件的模拟 DOM 测试逻辑（将 Node 的 vm/runInNewContext 适配为同隔离作用域 eval，不改变业务断言），执行全部 22 条，其中短编号复制/搜索、抽屉遮罩点击、取消关闭保留草稿均 PASS。
- **Python 函数级隔离执行 PASS（6/6）**：直接从 GitHub `app.py` blob 抽取 `display_task_id` 原函数，在隔离 Python 3.13.5 中复制原函数内容执行 6 条断言：常规 UUID、历史任务、非法日期、时区字符串、大小写和缺日期均 PASS。此测试不是完整 app.py 的 `unittest` 套件，也不验证 reducer 与 HTTP。
- **隔离执行环境**：V8 运行时代码模式及 Linux Python 3.13.5；另一个隔离容器虽具备 Node v22.16.0 和 Chromium，但不能连通 GitHub 获取完整仓库，因此没有运行仓库原始 Node 测试命令或真实 Chromium E2E，也未运行完整 Python unittest。
- **重要区分**：本轮结果只代表 V8 模拟 DOM JS 22/22 与复制的 Python 单函数 6/6；**完整 Python、原生 Node、真实 Chromium、Windows 和 GitHub Actions 均 NOT TESTED**。旧 main SHA 的 CI PASS 不可作为此 SHA 的验收证据。
- **安全和费用**：没有创建 PR（避免 `pull_request` 自动触发 Actions）、没有主动触发 CI、没有修改 main/工作档案分支、没有部署或触碰真实数据。
- **下一步门槛**：在不触发未经批准费用的可访问源码环境运行准确 SHA 的 `python -m unittest discover -s tests -v`、`node --test tests/test_ui_shell.mjs`、必要的真实浏览器定向测试；再审查安全/文件差异及用户批准，方可进入正式 2.0.1 发布和合并。工作档案继续暂停。



- **用户最新优先级**：本对话负责上述小版本改进；个人工作档案开发暂缓，保留原 M0/功能分支不修改。
- **准确 main 基线**：`fa51b0123aaac76ddff2064d34178e7cc6e3ab11`；GitHub 正式 `VERSION=2.0.0`，UI V2 生产电脑/真实 Drive 部署尚不视为通过。
- **本轮分支**：`feat/20261102-v2-0-1-task-ids-drawer`，从上述 main SHA 创建，与 `docs/20261102-personal-work-archive-m0` 和 `feat/20261102-m1-work-archive` 完全隔离。
- **产品代码实现**：
  - `app.py` 在 `GET /api/tasks` 中为任务生成稳定 `display_id`，保留 `task_id` 主键，创建接口也返回 `display_id`；同工作区显示编号碰撞时回退完整 ID 并警示。
  - `web/index.html` 的项目/列表/看板/日历/甘特与详情优先显示短编号，查询可用新旧编号；点击任务详情编号或复制图标使用剪贴板写入并告知结果。
  - 抽屉遮罩仅点击遮罩本体触发既有 `closeTaskDetail()`，保留草稿保护。
  - 没有改写事件格式、没有重编号旧任务、没有把工作事实伪装为已完成任务。
- **测试用例已新增、尚未执行 CI**：`tests/test_app.py` 覆盖历史/UUID 的稳定显示编号、非标准旧 ID、碰撞回退、事件文件不新增；`tests/test_ui_shell.mjs` 覆盖详情复制、短号搜索、遮罩关闭与未保存草稿取消。
- **测试状态**：本分支代码 **NOT TESTED（运行时）**，只做了 GitHub 内容读取和静态变更自查；不继承 main 的 CI PASS 冒充本 SHA PASS。本轮明确不触发 Actions，也不默认消耗 Codex 额度。批准 CI 后应在准确分支 SHA 跑定向回归，确认后再正式候选发布。
- **其他分支**：工作档案 PR #14 与 `feat/20261102-m1-work-archive` 仍独立保存，不修改、不合并；小版本合并之前若工作档案恢复推进，须在其代码分支同步 `main` 并处理重叠区域。
- **VERSION/合并/数据**：当前 VERSION 未变；未触发收费 Actions，未部署、未合并 main，未读写真实云盘工作数据。
- **下一步**：完成定向自测/CI 及风险审查，核对 Windows 隔离更新与数据完整性，再按用户批准建立/合并正式 PR。对事件型事项的记录模型等工作档案恢复后统一实现。



## 2026-11-02：UI V2.0.0 已发布到 GitHub main（尚未正式部署）

- **用户明确批准**：2026-11-02 授权将 UI V2 第一至第三阶段合并到 GitHub main。批准范围**仅限代码仓库合并**，不包含公司电脑、真实 Google Drive 或现有任务数据的更新。
- **正式 GitHub 合并**：使用集成 [PR #12](https://github.com/yudacheng666/AIWorkSpace/pull/12) 的普通 Git merge 保留历史，merge SHA：`c279a976437bb8c1a493be3407a9de3767fa20cf`。阶段一 [PR #10](https://github.com/yudacheng666/AIWorkSpace/pull/10)、阶段二 [PR #11](https://github.com/yudacheng666/AIWorkSpace/pull/11) 随祖先提交进入 main，GitHub 自动将 #10、#11、#12 全部标为 **merged / closed**；**没有重复执行三次合并**。
- **版本号**：main `VERSION=2.0.0`。正式发布候选 `19d17282de5448190420bdea4d60119f0d6b9b05` 在 [PR CI #41382727885](https://github.com/yudacheng666/AIWorkSpace/actions/runs/41382727885) 已三组 PASS。
- **合并后验收**：准确 merge SHA `c279a976437bb8c1a493be3407a9de3767fa20cf` 的 [GitHub Actions #41382882228](https://github.com/yudacheng666/AIWorkSpace/actions/runs/41382882228) 全部 SUCCESS：Ubuntu Python 103 PASS + Node 58 PASS；Windows Python 103 PASS + Node 58 PASS；Windows 真实 app.py + Chromium 更新/回滚及 UI E2E 3 PASS。
- **人工体验**：用户在随机 `127.0.0.1` 端口启动独立隔离体验版，对界面、项目、任务、详情、看板/日历、甘特、关联筛选、草稿保护 8/8 项标记为检查完成。见 [PR #12 原始记录](https://github.com/yudacheng666/AIWorkSpace/pull/12#issuecomment-6568183016)。未报告具体缺陷；不推断真实生产环境同样验证。
- **变更边界**：UI V2 正式代码不改变 `app.py`、`updater.py`、事件 JSON schema 和 API；新增项目管理、四任务视图、统一界面与独立测试启动包。实际公司 Windows `8770`、Google Drive 数据目录、生产安装和一键更新**均未操作或验收**。
- **下一步**：按已有发布/安全门槛安排一次公司电脑外的 Windows 非生产升级预演，验证旧程序备份、版本/构建显示、data-dir 完整性、失败回滚和本机启动；取得真实环境升级授权前，不在公司电脑点击“立即更新”，不删除正式目录和数据。后续新版差异继续使用 GitHub + AGENTS/PROJECT_STATE/DECISIONS/session 记忆机制。


更新日期：2026-10-30（北京时间）  
当前阶段：**M1/M2/M3.1/M3.2/M3.3/M3.4 及内置软件更新中心均已合入 `main`。M3.4 PR #6 合并 `5916744898ac3de1b82c4edf27c339ec9a0173c1`；软件更新中心 [PR #7](https://github.com/yudacheng666/AIWorkSpace/pull/7) 于 2026-10-30 用户批准后 Squash 合并 `ecac63dd1c03d1aa3ba02433bdcafb3d1139b7d2`。固定原产品验收 SHA `42573a34c3190b46c28c1573e98fbca202924a9c`，最新 Windows E2E/测试及工作流 SHA `1ed0d97b8252317425e6b24fd6b1d238d1f9f715`；[Actions #41074274048](https://github.com/yudacheng666/AIWorkSpace/actions/runs/41074274048) 276 PASS / 0 FAIL / 6 设计性 SKIP，Codex Linux 独立验收 PASS（已测范围），Windows 实际 app.py+Chromium 隔离更新/回滚两项 PASS。正式 main 的 API/raw VERSION/真实 ZIP 下载、白名单校验、Windows 隔离安装及真实 app.py 启动已 PASS（[QA PR #8](https://github.com/yudacheng666/AIWorkSpace/pull/8)，[Actions #41077145985](https://github.com/yudacheng666/AIWorkSpace/actions/runs/41077145985)）。公司 Windows 8770 与真实 Drive 仍 NOT TESTED。公司 Windows 8770 未升级、真实 Drive 未访问，**GitHub 合并不等于部署**。**

| 项目 | 当前事实 |
|---|---|
| 仓库 | AIWorkSpace，Public；PR #1 已以 squash 方式合并到 `main`，合并提交 `84fd0d234d799148c7a925a2d49408b11bd69481`；当前只在公司 Windows 电脑部署 |
| 当前代码基线 | `main` 已包含 M1 + M2 + M3.1 + M3.2 + M3.3 + M3.4 + 软件更新中心；PR #7 Squash 合并 `ecac63dd1c03d1aa3ba02433bdcafb3d1139b7d2`，版本文件 `VERSION=1.0.0`，公司 Windows 尚未升级 |
| 最近合并 PR | [PR #7：内置软件更新中心](https://github.com/yudacheng666/AIWorkSpace/pull/7)，2026-10-30 用户批准 Squash 合并，Windows 隔离 E2E 2 PASS，双平台 CI 276 PASS / 0 FAIL；前一 [PR #6：M3.4](https://github.com/yudacheng666/AIWorkSpace/pull/6) 已合入 |
| M1 Codex 验证的代码提交（历史） | `9f06969164e773cf08f03e5d2d02de52c38d688b`；M2 另行在 PR #2 进行 Chromium 复验与 CI |
| 原独立验收 | Codex 对旧 head `37cde4c` 判定 **FAIL，2 项 P2**：同事件 ID 并发写入静默覆盖；GET 接口接受任意 Host |
| 修复后 Codex 复验 | **PASS（本机 Linux 复验范围）**：两项原 P2 均通过；完整测试 23 PASS / 0 FAIL；额外 50 轮线程竞争、12 进程竞争及数据完整性检查通过；未发现新增已确认 P1/P2；限定安全扫描未发现密钥或隐私泄露 |
| P2 修复 A：并发事件丢失 | `append_event` 改用原子硬链接发布，不再以可覆盖目标文件的 `os.replace` 作为最终发布操作。并发复验确认相同事件 ID 最多一个成功，事件未覆盖 |
| P2 修复 B：Host/DNS rebinding | GET 与 POST 在处理请求前执行精确 Host allowlist 校验。复验确认恶意 Host 的 GET 返回 403，合法 localhost 访问正常 |
| GitHub Actions（M1 技术基线历史） | **23 PASS / 0 FAIL（Linux）+ 23 PASS / 0 FAIL（Windows）**：run [40827583905](https://github.com/yudacheng666/AIWorkSpace/actions/runs/40827583905)，Python 3.12；两套任务均 SUCCESS |
| 扩展竞争测试 | **PASS**：Codex 在本机 Linux 额外执行 50 轮线程竞争、12 进程竞争和数据完整性检查 |
| 实际 Windows 同步目录硬链接 | **PASS**：用户在实际 Windows 云盘同步数据目录下完成临时硬链接创建/读取测试；具体本机路径不写入公开仓库。测试目录为临时探针，已清理；现有事件数据未受影响 |
| 实际 Host 防护 | **PASS（用户本机实测）**：普通 Host `127.0.0.1:8770` 返回 200，合法 `localhost:8770` 返回 200，恶意 `attacker.example` 返回 403；新代码包含 Host allowlist 检查 |
| Windows 本机完整测试 | **23/23 PASS**：用户在 Python 3.15 环境执行 `python -m unittest discover -s tests -v`；输出 `Ran 23 tests ... OK`。出现的 ResourceWarning 未导致测试失败 |
| 本机网页创建 → 云端 | **PASS**：测试任务 `TASK-SYNC-TEST-4afb314a` 的创建事件已在 云盘 `AIWorkSpaceData/events` 中核实 |
| 本机网页修改 → 云端 | **PASS**：用户修改测试任务标题后，云端 中出现相应 update 事件；标题已更新为 `测试专用：网页写入同步-4afb314a-网页修改` |
| 云端 → 本机网页 | **PASS（用户实测）**：用户将独立事件 `evt_drive-reverse-0bf4ccb09c.json` 上传至云端 `events` 文件夹并等待同步，随后确认任务 `TASK-DRIVE-REVERSE-0BF4CCB09C` 出现在本机网页。该测试事件已随测试数据一起归档 |
| 断网修改 → 恢复网络 → 云端 | **PASS（用户实际环境）**：用户断网期间修改独立测试任务并保存；恢复网络后 Drive 显示同步完成。云端新增 update 事件 `evt_5075f54a-4aa8-4c32-bea3-3ebcc383b5f9.json` 已核实，`base_revision=2`，标题包含 `-断网测试` |
| 刷新后持久性 | **PASS（用户确认）**：恢复网络并同步后刷新工作台，用户确认标题仍正确保留 |
| 单机旧版本写入保护 | **PASS（Windows 实测）**：独立任务 `TASK-CONFLICT-PROBE-6512fe32` 第一次保存成功；同一旧 revision 的第二次保存返回 HTTP 409；最终标题为 `Conflict probe 6512fe32 - accepted save`，revision=3，`conflict=False`，原值保留。第一次验证的 `ORIGINAL_VALUE_PRESERVED=False` 源于 PowerShell 请求中文标题编码成问号；后续使用纯英文标题复验通过。测试事件保留在追加式历史中 |
| 测试数据归档（历史记录） | **截至 2026-10-29 的 M1 测试归档 PASS**：当时将 10 个虚构测试/演示事件移入 `events/_archive_test_events_20261029`，未删除或改写 JSON；当时用户确认列表为空。**此后 M2/正式部署验收又新增了虚构验收事件**，因此“根目录只剩归档子文件夹/列表为空”仅是历史状态，不代表当前状态。 |
| 单机范围限制 | 当前目标是公司 Windows 单机；不要求第二台电脑测试。已验证创建、网页修改、云端新增、断网期间修改后恢复同步、刷新持久性及旧版本写入保护。长时间稳定性、多次断网重连仍未专项验证 |
| 报告文件 | Codex 独立复验结论与结果摘要已回写 PR #1 评论；公开仓库不保存不可访问的执行环境本地路径 |
| GitHub 评论回写 | PR #1 已包含 Codex Linux 独立复验、Windows/云盘双向同步、断网恢复及旧版本写入保护结果 |
| 公开安全 | Codex 限定范围扫描未发现密钥或隐私泄露；这不是对所有类型泄露的绝对保证 |

## M1 合并前历史审查记录（2026-10-29，当时尚未合并 PR #1）

- 用户确认：公司电脑工作台任务列表为空；10 个历史测试事件全部在云端归档子文件夹，未删除或改写。
- PR #1：head `d4c75057d2e657e1efc9f908a38af40114e87ba5`；base `main`，mergeable；7 个变更文件；仍为 Draft，未合并。
- 最新 CI：[run 40894115476](https://github.com/yudacheng666/AIWorkSpace/actions/runs/40894115476) 两个 job 分别为 Linux/Windows，均 SUCCESS。
- 关键缺口（不能扩大结论）：现有网页能查看与编辑，但没有新建任务入口；过往通过 PowerShell 创建事件或人工上传到 Drive，**不能视为 ChatGPT 已经能够自动把用户口述任务直接创建为云端 JSON**。因此技术基线的实测通过，不等于日常使用型 AI 工作台的全部业务闭环通过。

## M2 进度与验收（2026-10-29）

| 项目 | 状态与证据 |
|---|---|
| 开发分支 / PR | `feat/20261029-m2-web-task-create` / [PR #2](https://github.com/yudacheng666/AIWorkSpace/pull/2)，**已 squash 合并 `main`**；合并提交 `d31f0e2dff7a6c1bf9f3f4ae5754f6d47eadd5bb` |
| 功能 | 服务端 `POST /api/tasks` 自动生成 UUID 编号、默认 todo、原子事件保存；网页新建任务表单 |
| Codex 独立验收 | 首轮 **FAIL（HEAD `4bc0fdb`）**：发现任务甲成功响应会清空后续任务乙草稿；修复后 Codex 在实际 Chromium 对最新修复 HEAD `8e8d4445a6e6787cefb5705c762b7c79e78e1a12` 定向复验 **PASS**，无新增已确认缺陷。原生 Windows 中文输入法仍 NOT TESTED |
| 修复 | **已提交并通过 Codex 定向复验**：提交前记录草稿内容与输入版本。异步成功响应仅在草稿未被编辑时清空；若用户正在填写新任务，保留草稿并提示尚未保存；失败不清空 |
| 自动化回归 | 30 项 Python 测试 + 5 项 Node 原生 UI 时序回归（含 UTF-8 BOM 兼容）；PR 最终 HEAD `ef6cb639` 的 [Actions #40998013795](https://github.com/yudacheng666/AIWorkSpace/actions/runs/40998013795) Linux 和 Windows **均 SUCCESS** |
| Codex 复验报告 | 已直接回写并核实 PR #2 [中文 Chromium 定向复验报告](https://github.com/yudacheng666/AIWorkSpace/pull/2#issuecomment-6500864805)；复验代码 SHA `8e8d4445`，原 P2 PASS。更晚的代码改动仅包含 UTF-8 BOM 兼容与相关测试，经 Linux/Windows CI PASS；这不等于 Codex 对后续 SHA 再做了完整 GUI 测试 |
| Windows + Drive 实机验收 | **PASS（2026-10-29）**：用户在公司 Windows 上以 `8771` 运行 PR #2 SHA `8e8d4445`，网页新建虚构任务 `M2测试：网页新建任务-20261029`，刷新后仍存在；通过已连接 Google Drive 实际读取到 `AIWorkSpaceData/events` 中对应 JSON 创建事件，标题、event ID、task ID、action=create、status=todo 均一致。公开仓库不记录私有 Drive 文件 ID 或本机路径 |
| ChatGPT → Drive → 本机工作台闭环 | **PASS（2026-10-30）**：ChatGPT 通过 Drive 连接器创建并上传合成事件；用户确认公司 Windows 在端口 `8772` 运行最新 PR #2 代码后，任务 `ChatGPT直写Drive链路验证-20261029` 自动出现在网页列表，刷新后仍存在。连同云端事件读回、`utf-8-sig` BOM 兼容修复及 Linux/Windows CI PASS，确认本次端到端链路成立。公开仓库不记录私有 Drive 文件 ID或本机路径 |

## M2 最终审查结论（2026-10-30）

- **产品代码检查：PASS（已审查的最小范围）**。相对 `main` 变动包括网页新建接口/表单、草稿保留、BOM 读取、测试与文档；沿用 M1 原子事件发布、Host/Origin 校验、409 冲突保护和完成确认限制。未发现已确认的新 P1/P2。
- **验证：PASS**。Codex [原 P2 Chromium 定向复验](https://github.com/yudacheng666/AIWorkSpace/pull/2#issuecomment-6500864805) PASS（SHA `8e8d4445`）；后续 BOM 补丁有 Python 回归与 Linux/Windows CI；公司 Windows 分别验证 8771 网页新建→Drive、8772 ChatGPT→Drive→工作台显示并刷新持久性。
- **未测与边界：** Windows 原生中文输入法组成输入专项、长期运行/多次断网重连、跨进程同时操作和多人权限不在此次验收范围；ChatGPT 云端写入依赖当前连接器和临时文件转换流程，不是后台自主执行系统。**不要把 M2 技术原型描述为完整 AI 工作总管。**
- **文档与公开安全：** 已检查 PR 的文件清单/差异；仅代码、测试和匿名化项目文档，没有真实个人数据、凭据或私有 Drive ID。README、项目状态与 PR 描述已调整为现行验收事实。
- **合并结果：** 用户于 2026-10-30 明确批准；PR #2 已从 Draft 转为 Ready 并以 **squash** 方式合并。GitHub 合并不会自动更新公司电脑本机运行的 8770/8771/8772 程序。

## M3 路线（沿用已确认的 REQUIREMENTS.md，不扩写无关文档）

M3 目标：从“可记录和同步的任务列表”升级为“可管理项目、执行任务、跟进进度的个人工作台”。先个人使用，暂不做团队权限或复杂自动化。

### 分阶段范围

1. **M3.1 项目与任务归属（已合并）**
   - 项目有稳定编号和名称；任务可指定一个主要所属项目，也可关联其他项目。
   - 保留“未归类/收件箱”任务，支持按项目查看任务。
   - 项目先保持轻量：不做项目成员权限、预算、甘特图、复杂项目状态或项目审批。
2. **M3.2 任务管理字段**
   - 增加负责人、优先级、截止日期、计划执行日期、下次跟进日期。
   - 截止日期、计划执行日期、下次跟进日期是三个不同字段，不合并。
3. **M3.3 编号执行步骤**
   - 任务可拆成有稳定编号的执行步骤；记录步骤状态与顺序。
   - 任务/步骤的完成均须用户明确确认，不允许 AI 自行标记完成。
4. **M3.4 首页工作总览与查询**
   - 首页逐步呈现：今日亲自处理、待审核/决策、跟进他人、临近到期、逾期/受阻风险。
   - 支持按编号、关键词、项目、状态、负责人和时间筛选。
5. **M3.5 AI 输入与持续跟进完善**
   - 多事项输入自动拆分；信息不足时先询问；重要冲突先给建议并由用户确认。
   - AI 更新进度、记录跟进及决策；重要结果经用户审核后归档。

### M3 共用技术约束与验收原则

- 继续使用当前本机 Python 标准库服务 + Google Drive 同步目录 + 追加式 JSON 事件；不引入付费 API、数据库服务或无关框架。
- 新字段必须向后兼容当前历史事件；禁止为了新模型批量改写旧 JSON，禁止静默覆盖、丢失历史或绕过冲突保护。
- 每个阶段只交付一个清晰的小切片：先需求/数据规则，再代码、自动化回归和 PR；不把后续阶段一并塞入。
- 只在本阶段相关代码发生变化时做针对性回归；不重复要求用户重测已通过的 M1/M2 功能。
- 实机验收仅针对用户指定的公司 Windows 电脑；不要求第二台电脑。
- Public 仓库只提交代码、虚构数据和必要项目记忆；不提交真实台账、个人/企业资料、私有 Drive ID、密钥或本机路径。

## 远程访问安排（2026-10-30）

- 用户决定：**暂时放弃远程访问，待产品功能完成后再补充**。
- 当前 M3.1 及后续产品功能开发期间，不修改本机 Host/Origin 安全限制，不为 Tailscale 增加远程访问白名单，不部署或验收远程入口。
- 当前公司 Windows 部署继续按本机 `127.0.0.1:8770` 使用；电脑二暂不通过 Tailscale 访问电脑一。
- 产品功能阶段完成后，再以届时最新稳定版本单独规划远程访问适配；不回到 M2 或旧测试中间版本重复修改。
- 本决策不改变 Google Drive 数据目录、追加式 JSON 事件模型、已通过的 M1/M2 同步与冲突保护机制。

## 运行实例定位（2026-10-30，用户最新确认）

- 目前在公司电脑本地端口 8770 运行的工作台及其中创建的事项，用户明确视为**开发/验收用测试内容**，不是需要维持不停机的正式业务环境。
- 后续研发切换版本可以停止该测试实例；不为维护旧进程影响开发进度，也不需要先按正式生产系统安排停服窗口。
- **允许停服不等于授权删除数据**：本机目录、Google Drive 中的历史事件与测试证据不得自动删除、清空或覆盖；若后续准备清理，应单独确认删除范围。
- GitHub 合并并不会自动替换当前机器上运行的代码，当前本机服务仍按部署时的 M2 版本运行，不应宣称 M3.1 已自动上线。

## M3.1 独立验收与 P2 修复（2026-10-30）

- 首轮独立 Codex 固定 HEAD `8341816fdd8538a945be31d03d8b147679741d6a`：**FAIL，确认 2 项 P2**。证据见 [PR #3 Codex 回评](https://github.com/yudacheng666/AIWorkSpace/pull/3#issuecomment-6515937505)。
- P2-1：两个同版本合法任务 update 的 `related_project_ids` 含不同数组时，`conflicting_fields()` 直接将列表加入 Python set 比较，抛 `TypeError: unhashable type: 'list'`，导致整个 `GET /api/tasks` 中断。修复为 JSON 规范化字符串比较，冲突仅冻结涉事任务；额外测试覆盖 API 整体读取、重复 event_id、其他任务正常可见与涉事任务 409 保护。
- P2-2：任务引用的项目事件未完成同步时，网页下拉列表没有原先的项目 ID，导致仅编辑标题却提交 `project_id:null, related_project_ids:[]`，追加一条清除引用的事件。修复为对尚未同步的关联显示原 ID 选项，并仅在用户实际修改项目选择时发送关联字段；服务端允许更新时保留**已有**未同步引用，但拒绝新增未知/冲突项目引用。额外测试覆盖网页仅改标题、明确取消主要项目关联、服务端旧引用保留和未知新引用被拒。
- 修复代码及测试 SHA：`ad87b6ca9587fc782aaadeb970680263eb8d1731`。[GitHub Actions #41010659532](https://github.com/yudacheng666/AIWorkSpace/actions/runs/41010659532)：**Linux 与 Windows 均 44 项 Python PASS、9 项 Node UI PASS、0 FAIL**。
- **验收边界**：上述为自动化回归结果；Codex 对本次修复还未独立复验。此前 Codex 未测试公司 Windows、真实 Google Drive 同步与原生中文输入法；本次未触碰本机正式版本、私人数据或 main。

## M3.1 最终独立复验与合并（2026-10-30）

- 修复后固定 HEAD：`aaf89a7ad26077b4292266d3a17429de900d6cdf`。[Codex 独立复验报告](https://github.com/yudacheng666/AIWorkSpace/pull/3#issuecomment-6516104306)：**PASS，原两项 P2 均关闭**；Chromium、项目未同步引用保留、显式取消关联、冲突隔离、未知引用拒绝均在隔离虚构数据下核验通过，无新增已确认 P1/P2/P3。
- [CI #41010816495](https://github.com/yudacheng666/AIWorkSpace/actions/runs/41010816495)：同一 HEAD 的 Linux/Windows 全部 SUCCESS，每平台 44 Python + 9 Node 测试 PASS。
- **用户已批准 Squash 合并 PR #3**。GitHub 返回 merged=true，Squash commit `581075266f94ac26feba8d68bf243f04243bda5d`；已复核 main 指向该提交。
- NOT TESTED：公司 Windows 上 M3.1 新项目界面操作、真实 Drive 双向项目事件同步、原生中文输入法、长时间稳定性。不能将独立云端 Chromium 测试扩展为这些环境已通过。

## M3.2 负责人、优先级与日期字段（2026-10-30）

- [PR #4：M3.2 任务管理字段](https://github.com/yudacheng666/AIWorkSpace/pull/4) 已由用户批准并以 Squash 方式合入 main；固定验收 HEAD `1c9324b991161c08fcaada8d0e2bd78c91cdc0c9`，合并提交 `94a93bcb6fc0bd5123f43925ffa9981edfc20150`。
- Codex 独立验收 [报告](https://github.com/yudacheng666/AIWorkSpace/pull/4#issuecomment-6516549509)：**PASS（已测范围）**。五字段、三日期独立修改/清除、旧数据兼容、冲突/409、异步草稿及失败保护通过；未发现新增已确认 P1/P2/P3。
- GitHub Actions [#41013700472](https://github.com/yudacheng666/AIWorkSpace/actions/runs/41013700472) 与 [#41013705760](https://github.com/yudacheng666/AIWorkSpace/actions/runs/41013705760)：Linux/Windows 每个平台 **53 Python + 15 Node PASS，0 FAIL**。
- NOT TESTED：公司 Windows 上 M3.2 新字段 UI、真实 Drive 对新字段的端到端同步、原生中文输入法、长时间运行与断电耐久性；本次不因此升级本机 8770。

## M3.3 编号执行步骤（已批准并 Squash 合入 main，2026-10-30）

- 开发分支：`feat/m3-03-numbered-task-steps`；[PR #5](https://github.com/yudacheng666/AIWorkSpace/pull/5)，base main `94a93bcb6fc0bd5123f43925ffa9981edfc20150`。**用户已明确批准并执行 Squash 合并，GitHub 返回 merged=true**；main 合并提交：`932f6f9aeb1a83ce537be43e6476674bf717300e`。
- 已实现：每项任务最多 100 个步骤，稳定 `STEP-<32位大写十六进制>` 编号，标题 1–200 字，独立状态/修订号、创建/上移/下移、用户明确确认完成；独立 `step_events/` 追加式事件，保留旧任务与历史事件兼容。按 D013–D015 保留完整排序、部分同步保护、跨 revision 重复 event_id 的冲突冻结和候选、409/Host/Origin/原子不覆盖写入。
- **首轮 P2（部分同步丢 STEP 引用）已关闭**：原版 `4d9e25f` 的 `[A,C,B]` 缺 C 会错误写入 `[B,A]`；修复后 Codex 在 `ce7ae42` 定向复验 PASS：缺 C 禁止排序，C 到达后恢复原排序并允许合法重排，所有旧事件字节不变。[首轮报告](https://github.com/yudacheng666/AIWorkSpace/pull/5#issuecomment-6518205090) / [复验报告](https://github.com/yudacheng666/AIWorkSpace/pull/5#issuecomment-6518742643)。
- **第二轮 P2（重复排序 event_id 跨 revision 未冻结）已关闭**：原版不同内容却共用 `event_id` 时，被当作连续 revision 应用。修复在 `app.py` 对受影响的排序流冻结并保留候选；API 返回 409，不影响独立步骤编辑；新增 3 项回归。[原失败报告](https://github.com/yudacheng666/AIWorkSpace/pull/5#issuecomment-6518742643) / [最终复验报告](https://github.com/yudacheng666/AIWorkSpace/pull/5#issuecomment-6520276064)。
- **代码及测试固定 SHA**：`633b5304e843ca632dca095d42a7ec66d4baabe4`；此 SHA 之后 PR 分支只有 README、PROJECT_STATE、DECISIONS 文档变更。任何后续新的产品/测试代码修改都要重新进行必要验收，不得沿用本次 PASS。
- **CI PASS**：[GitHub Actions #41029302644](https://github.com/yudacheng666/AIWorkSpace/actions/runs/41029302644) Linux/Windows 均 SUCCESS；每个平台 Python 76 PASS、Node UI 23 PASS，合计 198 PASS / 0 FAIL / 0 skipped。
- **Codex 最终独立验收 PASS（已测范围）**：固定产品/测试 SHA `633b5304`。[PR #5 评论](https://github.com/yudacheng666/AIWorkSpace/pull/5#issuecomment-6520276064) 和[证据报告](https://github.com/yudacheng666/AIWorkSpace/blob/31598f1dc95dcefd14ba5bc21f6ce7281cfbd4ab/REPORT.md)：跨 revision 重复 ID 冻结、409/无文件改写、页面冻结与内容独立编辑、不同 ID 连续合法排序；同 revision 并发及旧版本拒写、步骤/排序/父任务冲突隔离、100 步上限竞争、非法输入/ID/排序成员、Host/Origin、部分同步最小回归均 PASS。无新增已确认 P1/P2/P3。Codex 额外 3 条 Python 定向回归 3 PASS，但未重新运行整套 Python/Node，整套结果以 CI 为准。
- **仍 NOT TESTED，禁止扩大验收结论**：公司 Windows 原生 M3.3 界面、真实 Google Drive 的步骤事件双向同步、Windows 原生中文输入法、其他浏览器、真实跨设备同步、多实例并发、长时间运行和断电耐久性、远程访问。独立并发测试属于单机隔离 HTTP 服务，并非真实多设备一致性保证。
- **限制与安全**：公开仓库仅虚构数据；Codex 证据位于独立 audit 分支，不写入产品 PR；未部署/升级公司电脑 8770，未访问真实 Drive，未修改 main；远程访问依 D012 延后。
- **合并结果**：用户于 2026-10-30 明确批准。已将 PR #5 从 Draft 转 Ready 并以 Squash 合并至 main，合并 SHA `932f6f9aeb1a83ce537be43e6476674bf717300e`。CI 及 Codex 独立验收结果仅覆盖上述已测范围，不代表公司 Windows 或真实 Drive 已部署/验证。

## M3.4 首页工作总览与查询（已合入 main，独立验收 PASS（已测范围），尚未部署，2026-10-30）

- 开发分支：`feat/m3-04-workspace-overview-search`；[PR #6](https://github.com/yudacheng666/AIWorkSpace/pull/6) 已于 2026-10-30 Squash 合并，merge commit `5916744898ac3de1b82c4edf27c339ec9a0173c1`。main 当前包含 M3.4；尚未部署到公司 Windows。
- 当前最小切片：在现有 `web/index.html` 增加任务总览卡片、用户选择“本人负责人名称”、今日亲自处理／待跟进他人／7 天内到期／逾期受阻或冲突只读分类，并提供按任务/步骤编号与名称、主要或关联项目、任务状态、负责人、三个日期字段区间的组合查询。仅使用现有 `GET /api/tasks` 返回的数据，不修改 `app.py` 的数据模型、事件流或 API。
- **重要口径**：今日亲自处理=选择的本人的负责人且计划执行日期已到，未完成且未冲突；跟进他人=不同于本人、有负责人且跟进日期已到，未完成且未冲突；七天内到期=今天到第 7 天（含两端）且未完成、未冲突；逾期/受阻/冲突=截止已过、blocked 或 task.conflict；任务可以同时进入多个口径，计数不可相加为总数。日期按访问页面的本地日历。
- **不冒充审批数据**：当前数据没有“待审核/决策”结构字段，也没有可信登录身份；页面明确展示不可自动识别，不能用普通优先级/任务状态猜测审批或把未配置的“本人”显示成 0。身份由用户在当前页面人工选择与负责人一致的名称，不保存、也不写入事件。
- 多条件查询仅影响显示，空结果与 API 读取失败需区分；切换视图、筛选、刷新不应自动新增/修改任何事件；不破坏原 M1–M3.3 创建、编辑、草稿保护、步骤排序与冲突隔离。
- **首轮独立验收发现 P2**：[Codex 报告](https://github.com/yudacheng666/AIWorkSpace/pull/6#issuecomment-6521138972)，固定产品/测试 SHA `46d4a8a7edd4526d48fcff6c37db4a711265cfe3`。真实 Chromium 浏览器整页 reload 时，未保存的任务标题无确认即丢失；已保存事件字节未改变。页面内“刷新任务”保护通过。总览、负责人、查询、日期、空结果/错误区分、只读、页面内草稿保护等已测范围通过；新增 Node 8 PASS。Codex 确认 P2 后停止。
- **P2 修复**：产品代码提交 `5da608a8bbab4d53b2b98a7b6afc5276e17a7732` 在 `window.beforeunload` 监听未保存的任务/步骤编辑草稿；同时将新建任务表单纳入独立持久草稿集合，避免任务列表重绘清掉该状态。浏览器原生提示仅在存在 dirty 草稿时触发；成功保存/干净状态恢复后清除，不自定义浏览器文案。浏览器取消离开会留在页面并保留原输入。
- **回归测试**：新增 `tests/test_create_ui.mjs` 两项 beforeunload 定向测试，覆盖新建任务、任务标题编辑、步骤编辑、新增步骤；检查干净状态/恢复原值/保存成功后不再触发提示。产品/测试当前固定 HEAD：`a84779c12dbc2eb66dcd8573ccf05b2992cd22a7`（产品代码 commit `5da608a8`，最新测试 commit `a84779c1`）。不要把该 SHA 之后的文档维护提交冒充为代码测试版本。
- **CI 状态**：首次运行 [Actions #41046613451](https://github.com/yudacheng666/AIWorkSpace/actions/runs/41046613451) Linux/Windows 均 FAIL，原因是两处新增测试夹具问题（新建任务表单 mock 没模拟 bubbling/恢复基线，步骤列表 mock 选择器漏了 `.step-list` 层级），不是独立验收报告新增的产品缺陷。修正夹具后，[Actions #41046925220](https://github.com/yudacheng666/AIWorkSpace/actions/runs/41046925220) Linux/Windows 均 SUCCESS，每平台 Python 76 + Node 33 PASS，合计 **218 PASS / 0 FAIL / 0 skipped**。
- **第二轮独立复验发现的 P2**：[Codex 报告](https://github.com/yudacheng666/AIWorkSpace/pull/6#issuecomment-6521580578)，固定 SHA `a84779c12dbc2eb66dcd8573ccf05b2992cd22a7`。任务/步骤草稿的刷新确认、取消保留、恢复原值均 PASS；但新建任务表单将标题、负责人、截止日期等字段全部恢复为空后，仍出现原生刷新确认。15 次刷新均未改变 4 个事件文件名/字节，POST=0；Codex 新增 Node 2 PASS 后停止，其他保存成功、页面内保护回归、409/部分同步等 NOT TESTED。
- **第二轮 P2 根因与修复**：`createMetadataSnapshot()` 每次返回新对象；`watchUnsavedEditor()` 直接用 `snapshot() === cleanSnapshot` 比较引用，导致值完全相同仍判定 dirty。产品 commit `0103ae8d167995cc71e996f1e3bd0c6058ad2b7a` 将比较统一改为 `JSON.stringify(snapshot())` 的值快照；恢复每个表单字段的原始值即可从 dirty 集合移除。任务/步骤的原始字符串快照同样兼容。新增回归逐一覆盖新建任务标题、主要项目、关联项目、负责人、优先级、截止/计划/跟进日期的修改与恢复，并验证多字段恢复后不提示、任一字段仍不同则继续提示。
- **最新固定产品/测试 SHA**：`9e0b84e59041b1d8da6d23958e13449e374cbf4b`（产品 commit `0103ae8d`，测试 commit `9e0b84e5`）。[Actions #41049397248](https://github.com/yudacheng666/AIWorkSpace/actions/runs/41049397248) Linux/Windows 均 SUCCESS；每平台 Python 76 + Node 34 PASS，合计 **220 PASS / 0 FAIL / 0 skipped**。
- **前三轮阶段性结论（历史）**：第四轮验收完成前，前三轮固定 SHA `46d4a8a7`、`a84779c1`、`9e0b84e5` 各发现一项 P2；后续修复与最终独立复验结论见下文。当前最终结论为 PASS（已测范围），M3.4 已合入 main。
- **停止后 NOT TESTED**：浏览器整页刷新对步骤草稿的单独实测、查询场景步骤级 409/部分同步排序的额外回归、新建任务表单相邻专项的独立 Chromium 验收。其他未测：公司 Windows、真实 Drive、原生 IME、多浏览器/多客户端、长期/断电耐久性、远程访问。
- 首轮验收时的安全范围：仅测试虚构任务，不访问真实 Drive、公司 Windows 8770，不修改远程访问/Host/Origin；公开 GitHub 无真实资料。当时 PR #6 保持 Draft；后续第四轮独立验收 PASS、用户批准后已合入 main。整个 M3.4 过程未部署。

- **第三轮独立验收发现的 P2**：[Codex 报告](https://github.com/yudacheng666/AIWorkSpace/pull/6#issuecomment-6521932524)，固定产品/测试 SHA `9e0b84e59041b1d8da6d23958e13449e374cbf4b`。任务 A 原保存标题 X，改为 Y 并成功保存；任务 B 同时保留未保存草稿，导致 `refresh(true)` 被草稿保护阻止、列表未重绘；随后 B 恢复原值，再将 A 从已保存 Y 改回旧 X，watcher 因 cleanSnapshot 仍为 X 而错误移除 dirty 标记，整页刷新无确认，未保存 X 丢失。已保存事件没有被覆盖。
- **第三项 P2 修复**：产品 commits `ce0d6d4fd4061184c86c83df432e9bef2729ea79` 与 `eb035c611a592cc01dc7b02138a4951b32a69036`。`watchUnsavedEditor().markClean(savedSnapshot)` 将 clean baseline 推进到成功请求实际提交的快照，并立即按当前表单值重新计算 dirty；无论保存期间是否又有新输入，基线都必须代表已持久化的提交快照。若保存期间又有新输入，新输入仍保留 dirty；恢复到刚保存的快照才清除，恢复到保存前旧值仍为 dirty。任务编辑和步骤编辑保存成功均采用此规则，解决兄弟草稿导致刷新暂缓时的旧基线问题。
- **新增回归**：测试 commit `389c24273766efad612ee68aba34c512a5ad88e7`，分别覆盖任务编辑和步骤编辑：A/Y 保存成功，B 兄弟草稿拒绝放弃导致列表不重绘；B 恢复干净后，将 A 改回保存前旧值，beforeunload 仍必须拦截。测试明确令 in-page discard confirm 返回 false，确保真实覆盖延迟重绘路径。
- **最新固定 CI checkout SHA**：`eb035c611a592cc01dc7b02138a4951b32a69036`（产品代码 commit `eb035c61`；回归测试文件最后更新 commit `389c2427`，测试 blob 未在之后改变）。[Actions #41051917241](https://github.com/yudacheng666/AIWorkSpace/actions/runs/41051917241) Linux/Windows 均 SUCCESS；每平台 Python 76 + Node 36 PASS，合计 **224 PASS / 0 FAIL / 0 skipped**。
- **第三轮验收已测范围**：新建表单 8 字段恢复、原生刷新保护、正常保存、页面内保护、步骤 409、部分同步恢复均 PASS；Node 定向 3 PASS。64 次整页刷新前后已保存事件文件字节一致。新 P2 确认后立即停止，未继续扩展其他未测范围。
- **独立验收最终结论**：前三轮固定 SHA `46d4a8a7`、`a84779c1`、`9e0b84e5` 各发现一项 P2；三项修复后，第四轮在固定 SHA `eb035c61` 上对指定任务/步骤路径独立复验 PASS。三项 P2 均关闭；未发现新增已确认 P1/P2/P3。M3.4 已获用户批准并 Squash 合入 main。
- **第四轮独立复验 PASS**：[Codex 报告及证据](https://github.com/yudacheng666/AIWorkSpace/pull/6#issuecomment-6522552189)，固定产品/原测试 checkout SHA `eb035c611a592cc01dc7b02138a4951b32a69036`，真实 Chromium + 独立虚构数据。任务与步骤均覆盖 X→Y 保存、兄弟草稿阻止重绘、兄弟草稿恢复、再改回旧 X；整页 reload 出现原生 beforeunload，取消后旧 X 与全页面输入保留。保存期间新输入保护 PASS；新建任务 8 字段修改/恢复、正常任务/步骤/新增步骤/新建任务保存、页面内刷新/切视图/应用/清除、实际自动轮询、保存失败、步骤级 409、部分同步排序恢复及恢复后合法排序均 PASS（以报告明确列出的执行范围为准）。Node 定向 5 PASS / 0 FAIL；74 次整页刷新前后事件文件名及字节一致，无覆盖/删除，草稿未自动提交；未发现新增已确认 P1/P2/P3。
- **最新固定产品/原测试 SHA 与 CI**：`eb035c611a592cc01dc7b02138a4951b32a69036`（测试回归最后更新 commit `389c2427`，之后测试文件未变）。[Actions #41051917241](https://github.com/yudacheng666/AIWorkSpace/actions/runs/41051917241) Linux/Windows 均 SUCCESS，每平台 Python 76 + Node 36 PASS，合计 **224 PASS / 0 FAIL / 0 skipped**。CI 224 PASS 与 Codex 独立 Node 5 PASS 是不同执行环境和证据，不混算。
- **仍 NOT TESTED（不得扩大 PASS 结论）**：公司 Windows 原生 M3.4、真实 Google Drive、Windows 原生 IME、其他浏览器、多客户端一致性、长期/断电耐久性、远程访问与部署；未重复旧总览日期全套及所有草稿类型的页面内完整矩阵；物理键盘 F5 和关闭窗口未实测，本轮以真实 Chromium `Page.reload` 验证整页导航；步骤编辑请求期间自身输入控件处于 disabled，未强行解除禁用注入输入。
- 安全范围：测试使用隔离虚构数据；未访问真实 Drive、公司 Windows 8770；未部署或启用远程访问。PR #6 已合并；合并不代表部署。
- 安全范围不变：只使用虚构隔离数据，不访问真实 Drive、公司 Windows 8770；PR #6 已合并，不部署，main 未执行部署操作。

## M3.4 合并后状态与下一步

1. **合并已完成**：[PR #6](https://github.com/yudacheng666/AIWorkSpace/pull/6) 于 2026-10-30 经用户明确批准 Squash 合并；merge commit：`5916744898ac3de1b82c4edf27c339ec9a0173c1`。`main` 已包含该 merge commit；合并后仅追加 README 与 PROJECT_STATE 的文档状态更新，未改动产品或测试代码。
2. **代码与自动化证据**：固定产品/原测试 SHA `eb035c611a592cc01dc7b02138a4951b32a69036`；[Actions #41051917241](https://github.com/yudacheng666/AIWorkSpace/actions/runs/41051917241) Linux/Windows 每平台 76 Python + 36 Node PASS，合计 224 PASS / 0 FAIL / 0 skipped。
3. **独立验收证据**：[Codex 第四轮报告](https://github.com/yudacheng666/AIWorkSpace/pull/6#issuecomment-6522552189)：PASS（已执行范围），Node 定向 5 PASS，74 次整页刷新事件文件完整性 PASS；三项草稿保护 P2 均已修复并通过指定场景复验。
4. **未测边界**：公司 Windows 原生 M3.4、真实 Drive、Windows 原生 IME、其他浏览器、多客户端、长期/断电耐久性、远程访问/部署、物理 F5/关闭窗口及未重复的完整页面内草稿矩阵仍 NOT TESTED。不得把 M3.4 的已测范围 PASS 扩大为全部环境/所有行为均无缺陷。
5. **部署状态**：M3.4 仅合入 GitHub main，未部署到公司 Windows 8770；没有访问真实 Drive，也没有启用远程访问。未经用户明确要求，不自动部署、不修改本机服务或真实数据。
6. **后续阶段**：M3.4 已完成。M3.5 或部署专项尚未形成经用户确认的范围；开始下一阶段前，先依据新的用户目标明确优先级与验收门槛，不自行扩建功能。


## 内置软件更新中心（已合入 main、尚未部署，2026-10-30）

- **用户确认的目标**：首次下载/安装后，后续从工作台网页显示软件版本号、检查 GitHub 固定官方 main、点击一次“立即更新”即可获取、校验、备份、替换并自动重启，不再重复人工下载 ZIP/解压/复制。只允许更新程序，不得覆盖真实数据。
- **合并**：[PR #7](https://github.com/yudacheng666/AIWorkSpace/pull/7) 用户于 2026-10-30 明确批准，已从 Draft 标记 Ready 并 Squash 合并，PR Closed / Merged。merge commit `ecac63dd1c03d1aa3ba02433bdcafb3d1139b7d2`。本轮合并之前 GitHub main HEAD 为 `0a3c8f19808b270eea632e4c0ebddf5bc17cda6f`。
- **实现范围**：`VERSION=1.0.0`、网页当前版本/build、GitHub main 更新检查、app.py 更新 API、`updater.py` 独立 helper、只安装 `app.py`/`updater.py`/`VERSION`/`web/index.html` 四项程序文件；验证 commit SHA、来源、ZIP CRC/路径穿越/符号链接、文件清单/大小、Python 语法；程序数据目录安全隔离、程序外备份/manifest、停旧服务/同端口及同 `--data-dir` 重启、新版本健康检查/失败自动回滚；未保存草稿阻止更新；仍只允许本机 Host/Origin，不增加远程访问或付费依赖。
- **Linux 独立验收**：[Codex 报告及原始证据](https://github.com/yudacheng666/AIWorkSpace/pull/7#issuecomment-6524335908)，固定产品/原测试 SHA `42573a34c3190b46c28c1573e98fbca202924a9c`；真实 Chromium + Linux 本机隔离目录下，网页检查/更新/重启及失败回滚 PASS（已测范围），Python 定向 22 PASS、Node 2 PASS、29 项预检 PASS，无确认 P1/P2/P3。恶意压缩包、目录隔离、并发/草稿/Host/Origin 与数据完整性等指定测试 PASS。
- **Windows helper 原生回归**：GitHub Windows Runner 真实运行 `updater.py` helper（模拟 HTTP 程序）两项 PASS：新版本重启、故障自动回滚；不以该模拟服务测试冒充完整网页验收。
- **Windows 原程序 + 真实 Chromium E2E**：GitHub-hosted Windows Runner 临时应用目录复制原始 `app.py`、`updater.py`、`VERSION` 和 `web/index.html`，真实浏览器执行网页一键更新成功、旧进程退出、同端口及原 `--data-dir` 启动新版本；故意让新程序启动失败后完整恢复旧程序/旧服务，两项 **PASS**。所有模拟事件根目录及 `events/`、`project_events/`、`step_events/` 的虚构文件名与字节 SHA-256 不变；外部备份、manifest 及证据日志核对通过。固定 E2E/测试 SHA `1ed0d97b8252317425e6b24fd6b1d238d1f9f715`，更新操作源为固定 GitHub URL 的 mock commit/ZIP（非真实远程 ZIP）。[Actions #41074274048](https://github.com/yudacheng666/AIWorkSpace/actions/runs/41074274048) Windows、Linux 与 Windows Browser E2E 三项 job 全部 SUCCESS，**276 PASS / 0 FAIL / 6 个设计性 SKIP**；[artifact](https://github.com/yudacheng666/AIWorkSpace/actions/runs/41074274048/artifacts/12985633374) 保留截图、Playwright Trace、服务日志、网络请求、结果及备份证据。
- **真实 main 更新源校验（合并后已执行）**：官方 GitHub API/main、固定 commit RAW VERSION 现可读取 1.0.0，旧 404 阻塞已解除。[QA PR #8](https://github.com/yudacheng666/AIWorkSpace/pull/8) 的 Windows Runner 使用原版 `updater.prepare_update()`、**真实 GitHub API/raw/zipball（无 HTTP mock）**，按实际提交 `163827338372fafa57a15e55939d4f0955959310` 下载 ZIP，通过路径/白名单/来源校验后暂存和 `apply_staged_update()` 安装到临时应用目录，验证备份、构建信息与真实 `app.py` 在独立本地端口启动，`GET /api/update/status` 返回版本 1.0.0 和官方 SHA；虚构 data 根及 events/project_events/step_events 哨兵文件 SHA 未变化。[Actions #41077145985](https://github.com/yudacheng666/AIWorkSpace/actions/runs/41077145985) 三个 job 全部 SUCCESS、真实公开源烟测 1 PASS；[结果 JSON 和服务日志](https://github.com/yudacheng666/AIWorkSpace/actions/runs/41077145985/artifacts/12987521846)。首轮失败仅因为 Windows checkout CRLF 与 GitHub ZIP LF 的严格比较，修正 QA 的文本比较后重跑通过；**无产品代码更改**。该测试验证真实公开源 ZIP 下载/校验/安装/启动；不包含同一测试中的网页按钮/helper/回滚，后三项已在固定来源隔离 Windows Chromium E2E 2 PASS。语义版本仍为 1.0.0，后续仅文档提交可能改变 build SHA。
- **截至本轮仍 NOT TESTED**：将真实 GitHub ZIP 下载与网页按钮/helper/故障回滚合并为一条完整联合链路（真实 ZIP 单独安装已 PASS，浏览器/独立 helper/回滚已在固定来源隔离 E2E PASS）；公司 Windows 8770 上的新程序升级、真实 Drive、企业网络代理/权限、Windows IME、长时/断电、多浏览器、多客户端及远程访问。**GitHub 合并不会自动升级公司电脑**。
- **下一步**：已完成发布源真实 ZIP/隔离安装校验；QA PR #8 保持 Draft、未合并，仅用于验证和证据归档。下一阶段准备首次 Windows 非生产目录安装预演与操作手册，确认旧程序安全保留、独立 `--data-dir`、服务停止/启动和数据文件核对。只有用户另行明确批准本机部署后，才能升级公司 Windows 8770 或访问真实 Drive。首次正式部署最新版后，工作台网页的一键更新才可用于后续版本。


## UI V2 正式改造（阶段一已完成，等待用户体验确认，2026-10-31）

- **用户批准**：用户体验独立 HTML V2 交互原型后表示整体满意，批准按阶段正式开发，并要求开发记忆长久化；用户明确要求不转交 Work。本阶段通过 GitHub 仓库协作直接实施。
- **设计基线**：以用户确认的 V2 原型为准。阶段一先统一框架、工作总览、任务列表、任务详情抽屉、新建任务弹窗、项目与设置分页面；看板、日历、甘特图属于后续阶段。
- **开发分支 / PR**：`feat/20261031-ui-v2-phase1-layout`；[Draft PR #10](https://github.com/yudacheng666/AIWorkSpace/pull/10)，目标 `main`，保持 Draft / 未合并。UI 代码测试 SHA：`f29f0be8f6557e134a65fb58c7d2dd8eb15b5a3e`；基线 main SHA：`654d14b33f859d2b85e762e95154d0495ade116c`。
- **阶段一已实施**：
  1. 左侧统一导航和顶部工具栏；工作总览、全部任务、项目管理、系统设置拆分为独立页面。
  2. 软件更新中心移入系统设置，不再占据业务首页。
  3. 工作总览保留 M3.4 的五类快捷分类和统计；说明性小字收敛到悬浮提示。
  4. 任务列表使用摘要行，支持全局搜索、既有组合筛选及本地排序（项目/截止日期/优先级/名称）。
  5. 任务详情改为右侧抽屉，复用原有 `row(task)` 编辑器与 `stepPanel`，保留任务/步骤保存、revision/409、完成确认、步骤排序冲突和草稿保护。
  6. 新建任务改为弹窗，继续调用原有 `POST /api/tasks`，关闭弹窗保留未保存草稿；创建成功后进入任务列表。
  7. 项目管理独立成页；统一按钮、字体、间距、状态色、列表和响应式布局。
- **数据与安全边界**：未修改 `app.py`、API 契约或 `events/`、`project_events/`、`step_events/` 事件结构；没有新增工时、百分比进度、任务依赖等未批准字段。仅使用虚构数据；没有访问真实 Google Drive、公司 Windows 8770 或部署程序。
- **测试结果**：[GitHub Actions #41192430422](https://github.com/yudacheng666/AIWorkSpace/actions/runs/41192430422) 三个 job 全部 SUCCESS：Linux Python 103/103、Node UI 44/44；Windows Python 103/103、Node UI 44/44；Windows 真实 app.py + Chromium E2E 3/3 PASS（软件更新成功、失败回滚、新 UI 工作流）。UI 浏览器专项覆盖导航、设置页、弹窗打开/关闭、通过真实 API 新建虚构任务、任务详情/执行步骤抽屉、全局搜索、390px 窄屏无横向溢出及无未捕获页面错误。
- **视觉证据**：[Windows Chromium 截图、Playwright trace、测试结果和隔离服务日志 Artifact](https://github.com/yudacheng666/AIWorkSpace/actions/runs/41192430422/artifacts/13039321657)。证据均来自 GitHub-hosted Windows 临时目录和虚构数据。
- **明确未测范围**：用户公司电脑、真实 Google Drive、企业代理环境、真实数据升级/部署、其他浏览器、真实手机设备、屏幕阅读器/完整键盘可访问性及长时间耐久性。Chromium 的 390px 视口检查不能替代真实手机验收。
- **合并 / 部署状态**：PR #10 保持 Draft / 未合并；`main` 未修改；未部署。所有自动化通过不代表用户已完成视觉验收，也不代表可以直接合并。
- **下一步**：用户查看 PR #10 和浏览器证据；如有细节问题，继续在本分支迭代。只有用户明确批准合并后才可合并；阶段一确认后再进入阶段二看板、日历、甘特图。



## UI V2 第二阶段（2026-10-31，开发和自动化验收已通过，等待用户体验）

- **阶段关系**：第一阶段 Draft [PR #10](https://github.com/yudacheng666/AIWorkSpace/pull/10) HEAD `15a96bcc5f8f74221161b10b1c0cdfa6d81ddaed`，[Actions #41192788941](https://github.com/yudacheng666/AIWorkSpace/actions/runs/41192788941) 全部 SUCCESS，仍未合并。第二阶段在其 HEAD 建立 `feat/20261031-ui-v2-phase2-views`；[Draft PR #11](https://github.com/yudacheng666/AIWorkSpace/pull/11) 对 main 展示累计变更，**依赖 #10，不应独立合并**。
- **已实现功能**：全部任务页四视图（列表／看板／日历／日期甘特图）。看板按待处理、进行中、受阻、已完成、冲突分别展示，任务可打开已有详情；日历按截止日期、计划执行日、跟进日期择一展示，缺失日期单列；日期甘特显示 42 天计划日及截止日窗口，日期缺失、倒序、冲突不强行绘制。没有工时、实际进度、依赖关系、拖放写入或新增持久化字段。
- **已保留保护**：所有视图共用既有搜索、筛选、排序与任务详情抽屉；切换视图前保护未保存任务或步骤草稿。app.py、更新器、事件结构/API 未修改；完成状态仍需明确人工确认。
- **固定验收 SHA**：`295dfb6fb88ef063697a67502585ed5935484ae6`；[GitHub Actions #41196846211](https://github.com/yudacheng666/AIWorkSpace/actions/runs/41196846211) 全部 SUCCESS：
  - Linux：Python 103 PASS；Node UI 51 PASS（0 FAIL）。
  - Windows：Python 103 PASS；Node UI 51 PASS（0 FAIL）。
  - Windows 隔离真实 app.py + Chromium：3 PASS（原软件更新成功／故障回滚、新的 UI 工作流）。
  - 新 Chromium UI 工作流包含真实网页创建带日期虚构任务、看板分组、日历三日期逻辑、甘特日期标记与导航、筛选、390px 模拟移动视口和无未捕获页面错误。它不是用户公司电脑或实体手机验收。
- **测试证据**：[Windows Chromium 截图、Playwright trace、结果 JSON 及服务日志 Artifact](https://github.com/yudacheng666/AIWorkSpace/actions/runs/41196846211/artifacts/13040502691)。CI 使用虚构数据和 Windows 临时隔离安装目录，没有访问公司 8770 或 Google Drive 真实数据。
- **剩余未测与门槛**：用户实际视觉/业务体验、真实公司 Windows/Drive 环境、真实手机设备、其他浏览器、完整键盘可访问性/屏幕阅读器、长时间运行。自动化 PASS 不等于整体用户体验验收，也不授权合并/部署。
- **下一步**：用户查看 PR #11 的 UI 截图/证据；如有反馈，在独立分支精确修复。保留 PR #10/#11 Draft；只在用户明确批准合并后按依赖顺序进入 main。后续阶段增强需沿用已批准范围，不擅自引入新的业务字段。

## UI V2 第二阶段视觉复核与导航修订（2026-10-31，待本轮 CI）

- 用户继续推进后，读取第二阶段 [Actions #41197003074](https://github.com/yudacheng666/AIWorkSpace/actions/runs/41197003074) 的真实 Chromium Artifact，直接查看 `ui-v2-phase2-gantt.png`、桌面详情抽屉和 390px 移动视口截图；发现甘特图 42 日挤压成密集文字、日历和甘特入口藏在任务页标签下，未完全符合已确认独立页面入口。
- 本轮修订同一个阶段二 Draft PR #11，不另开重复 PR：左侧增加状态看板、任务日历、日期甘特图入口；进入页面时上下文标题/侧栏高亮与对应视图一致。组合筛选折叠为可展开区，避免阻挡图表主体。
- 甘特图改为至少 1840px 横向滚动时间轴，单日不小于 36px，加周起始分隔线，避免 1440 宽一屏挤 42 天；新增日历月／周视图及上周／下周按钮语义，七天周视图在窄屏下支持横向滚动。无业务数据模型变更。
- 新增 DOM 和 Windows 真实 Chromium 定向断言：导航页标题、月/周切换与日期范围、甘特横向滚动、筛选可用性；保持 CI 去重规则，**本轮新 SHA 仍待验证，不可沿用上一版 PASS**。
- 合并/部署仍禁止：PR #10/#11 保持 Draft，main 未修改，真实公司数据、Drive、手机未使用。项目记忆以此文档、会话文件、PR #11 和 Actions 的准确 SHA 为准。

- **2026-10-31 窄屏缺陷修复候选**：视觉复核增量的首轮准确 SHA `58cee55227dd2fb6c2ff41d062235d28f0d0cde1`，Linux/Windows Python+Node PASS，Windows Chromium 真实应用更新/回滚 PASS，但 **390px 移动视口页面横向溢出 FAIL**；从失败 trace 中核实侧栏入口增长后页面宽度被撑大。已修复移动端 CSS Grid `1fr` 的自动最小宽度为 `minmax(0,1fr)`，为侧栏、导航、工具栏和内容建立明确 100% 宽度边界，新增周历与首页窄屏断言并输出诊断宽度。新提交待 CI 证实；不把首轮误记为 PASS。


## UI V2 第三阶段（2026-10-31，开发中）
- 用户明确同意执行第三阶段项目管理/交互完善，完成后再提供独立测试软件包；未授权合并 main 或部署公司电脑。
- 阶段二基线 Draft PR #11 HEAD `1a6ce37837ffa8408d119580fe69e2a3e35a98c2`，Actions #41200661751 Linux/Windows/Chromium PASS。
- 新分支 `feat/20261031-ui-v2-phase3-projects` 从第二阶段未合并代码派生，项目卡片增加主要归属/关联/风险统计、项目检索排序、项目任务只读概览以及直达已筛选任务列表。同步缺失的项目仅标记待核查，不生成新的事件或抹除原项目 ID。
- 项目新增和改名仍由原 API 保存；新增项目编辑草稿的刷新/切换保护；保留原 revision/409 和任务人工确认机制。app.py、持久化事件结构保持不变。
- Node 新增四组项目专项，尚需准确 SHA 的 GitHub CI 与 Windows Chromium 真实浏览器测试。未合并、未部署，不触碰真实 Google Drive。

- **2026-10-31 测试包构建方案**：第三阶段第一轮固定 SHA `6c6b5b85f43469a143640b4e5b1a02be9eaeea7b`，GitHub Actions #41203032835 三组 SUCCESS；为用户交付可实操的 V2 测试版本，在同分支添加无外部依赖的隔离启动脚本 `preview/launch_isolated.py` 和 Windows 双击启动器。测试时由系统临时目录复制应用白名单文件、使用随机 `127.0.0.1` 端口和全新临时 data-dir；按 Enter 终止并清理，不访问真实 Drive/8770。Windows CI 通过后上传 `AIWorkSpace-UI-V2-isolated-preview` Artifact ZIP，供用户下载实操；首次构建需按新 SHA 复验，不提前宣告 PASS。


## 2026-11-02：UI V2 用户人工体验进展（第三阶段）

- **反馈来源**：用户实际启动 UI V2 独立隔离体验包后，逐项回传 8 项勾选：①整体界面、②创建项目、③创建任务、④任务详情、⑤看板与日历、⑥甘特图、⑦项目关联和筛选、⑧未保存保护。
- **结论口径**：八项均已被用户标记为**检查完成（8/8）**，尚未提供具体缺陷描述；不能把没有缺陷报告自动等同于正式发布批准或真实生产环境兼容验收。没有再次执行自动测试。
- **验收依据**：[PR #12 人工体验原始记录](https://github.com/yudacheng666/AIWorkSpace/pull/12#issuecomment-6568183016)；此前已完成的准确产品 SHA `2760425ecc9b9f8f23b477a5b69f719632fe6554` 和 [Actions #41203324785](https://github.com/yudacheng666/AIWorkSpace/actions/runs/41203324785) 仍为代码与 CI 权威证据（Linux/Windows Python 103 PASS、Node 58 PASS；Windows 真实 Chromium 3 PASS）。
- **发布边界**：用户体验采用随机 `127.0.0.1` 端口、临时数据目录；不等于在公司 8770/真实 Google Drive 上已验证安装与升级。#10、#11、#12 均仍 Draft/未合并；main 仍为 `654d14b33f859d2b85e762e95154d0495ade116c`，没有正式升级 1.0。
- **下一步**：待用户明确反馈是否仍有需要修改的操作/视觉问题；如明确批准合并，先核对三阶段分支依赖与重复差异并按用户批准的方案合并。正式升级前补足非生产真实 Windows 安装、备份/回滚、真实数据隔离边界检查；未经用户明确授权不执行合并或部署。


## 2026-11-02 UI V2 合并批准与版本发布候选

- **明确用户授权**：用户批准把已体验的 UI V2 合并到 `main`；没有批准在公司电脑部署、点击网页一键更新或访问/修改 Google Drive 真实数据。
- **合并预检**：#10 HEAD `15a96bcc`、#11 HEAD `1a6ce378`、#12 HEAD `77cf74fd` 形成线性祖先链，后者完整包含前两个阶段；main `654d14b` 未改变。对比 main→#12 共 28 提交，14 个文件，仅网页、测试、CI、项目记忆和独立预览脚本；未修改 `app.py`、`updater.py` 或现有事件数据结构。
- **已有测试/体验证据**：上一产品 SHA `2760425ecc9b9f8f23b477a5b69f719632fe6554` 的 [Actions #41203324785](https://github.com/yudacheng666/AIWorkSpace/actions/runs/41203324785) Linux/Windows Python 103 PASS、Node 58 PASS，Windows Chromium 3 PASS；后续文档改动不改变产品。用户隔离体验 8/8 已检查，见 [PR #12 回评](https://github.com/yudacheng666/AIWorkSpace/pull/12#issuecomment-6568183016)。
- **发布版本标记**：在同一个集成 PR #12 中将 `VERSION` 从 `1.0.0` 更新为 `2.0.0`，同时维护真实版本端点测试和说明。这一版本变动需按新的准确 SHA 重跑必要 CI，**运行通过前不得称为正式 PASS 或合并**。
- **最终合并策略**：只用 #12 作为三阶段累计变更的最终 Git 合并入口，使用保留历史的 merge commit 使 #10/#11 的祖先提交进入 main；对两旧 PR 保留记录，若 GitHub 未自动关闭，则以重复已吸收为由关闭（不分别重复合并）。
- **正式部署门槛**：合并与代码发布不启动公司 Windows、8770、Drive 同步或任何程序自动更新；真实生产环境仍须独立安装与备份/回滚验证及明确授权。


## 2026-11-04：数据核查中心可用性改造（2.0.8 候选）
- 用户反馈：现有“数据核查”页面展示内部 ID、SHA-256、原始 JSON 和英文校验错误，普通管理者无法理解异常或判断如何处理。
- 基线：正式 main SHA c4817668730de6631c86877e93571bd5d4456e15，VERSION=2.0.7；本轮在独立分支 fix/20261104-review-center-usability 开发，不修改 main，不操作公司 Windows 8770 或真实 Drive 数据。
- UI 改造：统计卡片和状态改为业务语言；列表显示关联任务名称及异常含义；详情分为“发生了什么 / 对工作台的影响 / 建议怎么处理”；修复预览改为目标对象与字段值；原始 JSON、内部编号、SHA-256、原始错误及 proposal 结构默认折叠到技术详情。
- 后端补充：将 invalid step_id 归类为“执行步骤记录中的步骤编号无法识别”，解释其不可自动修复原因，明确不猜测/不改绑/不覆盖；提供关联任务名称和记录中的步骤名称。无效步骤编号只允许人工核对后记录“保留、不写入”，原始文件和业务事件均不修改。
- 新增 Python 数据治理测试及 Node UI 测试；测试结果以该分支准确 SHA 的 GitHub Actions 为准，当前尚未运行。
- 安全边界：不自动写入或删除真实数据；保留授权/执行分离、源 SHA、目标 revision、冲突检查和 validator；候选 VERSION=2.0.8，未合并、未发布、未部署。
- 下一步：核验 PR 与准确 SHA 的 GitHub Actions（Linux、Windows、Windows Chromium）；修复失败项后只复测受影响范围。通过后向用户展示 PR/CI 结果，等待用户决定是否发布。

- 最终候选 PR：#28（https://github.com/yudacheng666/AIWorkSpace/pull/28），准确 head SHA d23d050701ff831a81fe2b9282857ca1fc606c26；GitHub Actions run 41770447630 对该 SHA 的 Linux Python、Windows Python、Windows real-app + Chromium E2E 三个 jobs 全部 PASS。
- Windows Chromium E2E 已调整为验证“技术详情默认折叠、用户主动展开后仍可查看原始 JSON”，并验证新授权按钮文案；原先旧测试仍要求 JSON 默认显示和旧按钮文案，首次 CI 因测试断言过时而失败，已更新 E2E 后完整复验通过。
- 当前 PR 仍为 Draft / Open，未合并 main、未发布、未部署；本轮不访问真实工作台数据；此前真实数据层核查/修复记录见本文件 2026-11-03 专项记录。

- 最终分支 head 已推进至 277044654d2c0d1e52d5259c96374e2f4d47062d（含最后的文档/会话记录提交）；GitHub Actions run 41770691637 对这一准确 SHA 再次完整通过：Linux Python、Windows Python、Windows real-app + Chromium E2E 全部 SUCCESS。PR #28 仍为 Draft / Open。


## 2026-11-04：数据异常处理列表聚合与统计口径修正
- 用户指出核查界面无法理解；首轮 2.0.8 候选已把英文错误、原始 JSON 和内部编号移入折叠技术详情，并提供中文影响/建议，但复核发现相同任务/步骤的异常仍重复占据列表，侧栏名称与页面用途不一致，统计卡片的“需要处理”还包含“已授权待执行”而重复计数。
- 本轮在 PR #28 分支追加：侧栏改名“异常处理”；按任务/步骤对象聚合多条异常，展开后仍逐条独立处理；无效步骤引用只按记录中的步骤名称作分组提示，不建立错误关联；待核对、已授权待执行、已修复、已确认保留改为互斥计数。
- 仅修改展示逻辑、Node UI 测试和项目文档；不改变后端事件模型、授权 API、业务事件或任何真实工作台数据。现有 2.0.8 候选的 Linux/Windows/Chromium CI 已对前一 SHA 通过；本次新增改动等待新准确 SHA 的 GitHub Actions 回归。

- 本轮首次回归 Actions #41771911358 的 Ubuntu UI 测试发现测试夹具未调用 loadReviews，导致分组列表为空；统计文案断言未考虑测试 DOM 的文本节点空格。属于新增测试自身问题，已按真实页面加载路径修正，等待下一准确 SHA 的完整回归。
- **最终回归通过**：产品/测试准确 SHA `cedf8b9c7c2e6a87bbcf23450b32eeabd918823b` 的 [Actions #41772135553](https://github.com/yudacheng666/AIWorkSpace/actions/runs/41772135553) 3/3 SUCCESS：Ubuntu Python+Node、Windows Python+Node、Windows real-app + Chromium 更新/回滚 3 PASS、工作台 UI E2E 7 PASS（含数据核查授权/执行/追踪真实浏览器流程）。首轮 Node 测试夹具问题已修正，未重复执行旧 SHA 的测试。
- **当前发布边界**：PR #28 仍 Draft / Open；未合并 main、未发布、未部署公司 Windows 8770；本轮没有读取、写入或删除任何真实工作台业务数据。下一步等待用户决定是否将 2.0.8 候选合入 main。



## 2026-11-04：2.0.10 正式合并发布

- 用户明确批准最新合并，并补充长期规则：若合并前分别提出多项改进且均已通过测试，应审计并一并纳入，不得只合并最新一个 PR。
- 开发规则复核：完整读取 AGENTS.md、README.md、docs/REQUIREMENTS.md、docs/PROJECT_STATE.md、docs/DECISIONS.md。按要求核对所有开放 PR；本次唯一开放 PR 为 #33，包含步骤文档折叠、任务名称直达详情、任务编号点击复制、已完成任务置底四项，均按同一候选验收。
- PR #33 转为 Ready 后，以 GitHub 标准 Merge 合并；最终 head SHA `31a720d0f226bedb98653fb224cb9450a98aa389`，对应 Actions #41784404642 **3/3 SUCCESS**；merge SHA `0ec256205bf47a7ee36ae74d3a638a3bb71ef44b`。
- 已复核 main 的 `VERSION=2.0.10`，PR #33 已合并，开放 PR 搜索结果为 0。
- 本轮仅合并 GitHub 代码；未升级公司 Windows 8770，未读取、写入或删除真实 Google Drive 任务、步骤或 review_events 数据。
- **下一步**：如需在公司电脑使用 2.0.10，另行进行备份和部署确认；本次合并授权不等于本机自动升级或真实数据操作授权。
