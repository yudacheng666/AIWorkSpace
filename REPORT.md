# PR #5 M3.3 跨revision重复事件修复后独立验收

日期：2026-10-30（北京时间）。**实际测试产品及原测试SHA：633b5304e843ca632dca095d42a7ec66d4baabe4**。

**总体结论：PASS（本机Linux、真实Chromium/API已执行范围）。跨revision重复排序event_id的P2已复验通过，本轮剩余并发、冲突、100步、非法输入及Host/Origin专项均已完成，未发现新增已确认P1/P2/P3。**

## 版本与范围依据

读取了PR #5最新描述、原失败回评、固定提交的规则/项目记忆及修复差异。PR当前HEAD为dd570b2c05d5d10c40013541a419da93558a1cc4；描述“下一步验收”段落还包含旧HEAD 0d01a6d…，而用户明确固定产品/测试SHA为633b5304…。本次严格按用户固定SHA导出测试，未把其他HEAD当作实际测试版本。git diff确认633b5304至当前HEAD只有README、PROJECT_STATE、DECISIONS文档变化。

先执行原跨revision重复ID的定向复验，再完成其余尚未执行专项。没有重跑首轮已通过的完整创建/编辑/排序/完成确认业务路径，也没有重复M1/M2/M3.1/M3.2全流程。

## 1. 跨revision同event_id不同内容：PASS

同一虚构任务包含完整步骤A/B，两份排序事件使用同一个event_id：base_revision0的[A,B]与base_revision1的[B,A]。

- 读取结果step_order_conflict=true、step_order_revision=0，没有把冲突变体接成合法revision2。
- 两个排序候选完整保留并在实际Chromium显示。
- API排序请求返回409；完整文件名和所有字节快照完全不变，没有新增、覆盖或改写事件。
- 页面所有上下移按钮disabled，步骤编辑按钮仍enabled。
- 实际浏览器独立修改步骤标题成功，只追加1条步骤内容事件，父任务revision不变，排序仍冻结，所有旧事件字节不变。

**原跨revision身份冲突P2在固定633b5304、本轮已测环境复验关闭。**

## 2. 不同event_id合法连续排序：PASS

另一隔离虚构任务的两个排序事件使用不同ID，base_revision0的[C,D]与base_revision1的[D,C]正常应用为revision2；step_order_conflict=false。后续合法重排返回200，追加1个事件，网页顺序/排序按钮正常，历史字节全部保持。修复没有把普通合法连续重排过度冻结。

## 3. 已补齐的剩余独立专项

| 专项 | 结果 | 实测内容 |
|---|---|---|
| 同一步骤同revision并发 | PASS | 8个真实并发HTTP更新：恰好1×200、7×409；最终标题与唯一成功请求对应，revision2；只追加1个事件，全部原字节不变 |
| 旧步骤revision | PASS | 明确再发旧revision1更新，409，完整目录文件名/字节快照不变 |
| 同排序revision并发 | PASS | 8个真实并发重排：1×200、7×409，只追加1个完整排序事件，原历史不变 |
| 步骤内容冲突隔离 | PASS | 同步两条同base_revision不同标题事件，涉事步骤更新409，兄弟步骤仍200，排序操作仍200；内容冲突不误冻结整个父任务或排序 |
| 不同ID同revision排序冲突 | PASS | 排序流conflict=true，重排409且不写文件；步骤内容仍可更新200。真实页面只有排序控件禁用，步骤编辑仍可用 |
| 父任务冲突 | PASS | 父任务同版本标题冲突后，子步骤新增、更新、排序三个API全部409，所有事件字节完全不变；实际页面子步骤保存/排序/新增按钮均禁用 |
| 99→100步及最后名额并发 | PASS | 99个隔离步骤后，8请求竞争最后名额：1×201、7×409，最终恰好100步；成功标题长度200。第101步再请求409、无文件变化 |
| 100步页面保护 | PASS | 实际Chromium显示100个step-row、100步计数，新增步骤按钮disabled；截图含计数与页面末尾禁用按钮 |
| 标题边界 | PASS | 1字符新增成功、200字符在第100步成功；空白、空串、201字符、null、数字、列表/对象等拒绝 |
| 非法状态与STEP ID | PASS | 非法状态/大小写/类型，create伪造step_id/actor，格式非法/小写/路径形式STEP ID，均400或404且不写入 |
| 排序成员 | PASS | 空、缺失、重复、额外未知、未知替换、属于另一任务、格式错误、null、超100成员等均400，无文件变动 |
| 非法输入总计 | PASS | 上述累计34次独立非法请求全部400/404，整组前后文件名和字节快照一致 |
| Host/Origin三个写端点 | PASS | 新建步骤、编辑步骤、重排分别测试3种恶意/伪装Host、2种外部/错端口Origin，15次POST全部403且零文件变化 |
| GET保护与合法本机访问 | PASS | 恶意Host/Origin的GET403；精确localhost+相同Origin的GET与步骤编辑200。所有请求均发往隔离回环服务，没有进行远程访问测试 |

