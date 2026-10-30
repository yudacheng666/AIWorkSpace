# PR #7 软件更新中心独立验收

**结论：PASS（Linux 隔离环境、固定源网络夹具及下述已执行范围）。未发现已确认 P1/P2/P3。Windows 原生链路、真实 main 成功更新为 NOT TESTED，不能视为全部发布/部署环境已通过。**

日期：2026-10-30。固定产品及原测试 SHA：`42573a34c3190b46c28c1573e98fbca202924a9c`。读取 PR #7 最新描述及全部8项验收指令，以及固定版 AGENTS.md、docs/REQUIREMENTS.md、docs/PROJECT_STATE.md、docs/DECISIONS.md。PR HEAD `d73f739b702b29abcb677d03f0e81f823bdcd84b` 相对固定 SHA 仅 PROJECT_STATE 文档更新，未将文档HEAD冒充代码版本。

## 执行及等级

- 原版更新器 Python 定向：**17 PASS**。
- 原版新增更新 API Python 定向：**5 PASS**。
- 原版更新中心 Node 定向：**2 PASS**。
- 独立 Chromium/API/恶意包预检：**29项 PASS**。
- 独立 Linux 真实多进程更新/回滚链路：**成功更新 PASS；新版本启动失败自动回滚 PASS**。

