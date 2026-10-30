# PR #5 M3.3 P2修复后独立复验

日期：2026-10-30（北京时间）。固定HEAD：`ce7ae429b903acf2839b14c05478639400ff72cd`，产品/原测试基线SHA：`0c815dad7e28c1ccd82a2b3487711e8dc4d11cd7`。开始及结束均通过Git refs核对PR仍为此HEAD。

**总体：FAIL。原部分同步丢失STEP ID的P2已定向复验通过，但补测发现1项新的P2：相同reorder event_id、不同内容分布于不同base_revision时，排序流未被冻结。** 已按“若任一项失败，保留证据并停止”停止后续测试，仅整理证据和回写，不自行修复。

## 依据与执行顺序

读取PR最新描述、原失败报告与[修复后独立复验指令](https://github.com/yudacheng666/AIWorkSpace/pull/5#issuecomment-6518516148)，并读取固定版本AGENTS、需求、项目状态、决策与代码差异。

严格先完成A组原P2复验，A全部通过后才执行B组缺失专项。没有重复首轮已PASS的完整创建/编辑/完成确认流程，也未重跑M1/M2/M3.1/M3.2整套业务。所有事件/任务/步骤及名称均为隔离虚构数据，使用临时目录和临时本机端口。

## A. 原P2定向复验：全部PASS

| 指令项 | 结果 | 实际证据 |
|---|---|---|
| A1：[A,C,B]但C创建文件未到 | PASS | 实际Chromium仅显示A/B，明确显示“尚未同步”警告；API模型step_order_incomplete=true、missing_ids=[C] |
| A2：排序禁用及回调保护 | PASS | 全部上下移按钮disabled；步骤内容编辑按钮仍enabled。对禁用按钮dispatch click，并直接调用真实saveStepOrder回调，均零POST且文件名称/字节不变 |
| A3：直接API拒写 | PASS | POST[B,A]、revision1返回409；完整目录文件名和字节快照完全相同，无新增/覆盖/改写事件 |
| A4：C迟到后恢复原顺序 | PASS | 添加C的合法create文件后刷新，顺序恢复[A,C,B]，missing_ids=[]、incomplete=false，旧排序JSON字节不变。C创建position故意为3，证明按完整排序恢复而非碰巧按创建位置 |
| A5：恢复后合法排序 | PASS | 实际Chromium排序成功为[C,A,B]，恰好新增一条排序事件；此前所有事件字节保持一致 |

原P2在此固定SHA、本机已测范围可复验关闭。**这不代表PR整体PASS，因为后续发现新P2。**

## B. 已补齐的同步和重复专项

| 场景 | 结果 |
|---|---|
| 步骤create先于父任务到达 | PASS：先警告、无父任务，父任务加入后重建该步骤 |
| 步骤update先于create到达 | PASS：创建前不伪造步骤；create到达后正确恢复标题和revision2 |
| 排序先于全部步骤create到达 | PASS：先标记incomplete，所有create到达后按指定[B,A]恢复 |
| 排序revision1先于revision0到达 | PASS：缺前序时排序冲突，补齐后恢复连续链revision2和[B,A] |
| 相同event_id相同create/reorder内容重复 | PASS：告警去重，无多余步骤、无额外revision，读取不改写文件 |
| 相同step-update event_id，不同内容/不同revision | PASS：仅受影响步骤被冻结，兄弟步骤正常 |
| 相同reorder event_id，不同内容但相同base_revision | PASS：排序冻结，步骤内容不冻结 |
| 相同reorder event_id，不同内容且不同base_revision | **FAIL / P2**：两份冲突身份事件被当成合法连续排序，详见下文 |

## 新P2：跨revision的重复排序event_id未触发排序冻结

位置：app.py:444-448仅追加警告/补入变体；app.py:465-486随后按base_revision将它们作为连续排序接受，缺少独立的event_id身份冲突冻结。

### 复现

1. 建立同一虚构任务与合法步骤A/B，create事件完整，排除部分同步问题。
2. 写入合法排序事件：`event_id=order-event-001`、`base_revision=0`、`step_ids=[A,B]`。
3. 另一个文件复用**同一个event_id**，但`base_revision=1`、`step_ids=[B,A]`，两个JSON内容不同。
4. 读取工作台并在实际Chromium查看。

实际：

- warnings能发现重复event_id不同内容，页面也显示该警告。
- 但`step_order_revision=2`、`step_order_conflict=false`、顺序[B,A]，两份同身份冲突事件被都应用为合法连续历史。
- 实际Chromium上下移按钮依然可用，没有显示排序冻结；不是仅有告警文字而已。
- 所有原始事件仍完整，缺陷是当前排序流未冻结并应用了冲突身份事件，不是文件物理覆盖。

期望：相同event_id不同内容应标记受影响排序流为冲突、保留候选并停止排序；不能只因base_revision能接成链就信任二者。此原则与代码“A reused event ID with different content freezes each affected step/order stream”的注释及同ID步骤保护一致。

新缺陷确认为**P2**。没有把普通两条不同event_id的合法连续重排误判为冲突。证据文件保存两个复用ID事件原文、API模型、警告、完整步骤状态与文件完整性结果。

确认此错误标志后，仅启动只读GET用于保留真实浏览器截图，未执行后续排序写入，没有继续其他专项。

## 停止后未执行：NOT TESTED

依PR明确停止条件，本轮没有继续独立执行：

- 同一步骤同revision并发HTTP更新与旧revision409；
- 两条不同event_id的同版本排序冲突隔离、父任务冲突拒写专项；
- 100步上限、非法标题/状态/STEP ID、重复/缺失/额外排序成员边界；
- Host/Origin本机访问专项。

A3实际409仅证明部分同步时拒绝重排，不能冒充上述其他409/并发专项通过。B中已测同ID排序冲突也不冒充完整的不同ID并发排序隔离测试。首轮或原套件的通过结果不用于替代本轮未做的独立实操。

公司Windows、真实Drive、原生中文输入法、远程访问、长期/断电耐久性仍NOT TESTED。没有部署或操作公司8770，没有访问真实Drive。

## 测试记录与环境

- partial.py / partial.log：真实Chromium与HTTP的A组5项全部完成，退出0。
- sync.py / sync.log：按顺序补测B，遇上述P2后退出1并停止；前7组PASS及最后FAIL分别记录。
- 环境：Linux，Python3.12.14，Chromium154.0.8037.57，Playwright Python1.62.0，headless视口1440×1200。未执行公司平台测试。
- 本轮不重跑首轮PASS的完整功能路径；原Python/Node全套也未在本轮重新执行。PR声明修复后73 Python + 23 Node PASS，GitHub API确实显示当前固定HEAD Linux/Windows Checks SUCCESS；这些是CI背景证据，**不是本轮独立运行计数或P2已全部关闭的证明**。
- P1未发现已确认问题；新P2共1项；P3未新增已确认问题。未执行部分不作无缺陷保证。

## 只读保证

git archive导出精确HEAD；独立探针和虚构数据均在仓库外。验收后全部11个跟踪文件与固定HEAD逐字节一致（source-sha256.json）；原本地HEAD仍e9274f41918f8df4c30d2ecaef38533cff82c865且工作区干净。远端main开始/结束均94a93bcb6fc0bd5123f43925ffa9981edfc20150；产品/原测试/CI/PR分支/main未修改，未合并PR。临时服务已关闭。报告资产只新增到独立证据分支，不进入产品PR差异。

## 截图与日志

- [部分同步警告、排序禁用](01-incomplete-protected.png)
- [C到达后恢复原[A,C,B]](02-original-order-restored.png)
- [同步完成后合法重排](03-reorder-after-sync.png)
- [新P2：重复排序ID警告存在但排序未冻结](04-duplicate-order-not-frozen.png)
- [原P2复验结果/API409证据](partial-result.json) / [实际排序POST](partial-posts.json)
- [新P2双事件原文及工作台模型](duplicate-failure.json)
- [A组日志](partial.log) / [B组日志](sync.log)
- [A组独立探针](partial.py) / [B组独立探针](sync.py)
- [源文件摘要](source-sha256.json) / [PR与CI背景元数据](pr-metadata.json)

全部截图真实、数据虚构。探针复现前先按脚本指定路径导出固定SHA；sync.py预期在该产品缺陷重现时退出1，不会自行修改产品。
