# AIWorkSpace｜工作记录与补记功能设计（2.3.0 候选）

状态：2026-11-05 用户批准“按分析推进，做文档，开发，测试，汇报”。基于 2.2.0 最新 main 开发；尚未合并、发布或操作真实 Google Drive 数据。

## 1. 为什么不是“先新建待办再标记完成”

- **任务**：未来有行动需要安排、跟踪或确认完成，使用 todo / doing / blocked / done。
- **工作记录**：已经发生的事实，包括无事先计划的临时工作、沟通、会议、问题处理、阶段成果；不使用任务状态。
- **任务轨迹**：已有任务的人工完成，直接从原任务事件派生只读轨迹，不把它复制成工作记录。任务尚未完成的实际阶段进展，用户可以补记一条工作记录并关联现有任务。

项目、任务和工作记录既可单独存在也可关联；记录不强制绑定任务，避免“完成数量”虚增。记录数量与任务人工完成次数分开统计。

## 2. 本轮交付的用户入口与流程

1. 工作台左侧新增「工作记录」，顶部新增「＋ 补记工作」，不覆盖「新建任务」。
2. 必填：实际工作内容（1–4000 字）、发生日期（真实日历日期，默认本机今天）；允许事后补记早前的日期。
3. 可选：关联项目、关联已有任务、工作成果（2000 字以内）、耗时（1–1440 分钟）。空项保持空，不由 AI 伪造。
4. 工作轨迹按**发生日期**降序；另显示真正写入的时间 created_at。过滤内容、日期范围和项目；点击工作记录可编辑，点击人工完成轨迹可打开现有任务。
5. 更新必须携带 revision；若同版本并发事件或关联项目/任务尚未同步，拒绝写入，提示刷新或核查，保留原数据。
6. 已明确确认完成的任务事件在轨迹中**只读展示**，不产生额外事件、不改任务状态，周期任务可显示具体周期。
7. 保存请求进行中允许继续输入，但服务器只保存提交时的表单快照；成功响应后若表单已变化，以提交快照推进 clean baseline，并保留新输入为未保存草稿。保存期间阻止离开页面、禁用清空/取消，避免新输入被旧请求响应覆盖。

本期不实现自动语义分类、AI 不经人发起的后台处理、日报/周报自动总结、跨事件事实去重、历史误分类任务转为工作记录或大批量迁移。上述功能进入后续阶段。关联任务不是修改该任务状态；用户叙述“做完某事”也不等于自动写入原任务 done。

## 3. 数据格式与目录

延续原有 --data-dir（Google Drive 同步目录），新对象仅写入：

    work_archive/record_events/evt_<event_id>.json

每个文件含 version=1、record_id=RECORD-<32位大写十六进制UUID>、event_id、action=create|update、actor=user|chatgpt、timestamp（带时区的实际写入时间）、base_revision 和 changes。示例（全部为虚构内容）：

    {
      "version": 1,
      "event_id": "work-demo-00000001",
      "record_id": "RECORD-AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
      "action": "create",
      "actor": "user",
      "timestamp": "2026-11-05T09:20:00Z",
      "base_revision": 0,
      "changes": {
        "content": "与虚构设备供应商沟通交期",
        "occurred_on": "2026-11-03",
        "project_id": null,
        "task_id": null,
        "outcome": "对方确认按原计划供货",
        "duration_minutes": 30
      }
    }

occurred_on 为用户指定的工作发生日，不应被 timestamp（补记日）替换。R-YYMMDD-XXXXXXXXXXXX 显示编号根据原始创建事件时间和记录 ID 产生，**修改发生日期不会改编号**。内部关联始终使用长 record_id。

事件校验拒绝任务状态字段、非法日期、未知字段、非整数耗时和非本产品 ID。每个事件通过原有原子发布函数写入独立 JSON 文件。读取时重复 event_id 一致可去重，异内容冲突冻结相关记录；同 base_revision 多个更新必须冲突，不能选最新覆盖。外部 AI 通过 Google Drive 直写也必须遵守相同 schema 与项目治理规则。

- GET /api/work-records：返回 records、task_completions、warnings。
- POST /api/work-records：新建记录，服务器生成 record_id。
- POST /api/work-records/RECORD-…/update：按精确 revision 修改。
- 沿用现有 local Host/Origin 校验，不新开公网服务；不引入 API 密钥、模型服务或费用。
- 程序更新只换程序文件，不覆盖 data-dir 及记录。

## 4. 工作轨迹口径与限制

- 人工补记：occurred_on 是统计日期，created_at 是实际补录时间，可修订日期但历史事件不删。
- 原任务人工完成：读取旧 events/ 中有效、action=update、changes.status=done 且 confirmed_done=true 的事件；仅在对应任务现在有效、无冲突、未进入回收站时展示。事件时间以 ISO 时间戳返回，浏览器按本机日期转换。
- 若任务多次明确完成，轨迹显示多次**完成事件**而不是伪装成多个独立任务；它不代表工作量加总或绩效。
- 不把任务创建、排序、标题修改、普通状态切换当成完成，也不自动生成重复工作记录。
- 旧版代码不认识新记录目录，但旧任务事件字节绝不改变。首次创建工作记录前必须让共享该数据目录的设备统一升级。

