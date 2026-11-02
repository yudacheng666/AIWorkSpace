# 2026-11-02｜V2.0.1 任务交互小优化

## 优先级与隔离
- 用户明确：当前对话优先开发小更新，工作档案暂缓，不改另一开发分支。
- 起点 main SHA：`fa51b0123aaac76ddff2064d34178e7cc6e3ab11`，VERSION=2.0.0。
- 开发分支：`feat/20261102-v2-0-1-task-ids-drawer`。
- 工作档案分支 `docs/20261102-personal-work-archive-m0`、`feat/20261102-m1-work-archive` 不修改。

## 设计与实现
- task_id 保持原 UUID，新的 display_id 只作用户显示与查询：T-YYMMDD-12HEX，YYYYMMDD 取创建事件 UTC 时间；无效/缺失日期用 000000，非标准 task_id 用 SHA256。
- 相同显示编号不混淆：冲突时回退原始 task_id 并附警告。
- 网页主要任务视图、抽屉、创建反馈展示短号；点击编号或复制图标复制；无遮罩或非本体点击不关闭抽屉。
- 未保存草稿继续受原 closeTaskDetail() 保护。
- 不开发另一个 work_archive/工作记录数据层；事件型事项分类等工作档案恢复后处理。
- 候选发布为 2.0.1；产品代码分支 VERSION 仍为 2.0.0，未发布。

## 代码/测试文件
- app.py
- web/index.html
- tests/test_app.py
- tests/test_ui_shell.mjs

## 验证状态
- GitHub 已提交实现与测试，**未运行 CI 和真实浏览器 E2E，不能写 PASS**。
- 同 SHA CI 证据待补；main 之前的 PASS 不能移用到新修改。
- 不触发 Actions、不修改 main、不接触公司电脑/真实 Drive/实际任务数据、不合并/部署。

## 下一步
- 运行准确代码 SHA 的 Python/Node/定向浏览器测试（在不产生用户未批准费用的环境）。
- 根据结果修复，审阅 UI 和数据兼容性，再由用户决定 PR、发布和合并。


## 2026-11-02 增量隔离验证结果

- 产品/测试代码 SHA：`187e097ecfd414b0c8fd1c7bf615be74daae748d`；项目记忆补充提交不修改产品/测试源码。
- **V8 DOM 模拟逻辑 22/22 PASS**：GitHub 连接器读取本分支原网页内嵌 JavaScript 与 `tests/test_ui_shell.mjs`，在 V8 沙箱内载入真实脚本，用该测试文件的全部断言验证。适配了 Node vm 的执行外壳；首次沙箱 navigator 绑定不一致导致复制假失败，修正测试沙箱注入后 22/22 全部通过，非产品代码修复。
- **Python 3.13.5 单函数 6/6 PASS**：把 app.py 中 `display_task_id` 原函数复制到隔离文件运行，验证 UUID / 旧 ID / 无效日期 / 含偏移时间 / 大小写 / 缺日期，未改动产品实现。
- 完整 Python 应用测试、原生 Node 测试、实际 Chromium GUI、Windows/Drive、Actions 本轮都 **NOT TESTED**。
- 执行容器没有 GitHub 外网访问，未能获取完整仓库用于运行 `unittest` 和 Node 原始测试命令；不将上述隔离结果冒充原生 CI 或 E2E。
- 没有修改 main、工作档案分支、真实数据、部署，也没有创建会触发 Actions 的 PR。
- 其余下一步按 `PROJECT_STATE.md`；不因当前部分 PASS 越过正式发布门槛。


## 2026-11-02 GitHub Actions 正式测试与缺陷闭环

