# PR #5 M3.3 独立 Chromium/API 验收

日期：2026-10-30（北京时间）。固定测试SHA：`4d9e25f94195ce6f0c7964a253d4965ea7d0dc85`，与PR最新评论要求一致。验收前后PR仍为此SHA。

**结论：FAIL，发现1项P2。按PR评论“若失败，保留证据并停止，不自行修复产品代码”，确认缺陷后停止后续验收，仅整理证据和回写。没有修复或修改产品、原测试、CI、PR分支或main。**

## 范围依据

已读取固定版本AGENTS.md、docs/REQUIREMENTS.md、docs/PROJECT_STATE.md、docs/DECISIONS.md，PR描述及最新评论：[M3.3独立验收指令](https://github.com/yudacheng666/AIWorkSpace/pull/5#issuecomment-6517946534)。产品代码SHA c9e537c91ce38395657ef13054f2a5a220aa5777仅作背景，不使用中间版本的失败结果替代本次固定HEAD。

所有步骤/任务/人员名称及事件均为隔离虚构数据，运行于临时目录和本机临时端口；未访问真实Drive，未部署或操作公司Windows8770，未测试远程访问。

## P2：部分步骤尚未同步时，对可见步骤排序会丢弃既有排序中的隐藏STEP ID

位置：app.py:492-500（输出steps仅含已同步步骤），app.py:887-898（只根据当前可见steps验证/写完整排序），web/index.html:315-327（只把task.steps作为完整ID集合发送）。

### 确定性复现

1. 创建虚构任务TASK-PARTIAL；创建两个可见步骤A、B，对应STEP-A…A、STEP-B…B。
2. 追加一条合法的任务级排序事件，`base_revision=0`、`changes.step_ids=[A,C,B]`，其中C为合法STEP-C…C，但C的create文件尚未同步。
3. 实际Chromium刷新：当前只显示A、B，排序revision=1。
4. 点击A的“下移”，对当前可见步骤调整顺序。
5. 前端发送`{step_ids:[B,A], revision:1}`，服务端成功追加新的reorder事件，`base_revision=1`、`step_ids=[B,A]`。C从新的完整排序记录中消失，没有阻止或提醒此丢失。

本次真实值：

- A：`STEP-AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA`
- B：`STEP-BBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB`
- C：`STEP-CCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCC`
- 原排序：`[A,C,B]`
- 新排序：`[B,A]`

**这是当前完整排序语义的丢失，不是原始JSON物理删除。** 原reorder文件逐字节不变，但服务端接受了省略C的新完整顺序。该场景直接违反评论第5项“不会把尚未同步的STEP ID从已有排序记录中静默丢掉”。

预期：保留完整已知排序成员，包括尚未到达的步骤ID；或者在同步不完整时明确阻止排序。不能只凭当前可见步骤集合认定用户提交了完整排序。

确认后按指令停止，未继续注入C的create文件来测试最终位置，未扩展其他缺陷或自行修复。

证据：failure.json完整保存原/新排序事件及真实POST；03-partial-sync-before.png与04-partial-sync-after.png；browser.log；posts.json；browser.py可重现。Playwright trace另存在本次本地证据包。

## 逐项执行状态

| 评论要求 | 本次独立执行结果 |
|---|---|
| 1. Chromium创建、稳定ID、显示编号、创建顺序、编辑、上下移、刷新 | PASS：实际创建3步，STEP-ID格式/顺序/显示1、2、3正确；编辑首步标题与doing；上下移后刷新保持顺序与ID |
| 2. 单步编辑隔离性 | PASS：对比编辑前后，父任务revision、M3.2五字段及另外两步完整状态均未改变，只有首步revision递增 |
| 3. 完成确认及ChatGPT限制 | PASS：取消浏览器确认无新增JSON、未写done；接受后才done；actor=chatgpt即便带confirmed_done=true也被validate_step_event拒绝 |
| 4. 事件历史与旧任务 | PASS（已测部分）：旧任务无step_events时显示空步骤；正常创建/编辑/排序产生追加事件，原父任务JSON未变；缺陷场景原排序事件未覆盖而新增记录丢失C。未做全历史/断电保证 |
| 5. 同步时序与部分可见排序 | FAIL / P2：排序事件包含尚未到达的C，用户对可见A/B排序后写入[B,A]丢C。步骤先父任务到达、其他乱序、重复event_id/不同内容等额外独立场景因停止条件NOT TESTED |
| 6. 并发同revision、旧409、内容冲突/顺序冲突/父任务冲突 | NOT TESTED（额外独立实操）：确认P2后停止，未继续执行。本轮已跑原72项涵盖对应回归，但不冒充本轮额外并发与浏览器专项通过 |
| 7. 100步边界、标题/状态/编号/排序成员、Host/Origin | NOT TESTED（额外边界专项）：确认P2后停止。普通合法创建/排序已实际执行；其余边界不因原套件通过而标独立PASS |

## 原套件与环境

在缺陷确认前启动并完成固定HEAD原测试：

- `python3 -m unittest discover -s tests -v`：**72 PASS / 0 FAIL**，Ran72 tests，OK，退出0。
- `node --test tests/test_create_ui.mjs`：**22 PASS / 0 FAIL / 0 skipped / 0 cancelled**，退出0。
- 独立浏览器探针发现上述产品FAIL并以退出1结束；这与“原72/22测试通过”分别记录，不混称全部验收PASS。
- GitHub API核对固定HEAD远端Linux/Windows Checks均SUCCESS；CI未覆盖本次发现的完整排序成员丢失边界。
- 环境：Linux、Python3.12.14、Node v24.19.0、Playwright Python1.62.0、真实Chromium154.0.8037.57（headless，1440×1200）。Node本机版本按实际记录，不冒充CI配置。
- P1未发现已确认问题；P2确认1项；P3未新增已确认问题。由于按指令停止，不能保证未执行路径没有其他缺陷。

## NOT TESTED 与执行限制

除了表中明确未执行的独立场景，公司Windows M3.3、真实Drive步骤同步、原生中文输入法、长期运行/断电耐久性、远程访问均NOT TESTED。本地先放排序文件、暂缺创建文件仅是隔离数据模拟，不描述为真实Drive验证。

没有重复M1/M2/M3.1/M3.2整套业务验收；只运行原套件作为必要回归及本次M3.3专项。发现产品失败后只进行截图、日志、源文件校验、报告发布，没有继续产品测试或编码修复。

## 方法说明

首次外部探针误等待页面并未实现的“步骤已保存”提示，实际保存与DOM已更新。这属于独立探针断言假设错误，不是产品失败；只修正仓库外探针的等待条件为真实控件恢复与状态读回后，从隔离新数据重跑。harness-first-attempt.log/png保留此过程，不作为P2证据，未修改原测试或产品。随后实际重现上述P2并停止。

固定SHA导出至/tmp/pr5-audit-4d9e25f，所有外部探针位于仓库外。验收后11个跟踪文件与固定HEAD逐字节一致（source-sha256.json）。本地原HEAD仍为e9274f41918f8df4c30d2ecaef38533cff82c865，工作区干净；main开始及结束为94a93bcb6fc0bd5123f43925ffa9981edfc20150；PR未合并，分支未改动。临时服务已停止。

## 证据索引

- [步骤创建、编号和顺序](01-created-steps.png)
- [编辑、上下移与完成确认后](02-edit-order-completion.png)
- [部分同步：排序前](03-partial-sync-before.png) / [只对可见步骤排序后](04-partial-sync-after.png)
- [核心失败事件/POST数据](failure.json) / [完整POST记录](posts.json)
- [浏览器独立日志](browser.log) / [独立复现探针](browser.py)
- [Python原套件日志](python.log) / [Node原套件日志](node.log)
- [源文件摘要](source-sha256.json) / [PR与CI元数据](pr-metadata.json)

所有截图为真实产品浏览器输出，全部数据虚构。报告资产存于独立证据分支，不进入产品PR差异。探针应先按脚本指定路径导出固定SHA，运行会以FAIL退出1重现P2，不修改产品。
