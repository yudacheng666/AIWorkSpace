# PR #6 / M3.4 第三轮独立验收：FAIL，1 项新 P2

验收日期：2026-10-30。实际产品及原测试固定 SHA：`9e0b84e59041b1d8da6d23958e13449e374cbf4b`。

读取固定版本 AGENTS.md、docs/REQUIREMENTS.md、docs/PROJECT_STATE.md、docs/DECISIONS.md、PR 最新描述及上轮 Codex 失败报告。最新 PR 文档 HEAD `e9d6fa5d80ccdb99f0c0ae77aec40e5335f64054` 相对固定 SHA 仅 README、PROJECT_STATE、DECISIONS 文档更新。固定版本 PROJECT_STATE 还保留旧 a84779c1 待验状态；执行依据为用户指定 SHA 和最新 PR 描述，未采用旧版本代码。

## 结论

**FAIL / P2：保存成功但因另一个草稿而延迟重绘后，原表单的干净基线没有更新；输入保存前旧值会被错误视为干净，整页刷新无确认并静默丢失这次未保存修改。** 确认后立即停止，未自行修复、未继续产品测试。

前两项 P2 在本轮直接复验场景中均通过：任务/步骤原生离开保护正常；新建表单 8 字段逐一恢复、全部恢复、仅保留一个字段的保护均正常。新缺陷属于“保存成功后的 dirty 基线与多草稿保护集成”边界，不能据此将本轮整体标记 PASS。

确认新增 1 项 P2；未确认新增 P1/P3，不对未测范围作无缺陷保证。已保存事件没有被覆盖或丢失，失败影响的是用户尚未保存的输入。

## 新 P2 操作链

用两个独立虚构任务 A=`TASK-MAIN`、B=`TASK-SECOND`。A 当前已保存标题为“虚构已保存任务新标题”（记为 X）。

1. 将 A 标题改为“虚构再次保存的新标题”（Y），将 B 标题改为“虚构第二任务尚未保存”。
2. 点击保存 A，等待成功。API 200，事件实际保存 Y。B 草稿仍在，因此 `refresh(true)` 按保护逻辑暂不重绘任务列表，A 原表单继续挂载。
3. 把 B 恢复原值，使其没有草稿；再把 A 标题从刚保存的 Y 改回 X。此时 X **不同于最新已保存 Y**，属于真实未保存修改，并不是恢复当前已保存值。
4. 执行浏览器整页 reload。监听默认取消确认，但**没有收到任何原生对话框**，页面直接导航。A 输入从 X 变为 Y，未保存的回退修改被丢弃。

期望：仍有未保存修改 X，必须原生确认；取消应保留 X。实际：原生确认 0 次、导航 1 次、草稿消失。

[刷新前任务卡截图](08-reverted-after-deferred-render.png) / [刷新后完整真实页面](failure-missing-native-prompt.png) / [前后输入、对话框、文件哈希断言](failure.json) / [对应 POST 及响应](posts.json) / [响应状态](responses.json)。取消监听在之前 32 次原生确认中实际工作，失败不是探针自动接受对话框。

只读源码定位：`web/index.html:314` 创建 cleanSnapshot；任务表单 `:717` 调用 watchUnsavedEditor 但未保存返回的 markClean；成功保存 `:758–762` 只删除 dirty 集合条目并尝试刷新。另一个草稿导致 `:967–970` 提前返回，原表单及其 X 基线继续存在。之后输入 X 与旧基线相等，删除 dirty 条目，尽管服务器最新值是 Y。没有修改产品代码；未将未实测的其他表单相同风险判为已确认缺陷。

## 实测矩阵

| 检查 | 结果 |
|---|---|
| 新建任务 8 字段逐一修改/恢复 | PASS：标题、主要项目、关联项目、负责人、优先级、截止/计划/跟进日期；每字段修改时原生确认，取消输入保留，恢复后无确认 |
| 8 字段一起修改，再全部恢复 | PASS：修改时保护，全部恢复后无确认；截图 01/02 |
| 8 种“只有一个字段仍不同” | PASS：先全部修改，再每次只留下一个字段；均继续原生确认，最后一个恢复后无确认 |
| 任务标题、负责人/日期草稿 | PASS：整页刷新原生确认、取消保留整个页面状态、恢复原值无确认、明确接受才导航 |
| 步骤编辑及新增步骤草稿 | PASS：同上 |
| 新建任务完整草稿及仅管理字段草稿 | PASS：取消保留、恢复干净无确认、明确接受离开 |
| 无草稿整页刷新 | PASS：无多余确认 |
| 正常任务编辑/步骤编辑/新增步骤保存成功 | PASS：分别完成真实写 API，确认服务器状态正确；随后刷新无多余确认 |
| 查询生效时新建任务保存成功 | PASS：匹配新建标题的查询从无结果变为新任务；表单清空；整页刷新无确认 |
| 新建任务草稿跨列表筛选/清除/刷新 | PASS：持久表单输入保留，原生保护仍在；恢复后无确认；没有 POST/文件写入 |
| 页面内刷新、风险视图切换、应用查询、清除查询 | PASS（本轮任务标题草稿）：逐项取消自定义确认，草稿保留、零写入 |
| 自动刷新 | PASS（本轮任务标题草稿）：移开焦点，等待实际 5.5 秒轮询，提示暂停刷新，草稿保留，零写入 |
| 保存失败 | PASS：隔离服务进程临时注入发布 OSError，真实 API 500，事件不变；草稿保留，整页刷新仍原生保护；恢复后无确认 |
| 查询下步骤级 409 | PASS：页面编辑旧版本步骤；独立虚构追加提高步骤 revision；旧提交 API 409、无写入、输入保留、原生保护仍在；明确同意页面内刷新后加载最新步骤 |
| 查询下部分同步排序 | PASS：完整顺序引用尚未收到创建事件的 H；排序按钮禁用，直接 API 重排返回 409，文件不变；H 创建事件到达后恢复原 [A,H,B]，原排序事件字节不变 |
| 保存成功但兄弟草稿阻止重绘后的再次修改 | **FAIL / P2**：上述操作链，未保存回退被当成干净状态，整页刷新静默丢弃 |
| 新增 beforeunload Node 定向测试 | PASS：3 PASS / 0 FAIL / 0 skipped |

