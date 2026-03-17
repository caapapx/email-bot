# OpenClaw 渐进式开放测试方案（master 直更版）

日期：2026-03-17  
项目：`email-bot`

## 固定执行约束

1. OpenClaw 仓库固定工作目录：`~/.openclaw/email-bot`
2. 只使用 `master` 分支开发，不创建阶段分支。
3. 每个阶段开始前都先 `git pull --ff-only origin master`，确保最新。
4. 每个阶段结束后直接提交到 `master`，提交信息带阶段号。
5. 前 3 个分析阶段必须只读：禁止 `send/move/delete/archive/flag`。

## 阶段通用前置提示（每次都贴）

```text
先执行仓库同步，不要开始功能开发：
1. 工作目录固定为 ~/.openclaw/email-bot
2. 如果目录不存在：git clone https://github.com/caapapx/email-bot.git ~/.openclaw/email-bot
3. 进入目录后切换 master：git checkout master
4. 拉取最新代码：git pull --ff-only origin master
5. 输出当前目录、当前分支、最近一次 pull 是否成功
6. 若 pull 失败，停止并报告错误，不要继续

后续所有改动都直接在 master 进行。
```

## Preflight 0：邮箱登录与连通性冒烟测试（必须先过）

目标：先证明能连上邮箱并执行只读拉取，否则后续“读能力测试”无效。

通过标准：

1. `scripts/check_env.sh` 通过
2. `scripts/render_himalaya_config.sh` 通过
3. `himalaya` 可用，且可执行最小只读拉取
4. 输出失败归因：配置/认证/网络/CLI 缺失

给 OpenClaw 的 prompt：

```text
先执行“阶段通用前置提示”里的仓库同步步骤，确认在 ~/.openclaw/email-bot 的 master 最新状态工作。

当前阶段：Preflight 0（邮箱冒烟测试）
硬性约束：
1. 只允许环境检查、配置渲染、只读拉取
2. 禁止发送、移动、删除、归档、标记邮件

执行步骤：
1. 阅读 README.md、SKILL.md、scripts/check_env.sh、scripts/render_himalaya_config.sh
2. 运行 bash scripts/check_env.sh
3. 运行 bash scripts/render_himalaya_config.sh
4. 检查 himalaya 是否可用并识别 account
5. 运行一次最小只读验证（优先）：
   himalaya --account <account> envelope list --folder INBOX --page 1 --page-size 5 --output json
6. 生成：
   - docs/validation/preflight-mailbox-smoke-report.md
   - runtime/validation/preflight/mailbox-smoke.json
7. 报告结论：是否允许进入 Phase 1

完成后直接提交到 master：
git add .
git commit -m "preflight: mailbox smoke test"
git push origin master
```

## Phase 1：邮件分布普查（只读）

目标：验证“读大量邮件并给出整体分布”的能力。

给 OpenClaw 的 prompt：

```text
先执行“阶段通用前置提示”里的仓库同步步骤，确认在 ~/.openclaw/email-bot 的 master 最新状态工作。

当前阶段：Phase 1（邮件分布普查）
硬性约束：
1. 只读，不允许 send/move/delete/archive/flag
2. 先小样本，再扩大样本
3. docs 报告必须脱敏

任务：
1. 设计普查流程：envelope list -> 抽样正文
2. 输出统计：
   - 发件人域名 Top N
   - 联系人/组织 Top N
   - 主题关键词 Top N
   - 时间分布（日/周）
   - 内外部邮件占比
   - intent 候选分布（support/receipt/newsletter/human/internal_update/scheduling/finance/recruiting）
   - 附件占比
   - 高频线程/长线程
3. 产出文件：
   - runtime/validation/phase-1/mailbox-census.json
   - runtime/validation/phase-1/intent-distribution.yaml
   - runtime/validation/phase-1/contact-distribution.json
   - docs/validation/phase-1-report.md
   - docs/validation/diagrams/phase-1-mailbox-overview.mmd
   - docs/validation/diagrams/phase-1-sender-network.mmd
4. 报告中区分：事实 / 高置信推断 / 待确认假设

完成后直接提交到 master：
git add .
git commit -m "phase1: mailbox distribution census"
git push origin master
```

## Phase 2：用户画像与公司业务画像（只读）

目标：从邮件分布和样本推断“你是谁、公司在做什么”。

给 OpenClaw 的 prompt：

```text
先执行“阶段通用前置提示”里的仓库同步步骤，确认在 ~/.openclaw/email-bot 的 master 最新状态工作。

当前阶段：Phase 2（画像推断）
硬性约束：
1. 只读，不允许修改邮箱状态
2. 每条结论必须给证据
3. 低置信结论必须标记为待确认

任务：
1. 输出用户画像候选：角色、职责、决策参与、沟通对象、节奏压力、表达风格
2. 输出公司业务画像候选：业务活动、上下游对象、关键流程、邮件依赖点、AI 切入点
3. 产出文件：
   - docs/validation/phase-2-report.md
   - runtime/validation/phase-2/persona-hypotheses.yaml
   - runtime/validation/phase-2/business-hypotheses.yaml
   - docs/validation/diagrams/phase-2-relationship-map.mmd
4. 最后给最多 7 个“最小确认问题”

完成后直接提交到 master：
git add .
git commit -m "phase2: persona and business profile inference"
git push origin master
```

