# PR #6 / M3.4 独立 Chromium 复验：FAIL，确认 1 项 P2 后停止

验收日期：2026-10-30。固定产品及原测试 SHA：`a84779c12dbc2eb66dcd8573ccf05b2992cd22a7`。

读取 PR 最新描述、上次独立失败报告，以及固定版本 AGENTS.md、docs/REQUIREMENTS.md、docs/PROJECT_STATE.md、docs/DECISIONS.md。PR 文档 HEAD 为 `404d90eb692fd0306d8ca17a6f1e3d56600d73a9`；相对固定 SHA 仅 README/PROJECT_STATE/DECISIONS 文档变化，本轮运行固定 SHA 的产品和测试。

## 结论与等级

**FAIL / P2：新建任务表单恢复初始值后，仍显示不必要的浏览器原生离开确认。** 原任务标题刷新丢失问题在本轮已执行场景中通过，但不能将本次修复整体标记 PASS。确认这项新 P2 后立即停止，没有执行脚本后续场景或自行修复。未确认新增 P1/P3；未测范围不作无缺陷保证。

此缺陷是“恢复干净状态后不再提示”这一明确验收条件失败，影响用户对离开保护的判断；本轮没有发现已保存数据丢失，也没有把该缺陷描述为旧版静默丢稿问题仍然存在。

## P2 可重现步骤

1. 用隔离虚构事件启动本机随机端口服务，打开 Chromium。新建表单初始标题/负责人/三个日期均空，优先级 normal，主要项目未归类，关联项目空。
2. 输入标题“虚构新任务未保存草稿”、负责人“虚构新负责人”、截止日期 `2030-02-03`，不提交。
3. 整页 reload 出现原生 `beforeunload`；取消后，整张页面的输入值完全保留（此项 PASS）。
4. 将上述三个字段依次恢复为空；此时所有新建表单字段与初始值相同，所有已有任务和步骤也无草稿。
5. 再次整页 reload，**实际仍出现原生 `beforeunload`**，取消后没有发生导航。期望：无确认直接刷新。

[恢复为空的原始浏览器画面](06-new-task-restored-clean-trace.jpeg) / [完整表单状态](failure-clean-ui.json) / [失败断言及前后事件摘要](failure.json) / [原生对话框记录](dialogs.json)。截图来自 Playwright trace 的原始帧，未经修改；不在页面中绘制模拟原生弹窗。

源码定位：`web/index.html:314–325` 的 `watchUnsavedEditor` 使用 `snapshot() === cleanSnapshot`；任务/步骤快照为字符串，但 `web/index.html:1011–1024` 的新建表单 `createMetadataSnapshot()` 每次返回新对象。字段值相同仍是不同对象引用，因此恢复输入后无法从 dirty 集合移除。此定位来自只读检查，没有修改代码。

## 实测结果

| 检查 | 结果与证据 |
|---|---|
| 初始干净页面整页刷新 | PASS：无原生确认，发生导航，文件字节不变 |
| 任务标题草稿 | PASS：原生确认；取消后全页面输入完整保留；恢复原值后无确认；明确接受才导航 |
| 任务负责人和截止日期草稿 | PASS：同上，包含字段组合修改与恢复 |
| 步骤内容编辑草稿 | PASS：原生确认、取消保留、恢复原值无确认、接受离开 |
| 新增步骤草稿 | PASS：原生确认、取消保留、恢复为空无确认、接受离开 |
| 新建任务标题/负责人/截止日期草稿 | PASS（部分）：原生确认及取消保留；恢复初始值检查 FAIL/P2，随后停止；本表单接受离开场景未执行 |
| 已保存事件文件名、原始字节 | PASS（已执行范围）：4 个初始事件文件；15 次整页刷新尝试的每次前后文件集合及 SHA-256 完全一致，结束时仍相同 |
| 未提交草稿不得写事件 | PASS（已执行范围）：浏览器 POST 为 0，没有新增事件 |
| 新增 Node 浏览器刷新定向测试 | PASS：2 PASS / 0 FAIL / 0 skipped；日志见 node-focused.log |

