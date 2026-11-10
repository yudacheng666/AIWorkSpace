# 2026-11-10：Windows 轻量桌面启动器 2.9.2 正式合并

## 用户目标
不再每次打开 PowerShell 启动 AIWorkSpace；不制作 EXE、不制作安装程序、不引入额外运行时或第三方依赖。日常通过桌面快捷方式启动和关闭现有本地 Python Web 服务。

## 开发与合并
- 仓库：`yudacheng666/AIWorkSpace`
- 开发分支：`feature/desktop-launcher-292`
- 原 main 基线：`8664a3b81e67513e7101a3ac5f8562491818ca43`，VERSION=2.9.1
- [PR #52](https://github.com/yudacheng666/AIWorkSpace/pull/52) 已于 2026-11-10 以 Squash 合并。
- 正式 main 合并 SHA：`4ad1bcae7449e498df2395380ed150ed8e53282c`；main 的 VERSION=2.9.2。
- 软件更新器直接跟踪 GitHub main 最新提交和 VERSION，不依赖 GitHub Release 页面。

## 实施内容
- 新增 Python 标准库 `desktop_launcher.py` 与三个 Windows Script Host VBS 入口：首次设置、启动、关闭。
- 首次设置在每台电脑本机 LocalAppData 保存独立 launcher 配置，在桌面创建「AI 工作台」「关闭 AI 工作台」快捷方式；配置、日志、运行状态和锁均不进入 Google Drive 数据目录。
- 启动优先使用 `pythonw.exe`，后台启动原 `app.py`，检查健康接口和 8770 端口；服务就绪后打开浏览器。重复点击复用已有实例；识别旧版服务；未知程序占用端口时拒绝启动。
- 关闭通过每次启动生成的随机凭证调用 loopback 关闭接口，不使用 taskkill、不按 PID/端口强杀、不结束其他 Python 进程；旧 PowerShell 服务需手动关闭一次。
- 日志放在 LocalAppData，启动时轮换，保留一个备份；无新增第三方依赖。
- 将新文件加入 2.9.2 updater 白名单、备份和回滚；旧版本原本不存在的新文件在新更新器回滚时会移除。

## 旧更新器兼容修正
正式版 2.9.1 的 updater 只安装原有四个白名单文件，并忽略 ZIP 中新增文件。为保证从 2.9.1 一次升级成功，2.9.2 的 `app.py` 内嵌四个启动器文件的可信副本，并在首次启动时原子补齐缺失文件；之后新 updater 接管这些文件的升级、备份与回滚。新增测试验证嵌入副本与仓库文件一致，且不会覆盖已存在文件。

## 自动化验收
- 最终产品/测试 SHA：`5fb595c473d28518c0892ee2f0e8360e0776a254`
- GitHub Actions [PR #42791328366](https://github.com/yudacheng666/AIWorkSpace/actions/runs/42791328366)：**3/3 SUCCESS**
  - Ubuntu：Python 299 项（32 skipped），Node UI 124/124 PASS
  - Windows：Python 299 项（29 skipped），Node UI 124/124 PASS；包括三个 VBS 脚本的 Windows Script Host 语法检查
  - Windows Chromium：更新/回滚 3/3 PASS，工作台 UI E2E 26/26 PASS，隔离预览启动包检查通过
- 早期 Windows CI 曾发现 VBS JSON 转义错误及 Windows 路径断言问题，均已修正；最终候选 SHA 的三组 Actions 全部通过。
- 主干合并提交 `4ad1bcae7449e498df2395380ed150ed8e53282c` 的 push Actions #42793149239 已触发，最终结果待回写。

## 当前部署边界
- GitHub main 已正式包含 2.9.2；尚未在用户电脑执行更新、创建快捷方式或重启本机 8770。
- 未访问、读取、修改或删除真实 Google Drive 工作台数据。
- CI 在 GitHub 临时环境完成，不等于用户两台电脑的真实部署验收。

## 用户电脑首次部署步骤
1. 在现有 AIWorkSpace 页面通过软件更新功能检查并安装 2.9.2。
2. 每台 Windows 电脑各运行一次 `setup_desktop_shortcuts.vbs`。
3. 在弹出的输入框粘贴现有数据根目录完整路径（可从文件资源管理器地址栏复制），不要选择 `events`、`project_events` 或 `step_events` 子目录。
4. 若旧 PowerShell 服务仍在运行，首次切换时手动关闭旧窗口一次。
5. 之后双击桌面「AI 工作台」启动，双击「关闭 AI 工作台」安全关闭。