## 4. 原部分同步P2最小回归：PASS

仅做数据层最小检查，没有重跑此前完整Chromium流程：已有[A,C,B]但C创建未到，标记incomplete和missing_ids=[C]；补入C后恢复[A,C,B]，缺失清单清空，原排序事件字节不变。此前该P2完整5项独立复验记录继续保留，不冒充本轮重跑。

## 5. 原测试、CI与独立实操区分

本轮实际运行固定版本新增3个Python定向回归，3 PASS / 0 FAIL，Ran3 tests，OK：

- DataTests.test_duplicate_reorder_event_id_across_revisions_freezes_order_stream
- DataTests.test_distinct_reorder_event_ids_across_revisions_remain_valid
- ServerTests.test_duplicate_reorder_event_id_across_revisions_blocks_api_write

本轮没有重新执行完整Python/Node套件。PR声明固定产品SHA CI为76 Python+23 Node PASS；通过GitHub check-runs API独立核实**633b5304本身**的Linux/Windows Checks均SUCCESS（fixed-sha-ci.json）。76/23是远端CI背景，不是本轮独立运行计数。独立Chromium/API探针及上述3条定向原测试均已实际完成，日志另列。

## 6. NOT TESTED 与等级

NOT TESTED：公司Windows M3.3实机、真实Drive同步、Windows原生中文输入法、真实跨设备网络、断电/长期耐久性、其他浏览器、远程访问。并发验证是独立单服务的HTTP并发；不扩大为所有外部同步客户端、断电或多实例的绝对保证。

本轮未发现新增已确认P1/P2/P3；原第二项P2已复验通过。无失败触发停止条件。PASS仅对应上述固定SHA和执行范围，不构成合并批准或未测平台验收。

## 7. 隔离性与只读保证

Linux、Python3.12.14、Chromium154.0.8037.57、Playwright Python1.62.0，实际headless浏览器。全部任务、事件、名称、ID虚构，临时目录与临时端口隔离；不访问真实Drive，不操作公司8770，不做远程测试。

使用git archive导出固定633b5304；独立探针在仓库外。所有11个跟踪文件验收后与固定SHA逐字节一致，source-sha256.json为证。本地原HEAD仍e9274f41918f8df4c30d2ecaef38533cff82c865且工作区干净；main开始/结束均94a93bcb6fc0bd5123f43925ffa9981edfc20150；PR分支未修改，未合并。报告仅新增到独立证据分支，不进入产品PR差异。临时服务均关闭。

## 8. 证据

- [跨revision重复ID冻结](01-identity-order-frozen.png)
- [排序冻结期间实际内容编辑成功](02-content-edit-during-order-conflict.png)
- [不同ID合法连续排序](03-distinct-ids-order-normal.png)
- [不同ID同版本排序冲突隔离](04-distinct-order-conflict.png)
- [父任务冲突子步骤写控件冻结](05-parent-conflict.png)
- [100步计数](06-hundred-step-counter.png) / [第100步和禁用新增按钮](07-hundred-step-blocked.png)
- [身份冲突定向日志](identity.log) / [409及事件快照断言结果](identity-result.json) / [真实页面POST](identity-posts.json)
- [剩余专项日志](remaining.log) / [逐次HTTP请求响应](api-records.json) / [累计结果](remaining-result.json)
- [新增3项原Python回归日志](focused-python.log) / [最小部分同步回归](minimal-partial.log)
- [身份定向探针](identity.py) / [剩余专项探针](remaining.py)
- [源码摘要](source-sha256.json) / [固定SHA远端Checks](fixed-sha-ci.json) / [读取的PR背景](pr-metadata.json)

截图全部来自实际Chromium，非合成图。探针复现前按脚本路径导出固定产品SHA，运行仅使用临时虚构数据。完整Playwright trace另存本次对话本地证据包。
