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