原两项 P2 的基本场景已通过，不代表所有多表单交互边界都通过。没有重复旧完整功能套件；本机未重跑 Python 全套或全部 Node。最新 [CI #41049397248](https://github.com/yudacheng666/AIWorkSpace/actions/runs/41049397248) 已读回，固定 SHA 正确、Linux/Windows jobs SUCCESS；PR 提供的每平台 Python76+Node34、合计220 PASS 仅为背景，不作为本轮本机执行计数。

## 事件与 POST 核验

- 共 **64 次整页刷新尝试**：前 63 次符合各自预期，第 64 次为确认的新 P2。逐次记录见 [reload-records.json](reload-records.json)。
- 原生 beforeunload **32 次**：取消26、接受6；页面内自定义 confirm5次，其中取消4次、明确接受刷新1次。失败那次没有原生对话框，导航1次。
- 每次整页刷新前后，完整事件文件名集合及原始字节均完全一致。跨各次正常追加的全部已存在文件哈希也始终保留，不仅检查最后一次刷新。
- 初始4个事件文件，最终12个：5次预期成功网页保存各追加1个，独立夹具追加步骤新版本、完整排序、迟到步骤创建共3个；没有覆盖/删除旧文件。
- 浏览器 POST 共7次：200×3、201×2、500×1、409×1。另有1次 http.client 直接 API 排序 POST=409；它不在浏览器 POST 列表内，断言和执行通过日志见独立探针。
- 只读字段/刷新保护阶段 POST=0；失败保存、步骤409、部分同步排序409均前后零文件变化。最终丢失的回退草稿没有自动提交，服务器仍为已确认保存 Y。

[核验摘要](integrity-summary.json) / [初始哈希](initial-event-hashes.json) / [最终哈希](final-event-hashes.json) / [最终虚构事件原文](final-events.json) / [浏览器 POST](posts.json) / [POST 状态](responses.json)。

## NOT TESTED 与限制

确认新 P2 后没有继续产品测试或尝试修复。部分同步恢复后再次主动合法重排、兄弟草稿场景在其他任务字段/步骤表单中的扩展复现均 NOT TESTED。本轮页面内四操作/自动轮询重点复测任务标题；任务字段、步骤编辑/新增步骤的完整页面内四操作矩阵没有重复上一轮已通过套件，不能算本轮新增 PASS。

公司 Windows 原生 M3.4、真实 Drive、Windows 原生 IME、其他浏览器、多客户端、长期/断电耐久性、远程访问、部署均 NOT TESTED。

环境 Linux / Python3.12.14 / Node24.19.0 / Chromium154.0.8037.57 / Playwright1.62.0；headless，中文 locale，Asia/Shanghai。独立 TemporaryDirectory 虚构事件，服务仅绑定127.0.0.1随机端口42731。浏览器 trace网络只有该本机服务。未访问真实Drive、公司Windows8770，没有部署/合并。

探针先发 F5 按键；本 headless 环境不把它派发为浏览器快捷刷新，随后调用 Chromium Page.reload 执行真实整页导航。原生对话框由真实 Chromium beforeunload 事件验证；没有声称系统物理F5、关闭整个窗口已经实测。取消导航造成 Page.reload等待超时是预期；P2依据为有真实未保存修改却无确认并发生导航，而非超时。

## 证据与只读保证

- [八字段修改后取消](01-eight-fields-dirty-cancel.png) / [全部恢复干净](02-eight-fields-restored-clean.png)。
- [任务取消](01-task-title-after-cancel.png) / [步骤编辑取消](03-step-edit-after-cancel.png) / [新增步骤取消](04-step-add-after-cancel.png) / [新建任务取消](05-new-task-after-cancel.png)。
- [部分同步恢复](07-partial-sync-query-restored.png) / **[新P2刷新前](08-reverted-after-deferred-render.png)** / **[刷新后](failure-missing-native-prompt.png)**。
- [真实浏览器日志](browser.log)、[独立探针](browser.py)、[完整Playwright trace](trace.zip)、[对话框记录](dialogs.json)、[Node日志](node-focused.log)、[PR要求快照](pr-metadata.json)、[CI运行](ci-run.json)、[CI jobs](ci-jobs.json)。

截图为实际网页，不绘制模拟原生弹窗；对话框出现与选择以日志为证。固定SHA全部11个跟踪文件逐字节核验一致，见 [source-sha256.json](source-sha256.json)。原工作区干净，PR分支仍 `e9d6fa5d80ccdb99f0c0ae77aec40e5335f64054`，main仍 `b209da970434b71bb4e1b97e86bfdf1fa0483e98`。没有修改产品、原测试、CI、PR分支或main，临时服务和浏览器均已关闭。

所有事件、人员、任务、项目、截图均虚构。发布前核查凭据模式与本机trace网络，未含真实台账/凭据/私有Drive标识。证据仅上传独立audit分支，不进入产品PR差异。