以上计数代表不同层次的实际执行，不合并成“完整产品套件”。没有重复全部已通过的旧功能测试。CI [#41059764656](https://github.com/yudacheng666/AIWorkSpace/actions/runs/41059764656) 已读回：固定 SHA、Linux/Windows jobs SUCCESS；PR记录每平台98Python+38Node、总272PASS属于CI背景，不能代替本轮独立Windows验收。

没有确认产品P1/P2，因此未触发产品失败停止条件。两次独立探针夹具断言问题和修正均保留原始证据，详见下文；未隐去失败日志、未把它们冒充已确认产品缺陷。

## 网页及API

| 项目 | 结果 |
|---|---|
| 首次未登记构建 | PASS：真实Chromium显示 `v1.0.0 · build 未登记` |
| 已登记构建 | PASS：显示 `v1.0.0 · build 42573a3` |
| 有更新/同版本新构建 | PASS（固定官方URL mock）：展示构建、说明和立即更新按钮 |
| 无更新 | PASS（同构建mock）：提示当前最新，安装按钮隐藏 |
| 离线及检查失败 | PASS：错误说明出现，任务仍可见，不冒充无更新 |
| 用户拒绝安装 | PASS：原生confirm取消，没有发安装POST |
| 未保存草稿阻止安装 | PASS：新建任务、已有任务标题、步骤编辑、新增步骤4类分别验证；输入保留、无安装POST、没有先弹安装确认 |
| 下载/安装期间锁定 | PASS：检查和安装按钮禁用；下载门闩期间直接并发POST返回409 |
| Host/Origin | PASS：恶意Host读取任务/版本/检查均403；外部Origin安装403 |
| 非法输入 | PASS：错误commit、任意URL额外字段、错误长度400，不启动helper |
| 原任务/步骤追加 | PASS：HTTP合法写入各新增1事件，原有所有历史文件字节保留 |

[未登记版本](01-version-unknown.png) / [草稿阻止安装](02-draft-blocked.png) / [离线提示](03-offline.png) / [详细HTTP请求响应](api-requests.json)。

## 更新包安全与来源

独立构造语料实际调用固定版校验器，并在拒绝前后比较应用目录及完整虚构数据目录：

- **PASS**：`../`路径穿越、绝对路径、反斜线、符号链接、重复app.py、缺少updater.py、错误commit根目录、CRC损坏、Python语法错误、无效VERSION、单文件超5MiB、包超25MiB、非ZIP均被拒绝；未产生暂存/越界文件，数据字节不变。
- **PASS**：包含额外 `evil.py` 的有效包只暂存4个白名单程序文件，不提取/执行额外脚本。允许执行受信白名单app.py是安装链路本身，不等同执行ZIP内任意额外脚本。
- **PASS**：应用目录等于data-dir、应用位于数据目录内、data-dir覆盖web程序路径均拒绝。
- **PASS**：上游API无效JSON、无效SHA、不受信任最终重定向域名被拒绝；main SHA已变化时不下载旧目标。
- 网络夹具仅接受官方仓库 `commits/main`、该固定40位SHA的raw VERSION、该SHA zipball三类精确URL。抓取记录可查，没有任意下载源/用户目录参数。

[独立预检结果及拒绝原因](preflight-results.json) / [固定源请求](preflight-requests.json) / [前后数据哈希](preflight-data.json) / [独立探针](probe.py)。错误跳转测试模拟最终response URL，不宣称实际访问了恶意域名。

## 真正的Linux多进程一键更新

未修改产品文件或原测试；仅复制到独立临时安装目录运行固定产品。虚构旧安装使用相同固定代码、`VERSION=0.9.0`、登记commit=`bbbb…`作为本地基线。更新包中的4个白名单文件均是固定SHA的原始字节，根目录为 `yudacheng666-AIWorkSpace-42573a3`，更新后VERSION=1.0.0、登记完整42573a3SHA。

为满足隔离测试，外部 `sitecustomize.py` 仅做两类环境夹具：

1. 仅模拟官方GitHub的commit/version/archive响应；localhost HTTP全部真实，产品prepare、ZIP校验、helper、替换、启动/健康验证代码均实际运行。
2. `Path.home()`返回独立临时home，使产品默认 `.aiworkspace/update-backups` 位置落在临时目录内；没有改写HOME环境变量，没有写入用户真实home。**真实home的权限/默认备份目录访问行为没有验证。**

### 成功更新：PASS

真实Chromium检查到1.0.0→用户确认立即更新→真实API准备下载→检查/安装按钮禁用→并发安装409→释放固定ZIP→API202→旧服务退出→真实独立updater.py helper备份/替换→按原端口、原绝对data-dir启动新app.py→健康接口验证完整SHA→浏览器自动reload显示 `v1.0.0 · build 42573a3`。

更新后4个程序文件逐字节等于固定SHA，数据任务仍可见，外部备份完整，暂存清理。共3个真实Python进程（旧服务/helper/新服务）；没有把模拟函数调用当作自动重启。

[更新前](e2e-success-before.png) / [锁定期间](e2e-success-locked.png) / [重启后新版本](e2e-success-after.png) / [真实进程日志](e2e-success-process.log)。

### 新版本启动失败自动回滚：PASS

再次建立全新隔离安装/数据。外部bootstrap仅对新登记SHA的app.py进程注入退出码71，**不改写更新包中的产品代码**；旧服务和helper不受该故障注入影响。

真实helper检测新进程失败→恢复备份的旧程序与旧构建信息→写rolled_back结果→用原端口/data-dir重启旧服务→网页显示“已自动恢复旧版本，任务数据未修改”。最终VERSION0.9.0、旧commit=`bbbb…`；全部旧白名单程序及旧build信息逐字节恢复，备份有效，暂存最终清理。共4个进程（旧服务/helper/失败新服务/恢复旧服务）。

[故障更新前](e2e-startup-failure-rollback-before.png) / [锁定期间](e2e-startup-failure-rollback-locked.png) / [回滚结果](e2e-startup-failure-rollback-after.png) / [真实进程日志](e2e-startup-failure-rollback-process.log)。

[e2e-results.json](e2e-results.json) 记录两条最终结果、原端口、启动argv、请求与响应、备份文件hash、程序hash、完整数据hash、来源URL及夹具定义。成功用例保留首次有效执行，最终脚本只重跑有清理时序争议的回滚用例；[首次脚本](e2e-first-attempt.py) 可复现完整两条路径。

## 数据绝对隔离

两条链路分别使用新临时数据目录：`events/`、`project_events/`、`step_events/`各1个虚构事件，另含数据根history.bin与events/archive/old.txt，共5个文件。包含二进制及归档子目录，比较整个递归文件名集合、原始字节及SHA-256。

**PASS：安装前、下载期间、更新后及启动失败回滚后，5个文件全部字节一致，未增加/删除/改写。** 备份只含旧程序/本机元数据，位于应用和数据目录之外；两次并发POST均409，没有第二次安装。备份manifest及旧程序内容实际读取校验有效。

[摘要](audit-summary.json) / [两条链路原始记录](e2e-results.json) / [预检初始及最后数据](preflight-data.json)。预检最后2次合法任务/步骤修改为明确的回归操作，预期各追加1事件；这不混同更新流程的零业务数据写入断言。

## 真实main、Windows及NOT TESTED

- **真实公开main的成功检查/安装：NOT TESTED。** 实际尝试产品check_latest_update，收到HTTP404；另用GitHub API确认当前main没有VERSION。main仍为 `0a3c8f19808b270eea632e4c0ebddf5bc17cda6f`，尚未含本PR的更新中心。这是当前发布前源状态，不能把mock更新PASS说成真实main已支持一键升级。[实际产品检查结果](real-public-main-check.json) / [main VERSION API响应](main-version-response.json)。未为测试修改main或发布构建。
- **Windows原生更新链路：NOT TESTED。** 只有Linux执行器，没有独立Windows环境。未测试Windows文件锁、不同Python安装/启动方式、helper脱离终端及原生失败恢复。Windows CI单元测试不替代这些场景。
- NOT TESTED：真实home/默认备份位置权限、真实GitHub包下载和重定向完整链路、企业代理/防火墙与限流、下载中断/断电/长时间运行、其他浏览器/多客户端、真实Drive、公司8770、远程访问与部署。Linux更新/回滚是明确的外部网络及home夹具环境；不得扩大为这些平台通过。

## 两次夹具断言及原始证据

1. 预检首次合法任务更新漏传服务端必需的status，得到400；是独立探针输入错误。修正探针加入status=todo后重新通过，没有改产品/原测试。保留 [首次日志](preflight-first-attempt.log)、[当时未分类记录](harness-first-attempt.json)、[截图](harness-first-attempt.png)。
2. 首次回滚已恢复旧程序/服务/数据，但探针在helper健康验证结束、finally清理前立即断言暂存已删除。该断言过早；原探针对任意断言自动赋P2字段不代表确认产品P2。核查失败点后仅为清理完成增加最多5秒有界等待，单独重跑回滚通过。保留 [首次多进程日志](e2e-first-attempt.log)、[首次结果](e2e-first-attempt-results.json)、[首次回滚trace](e2e-startup-failure-rollback-first-trace.zip) 与 [重跑日志](e2e.log)。未绕过程序/备份/数据/服务断言，没有自行修复产品。

## 证据与只读保证

[17项Python](python-updater.log)、[5项API Python](python-update-api.log)、[2项Node](node-update.log)、[29项独立预检日志](preflight.log)、[预检Chromium trace](preflight-trace.zip)、[成功链路trace](e2e-success-trace.zip)、[回滚链路trace](e2e-startup-failure-rollback-trace.zip)、[最终独立多进程探针](e2e.py)、[固定SHA源文件校验](source-sha256.json)、[PR要求快照](pr-metadata.json)、[CI运行](ci-run.json)、[CI jobs](ci-jobs.json)。

Linux/Python3.12.14、Node24.19.0、Chromium154.0.8037.57、Playwright1.62.0，真实headless Chromium。截图均实际页面，未绘制模拟UI。发布前核查凭据模式、截图和trace；所有浏览器网络仅127.0.0.1测试随机端口，数据均虚构，无凭据、真实台账、私有Drive标识。

固定SHA全部14个跟踪文件验收后逐字节一致，原工作区干净。PR仍`d73f739b702b29abcb677d03f0e81f823bdcd84b`，main仍`0a3c8f19808b270eea632e4c0ebddf5bc17cda6f`。未修改产品、原测试、CI、PR分支或main；未访问真实Drive/公司Windows8770，未部署、未合并。临时浏览器、服务、helper及重启子进程均已清理。报告/证据仅提交独立audit分支，不进入产品PR差异。
