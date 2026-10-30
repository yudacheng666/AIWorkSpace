# AIWorkSpace｜当前项目状态

更新日期：2026-10-30（北京时间）  
当前阶段：**M1/M2/M3.1/M3.2 已合入 `main`；M3.3 在 Draft PR #5 开发。第二项 P2 已修复，产品代码/测试 SHA `633b5304e843ca632dca095d42a7ec66d4baabe4` 的 Linux/Windows CI 均 PASS；等待 Codex 独立复验，未合并。**

| 项目 | 当前事实 |
|---|---|
| 仓库 | AIWorkSpace，Public；PR #1 已以 squash 方式合并到 `main`，合并提交 `84fd0d234d799148c7a925a2d49408b11bd69481`；当前只在公司 Windows 电脑部署 |
| 当前代码基线 | `main` 已包含 M1 + M2 + M3.1 + M3.2；PR #4 Squash 合并提交 `94a93bcb6fc0bd5123f43925ffa9981edfc20150` |
| 最近合并 PR | [PR #4：M3.2 任务管理字段](https://github.com/yudacheng666/AIWorkSpace/pull/4)，用户批准 Squash 合并；固定 HEAD `1c9324b` Codex 独立验收 PASS，Linux/Windows CI 各 53 Python + 15 Node PASS；新阶段进入 M3.3 |
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

## M3.3 编号执行步骤（修复中，2026-10-30）

- 开发分支：`feat/m3-03-numbered-task-steps`；[Draft PR #5](https://github.com/yudacheng666/AIWorkSpace/pull/5)，从合并后的 main `94a93bcb` 创建，尚未合并。
- 范围：任务可拆成有稳定编号的执行步骤，记录步骤状态与顺序；任务/步骤完成均须用户明确确认。
- 数据模型：独立 `step_events/` 追加式事件流；每步独立 STEP ID 与 revision；顺序由任务级完整 STEP ID 列表事件维护。旧任务无步骤时无需迁移；原事件不覆盖。
- 规则：STEP ID 为 `STEP-<32位大写十六进制>`；每任务最多 100 步；标题 1–200 字；状态 `todo/doing/blocked/done`。**step_events 内 event_id 全局唯一**：相同 ID 相同内容的重复文件可忽略；相同 ID 不同内容必须冻结所有受影响步骤/排序流，冲突变体不得作为有效 revision 应用。步骤内容冲突只冻结涉事步骤；顺序冲突只冻结排序；父任务冲突阻止步骤写入。Host/Origin 本机校验、409 和原子不覆盖写入继续保留。
- **首轮独立验收 FAIL（1 项 P2，已修复并定向复验通过）**：固定 HEAD `4d9e25f94195ce6f0c7964a253d4965ea7d0dc85`。部分同步时既有排序 `[A,C,B]` 而 C 创建事件未同步，网页只显示 A/B，原代码允许写入 `[B,A]` 丢掉 C 引用。原始历史文件未覆盖。证据：[Codex 报告](https://github.com/yudacheng666/AIWorkSpace/pull/5#issuecomment-6518205090)。
- **原 P2 修复后的独立复验 PASS**：固定 HEAD `ce7ae429b903acf2839b14c05478639400ff72cd`。Codex [报告](https://github.com/yudacheng666/AIWorkSpace/pull/5#issuecomment-6518742643)确认：缺 C 时页面警告、排序禁用、API 409 且文件字节不变；C 到达后恢复 `[A,C,B]`，之后合法重排成功且只追加一条事件。
- **第二项独立验收 FAIL（新 P2）**：同一排序 `event_id=order-event-001`，一个事件 `base_revision=0, [A,B]`，另一个事件 `base_revision=1, [B,A]`。旧代码只告警，仍按连续 revision 接受两者，得到 `step_order_revision=2`、`step_order_conflict=false`，页面继续允许排序。Codex 已按要求停止；独立并发、100 步/非法输入、Host/Origin 等剩余专项仍 NOT TESTED。证据及截图/日志：[PR #5 报告](https://github.com/yudacheng666/AIWorkSpace/pull/5#issuecomment-6518742643)。
- **第二项 P2 修复已提交，自动化 CI PASS，等待独立复验**：
  - `app.py`：建立每个受影响 task 的重复排序 ID 冲突集合；冲突涉及的 revision 不进入排序归约；只保留最后一个无冲突前缀，所有冲突变体作为候选；API 因 `step_order_conflict` 返回 409。步骤内容编辑不受影响。
  - `tests/test_app.py`：新增 3 项回归：同 ID 跨 revision 必须冻结；API 不得写入冲突排序且历史字节不变、步骤仍可编辑；不同 ID 的合法连续 revision 仍正常应用。
  - 修复提交：`ad0f981d04adb2652909a69a156310c8757ba6ae`（服务端）；`633b5304e843ca632dca095d42a7ec66d4baabe4`（Python 回归）。
  - 产品代码/测试固定 SHA 与当前 PR HEAD：`633b5304e843ca632dca095d42a7ec66d4baabe4`。
  - GitHub Actions [#41029302644](https://github.com/yudacheng666/AIWorkSpace/actions/runs/41029302644)：Linux、Windows 均 SUCCESS；每个平台 **Python 76 PASS + Node UI 23 PASS，0 FAIL、0 skipped**。
- **当前状态：新 P2 尚未由 Codex 独立复验关闭。** CI PASS 不能替代独立 Chromium/API 实操。
- 未访问真实 Google Drive，未部署公司 Windows 8770，未修改 main；本机测试实例保持原状。公司 Windows UI、真实 Drive 步骤同步、原生中文输入法、长期/断电耐久性仍未测试。

## 下一步

1. 委托 Codex 对固定 PR HEAD `633b5304e843ca632dca095d42a7ec66d4baabe4` 定向复验新 P2：同一排序 event_id、不同内容、跨 revision 时必须冻结排序，API 返回 409、不新增/覆盖事件、候选保留；不同 event_id 的合法连续排序必须仍可应用；步骤内容编辑仍可用。
2. 同时补齐前两轮因失败停止而尚未执行的独立专项：同 revision 并发/旧 revision 409、不同 ID 同 revision 排序冲突、父任务冲突、100 步上限、非法标题/状态/STEP ID/排序成员、Host/Origin。本轮不要重复首轮已 PASS 的完整创建/编辑/完成确认流程；部分同步 P2 已在 `ce7ae42` 定向复验 PASS，可做最小回归确认而非重跑全套。
3. Codex 只独立验收，不修改产品、原测试、CI 或 PR 分支；使用隔离虚构数据，不访问真实 Drive、不部署公司 Windows 8770。失败时保留证据并停止。
4. ChatGPT 审核独立报告，若有新缺陷再做最小修复。**未经用户明确批准不合并 PR #5。**
5. 不升级公司 Windows 8770，不访问真实 Drive，不测试远程访问；远程访问继续按 D012 暂缓。M3.3 完成后再进入 M3.4。

**交接规则：** 新 AI 应先读 `AGENTS.md`、`docs/REQUIREMENTS.md`、本文件和 `docs/DECISIONS.md`，核实 main、PR 最新 HEAD、CI 及独立验收报告；不能把 CI SUCCESS 当作独立实操已通过。