## Phase 3：生命周期建模与图示更新（只读）

目标：把邮件从“分类结果”升级为“线程生命周期状态机”。

给 OpenClaw 的 prompt：

```text
先执行“阶段通用前置提示”里的仓库同步步骤，确认在 ~/.openclaw/email-bot 的 master 最新状态工作。

当前阶段：Phase 3（生命周期建模）
硬性约束：
1. 只读，不允许修改邮箱状态
2. 不能只列标签，必须做 thread 级阶段模型
3. 无法高置信建模的流程必须明确说明

任务：
1. 归纳至少 3 条主要生命周期流（如商务/招聘/合作/财务/内部决策）
2. 每条流至少定义 5 个阶段，并包含：
   - 阶段进入信号
   - 阶段退出信号
   - 高风险信号
   - 推荐 AI 动作（仅 summarize/classify/remind/draft）
3. 产出文件：
   - runtime/validation/phase-3/lifecycle-model.yaml
   - runtime/validation/phase-3/thread-stage-samples.json
   - docs/validation/phase-3-report.md
   - docs/validation/diagrams/phase-3-lifecycle-overview.mmd
   - docs/validation/diagrams/phase-3-thread-state-machine.mmd
4. 给出 policy/profile 的 5 条建议（先写建议，不直接改配置）

完成后直接提交到 master：
git add .
git commit -m "phase3: lifecycle modeling and diagrams"
git push origin master
```

## Phase 4：日报/周报价值输出（只读）

目标：验证用户能否快速感知价值。

给 OpenClaw 的 prompt：

```text
先执行“阶段通用前置提示”里的仓库同步步骤，确认在 ~/.openclaw/email-bot 的 master 最新状态工作。

当前阶段：Phase 4（只读价值输出）
硬性约束：
1. 只读，不写发送动作
2. 输出必须短、准、可执行
3. 每条结论要可追溯

任务：
1. 生成：
   - 今日紧急清单
   - 待我回复清单
   - SLA 风险清单
   - 本周摘要
2. 文件：
   - docs/validation/phase-4-report.md
   - runtime/validation/phase-4/daily-urgent.yaml
   - runtime/validation/phase-4/pending-replies.yaml
   - runtime/validation/phase-4/sla-risks.yaml
   - runtime/validation/phase-4/weekly-brief.md

完成后直接提交到 master：
git add .
git commit -m "phase4: daily and weekly read-only outputs"
git push origin master
```

## Phase 5：本地草稿生成（不发送）

目标：验证草稿质量和人工编辑负担是否下降。

给 OpenClaw 的 prompt：

```text
先执行“阶段通用前置提示”里的仓库同步步骤，确认在 ~/.openclaw/email-bot 的 master 最新状态工作。

当前阶段：Phase 5（草稿不发送）
硬性约束：
1. 只允许写本地草稿到 runtime/drafts/
2. 禁止发送
3. 外部/法务/财务/附件场景默认 review_required=true

任务：
1. 从 Phase 4 输出中选线程生成草稿
2. 产出：
   - runtime/validation/phase-5/draft-candidates.yaml
   - docs/validation/phase-5-report.md
   - runtime/drafts/<thread_id>.eml

完成后直接提交到 master：
git add .
git commit -m "phase5: local draft generation without send"
git push origin master
```

## Phase 6：学习闭环（!learn / !rule / !edit）

目标：把人工修订稳定沉淀成规则。

给 OpenClaw 的 prompt：

```text
先执行“阶段通用前置提示”里的仓库同步步骤，确认在 ~/.openclaw/email-bot 的 master 最新状态工作。

当前阶段：Phase 6（学习闭环）
硬性约束：
1. 一次只提一条新规则
2. 必须有“草稿 vs 人工修改”证据
3. 先提议，确认后再落盘

任务：
1. 比对草稿与人工修改
2. 输出候选规则和证据
3. 产出：
   - docs/validation/phase-6-report.md
   - runtime/validation/phase-6/learned-rule-candidates.yaml
4. 如果确认，再写入 config/profiles/rules/<profile>.md

完成后直接提交到 master：
git add .
git commit -m "phase6: learning loop rule proposals"
git push origin master
```

## Phase 7：受控发送演练（最后执行）

目标：仅在显式 `CONFIRM_SEND` 时验证发送守护。

给 OpenClaw 的 prompt：

```text
先执行“阶段通用前置提示”里的仓库同步步骤，确认在 ~/.openclaw/email-bot 的 master 最新状态工作。

当前阶段：Phase 7（受控发送）
硬性约束：
1. 没有明确 CONFIRM_SEND，禁止发送
2. 发送前必须复述：草稿、收件人、风险、条件
3. 必须输出审计记录

任务：
1. 校验确认令牌与草稿
2. 条件不足则拒绝发送并说明原因
3. 条件满足再执行一次受控发送演练
4. 产出：
   - docs/validation/phase-7-report.md
   - runtime/validation/phase-7/send-audit.json

完成后直接提交到 master：
git add .
git commit -m "phase7: controlled send drill"
git push origin master
```

## 建议先跑到哪里

如果当前重点是“读能力验证”，建议先跑：

1. `Preflight 0`
2. `Phase 1`
3. `Phase 2`
4. `Phase 3`

这四步过了，再进入草稿和发送环节。
