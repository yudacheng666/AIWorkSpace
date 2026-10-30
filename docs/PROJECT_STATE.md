# AIWorkSpace｜当前项目状态

更新日期：2026-10-30（北京时间）  
当前阶段：**M1/M2/M3.1/M3.2/M3.3/M3.4 已合入 `main`。M3.4 [PR #6](https://github.com/yudacheng666/AIWorkSpace/pull/6) 于 2026-10-30 经用户批准 Squash 合并，合并提交 `5916744898ac3de1b82c4edf27c339ec9a0173c1`。固定产品/原测试 SHA `eb035c611a592cc01dc7b02138a4951b32a69036` 的 Linux/Windows CI 224 PASS / 0 FAIL；Codex 第四轮真实 Chromium 独立复验 PASS（已测范围），前三轮发现的三项草稿保护 P2 均已修复并通过指定路径复验。M3.4 未部署，公司 Windows 8770 未升级，真实 Drive 未访问。内置软件更新中心在 Draft PR #7；Codex 独立 Linux 隔离验收 PASS（已测范围），GitHub Actions 新增 Windows 原生 helper 进程级正向/失败回滚测试 PASS，但公司 Windows 实机、真实 GitHub main 成功更新及真实 Drive 仍 NOT TESTED；尚未合并或部署。**

| 项目 | 当前事实 |
|---|---|
| 仓库 | AIWorkSpace，Public；PR #1 已以 squash 方式合并到 `main`，合并提交 `84fd0d234d799148c7a925a2d49408b11bd69481`；当前只在公司 Windows 电脑部署 |
| 当前代码基线 | `main` 已包含 M1 + M2 + M3.1 + M3.2 + M3.3 + M3.4；M3.4 PR #6 Squash 合并提交 `5916744898ac3de1b82c4edf27c339ec9a0173c1`（产品/原测试固定验收 SHA `eb035c611a592cc01dc7b02138a4951b32a69036`） |
| 最近合并 PR | [PR #6：M3.4 首页工作总览与组合查询](https://github.com/yudacheng666/AIWorkSpace/pull/6)，用户批准 Squash 合并；Codex 固定产品/原测试 SHA `eb035c61` 独立验收 PASS（已测范围），Linux/Windows CI 每平台 76 Python + 36 Node PASS；之前 [PR #5：M3.3 编号执行步骤](https://github.com/yudacheng666/AIWorkSpace/pull/5) 已合入 |
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


## 内置软件更新中心（Linux 独立验收 PASS，Windows CI helper 专项 PASS，尚未合并，2026-10-30）

- **用户目标**：首次下载安装后，后续从工作台网页显示版本号、检查固定 GitHub main 并一键更新；不再重复人工下载 ZIP、解压和复制程序。
- **代码位置**：[Draft PR #7](https://github.com/yudacheng666/AIWorkSpace/pull/7)，分支 `feat/software-update-center-20261030`，基于 M3.4 main `0a3c8f19808b270eea632e4c0ebddf5bc17cda6f`；尚未合并，也未部署。
- **产品范围**：新增 `VERSION=1.0.0`、网页版本及 build 标识、检查/安装 API、`updater.py` 独立 helper、固定 GitHub 官方 main commit、ZIP 完整性/路径/符号链接/文件白名单验证、应用程序备份/失败回滚、原端口及 `--data-dir` 重启、保存草稿时禁止启动更新。只替换 `app.py`、`updater.py`、`VERSION`、`web/index.html`；备份和暂存位于实际数据目录外。
- **Codex 独立验收**：[Linux 隔离报告与证据](https://github.com/yudacheng666/AIWorkSpace/pull/7#issuecomment-6524335908)，固定原产品/测试 SHA `42573a34c3190b46c28c1573e98fbca202924a9c`，**PASS（Linux 隔离已执行范围）**，无确认 P1/P2/P3。独立 Python 22 PASS、Node 2 PASS、预检 29 PASS；真实 Chromium 在固定官方 URL mock/隔离临时目录下完成网页一键更新及失败回滚两条链路，helper 停服务/安装/原端口及数据目录重启，测试数据所有文件哈希一致；并发、草稿阻止更新、更新包恶意输入、Host/Origin 和任务/步骤写入定向检查 PASS。Codex 未触及产品/原测试/CI/main。
- **Codex 明确 NOT TESTED**：独立真实 Windows 一键更新/回滚（当轮无 Windows 执行器），真实 GitHub main 成功升级（检查返回 HTTP 404，原因是 main 尚未包含 VERSION；PR 未合并，因此当前不可用于真实自动更新）。真实 home 权限、企业网络代理/限流、真实 Drive、公司 8770、长期/断电、其他浏览器、远程访问亦 NOT TESTED。
- **新增开发侧 Windows 原生 CI 专项**：`tests/test_updater_native.py` 增加两项仅在 `win32` 运行的隔离本机进程级回归：用 Windows 子进程真实运行 `updater.py` helper、等待旧进程退出、替换程序、原端口/`--data-dir` 启动新 mock HTTP 服务并核验 build；新程序故障退出时回滚程序、恢复旧 mock 服务。均检查 `events/`、`project_events/`、`step_events/` 的虚构文件字节不变。**该测试使用模拟 app.py，验证的是 Windows helper/原生进程与回滚机制，不代表真实完整网页端到端链路通过**。
- **最新固定产品及测试 SHA**：`f114f8a81d5e4e69286f77af1f8942dfb60e1137`，相较 Codex 独立验收 SHA 只增加 PROJECT_STATE 文档和两项 Windows 本机测试，不改产品代码。最新 [Actions #41067205073](https://github.com/yudacheng666/AIWorkSpace/actions/runs/41067205073) Linux/Windows 均 SUCCESS；Windows Python 100 PASS + Node 38 PASS；Linux Python 98 PASS + Node 38 PASS，另两项仅适用 Windows 的测试按设计 SKIP。合计 **274 PASS / 0 FAIL / 2 SKIP**。
- **合并门槛现状**：Linux 独立验收 PASS + 双平台 CI PASS，Windows helper 本机隔离专项已通过；**真实 Windows 网页端到端仍 NOT TESTED**。版本 `VERSION` 不在 main 是未发布状态，不能为了冒充真实成功而绕过版本校验。是否将 Windows 全链路实机验收设为合并前门槛，应依据部署风险保守处理：在公司首次部署前必须做真实 Windows 隔离或正式环境预演（绝不访问公司真实数据）。
- **接下来**：保持 PR #7 Draft；让 Codex Cloud 先读取 PR 最新验收说明和状态，若有独立 Windows 云端环境，则用虚构目录对真实 `app.py` + 网页触发完整 helper 和回滚；若仅 Linux 则记录 Windows NOT TESTED，不重复已有 Linux 全套。用户批准合并前不可合并，首次实际安装前先解决 build登记和真实 main `VERSION` 发布路径，禁止自动升级公司 Windows 8770。
