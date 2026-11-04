# 2026-11-04 数据核查界面可用性改造

## 用户反馈
用户提供数据核查页面截图，反馈现有界面完全看不懂、不知道异常如何处理，要求修正。

## 基线与范围
- 仓库：yudacheng666/AIWorkSpace
- 基线 main SHA：c4817668730de6631c86877e93571bd5d4456e15（VERSION 2.0.7）
- 修复分支：fix/20261104-review-center-usability
- 候选版本：2.0.8
- 不操作本地 8770 实例或真实工作台业务数据；不合并 main、不发布、不部署。

## 主要问题
旧页面将开发人员日志直接呈现给管理者：内部 ID、SHA-256、原始 JSON、英文校验错误默认可见；异常标题泛化；修复建议以 JSON 展示；“标记已核查·不写入”没有解释其业务含义。

## 设计决策
1. 页面默认以“发生了什么 / 对工作台的影响 / 建议怎么处理”解释异常。
2. 列表显示关联任务名称和业务含义；状态用“需要你处理 / 等你执行 / 已修复并验证 / 已确认保留”等表达。
3. 安全修复预览展示目标任务/步骤和字段值；授权与执行继续分开。
4. 原始 JSON、内部编号、来源文件、SHA-256、原始错误和完整 proposal 结构保留为只读技术详情，默认折叠。
5. 无效 step_id 单独分类，明确系统无法识别步骤归属；禁止猜测、改绑、自动创建或覆盖。用户核对后可通过正常任务界面重新录入，并将原异常记录为“确认保留，不写入”。
6. 扫描仍只读；dismiss 仅追加人工核查记录，不修改任务、步骤或原始异常文件。

## 实现
- app.py：新增 invalid_step_reference 分类、不可自动修复原因、用户说明字段、关联任务名称和记录中的步骤名称。
- web/index.html：重做数据核查页面文案、异常列表、说明卡片、可读修复预览、折叠技术详情及处理按钮。
- 测试：新增 invalid_step_id 数据治理回归测试；更新 Node UI 测试；更新 Windows Chromium E2E，验证技术详情默认折叠且展开后可查看原始 JSON。

## 验收
- 首次 PR CI：旧 Windows E2E 仍要求原始 JSON 默认显示并匹配旧授权按钮文案，因 UI 改版导致断言失败；Linux Python、Windows Python、Windows updater E2E 均通过。
- 更新 E2E 断言适配新设计后，最终 head SHA：d23d050701ff831a81fe2b9282857ca1fc606c26。
- GitHub Actions run 41770447630：Linux Python PASS；Windows Python PASS；Windows real-app + Chromium E2E PASS；总体 SUCCESS。
- PR #28：https://github.com/yudacheng666/AIWorkSpace/pull/28，Draft / Open，未合并。
