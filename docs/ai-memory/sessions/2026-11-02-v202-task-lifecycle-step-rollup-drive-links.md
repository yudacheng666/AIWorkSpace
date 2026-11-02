# 2026-11-02｜AIWorkSpace 2.0.2 三项任务增强开发与验证

## 用户需求与约束
- 用户反馈实际工作台 2.0.1 网页自动更新成功，要求下一版支持回收站（删除、恢复、可选清空周期和勾选彻底删除）、执行步骤对任务状态联动、Google Drive 共享链接引用。
- 保留统一工作台语义版本体系，2.0.2 为候选，开发阶段 VERSION 仍 2.0.1；不改 main、公司设备、真实 Drive 数据。
- 工作档案 M1 按用户更早决定暂停，相关 PR #14 和分支不修改。

## 实施
- 独立 Draft PR #17： https://github.com/yudacheng666/AIWorkSpace/pull/17 。代码 app.py、web/index.html；测试 tests/test_v202_features.py、tests/test_task_id_drawer_windows_e2e.py。
- 任务 trash、restore、purge 都以追加式事件表示，读模型默认隐藏已删除任务，回收站单独列出，purge 墓碑防止迟到旧事件复活。留存周期配置为 0/7/30/90 天，默认为 30 天，访问时触发清理。本机删除经明确确认，不能保证各设备/Google Drive 历史版本和备份的物理擦除。
- 关键安全收敛：**来自远端的 purge 墓碑只隐藏任务，绝不在当前设备自行物理擦除原事件文件**。actor='user' 只是声明，不是强身份认证；清理由本机确认或本机已配置到期规则触发。新的两设备延迟同步测试需要同时验证不可复活与不自动物理擦除。
- 只读聚合 steps 的有效 task 状态：blocked 优先，部分 doing/done 则 doing，全 todo 则 todo；全 done 不自动关闭任务，只标记待人工确认；状态冲突和步骤同步不完整不推断。原始任务事件和 revision 不变。
- Google Drive 文档链接只保存任务级 title 和可信 HTTPS URL（最多20），跨设备按链接打开；使用已连接 Google Drive 读取需要用户的真实访问权限，不自动下载/缓存文件或扩大授权。

