# PR #4 M3.2 独立验收报告

日期：2026-10-30（北京时间）。固定测试HEAD：`1c9324b991161c08fcaada8d0e2bd78c91cdc0c9`。开始与结束核对PR均为此SHA。

**总体：PASS（Linux实际Chromium、API及原测试已执行范围）。未发现新增已确认P1/P2/P3。公司Windows、真实Drive、原生中文输入法等未测范围仍为NOT TESTED。**

## 需求与边界

已读取固定HEAD的AGENTS.md、docs/REQUIREMENTS.md、docs/PROJECT_STATE.md、docs/DECISIONS.md，GitHub PR #4描述、6文件变更与测试要求。验收五字段为owner、priority、due_date、planned_date、follow_up_date；三个日期为独立本地日历日期，不是时间戳，不自动互相推导。

GitHub固定SHA的Linux/Windows Checks均SUCCESS（元数据另存）。本次另行运行原Python/Node测试，并用隔离虚构数据、实际Chromium和真实临时HTTP服务独立验证，不以CI或模拟DOM替代浏览器实测。

## 结果矩阵

| 检查 | 结果 | 实际证据 |
|---|---|---|
| 五字段网页创建与读回 | PASS | 中文虚构负责人、urgent、2028-02-29/2026-11-01/2026-11-09分别创建；API与实际任务控件五值一致，项目归属保留；合法闰日被接受 |
| 正常成功后新建表单清空 | PASS | 确认保存后标题、owner、三个日期清空，priority回normal；项目选择保留。保存事件仍包含原五字段 |
| 截止日期独立修改及清除 | PASS | 只改due_date，再单独清空；每次POST只有这个管理字段，其余四字段和项目不变；清除保存为null |
| 计划执行日期独立修改及清除 | PASS | 只改planned_date，再单独清空；其他管理字段和项目不变，清除保存为null |
| 下次跟进日期独立修改及清除 | PASS | 只改follow_up_date，再单独清空；其他管理字段和项目不变，清除保存为null |
| owner清除、priority恢复普通 | PASS | owner可独立清为空而保留urgent；priority随后可单独恢复normal，不重置其他字段 |
| 日期修改不清除尚未同步项目 | PASS | 任务带不存在的主要M/关联R；仅改跟进日期，真实POST不带项目字段；修改后仍是M/R |
| 旧事件兼容 | PASS（已测旧格式） | 无管理字段的原事件默认owner=null、priority=normal、三个日期null；网页仅改旧任务标题，真实POST不夹带新管理字段，原create字节未变；没有批量迁移 |
| 日期/类型/owner/priority验证 | PASS | 37组非法字段分别发到新建与更新接口，共74次400；覆盖无效闰日、月日溢出、非严格格式、时间戳、周日期、year0000、数字/对象/布尔、owner超长/错误类型、未知或非法priority；全部拒写、已有JSON字节不变 |
| API明确清除及省略语义 | PASS | 每个日期传空字符串单独转null，未提交字段均不变；owner空白单独转null，不重置priority；原JSON完整 |
| 异步完整新草稿保护 | PASS | 外部包装真实os.link，用Event延迟发布；任务甲请求发出后在实际网页填写乙标题、含首尾空格的owner、新priority及三个新日期。甲成功保存原五值；乙六项草稿原样保留，无自动POST/事件。等待期间额外submit被拒，只有一个create |
| 仅管理字段的异步草稿保护 | PASS | 不改标题，只在请求等待中改owner和follow_up_date；晚返回成功不清空标题及这两个修改，显示草稿已保留 |
| 写入失败保护 | PASS | 真正服务端os.link注入OSError产生500；页面保留owner和日期草稿、提示结果未确认；文件快照完全不变，没有phantom事件 |
| 同版本并发HTTP日期更新 | PASS | 8个同时请求恰好1×200、7×409；最终日期对应唯一成功请求，不被旧版本静默覆盖 |
| 外部并发事件与候选 | PASS | 合法同base_revision事件在全部五个管理字段给出不同值，含due_date=null对具体日期。全API仍200，conflict_fields含五字段，涉事任务409拒写，其他任务可读可编辑 |
| 冲突实际页面 | PASS | 五字段冲突候选可见，日期null展示“未设置”，涉事任务保存禁用，其他行可操作，没有全工作台读取失败 |
| 原始历史完整性 | PASS | 旧create逐字节未变；拒写操作前后文件快照一致；正常更新只增加事件，不覆盖既有文件；原测试中的原子追加、项目、Host/Origin保护均通过 |
| 浏览器JS异常 | PASS | 本次主浏览器流程无pageerror；预期注入的500与产品JS异常区分 |

## 原测试和独立证据

- `python3 -m unittest discover -s tests -v`：**53 PASS / 0 FAIL**，Ran 53 tests，OK，退出0。
- `node --test tests/test_create_ui.mjs`：**15 PASS / 0 FAIL / 0 skipped / 0 cancelled**，退出0。
- 额外独立浏览器与API探针均完成，日志中的PASS均有断言；未用零测试或语法检查替代功能测试。
- 环境：Linux、Python3.12.14、Node v24.19.0、Playwright Python1.62.0、Chromium154.0.8037.57，实际headless浏览器，1440×1200视口。CI配置Node22，本机版本按实际记录。
- 日期在浏览器原生控件中的可视格式由其locale决定，断言检查DOM value与事件JSON的YYYY-MM-DD值，不拿截图的本地显示格式冒充存储格式。

## NOT TESTED

公司Windows、真实Google Drive同步、Windows原生中文输入法、其他浏览器/移动端专门布局、长期运行/断电耐久性、真实跨设备网络冲突均未专项验证。本地添加虚构事件是数据重建与冲突验证，不代表真实Drive同步PASS。本次不部署到公司实例，不访问或修改真实Drive。

缺陷等级：已测范围未发现新增已确认P1（严重）/P2（需修复功能或数据保护）/P3（较低影响）问题。PASS仅对应固定SHA与以上执行范围，不等于批准合并或全平台验收。

## 只读和源文件校验

使用git archive导出固定SHA；独立探针和虚构数据位于仓库外。验收后全部11个跟踪文件与固定HEAD逐字节一致，见source-sha256.json。原本地HEAD仍为e9274f41918f8df4c30d2ecaef38533cff82c865且工作区干净；远端main开始及结束均为3814262a010cd4aba1bb95c5e1db16971d283ea0。未修改产品代码、原测试、CI或main，未提交产品变更，未合并PR。所有临时服务已停止。

报告、日志和截图另存独立验收证据分支，不进入产品PR差异或main。

## 证据索引

- [五字段创建与读回](01-five-fields-created.png)
- [三个日期独立清空后](02-cleared-independent.png)
- [异步保存：甲已入库，乙完整草稿保留](03-async-draft-preserved.png)
- [失败保留管理字段](04-failure-retains-metadata.png)
- [五字段冲突候选与冻结](05-metadata-conflict.png)
- [Python完整日志](python.log) / [Node完整日志](node.log)
- [真实Chromium与并发日志](browser.log) / [额外API验证日志](api.log)
- [真实POST记录](posts.json) / [浏览器独立探针](browser.py) / [API独立探针](api.py)
- [源码摘要](source-sha256.json) / [PR与CI元数据](pr-metadata.json)

截图均为实际产品浏览器截图，全部输入/ID虚构。探针复现前应按脚本中指定路径导出本固定SHA；运行时只创建临时数据。证据链接由PR回评提供，不使用不可访问的本机路径作为GitHub截图链接。