已执行 **15 次**整页刷新尝试：初始干净页 1 次，任务标题/任务字段/步骤编辑/新增步骤各 3 次，新建任务 2 次。原生 beforeunload 共 10 次；取消 6 次、接受 4 次，均由真实 Chromium 对话框事件记录，不依赖提示文案。

### 停止后 NOT TESTED

- 本轮任务保存成功、步骤保存成功/新增成功、新建任务保存成功后不再提示的真实浏览器检查（Node 模拟测试 PASS 不替代这些实操）。
- 新建任务明确接受离开、仅管理字段草稿及查询 rerender 后持久保护。
- 本轮页面内刷新、总览切换、应用/清除查询及自动刷新保护的集成回归。首轮通过情况仅作为背景，不算本轮重新 PASS。
- 首轮停止后的必要相邻专项：查询下步骤级 409、部分同步排序恢复及新建表单其他相邻回归。
- 公司 Windows、真实 Drive、Windows 原生 IME、其他浏览器、多客户端、长期/断电耐久性、远程访问及部署，均未执行。

没有重复已通过的完整旧功能套件；双平台 CI 218 PASS 为 PR 提供的背景，不作为本轮本机执行结果。

## 环境、方法与限制

Linux；Python 3.12.14；Node v24.19.0；真实 Chromium 154.0.8037.57，Playwright 1.62.0，headless，中文 locale，Asia/Shanghai。服务只绑定 127.0.0.1 随机端口，2 个虚构任务、1 个虚构步骤、1 个虚构项目，TemporaryDirectory 隔离事件；未访问真实 Drive、公司 Windows 8770，未部署或远程操作。浏览器网络 trace 仅含 `127.0.0.1:41233`。

探针先发送 `keyboard.press('F5')`；本环境 headless 不将这个按键派发为浏览器快捷刷新，继而调用 Chromium `Page.reload` 执行真实整页导航。每次实际触发方式写入 reload-records.json。因此本轮证实原生 reload/beforeunload 行为，**没有把系统级物理 F5 或关闭整个浏览器窗口宣称为已实测**。取消导航使 Page.reload 等待超时是预期现象；FAIL 判定依据为干净页面出现原生对话框，而非超时本身。

[独立探针](browser.py) 内保留了停止后未执行的计划代码；后续代码存在不代表执行成功。真实执行边界以 [browser.log](browser.log)、[reload-records.json](reload-records.json)、[failure.json](failure.json) 为准。

## 证据与完整性

- [任务标题取消后](01-task-title-after-cancel.png)、[步骤编辑取消后](03-step-edit-after-cancel.png)、[新增步骤取消后](04-step-add-after-cancel.png)。
- [新建任务草稿取消后](05-new-task-after-cancel.png)、[全部恢复初始值后](06-new-task-restored-clean-trace.jpeg)。
- [真实浏览器日志](browser.log)、[完整 Playwright trace](trace.zip)、[对话框](dialogs.json)、[15 次刷新及逐次文件哈希](reload-records.json)、[POST 空列表](posts.json)。
- [最终事件 SHA-256](final-event-hashes.json)、[固定 SHA 文件逐字节校验](source-sha256.json)、[Node 定向测试日志](node-focused.log)、[PR 要求快照](pr-metadata.json)。

固定版本全部 11 个跟踪文件验收后逐字节一致，原工作区 git status 干净。PR 分支仍为 `404d90eb692fd0306d8ca17a6f1e3d56600d73a9`，main 仍为 `b209da970434b71bb4e1b97e86bfdf1fa0483e98`。没有修改产品、原测试、CI、PR 分支或 main，没有合并；临时 Chromium 和服务已关闭。截图、日志、数据均为虚构；发布前核查截图及凭据模式。报告和证据仅发布到独立审计分支，不进入产品 PR 差异。