## 5. 后续迭代

**阶段 2：工作与任务联动**：工作记录与多个任务/步骤的多对多关系、任务详情反向追溯、事实记录派生待办建议、已存在任务查重；完成确认依然只能来自用户。历史错误建为待办的记录只能经用户确认转换，保留源事件。

**阶段 3：总结与职业档案**：每日/每周/月按时间和项目汇总；保存被引用的原始记录 ID、人工修订和版本，支持会议、成果、投入时间分析；逐步形成可追溯的工作业绩与简历素材。ChatGPT 由用户主动触发整理，未验证无人值守的 Drive 连接器写回能力前不承诺自动 AI 汇总。

## 6. 测试门槛

以准确 SHA 的 GitHub Actions Ubuntu/Windows Python + Node UI + Windows 真实 Chromium 为默认验收。专项覆盖：创建、回填过去日期、修改版本冲突、错误 schema 与未知 envelope 字段、部分同步、重复事件、关联缺失、原有任务字节不变、无任务状态字段、任务人工完成只读轨迹、普通失败/409 草稿不丢失、保存期间新输入保留及离页保护。真正的两电脑 Google Drive 离线/重连及真实工作台更新不属于云端 CI 的已覆盖范围，必须明示 NOT TESTED。未经用户合并发布授权，不合并 main、不碰真实工作台数据。


## 7. 完整闭环增量设计（2.4.0 候选）

原工作记录字段 project_id 和 task_id 继续兼容、不迁移。新字段 action_links 是 0–20 项列表，记录 target_type（task/step）、target_id、relation（progress_on/result_of/derived_action），步骤还要保留 task_id。历史关联永远保存原始 ID；任务/步骤转换后显示“未同步或已转换”，不以相似标题推断新对象。evidence_links 延续系统的 Google Drive/Docs HTTPS 文档白名单和标题校验；featured 是用户主动精选成果标识，不表示 AI 已评估绩效。

### 7.1 记录来源与幂等

work_archive/inbox_events 存储独立 INBOX-32HEX 事件。create 保存内容、发生日（可空）和项目（可空），dismiss 仅在用户明确确认后可写 ignored=true。把一条原文整理成正式工作记录时，先填入现有工作记录表单，再在成功创建的单条 RECORD 事件中固化不可修改的 source_inbox_id。显示“已整理”根据已有 RECORD 读取计算，不额外写一条收件箱 processed 事件。后端拒绝重复使用已处理/冲突/忽略来源；两个 RECORD 竞争占用同一来源时标示冲突，保留原始历史。

### 7.2 日、周、月报

GET /api/work-archive/preview 接受 period、day、project_id 参数，严格处理日历边界（周一至周日、自然月），只读返回整理底稿、来源 record IDs、人工完成 event IDs、填报耗时等；保存不会自动发生。已确认任务完成事件按 UTC 日历日，工作记录按发生日 occurred_on 统计。正文明确标记“来源整理底稿，非 AI 自动分析”，由用户/ChatGPT 主动核对润色。来源异常、超长或不存在则拒绝而非静默遗漏。

POST /api/work-archive/summaries 创建 SUMMARY-32HEX 独立追加事件，包含原来源、period、start/end、项目、用户编辑的 body 和 confirmed。后台重新按当前事件重算来源，提交的两个 ID 清单必须完全一致，否则 409；后续 POST /api/work-archive/summaries/SUMMARY-ID/update 只允许以准确 revision 更新 body/confirmed，保留历史。confirmed 只表示已核对总结，与 task done 无关。

### 7.3 数据和交互

work_archive 原有 record_events 外新增 inbox_events、summary_events。所有新目录位于 data-dir 而不是程序安装目录，不修改原 events/project_events/step_events。网页工作记录页扩展收件箱、总结、成果区，任务详情增加工作记录反向入口；三个表单都遵守草稿与保存中防离开规则。数据损坏、重复 ID 或同 revision 并发时冻结，保留原文件。共享数据目录的所有设备须升级到兼容版本再开始使用；真实双机同步/离线/重连未验收，不宣称通过。

### 7.4 模型与费用边界

没有模型 API 的本机网页只做可解释的规则性提取、来源列表和文本底稿，不会自动识别会议意图、生成行动、后台写 ChatGPT，也不会自动编写简历。用户可以点击复制总结到 ChatGPT，由 ChatGPT 按授权读取 Google Drive 原始证据并分析，必要时将核对后的正文回写。不能把工具未执行的自动分析写成已完成。
