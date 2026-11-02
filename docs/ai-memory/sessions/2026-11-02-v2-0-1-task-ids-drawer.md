# 2026-11-02｜V2.0.1 任务交互小优化

## 优先级与隔离
- 用户明确：当前对话优先开发小更新，工作档案暂缓，不改另一开发分支。
- 起点 main SHA：`fa51b0123aaac76ddff2064d34178e7cc6e3ab11`，VERSION=2.0.0。
- 开发分支：`feat/20261102-v2-0-1-task-ids-drawer`。
- 工作档案分支 `docs/20261102-personal-work-archive-m0`、`feat/20261102-m1-work-archive` 不修改。

## 设计与实现
- task_id 保持原 UUID，新的 display_id 只作用户显示与查询：T-YYMMDD-12HEX，YYYYMMDD 取创建事件 UTC 时间；无效/缺失日期用 000000，非标准 task_id 用 SHA256。
- 相同显示编号不混淆：冲突时回退原始 task_id 并附警告。
- 网页主要任务视图、抽屉、创建反馈展示短号；点击编号或复制图标复制；无遮罩或非本体点击不关闭抽屉。
- 未保存草稿继续受原 closeTaskDetail() 保护。
- 不开发另一个 work_archive/工作记录数据层；事件型事项分类等工作档案恢复后处理。
- 候选发布为 2.0.1；产品代码分支 VERSION 仍为 2.0.0，未发布。

## 代码/测试文件
- app.py
- web/index.html
- tests/test_app.py
- tests/test_ui_shell.mjs

## 验证状态
- GitHub 已提交实现与测试，**未运行 CI 和真实浏览器 E2E，不能写 PASS**。
- 同 SHA CI 证据待补；main 之前的 PASS 不能移用到新修改。
- 不触发 Actions、不修改 main、不接触公司电脑/真实 Drive/实际任务数据、不合并/部署。

## 下一步
- 运行准确代码 SHA 的 Python/Node/定向浏览器测试（在不产生用户未批准费用的环境）。
- 根据结果修复，审阅 UI 和数据兼容性，再由用户决定 PR、发布和合并。