- 用户澄清 Actions 免费及 CI 优先，核实 Public 仓库和标准 Ubuntu/Windows runner 后，创建 [Draft PR #15](https://github.com/yudacheng666/AIWorkSpace/pull/15) 触发免费的既有 CI。
- 在现有 Windows Chromium job 中新增独立 `tests/test_task_id_drawer_windows_e2e.py`，以临时虚构数据、真 app.py + 浏览器验证短号复制、点击抽屉外遮罩关闭、用户取消放弃草稿及数据文件哈希保持不变。
- 第一次包含新增 E2E 的产品/测试 SHA `73840f58a13195ad4daa6b4ec3bad710dd8d2229`：Ubuntu/Windows Python+Node PASS，Windows 原有 Chromium 3 PASS、新增草稿保护 PASS，但复制测试的 `page.wait_for_function` 违反页面 CSP（`unsafe-eval`），属测试方法 ERROR，未动产品安全策略。
- 修复提交 SHA `65126022808bc0af1847d67dd999ea7f6e31dee9`：仅把测试等待改成 Playwright locator 兼容 CSP 的方式，不修改产品逻辑。
- [Actions #41420159188](https://github.com/yudacheng666/AIWorkSpace/actions/runs/41420159188) 最终 **SUCCESS / 3 jobs**：
  - Ubuntu Python 107 total / 7 SKIP / 100 PASS，Node 60 PASS；
  - Windows Python 107 total / 5 SKIP / 102 PASS，Node 60 PASS；
  - Windows 原有 Chromium 3 PASS + 本轮 Chromium 2 PASS。
- 测试只在 GitHub-hosted 标准免费 runner 的临时虚构数据目录运行，无真实 Drive、生产电脑/数据和 main 的写入；无 Codex 重复跑已覆盖路径。
- 2.0.1 仍为候选；VERSION 继续 2.0.0。发布/合并需用户批准；PR #15 保持 Draft。此次记忆写入是文档-only，产品/测试实测 SHA 不变。


## 2026-11-02：RC 2.0.1 创建及最终 CI PASS

- 用户授权执行第二阶段：仅在 PR #15 创建 `2.0.1` 正式发布候选，不允许提前合并 main 或升级真实数据。
- 原 `tests/test_app.py` 的 `test_update_status_reports_local_version_without_network` 固定断言 `2.0.0`，故先提交仅调整断言的 `a596d05fedf39f4cbc8467ec59ff3d6f3e5ee81d`（`[skip ci]`，避免中间不一致的重复 CI），然后提交 VERSION=`2.0.1`：**RC SHA `97ca50d74641fcb8ae2f232a95651ab7c50fbcd0`**。
- [GitHub Actions #41421749629](https://github.com/yudacheng666/AIWorkSpace/actions/runs/41421749629)：最终 **SUCCESS / 3 JOBS**；Ubuntu Python 100 PASS / 7 SKIP + Node 60 PASS；Windows Python 102 PASS / 5 SKIP + Node 60 PASS；Windows Chromium 原 E2E 3 PASS + 2.0.1 E2E 2 PASS。
- 此次 RC 仅新增明确版本号与对应测试断言；工作档案、任务事件 schema、原始编号、更新器白名单和数据目录均未修改。
- 工作档案继续暂停、main 仍为 2.0.0；PR #15 Draft、无部署、无真实 Drive/Windows 正式升级。后续需用户批准 PR #15 合并与另行授权正式部署。
- 精确产品/测试 SHA 以 `97ca50d74641fcb8ae2f232a95651ab7c50fbcd0` 为准，后续 Markdown `[skip ci]` 项目记忆提交不改变本次受测代码。


## 2026-11-02 用户批准合并 / Draft 阻塞（当前结果）

- 用户已批准 **PR #15 合并到 GitHub main**，不包含正式机器升级、Drive 数据操作或工作档案开发。
- 复核 `main` 基线 `fa51b0123aaac76ddff2064d34178e7cc6e3ab11` / VERSION `2.0.0`，PR #15 HEAD `b2b3bbf7f449c82ede322fe2e3b32085ce7069fa`，RC SHA `97ca50d74641fcb8ae2f232a95651ab7c50fbcd0` 的 Actions `#41421749629` 3/3 SUCCESS。RC 后仅 3 个 Markdown 说明/记忆文件，未改产品测试代码。
- GitHub PR #15 为 Draft。调用 ready-for-review 遭平台安全检查阻止；经 GitHub 原生 merge API (`merge`, `expected_head_sha`) 返回 HTTP 405：`Pull Request is still a draft`。未发生合并。
- 阻塞处理：仅需用户在 [PR #15](https://github.com/yudacheng666/AIWorkSpace/pull/15) 页面点击 **Ready for review** 解除 Draft；此后按已获得批准继续合并和 main SHA / CI 验证，不必再次获得合并批准。
- 禁止通过 force update main 等旁路绕过 Draft；公司实际机器/Google Drive 仍不操作；工作档案继续暂停。

## 2026-11-02 GitHub 2.0.1 合并完成

- 用户批准 PR #15 合并，随后在 GitHub 页面点击 Ready for review。
- 合并前 PR HEAD `5ee54db89a3f5d86e04815d54046250a1cface51`，发布候选产品/测试 SHA `97ca50d74641fcb8ae2f232a95651ab7c50fbcd0`，[Actions #41421749629](https://github.com/yudacheng666/AIWorkSpace/actions/runs/41421749629) 为 3/3 SUCCESS，发布候选之后仅发生 Markdown 记忆修改。
- 调用 GitHub 正常 PR merge，`merged=true`；准确合并 SHA `7d1a0f2c8cf8135b78a43108f666d750538d6a18`。再次读取 main HEAD 和 VERSION 验证为该 SHA 和 `2.0.1`。
- main push CI 状态暂时未核实：当前 GitHub 连接器仅枚举 PR 事件的 Actions，不能以此证明 push CI PASS。仓库 PR 自动化证据已通过，合并后 CI 仍待确认。
- 已按 AGENTS 维护 `PROJECT_STATE.md`、`DECISIONS.md`、此 session；没有操作实际 Windows 工作台、真实 Drive 任务数据，也没有修改暂停的工作档案开发分支。

## 2026-11-02：公开 GitHub 正式包的 Windows 隔离升级补缺验收

- 既有正式 RC [Actions #41421749629](https://github.com/yudacheng666/AIWorkSpace/actions/runs/41421749629) 已有 Linux/Windows Python/Node 及 Windows Chromium 网页一键更新成功、故障回滚和 2.0.1 任务操作的 PASS 证据，本轮不重复完整回归。
- 独立 QA 分支执行真实公开源测试：从官方旧 main SHA `fa51b0123aaac76ddff2064d34178e7cc6e3ab11` 读取 2.0.0 程序文件，再获取官方 main SHA `31963c3c48c9d9cd95663c971a55cb3bb9b108f6` / VERSION `2.0.1` / zipball。Windows Runner 在临时目录中下载校验、备份旧版、安装新版、随机本地端口启动服务、核对 build SHA 和虚构数据哈希不变，再从备份恢复 2.0.0 程序并验证逐文件 SHA-256。
- [QA PR #16](https://github.com/yudacheng666/AIWorkSpace/pull/16) 准确 QA HEAD `749beb40f3748617356861a6919c2f75dd9f4167`；[Actions #41425066853](https://github.com/yudacheng666/AIWorkSpace/actions/runs/41425066853) **SUCCESS / 1 PASS / 0 FAIL**；artifact `qa-v201-real-public-source` ID `13130903143`，[证据评论](https://github.com/yudacheng666/AIWorkSpace/pull/16#issuecomment-6574287190)。PR #16 已关闭，未合并 main。
- 合并 SHA `7d1a0f2c8cf8135b78a43108f666d750538d6a18` 的 main push CI 当前连接器只能查 PR workflow run，无法据此核实结果；不得将其写为 PASS。真实公司 Windows 电脑、Google Drive、长期运行均 NOT TESTED/NOT DEPLOYED。
- 2.0.1 已在 GitHub main 发布；下一步应先核查实际电脑当前版本、程序目录、数据目录、备份和未保存草稿，再单独授权真实升级，不因隔离测试 PASS 直接触碰生产。工作档案仍暂停。
