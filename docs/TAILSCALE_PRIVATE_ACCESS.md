# AIWorkSpace｜手机 Tailscale Serve 私有访问（v2.9.1）

## 用途与安全边界

默认仍是纯本机工作台。只有用户明确为这一台电脑在 `app.py` **同目录**创建配置文件时才允许 Tailscale Serve 私有 HTTPS 入口；所有业务数据仍保存在原 data-dir（可为 Google Drive 同步目录），不会因此迁移或写入。服务始终监听 `127.0.0.1:8770`，不得改为 `0.0.0.0`；不需要路由器端口映射或修改 Windows 防火墙开放 8770。仅 Tailscale Serve 可用，**禁止 Funnel 公网共享**。

Tailscale Serve 对 Tailnet 用户注入 `Tailscale-User-Login` 身份头；Funnel 不注入，程序会拒绝无身份头转发请求。Tagged devices 不会收到这些身份头，所以本方案仅支持经 Tailscale 登录的普通用户设备；不能将 Tailnet 用户访问误称为工作台独立账户认证。仍需在 Tailnet ACL 中限制授权设备，避免向其他成员分享这台电脑的服务。

## 安装（只在电脑本地操作一次）

1. 先在工作台界面使用“检查更新／立即更新”，安装 GitHub main 已正式发布的 v2.9.1。请先按现有规定备份程序和工作台数据；如果尚未发布，勿提前部署未测候选。原电脑使用 `http://127.0.0.1:8770/` 不变。
2. 在 Windows PowerShell 定位当前运行程序的 `app.py` 路径：

   ```powershell
   $processId = (Get-NetTCPConnection -LocalPort 8770 -State Listen | Select-Object -First 1).OwningProcess
   (Get-CimInstance Win32_Process -Filter "ProcessId=$processId").CommandLine
   ```

   进入输出中的 `app.py` 所在目录（**不要在 C:\\Windows\\System32 中创建配置**）。
3. 以实际 `tailscale serve status` 的 `https://电脑名.tailnet名.ts.net` 为准，在程序目录执行（替换示例域名；**不带末尾斜杠和端口**）：

   ```powershell
   '{"tailscale_origin":"https://your-device.your-tailnet.ts.net"}' | Set-Content -Encoding ASCII .aiworkspace-tailnet-access.json
   Get-Content .aiworkspace-tailnet-access.json
   ```

   此本机文件被 Git 忽略，不在 updater 的安装/回滚白名单中；不要把真实域名写入公开仓库。
4. 关闭并**重新启动** AIWorkSpace 服务（不是只刷新浏览器），以读取新配置。保留 Tailscale Serve：

   ```powershell
   tailscale serve --bg 8770
   tailscale serve status
   tailscale funnel status
   ```

   状态必须显示 `(tailnet only)`；不得出现公网 Funnel。
5. 手机启用 Tailscale 后，Safari 访问 **Serve 状态输出中完整 HTTPS 地址**（不使用 `100.x.x.x:8770`）。可验证浏览页面和创建虚构测试任务；用户在实际业务数据上操作前请先确认备份和同步状态。

## 出问题时

- 仍显示 `local requests only`：确认本地程序已更新至 2.9.1、配置就在运行的 `app.py` 所在目录、配置值没有结尾 `/`、已重启服务、手机登录 Tailscale 的普通用户设备、Serve 输出为 Tailnet only；原程序或未启用配置将继续拒绝。
- 配置 JSON 错误或域名不合规：程序**拒绝启动**并说明原因；删除或修正配置后重启即可恢复本机工作台。
- 手机能打开但不能保存：检查来自 Safari 的 HTTPS 域名是否与配置完全一致；远程 POST 强制 Origin 同源。请不要关闭安全校验。
- 停止远程访问：在程序目录删除 `.aiworkspace-tailnet-access.json` 并重启工作台，另外运行 `tailscale serve --https=443 off` 停止代理。无需删除业务事件或修改防火墙。
- 启用或关闭 Serve、调整 Tailnet ACL 和排查公司电脑权限，均需要电脑用户自行操作；GitHub 合并发布不会远程控制现有电脑。

## 开发验收

Python HTTP 单元/集成测试覆盖：默认拒绝、严格域名格式与配置损坏拒绝、Serve GET/POST、跨站/空 Origin 拒绝、Funnel 无身份头拒绝、伪造转发 Host/Proto 拒绝。GitHub Actions Windows/Ubuntu/Chromium 自动化不等于在用户的 Tailscale 尾网、Windows 正式目录和 iPhone Safari 实机验收。

参考：[Tailscale Serve 官方文档](https://tailscale.com/docs/features/tailscale-serve)。
