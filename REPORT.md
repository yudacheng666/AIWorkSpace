# PR #6 / M3.4 第四轮独立复验：PASS（已执行范围）

日期：2026-10-30。实际产品及原测试 checkout SHA：`eb035c611a592cc01dc7b02138a4951b32a69036`。

读取固定版本 AGENTS.md、docs/REQUIREMENTS.md、docs/PROJECT_STATE.md、docs/DECISIONS.md、PR 最新描述及第三轮失败报告。固定文档部分段落仍记载 `389c2427` 待验；本轮以用户指定的 `eb035c61` 和最新 PR 指令为准。PR 文档 HEAD `2a29137c2b646543a0c02c6322035b87e5cc3210` 相对固定 SHA 只有 README、PROJECT_STATE、DECISIONS 文档变化，产品/测试文件未变。

## 结论与缺陷等级

**PASS：第三项 P2 的任务/步骤两条指定操作链均复验通过，保存期间新输入保护通过，指定回归通过。未发现新增已确认 P1/P2/P3。** 结论仅覆盖下述实际执行范围，不扩大到公司 Windows、真实 Drive、其他浏览器或未执行的交互组合。

共完成 **74 次真实 Chromium 整页刷新尝试**；Node 新增保护定向测试 **5 PASS / 0 FAIL / 0 skipped**。没有重跑无关旧完整 Python/Node 套件。CI 224 PASS 为背景，不计入本轮本机执行数。

## 第三项 P2：任务与步骤保存后基线

对任务标题及已有步骤标题分别实际执行：

1. 记录已保存 X；改为 Y，同时让兄弟任务 B 保留未保存标题草稿。
2. 保存 A（任务或步骤），服务器真实返回 200，直接读取隔离事件状态确认 Y 已持久化。
3. 验证原输入节点仍是同一个 DOM 节点。点击页面内刷新并**拒绝放弃草稿**，B 输入保持不变，原编辑器继续挂载。
4. B 恢复原值，再把 A 从已保存 Y 改回保存前 X。
5. 整页 reload 收到浏览器原生 beforeunload，取消后整个页面输入与 X 均完整保留；没有新 POST，事件字节不变。
6. 将 A 恢复为刚持久化的 Y，整页 reload 不再出现确认，实际导航并读取 Y。

**任务 PASS；步骤 PASS。** 这直接覆盖上轮失败的“兄弟草稿阻止重绘、旧 X 错误清除 dirty”路径，没有靠重绘重建 watcher 绕过问题。

任务：[刷新前 X](10-task-old-X-before-reload.png) / [取消后 X](11-task-old-X-after-cancel.png)。步骤：[刷新前 X](10-step-old-X-before-reload.png) / [取消后 X](11-step-old-X-after-cancel.png)。保留旧节点时截图修订号仍是原页面值，这是故意验证未重绘路径；服务器持久化结果由探针与事件原文核对。

## 保存请求期间的新输入

使用 Playwright 路由延迟**真实 HTTP 成功响应**：先 route.fetch 让隔离服务实际保存 Y，再暂不向页面交付成功响应；期间操作页面，最后释放原始响应。没有伪造成功 API 或修改产品文件。

- **任务编辑 PASS**：请求期间输入仍可编辑，将 Y 改为新草稿 Z；释放成功响应后 Z 保留，并提示保存期间新草稿尚未保存。整页刷新有原生确认，取消后 Z 保留。随后输入旧 X，仍需确认；恢复到本次请求已保存 Y，确认才解除。
- **步骤编辑 PASS（实际可操作范围）**：请求期间步骤标题和保存按钮被禁用，普通用户无法在该步骤内输入；没有强行移除 disabled 或用脚本伪造该步骤的新输入。期间在仍可编辑的兄弟任务输入 Z，释放步骤保存响应后 Z 保留且原生保护仍有效。兄弟草稿恢复后，将已保存步骤改回旧 X 仍受保护，恢复 Y 才解除。

[任务 Z 取消后](12-task-inflight-after-cancel.png) / [步骤保存后的真实页面](12-step-inflight-after-cancel.png)。第二张截图为任务 A 卡片，兄弟 B 的 Z 具体值另见 [逐次完整草稿状态](draft-states.json) 和 trace。

## 指定回归

| 检查 | 结果 |
|---|---|
| 新建任务8字段逐一修改/恢复 | PASS：标题、主要项目、关联项目、负责人、优先级、截止/计划/跟进日期；逐项修改均有确认，取消保留，恢复无确认 |
| 8字段同时修改后全部恢复 | PASS：全部恢复后无多余确认 |
| 每种字段作为唯一剩余修改，共8种 | PASS：任一字段尚不同则继续保护，最后字段恢复后解除 |
| 干净页面 | PASS：整页刷新没有原生确认 |
| 任务标题、任务负责人/日期 | PASS：原生确认、取消保留、恢复原值无确认、明确接受才允许离开 |
| 步骤编辑、新增步骤草稿 | PASS：同上 |
| 新建任务及仅管理字段草稿 | PASS：同上 |
| 正常任务编辑/步骤编辑/新增步骤保存 | PASS：真实保存成功、读取值正确，随后整页刷新无多余确认 |
| 查询生效时新建任务 | PASS：新任务匹配查询出现、表单清空，随后刷新无确认 |
| 新建任务草稿跨查询应用/清除/刷新 | PASS：持久表单未丢输入，原生保护仍有效；恢复后解除，零额外写入 |
| 页面内刷新、风险视图、应用/清除查询 | PASS（本轮任务标题草稿）：逐项拒绝放弃，保留全部输入，无POST和事件变化 |
| 自动刷新 | PASS（本轮任务标题草稿）：焦点移出编辑器，等待实际5.5秒轮询，提示暂停刷新并保留草稿，零写入 |
| 保存失败 | PASS：隔离服务运行时注入发布 OSError，API500，草稿保留、原生保护仍在、零事件变化；恢复原值解除 |
| 查询下步骤级409 | PASS：独立虚构追加提高步骤revision，旧页面提交409；无写入、输入保留、原生保护仍在；明确同意刷新后加载最新步骤 |
| 查询下部分同步排序 | PASS：完整顺序引用尚未到达的步骤H；排序按钮冻结、直接API409且零事件变化；H创建事件到达后恢复原[A,H,B]，原排序事件字节保留 |
| 部分同步恢复后的合法重排 | PASS：网页将H上移，实际显示/服务器顺序为[H,A,B]，新增排序事件，所有旧事件字节不变，之后刷新无多余确认 |
| Node定向回归 | PASS：5 PASS / 0 FAIL / 0 skipped |

