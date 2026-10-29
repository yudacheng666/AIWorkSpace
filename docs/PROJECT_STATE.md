# AIWorkSpace｜当前项目状态

更新日期：2026-10-29（北京时间）  
当前阶段：**M1 双向任务闭环：原 Codex 验收发现的 2 项 P2 已修复；Linux + Windows 自动测试 23/23 通过；等待 Codex 复验及实际 Google Drive 文件系统复测**

| 项目 | 当前事实 |
|---|---|
| 仓库 | AIWorkSpace，Public；PR #1 保持 Draft，未合并 |
| 当前开发分支 | `feat/20261027-m1-task-loop` |
| 需求 | [REQUIREMENTS.md](REQUIREMENTS.md) V1 已确认 |
| 原独立验收 | Codex 对旧 head `37cde4c` 判定 **FAIL，2 项 P2**：同事件 ID 并发写入静默覆盖；GET 接口接受任意 Host。用户提供的报告摘要同时说明真实浏览器/Windows/Drive 本轮 NOT TESTED |
| P2 修复 A：并发事件丢失 | `append_event` 改用原子硬链接发布，不再使用可覆盖目标文件的 `os.replace` 作为最终发布操作。两个同 ID 并发写入最多一个成功，另一个得到 `FileExistsError`；回归测试用 barrier 强制两线程同时到达发布点 |
| P2 修复 B：Host/DNS rebinding | GET 与 POST 在处理请求前执行精确 Host allowlist 校验，允许 `127.0.0.1:<当前端口>`、`localhost:<当前端口>`、`[::1]:<当前端口>`；任意域名、后缀伪装及不匹配 Origin 被拒绝 |
| 自动测试 | **23 PASS / 0 FAIL（Linux）+ 23 PASS / 0 FAIL（Windows）**：GitHub Actions run [40827583905](https://github.com/yudacheng666/AIWorkSpace/actions/runs/40827583905)，Python 3.12；两套任务均 SUCCESS |
| 新增并发回归测试 | PASS：两线程在原子发布点同步竞争同一事件 ID，断言恰好一个成功、一个报 `FileExistsError`，且最终只保留一个完整事件 |
| 新增 Host 回归测试 | PASS：恶意 Host 的 GET/POST 返回 403；合法 localhost Host 与原本本机 API 请求正常 |
| 既有用户实测 | Windows 网页启动、任务显示、Drive 双向同步、ChatGPT 读回、刷新、服务重启及冲突 UI 曾由用户实测通过；这些证据来自修复前版本，不能自动代表本轮修改后的 Drive 文件系统兼容性 |
| 待实测 | 在用户实际 Google Drive 同步目录验证 `os.link` 支持情况及完整双向同步；本轮 CI Windows runner 不等同于 Google Drive 虚拟/同步目录 |
| Codex 复验 | **待执行**。原 Codex 结论仍记录为 FAIL；新代码虽通过双平台自动测试，但尚未由 Codex 对新 head 独立复验 |
| 公开安全 | 本轮只修改代码、测试、CI 与项目文档；未加入真实任务、个人资料、凭证或密钥 |

## 下一步

1. 由 Codex 对 PR #1 最新 head 进行只读复验，重点重跑两个原 P2 场景，并检查回归。
2. 同时在实际 Windows + Google Drive 数据目录做最小实测；若硬链接不受该文件系统支持，需改用兼容的原子排他方案后再验收。
3. 根据 Codex 复验与 Drive 实测结果修复缺陷；PR 保持 Draft，不合并 main。

**交接规则：** 新 AI 先读取根目录 `AGENTS.md`，再核实本文件、需求、决策、PR head 与最新 Actions 证据。不得把旧 head 的 Codex FAIL 改写成新 head 已复验通过。