## 测试历史与当前证据
- 在仅现有普通回归的旧 SHA `4c4c3213f82fea883006bab3c3b54c46be4fe3e4`，[Actions #41428386975](https://github.com/yudacheng666/AIWorkSpace/actions/runs/41428386975) 3/3 PASS；其时新增 Chromium E2E 尚未完成，不作为最终验收。
- 新增真实 Windows Chromium 两条定向 E2E：Drive URL、trash/restore/purge、步骤状态变化、全部 done 提示、人工任务 done。中间三次失败分别为说明误用隐藏 .hint CSS、异步保存后状态断言过早、任务完成保存断言过早。修复了显示样式和 Playwright 状态等待（不动 CSP、保留业务断言）。
- 受测产品/测试 SHA `6a1bf873790aa4786729c538d0cfd095c3d0304b`，[Actions #41429636009](https://github.com/yudacheng666/AIWorkSpace/actions/runs/41429636009) **3/3 SUCCESS**：Ubuntu Python 113 PASS/9 SKIP + Node60，Windows Python 115 PASS/7 SKIP + Node60，Windows Chromium 原3+新增4 PASS。
- 数据安全加固 SHA `9d25552e9899f27150899a12ab3be48e22b158c1`，[Actions #41430035182](https://github.com/yudacheng666/AIWorkSpace/actions/runs/41430035182) **3/3 SUCCESS**：Ubuntu Python 114 PASS/9 SKIP、Node 60，Windows Python 116 PASS/7 SKIP、Node 60；Windows Chromium 原有更新/回滚 3 + 任务 UI 4 PASS。
- 后续同时补入另一条真实两设备文件复制/延迟同步模拟测试 `e52531964c31ca1b547bc750852e9879eb42db1f`，但原断言错误地要求到达第二设备的同步墓碑自动清除当地文件；已纠正至安全决策 D-20261102-UI-08，最新产品/测试 SHA `5e995c7d2ef67bc4039cc91bba65e3e6d0bceba2`，该 SHA [Actions #41430588371](https://github.com/yudacheng666/AIWorkSpace/actions/runs/41430588371) **3/3 SUCCESS**：Ubuntu Python 124 total / 9 SKIP / 115 PASS、Node 60 PASS；Windows Python 124 total / 7 SKIP / 117 PASS、Node 60 PASS；Windows Chromium 原 3 + 任务操作 4 PASS，新增两设备延迟同步模拟通过。文件仅含虚构任务事件，真实多设备 Drive 仍 NOT TESTED。
- GitHub Actions 标准免费 runners CI 优先；不得无理由派 Codex 重复同范围。公司真实 Drive、第二台电脑实际同步、真实工作数据/文档权限、长期稳定性均 NOT TESTED。

## 下一步
- 核实最新准确 SHA CI；仅修复新增失败并重新验证受影响范围。
- 根据删除高风险和真实 Drive 访问测试缺口判断是否安排一次独立探索性验收。PR #17 保持 Draft，未经用户明确发布/合并批准，不改 VERSION/main/公司电脑。


## 2026-11-02 最终准确 SHA 自动化 CI（留证，不等于实际设备验收）

- 因跨设备仿真新增错误断言，首次 SHA `e52531964c31ca1b547bc750852e9879eb42db1f` 的 [Actions #41430342353](https://github.com/yudacheng666/AIWorkSpace/actions/runs/41430342353) Ubuntu FAILED：测试错误地要求仅接收到远程墓碑的第二台电脑自动物理删除本地源事件。正确安全规则 D-20261102-UI-08 是 **同步墓碑防复活，但仅本机亲自授权或本机已设置的到期规则可物理清理**。未修改这一安全产品行为，仅修正测试。
- **最终准确产品/测试 SHA** `5e995c7d2ef67bc4039cc91bba65e3e6d0bceba2`， [GitHub Actions #41430588371](https://github.com/yudacheng666/AIWorkSpace/actions/runs/41430588371) **SUCCESS（3/3 Jobs）**：
  - Ubuntu Python 3.12：124 tests，115 PASS / 9 SKIP / 0 FAIL；Node 22：60 PASS。
  - Windows Python 3.12：124 tests，117 PASS / 7 SKIP / 0 FAIL；Node 22：60 PASS。
  - Windows `app.py` + 真实 Chromium：原更新/回滚 + UI E2E 3 PASS，任务短编号、抽屉、Drive 链接、回收站、草稿保留、步骤联动及人工完成确认 4 PASS。
- 两个临时数据目录仿真：先任务事件、再永久删除墓碑、再迟到旧事件；结果任务不复活，且不自动物理清理仅收到标记的另一设备文件。是真实本地文件读写的仿真，不等于 Google Drive 云同步端到端验收。
- 发布边界：本 SHA 后只追加 `[skip ci]` Markdown 状态/验收记录，产品与测试代码保持上面准确 SHA。仍为 Draft PR #17，`main/VERSION=2.0.1` 未升级；工作档案继续暂停，真实 Drive/公司电脑/账户权限/长时使用 NOT TESTED。高风险独立验收待按覆盖缺口定向安排，绝不将已测 CI 匹配范围交 Codex 重跑。


## 发布候选 RC（2026-11-02，当次“继续”实际执行）

- 在保留工作档案暂停、PR #17 Draft/禁止自动合并的前提下，完成 GitHub 2.0.2 发布候选准备，`VERSION` 在独立分支改为 `2.0.2`，README 顶部更新当前发布说明；正式 main 仍 `2.0.1`。
- RC 首次 SHA `c655088ed1a23fb9ec7ef589a0774d9544c342fb` 的 [Actions #41443192582](https://github.com/yudacheng666/AIWorkSpace/actions/runs/41443192582) 在 Linux/Windows Python 同一旧测试失败：`test_update_status_reports_local_version_without_network` 写死 `2.0.1`。修复为以仓库 `VERSION` 的值断言，避免以后小版本变更误报；未修改任何任务/步骤/Drive 产品逻辑或数据迁移。
- **正式 RC 产品/测试 SHA** `faa092d2d9359171f53a01d3f7145197e6412a28`， [Actions #41443451302](https://github.com/yudacheng666/AIWorkSpace/actions/runs/41443451302) **SUCCESS 3/3**：Ubuntu Python 124 total / 115 PASS / 9 SKIP；Node 60 PASS；Windows Python 124 total / 117 PASS / 7 SKIP；Node 60 PASS；Windows 真 Chromium 更新器 3 PASS、任务/回收站/Drive 链接/步骤联动 4 PASS。0 FAIL。
- 这些结果是在 GitHub 标准 Runner 虚构数据环境完成，不代表真实两台电脑的 Google Drive 服务/实际文件权限/公司任务数据已验证。暂不执行额外 Codex 回归，不合并 PR、不改真实工作台，等待用户明确批准发布。
- 回写位置：PR #17 正文与评论、`docs/PROJECT_STATE.md`、`docs/DECISIONS.md`、本 session，确保跨对话从准确 SHA 接续开发。此后仅 docs Markdown 变化可复用上面的代码/测试 SHA 证据。


## 2026-11-02：用户批准 2.0.2 RC 合并，GitHub 正式 main 发布成功

- 用户在 CI 3/3 PASS、PR #17 RC 验证和发布说明之后明确回复“批准”。
- 合并前核对：PR #17 HEAD `ba6ce308992ecea157a92c5fe146034e9bbc9dd9`，准确 RC 产品/测试 SHA `faa092d2d9359171f53a01d3f7145197e6412a28`，后续仅 3 份 docs Markdown 改动；正式 `main/VERSION=2.0.1`，RC 分支 `VERSION=2.0.2`， [Actions #41443451302](https://github.com/yudacheng666/AIWorkSpace/actions/runs/41443451302) **3/3 SUCCESS**。
- 正常 GitHub 操作：`mark_pull_request_ready_for_review` **成功**，再通过 `merge_pull_request(merge_method=merge, expected_head_sha=ba6ce308...)` **成功**。GitHub 返回 `merged=true`，合并 SHA **`bfb741bbb9da943f1d63241a9f8b85df008e0b4a`**；PR #17 CLOSED / MERGED。
- 合并后立即验证：`main` HEAD 为合并 SHA，与合并 SHA 比较无差异；正式 `main/VERSION=2.0.2`。随后仅为项目记忆向 main 添加 `[skip ci]` Markdown docs 记录，产品/测试文件保持 RC 代码。
- GitHub main push Actions 对合并 SHA 的执行状态尚未通过当前 `fetch_commit_workflow_runs` 接口验证，因为该接口只返回 PR 事件关联结果；不能将空结果说成“无运行”，也不能冒充已经完成 post-merge CI。
- 用户的真实公司电脑 8770、Google Drive 数据、实际云端文件权限和多设备云同步均没有在这轮发布操作中改动或独立验证；GitHub 合并授权不包含在本机自动执行更新。用户之后可以在真实工作台**自主检查并手动确认一键升级**，完成后核对原数据、草稿保护、任务回收站/恢复/彻底删除、步骤联动以及文档链接。
- 工作档案 PR #14 继续暂停；遵守 ChatGPT + Actions CI 优先、不默认重复 Codex 和 GitHub 记忆持久化机制。
