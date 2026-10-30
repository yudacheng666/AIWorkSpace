# PR #3 两项 P2 独立定向复验

日期：2026-10-30（北京时间）。固定 HEAD：`aaf89a7ad26077b4292266d3a17429de900d6cdf`；开始及测试结束核对PR仍为此SHA。

**结论：PASS（本机Linux、真实Chromium已执行范围）。原两项P2均复验通过；未发现新增已确认P1/P2/P3。公司Windows、真实Drive、原生中文输入法仍为NOT TESTED。**

已读取目标提交的AGENTS.md、docs/REQUIREMENTS.md、docs/PROJECT_STATE.md、docs/DECISIONS.md，PR #3描述、原Codex失败评论/报告及最新修复回写，并检查8341816→aaf89a7产品差异。原失败证据：https://github.com/yudacheng666/AIWorkSpace/pull/3#issuecomment-6515937505 ；修复记录：https://github.com/yudacheng666/AIWorkSpace/pull/3#issuecomment-6516035969 。没有将修复声明或CI成功直接当作独立复验结论。

## 定向结果

| 场景 | 结果 | 本轮独立实测 |
|---|---|---|
| P2-1 原列表冲突 | PASS | 合法同版本update分别含related_project_ids=[] / [有效项目ID]。GET /api/tasks返回200；涉事任务conflict=true、冲突字段及两条候选暴露；不再抛TypeError，不断开工作台读取 |
| 冲突隔离与阻写 | PASS | 涉事任务更新409，文件快照未变；其他任务更新200，另建项目201。真实Chromium显示全部任务，只有冲突行控件禁用，没有全局读取失败 |
| 相同event_id不同列表内容 | PASS | 两个不同内容文件共用event_id，读取仍200、涉事任务冻结；普通任务正常可见 |
| P2-2 原缺失项目引用编辑 | PASS | 虚构任务引用尚不存在的主要项目M与关联项目R。浏览器有选中ID占位选项；仅改中文标题时真实POST不含project_id/related_project_ids；成功后DOM和API状态均保留M/R，警告仍在，不再静默清除 |
| API显式保留既有未知引用 | PASS | 旧客户端重复发送未改变的M/R，服务端200保留，不会因未同步引用拒绝普通编辑 |
| 明确取消主要项目 | PASS | 实际浏览器只把主要项目改成未归类，POST带project_id:null，不带related_project_ids；成功后主要为空而原缺失关联R仍保留 |
| 明确取消关联项目 | PASS | 随后实际浏览器清空关联多选，POST带related_project_ids:[]，成功清除R；不是后台自动清空，也未误清除其他字段 |
| 拒绝新增未知引用 | PASS | 新建任务指定未知主要/关联；现有任务指定新的未知主要/额外关联；非法列表/对象类型，合计6种创建/更新请求全部400，所有原JSON逐字节不变、无新增文件 |
| 取消后不能借历史重新添加未知引用 | PASS | 用户已明确清除M/R后，API尝试重加仍未知的M或R均400且不写文件。允许保留已有引用没有扩展为允许任意历史未知引用 |
| 项目迟到后的解析 | PASS | 另一个任务先引用缺失M/R，再将两个项目create事件加入本地隔离目录；原任务无需迁移即可读取正确项目名称。已明确取消归属的任务保持空引用，不会被迟到项目自动重新关联 |
| 事件完整性与浏览器异常 | PASS | 每次拒写前后比较文件快照；最终原始任务/项目事件字节均未变，无浏览器pageerror异常 |

## 原测试与运行环境

- `python3 -m unittest discover -s tests -v`：44 PASS / 0 FAIL，Ran 44 tests，OK，退出0。
- `node --test tests/test_create_ui.mjs`：9 PASS / 0 FAIL / 0 skipped / 0 cancelled，退出0。
- 实际浏览器为Chromium 154.0.8037.57，Playwright Python 1.62.0，Linux；Python 3.12.14、Node v24.19.0。本机Node不是CI配置中的22，按实际记录。
- PR固定HEAD的Linux/Windows Checks均SUCCESS，API元数据另存；Windows CI不是独立公司实机验证。
- 本轮额外探针只针对上述P2、明确取消、未知引用与必要回归，不重复无关M1/M2使用流程。

## NOT TESTED 与范围

没有访问或修改真实Drive，也未测试公司Windows、原生中文IME、真实同步网络延迟/断电场景或其他浏览器。本轮以临时目录中添加事件模拟“项目先后到达”，不把本地重建结果描述为真实Drive同步PASS。

缺陷等级：原两项P2在固定HEAD、本次已测范围复验关闭；未发现新增已确认P1/P2/P3。该结论不代表自动批准合并，也不覆盖未测试平台。

## 只读保证

使用git archive导出固定SHA至临时测试目录，独立探针和数据在仓库外；11个跟踪文件测试后与固定HEAD逐字节一致（source-sha256.json）。未修改产品代码、原测试、CI、main，未合并PR。原工作区仍干净；本地原HEAD为e9274f41918f8df4c30d2ecaef38533cff82c865；远端main开始/结束均为c218730a582d75d8c77333acc91fbf9ab1110e02。临时服务均已关闭。

独立截图日志只存于报告证据分支，不进入产品分支、main或PR产品差异。

## 截图与日志

- [列表冲突隔离、其他任务仍可见](01-conflict-isolated.png)
- [缺失引用：编辑前](02-missing-before-edit.png) / [只改标题后ID仍保留](03-missing-after-title.png)
- [明确取消主要项目、关联仍保留](04-explicit-primary-clear.png)
- [明确取消关联项目](05-explicit-related-clear.png)
- [完整Python日志](python.log) / [完整Node日志](node.log)
- [独立API及实际浏览器断言日志](recheck.log) / [真实浏览器POST记录](posts.json)
- [独立复现探针](recheck.py) / [固定源文件摘要](source-sha256.json) / [PR与CI元数据](pr-metadata.json)

全部截图为实际产品页面，全部输入/ID均为虚构。探针先将目标SHA导出到其中指定的/tmp/pr3-recheck-aaf89a7后即可运行；只创建临时虚构数据。
