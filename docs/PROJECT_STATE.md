# AIWorkSpace｜当前项目状态

更新日期：2026-10-29（北京时间）  
当前阶段：**M1 核心双向同步链路已在实际 Windows + 云盘同步目录完成关键实测；原两项 P2 已由 Codex 在 Linux 独立复验通过。长期同步稳定性及多设备并发仍待验证**

| 项目 | 当前事实 |
|---|---|
| 仓库 | AIWorkSpace，Public；PR #1 保持 Draft，未合并 |
| 当前开发分支 | `feat/20261027-m1-task-loop` |
| Codex 验证的代码提交 | `9f06969164e773cf08f03e5d2d02de52c38d688b`；本次验收记录只涉及文档更新，不改动产品代码、测试或 CI |
| 原独立验收 | Codex 对旧 head `37cde4c` 判定 **FAIL，2 项 P2**：同事件 ID 并发写入静默覆盖；GET 接口接受任意 Host |
| 修复后 Codex 复验 | **PASS（本机 Linux 复验范围）**：两项原 P2 均通过；完整测试 23 PASS / 0 FAIL；额外 50 轮线程竞争、12 进程竞争及数据完整性检查通过；未发现新增已确认 P1/P2；限定安全扫描未发现密钥或隐私泄露 |
| P2 修复 A：并发事件丢失 | `append_event` 改用原子硬链接发布，不再以可覆盖目标文件的 `os.replace` 作为最终发布操作。并发复验确认相同事件 ID 最多一个成功，事件未覆盖 |
| P2 修复 B：Host/DNS rebinding | GET 与 POST 在处理请求前执行精确 Host allowlist 校验。复验确认恶意 Host 的 GET 返回 403，合法 localhost 访问正常 |
| GitHub Actions | **23 PASS / 0 FAIL（Linux）+ 23 PASS / 0 FAIL（Windows）**：run [40827583905](https://github.com/yudacheng666/AIWorkSpace/actions/runs/40827583905)，Python 3.12；两套任务均 SUCCESS |
| 扩展竞争测试 | **PASS**：Codex 在本机 Linux 额外执行 50 轮线程竞争、12 进程竞争和数据完整性检查 |
| 实际 Windows 同步目录硬链接 | **PASS**：用户在实际 Windows 云盘同步数据目录下完成临时硬链接创建/读取测试；具体本机路径不写入公开仓库。测试目录为临时探针，已清理；现有事件数据未受影响 |
| 实际 Host 防护 | **PASS（用户本机实测）**：普通 Host `127.0.0.1:8770` 返回 200，合法 `localhost:8770` 返回 200，恶意 `attacker.example` 返回 403；新代码包含 Host allowlist 检查 |
| Windows 本机完整测试 | **23/23 PASS**：用户在 Python 3.15 环境执行 `python -m unittest discover -s tests -v`；输出 `Ran 23 tests ... OK`。出现的 ResourceWarning 未导致测试失败 |
| 本机网页创建 → 云端 | **PASS**：测试任务 `TASK-SYNC-TEST-4afb314a` 的创建事件已在 云盘 `AIWorkSpaceData/events` 中核实 |
| 本机网页修改 → 云端 | **PASS**：用户修改测试任务标题后，云端 中出现相应 update 事件；标题已更新为 `测试专用：网页写入同步-4afb314a-网页修改` |
| 云端 → 本机网页 | **PASS（用户实测）**：用户将独立事件 `evt_sync-reverse-0bf4ccb09c.json` 上传至 云端 `events` 文件夹并等待同步，随后确认任务 `TASK-SYNC-REVERSE-0BF4CCB09C` 出现在本机网页 |
| 双向同步范围限制 | 已验证创建/修改的代表性流程；**尚未验证**长时间稳定性、断网重连、两台设备同时编辑、长期并发压力及自动冲突恢复。两个测试任务及其事件文件目前保留在数据目录中；事件采用追加式历史，禁止手动删除事件文件来清理测试记录 |
| 报告文件 | Codex 报告路径：`/workspace/scratch/pr1-recheck-9f06969/REPORT.md`。这是执行环境中的本地路径，并非 GitHub 上可公开访问的 URL |
| GitHub 评论回写 | Codex 直接发表评论被代理以 HTTP 403 拒绝；本次尝试通过已连接的 GitHub 集成另行回写。以实际返回结果为准 |
| 公开安全 | Codex 限定范围扫描未发现密钥或隐私泄露；这不是对所有类型泄露的绝对保证 |

## 下一步

1. 已完成：Codex Linux 独立复验结论已回写 PR #1；保留旧 head FAIL 记录。
2. 已完成：Windows 实际同步目录硬链接、Host 防护、本机测试、网页创建/修改上云、云端新事件下行至网页的关键实测。
3. 下一步：验证断网重连、长时间同步稳定性、多设备同时编辑和冲突恢复；制定安全测试数据归档方法，不直接删除追加式事件文件。
4. PR 继续保持 Draft；未经后续审查与用户明确批准，不合并 main。

**交接规则：** 新 AI 先读取根目录 `AGENTS.md`，再核实本文件、需求、决策、PR head 与最新 Actions 证据。不得把 Linux 复验 PASS 扩大解释为 Windows/云端/浏览器闭环 PASS。