[8字段全部修改](01-eight-fields-dirty-cancel.png) / [8字段全部恢复](02-eight-fields-restored-clean.png) / [部分同步恢复](07-partial-sync-query-restored.png)。原生对话框是否出现与用户选择见 dialogs.json，不在网页截图上绘制模拟原生弹窗。

## POST、文件字节与实际草稿证据

- **74次**刷新尝试前后，完整事件文件名集合及原始字节均相同。
- 浏览器 beforeunload **38次**，取消32、接受6；自定义confirm **7次**，其中任务/步骤兄弟草稿拒绝2次、页面内四操作拒绝4次、409后明确同意刷新1次。
- 初始4个事件文件，最终16个。9次预期成功网页操作各追加1文件；独立夹具为步骤外部更新、完整排序、迟到创建追加3文件。所有既存文件的哈希在追加前后持续保留，没有覆盖或删除。
- 浏览器 POST **11次**：200×7、201×2、500×1、409×1。另有 http.client 直接API排序POST=409一次，不混计为浏览器请求。失败500、步骤409、部分同步排序409均无文件变化。
- 恢复字段、拒绝刷新、取消原生离开和自动刷新等只读阶段无额外POST；新输入Z及回退X没有被自动提交。探针日志中的“零POST/初始文件相同”针对相应只读回归阶段基线，不表示整个包含显式保存的验收从未写入隔离目录。
- 从原始 trace 导出 **74条逐次实际草稿状态**；所有取消刷新场景逐项比较全页面before/after输入完全一致。新建表单本轮关联项目夹具只有1项，关联选择状态也在截图/trace中保留。

[完整性摘要](integrity-summary.json) / [逐次刷新与哈希](reload-records.json) / [逐次实际输入](draft-states.json) / [全部对话框](dialogs.json) / [POST正文](posts.json) / [POST状态](responses.json) / [初始哈希](initial-event-hashes.json) / [最终哈希](final-event-hashes.json) / [最终虚构事件原文](final-events.json)。

## 环境、CI及 NOT TESTED

Linux、Python3.12.14、Node24.19.0、Chromium154.0.8037.57、Playwright1.62.0；headless，中文locale，Asia/Shanghai。TemporaryDirectory隔离虚构数据，服务只绑定127.0.0.1随机端口45861；trace浏览器网络仅此本机服务。所有人员/任务/项目/事件为虚构。

探针先发送F5键；本headless环境不将该键派发为浏览器快捷刷新，随后使用Chromium Page.reload执行真实整页导航。由真实beforeunload验证浏览器原生确认；**系统物理F5、关闭窗口、其他浏览器策略未实测**。取消导航后的Page.reload等待超时是预期现象，结果由原生对话框及导航/输入记录判定。

[CI #41051917241](https://github.com/yudacheng666/AIWorkSpace/actions/runs/41051917241) 已读回：head_sha为固定eb035c61，Linux/Windows jobs均SUCCESS。PR记录每平台76Python+36Node、总224PASS仅为CI背景。没有将其冒充本轮本机完整测试数。

NOT TESTED：公司Windows原生M3.4、真实Drive同步、Windows原生IME、其他浏览器、多客户端、长期/断电耐久性、远程访问、部署；未重复旧总览分类/日期全套和所有草稿类型完整页面内四操作矩阵。步骤保存期间在其自身disabled输入框中强行注入修改未执行，不声称普通用户能做此操作。PASS不扩展到这些范围。

## 证据与只读保证

[完整日志](browser.log)、[独立探针](browser.py)、[完整Playwright trace](trace.zip)、[5项Node日志](node-focused.log)、[PR要求快照](pr-metadata.json)、[CI运行](ci-run.json)、[CI jobs](ci-jobs.json)。

固定SHA全部11个跟踪文件逐字节校验一致，见 [source-sha256.json](source-sha256.json)；原工作区git status干净。PR分支仍为`2a29137c2b646543a0c02c6322035b87e5cc3210`，main仍为`b209da970434b71bb4e1b97e86bfdf1fa0483e98`。未修改产品、原测试、CI、PR分支或main，未部署、未合并、未访问真实Drive或公司Windows8770。临时服务和Chromium均已关闭。

发布前检查凭据模式、原始trace网络和实际截图；无真实台账/凭据/私有Drive标识。报告证据只发布独立audit分支，不进入产品PR差异。本报告不执行合并或部署。
