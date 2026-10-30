# PR #3 独立验收报告

日期：2026-10-30（北京时间）。固定测试 HEAD：`8341816fdd8538a945be31d03d8b147679741d6a`。验收结束 PR 仍为此 HEAD。

**总体：FAIL，发现2项P2。** 既有测试38 Python PASS + 7 Node PASS，但新增关联字段的任务冲突和缺失项目引用编辑两条路径未被现有测试覆盖。

## 已确认缺陷

### P2-1：关联项目列表参与任务冲突比较时，整个工作台读取失败

位置：[app.py:129-134](https://github.com/yudacheng666/AIWorkSpace/blob/8341816fdd8538a945be31d03d8b147679741d6a/app.py#L129)，调用点约292行。

用独立虚构数据创建任务，再追加两条合法update事件，使用相同base_revision，changes分别含`related_project_ids: []`和`related_project_ids: [有效项目ID]`。

实际：`conflicting_fields`把列表放进集合，抛出`TypeError: unhashable type: 'list'`。读取GET /api/tasks直接断开连接，实际Chromium显示“读取失败：Failed to fetch”，连其他无关任务也不能加载。创建无关项目的POST返回400并暴露同一类型错误，不能继续正常工作。原事件文件未被覆盖。

预期：比较列表内容并将受影响任务标为冲突，保留候选、禁止冲突写入；其他任务仍可查看。由于网页任务更新会带上related_project_ids，即使两次修改主要是标题等字段，也可能触及此边界。

证据：probe.log（完整堆栈与HTTP结果）、browser.log、06-related-conflict-read-failure.png。不是损坏JSON，而是通过validate_event的合法事件组合。

### P2-2：项目尚未同步时，网页编辑标题会清空任务已有项目归属

位置：[web/index.html:149-165](https://github.com/yudacheng666/AIWorkSpace/blob/8341816fdd8538a945be31d03d8b147679741d6a/web/index.html#L149)及[254-273](https://github.com/yudacheng666/AIWorkSpace/blob/8341816fdd8538a945be31d03d8b147679741d6a/web/index.html#L254)。

步骤：创建一个合法任务事件，主要项目为PROJECT-C…C、关联项目为PROJECT-D…D，但对应project_events尚未到达。任务最初仍可见且有警告。实际Chromium只修改其标题，然后点击保存。

实际：选项只从已知项目生成，缺失ID没有保留选项；主要项目选中空项，关联列表为空。前端自动发送`project_id:null, related_project_ids:[]`，服务端200成功追加update，任务转入收件箱，原有两个引用从当前状态消失，警告也随之消失。用户未明确取消项目归属。

预期：缺失引用应在普通标题编辑中保留，或者明确阻止该操作并说明原因，不能把“尚未同步”当作用户取消关联。

影响边界：原始create JSON仍完整，丢失的是新追加事件覆盖后的当前归属状态，不是物理删除历史。项目事件迟到后也不能自动撤销这个已写入的取消归属事件。

证据：03-missing-ref-before.png、04-missing-ref-lost.png、browser-posts.json（真实POST内容）、browser.log。

## 八项要求的执行结果

| 要求 | 结果 | 本轮独立证据 |
|---|---|---|
| 1. 旧版任务事件兼容 | PASS（已测旧格式） | 没有项目字段的虚构旧create仍显示原标题、状态、revision，默认project_id=null、related=[]；旧任务可编辑加入项目；BOM兼容及旧回归由完整38项覆盖。没有读取真实历史数据，不能宣称所有未知外部数据完全兼容 |
| 2. 项目创建、重命名和历史追加 | PASS | 实际网页中文创建两个项目、稳定PROJECT编号；重命名追加新事件；原create文件逐字节保持不变；同名拒绝等既有测试通过 |
| 3. 任务主要及关联项目 | PASS（普通路径）/ FAIL（异常边界） | 网页新建主要甲/关联乙、编辑为主要乙/关联甲、显式清空归属均正确；缺失引用编辑清空见P2-2；含列表的冲突见P2-1 |
| 4. 收件箱与项目分组 | PASS（普通路径） | 旧任务在未归类收件箱；新任务按主要项目分组，关联项目不重复分组；项目重命名后分组名更新；显式取消主要归属返回收件箱；没有自动删除空项目 |
| 5. 项目事件缺失/乱序/重复/冲突保护 | PASS（项目流）/ FAIL（任务列表冲突） | 独立7组：缺create冻结并告警、create迟到恢复；缺中间版本冻结，补齐后正确重建revision3；相同ID相同内容去重告警；不同内容重复ID及跨项目重复ID冻结；同版本重命名冲突冻结；坏JSON告警，原文件均保留。实际浏览器冲突项目重命名禁用。任务关联列表的冲突未受保护，见P2-1 |
| 6. 并发写入不覆盖历史 | PASS（已执行竞争） | 任务流和项目流分别8线程，用barrier强制同时到达真实os.link发布点，均恰好1成功、7 FileExistsError；成功记录完整且内容匹配成功调用。并发HTTP项目重命名8次：1×200、7×409。没有据此保证任意外部同步客户端或断电场景 |
| 7. Host/Origin和409 | PASS（正常工作区） | 新项目API恶意Host403、外部Origin403；GET恶意Host403；合法localhost正常。项目过期/并发revision409，任务旧revision409，原create字节不变。P2-1发生后正常读取不可用，不能称全部异常路径通过 |
| 8. 真实浏览器操作 | PASS（正常路径）/ FAIL（两项P2） | Linux真实Chromium操作项目创建/改名、任务新建项目归属、多选关联、变更归属、收件箱分组及项目冲突禁用；两项P2均由真实浏览器再现 |

## 测试与范围

- 实际运行原测试：`python3 -m unittest discover -s tests -v` → Ran 38 tests，OK，38 PASS / 0 FAIL；`node --test tests/test_create_ui.mjs` → 7 PASS / 0 FAIL / 0 skipped。
- Node为模拟DOM；本轮另用真实Chromium访问实际临时HTTP服务，并核对磁盘JSON及真实POST，不拿模拟DOM代替浏览器结果。
- 独立探针用例中的FAIL是本报告发现；“原38+7全通过”不包含这些新增探针，也不代表验收通过。
- GitHub API核对固定HEAD对应的Linux/Windows Checks均SUCCESS；远端CI不等于本次独立Windows实机测试。
- **NOT TESTED**：公司Windows、真实Google Drive、原生中文输入法、实际跨设备同步/网络恢复、断电耐久性、其他浏览器、所有未知历史数据。
- 不重复无关M1/M2业务闭环；38项原套件仅作为本次变更必要回归，额外探针专注项目结构。
- P1未发现已确认问题；P2共2项；P3未新增已确认问题。

## 只读与数据保护

先完整读取固定提交的AGENTS.md、docs/REQUIREMENTS.md、docs/PROJECT_STATE.md、docs/DECISIONS.md。使用git archive导出固定版本，原checkout未切换；全部11个产品跟踪文件验收后与固定HEAD逐字节一致（source-sha256.json）。未修改产品代码、原测试或CI，未修改main，未提交或合并产品变更。全部数据为独立虚构事件，位于临时目录，未访问或修改公司Drive。临时HTTP服务已关闭。

main在额外浏览器操作前和验收结束均为c218730a582d75d8c77333acc91fbf9ab1110e02；本地原HEAD仍为e9274f41918f8df4c30d2ecaef38533cff82c865，工作区干净。PR仍为固定测试HEAD。报告证据单独存放在验收分支，不进入产品PR差异或main。

## 截图和日志

以下链接在证据上传后指向独立验收分支，数据全部虚构。

- [正常项目分组与旧任务收件箱](01-project-groups.png)
- [重命名与任务归属编辑](02-edit-and-inbox.png)
- [缺失项目引用：编辑前](03-missing-ref-before.png) / [标题保存后引用被清空](04-missing-ref-lost.png)
- [项目冲突禁用重命名](05-project-conflict.png)
- [关联列表冲突导致全工作台读取失败](06-related-conflict-read-failure.png)
- [Python完整原测试日志](python.log) / [Node完整原测试日志](node.log)
- [独立数据/API/并发探针日志](probe.log) / [浏览器日志](browser.log) / [实际POST记录](browser-posts.json)
- [独立数据探针](probe.py) / [浏览器探针](browser.py) / [固定HEAD源文件校验摘要](source-sha256.json)

探针中的导出路径应先由固定SHA创建；探针只使用临时虚构数据。截图为实际Chromium输出，不是生成或合成图。中文报告、截图与日志通过本PR评论中的证据分支链接交付。
