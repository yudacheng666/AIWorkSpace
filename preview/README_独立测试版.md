# AIWorkSpace P1–P3｜独立体验版（2026-11-09）

**用途：** 检查「项目/任务/步骤快速进展、零碎笔记拆分、后续待办审核、个人/汇报总结、项目阶段线」的串联体验。**这是独立测试包，不是正式发布，不应存放真实业务数据。**

## 获取经过 CI 验证的体验包

- 版本依据：GitHub Draft [PR #50](https://github.com/yudacheng666/AIWorkSpace/pull/50)；产品／测试 SHA `16ea3b9c1cb7f187391ce5be33b9e82cb491137f`。
- CI：[Actions #42621080984](https://github.com/yudacheng666/AIWorkSpace/actions/runs/42621080984) 3/3 SUCCESS（Ubuntu、Windows、Windows 真实 Chromium）。
- [下载 AIWorkSpace-UI-V2-isolated-preview ZIP](https://github.com/yudacheng666/AIWorkSpace/actions/runs/42621080984/artifacts/13675288528)。此 ZIP 的旧随包说明可能仍引用早期 PR #12；**正确的版本和操作依据是本文及上面的 SHA**，启动代码已按本 SHA 在 CI 验证。GitHub 下载 Artifacts 可能需要登录账号。

## Windows 使用方法

1. 下载 ZIP 并**完整解压**到任意新建的测试文件夹；不要覆盖真实 AIWorkSpace 安装目录，也不要解压到正在同步真实工作数据的 Google Drive 文件夹。
2. 双击包根目录 `start_ui_v2_preview.bat`；电脑需要能运行 Python 3（`py -3` 或 `python`）。不需要 Node、模型 API 或 Codex。
3. 启动器在 Windows 临时目录复制程序文件，创建完全空白的 `test-data-only`，用随机 `127.0.0.1` 端口启动独立服务并尝试打开浏览器。**不是 8770 正式工作台**；不读取原有 Google Drive 或任务资料。
4. 在独立页面创建**虚构**项目、任务和步骤。进入「工作记录」页，用顶部「我要」按顺序体验：补记、原文拆分、项目阶段线、汇报版选材。一个较完整的操作路径见 `docs/WORK_ARCHIVE_USER_GUIDE.md` 的「P1–P3 整体验收」章节；也可在 GitHub 在线查看该文档。
5. 结束后切回**启动器命令窗口，正常按 Enter 关闭**，程序将停止并清理临时目录。强制杀死进程可能留下 Windows 临时测试文件夹；如发生这种情况请先确认不是正式工作台的数据目录再清理。

## 体验关注点与反馈

- **易懂性**：是否知道从哪里记录事实、在哪里核对每条拆分、如何返回项目和汇报版；是否有操作按钮或提示看不懂。
- **数据可靠性**：反复点击同一条来源不会生成多份记录；编辑 ChatGPT JSON 后要重新核对；未保存草稿不会在切换时无提示丢失；所有未选事件仍保留在个人轨迹。
- **报告真实性**：项目阶段线同一 RECORD 只计一次；「用该项目生成月度汇报」只预填该月份及项目，不自动挑选事实、不自动保存；需手动核对并勾选正式汇报来源。
- **安全边界**：不使用真实公司记录、私有文件链接或真实供应商资料；体验包中的更新按钮不要点击；不要把此 ZIP 复制到正式数据目录或将其作为日常版本。

GitHub 云端模拟了完成确认先到、部分 RECORD 后到的场景，并测试记录补齐后解除冲突；**这不等于**实际两台公司电脑的 Google Drive 断网／重连／旧客户端混用已通过验收。这些保持 NOT TESTED。PR #50 目前仍 Draft，main 版本仍为 2.8.4。
