# 2026-11-03 数据核查修复顺序保护

## 背景
- PR #23 已按用户授权合并为 AIWorkSpace 2.0.5，merge SHA `f137fd6cd400b23c7878b4cd514ff27b94d88c92`。
- 合并后 main Actions #41595962365 3/3 SUCCESS。
- 对同一目标多条异常的只读复核发现：同一执行步骤的连续异常可能分别引用 base_revision 2 和 3；如果后续事件先处理，重放旧事件可能覆盖较新的标题。
- 另发现旧 revision 的 task trash 不应被自动重基到已经更新的当前任务。

## 变更
- 对 base_revision 高于目标当前 revision 的异常，不生成授权预览；提示先处理同一目标更早的异常。
- 同一目标的异常按 task_id / step_id / source base_revision 升序显示。
- 任务 trash 只有在源 base_revision 与当前 task revision 相同的情况下才允许形成自动修复预览；旧 revision 的 trash 只能记录人工核查不写入，或由用户从当前任务正常操作入口重新发起。
- 对允许重基的候选，在修复预览中明确显示原始与当前 revision 差异。
- 新增两项合成 API 测试，覆盖连续异常按序执行、过期 trash 不重放。
- 原始事件只读保留；不读取或修改任何真实 Drive 文件。

## 发布边界
- 正式 main 仍为 2.0.5；独立 Draft PR 候选版本 2.0.6。
- 2.0.6 需以准确 SHA 通过 Actions 后再交用户审批；未获批准前不合并。
- 公司 Windows 8770 未升级，真实六项异常没有写入/删除/覆盖。
