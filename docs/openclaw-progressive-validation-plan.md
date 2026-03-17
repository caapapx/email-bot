# OpenClaw 渐进式开放测试方案（master 直更版）

日期：2026-03-17  
项目：`email-bot`

## 文档定位

这是一个面向通用智能体和人工初始化场景的长期维护型模板文档。  
它的职责是定义“初始化一个邮箱型智能体”时应该如何分阶段验证、沉淀和推进。

这个文档不应该混入某一次邮箱实例的实时证据、结论或推理。  
任何当前邮箱的阶段结果、价值判断、画像推断、工作流偏好，都应该写入独立的实例备注或结果文件。

## 价值验证原则

1. 每个阶段都要回答一个问题：用户今天能更快知道什么、少做什么、少漏什么。
2. 先证明只读价值，再进入草稿；先证明草稿价值，再进入发送。
3. `thread` 级理解优先于单封邮件标签化。
4. 通用模板保持稳定，实例化判断通过结果文件和固定链接承载。

## 实例化与结果约定

1. 运行时结论不要直接回写到本模板。
2. 当前邮箱实例的补充结论写入：`docs/validation/instance-calibration-notes.md`
3. 各阶段结构化结果写入：`runtime/validation/<phase>/`
4. 各阶段可读报告写入：`docs/validation/`
5. 智能体执行时，如果发现 `docs/validation/instance-calibration-notes.md` 存在，应先读取该文件，再决定本次初始化的优先策略

## 支持的初始化模式

本模板应同时适配以下 3 类初始化模式：

1. **智能体全自动执行**：智能体自行拉取邮件、分析、产出阶段文件
2. **对话驱动手工初始化**：用户逐阶段粘贴文本、截图、规则或材料，智能体据此推进
3. **混合初始化**：邮件自动拉取 + 用户手动补充工作材料、工作习惯、事实校正

这 3 类模式不应分叉成不同方案。  
它们都应收敛到同一套“标准化上下文输入 + 阶段化产出”结构。

## 人工补充上下文通道（跨阶段，可选但推荐）

目标：允许用户或智能体在邮件证据之外，补充对画像、流程、待办和风险判断真正有帮助的上下文，同时保持通用适配性。

### 允许接入的补充信息类型

1. **工作材料**：如 `xlsx/docx/pdf/md/txt`、截图、会议纪要、项目台账、排期表、周报模板、流程说明
2. **工作习惯与周期任务**：如“每周统计资源申请数据”“每月 5 号前总结上个月工作”
3. **组织/项目背景**：如角色说明、组织分工、项目别名、系统简称、常见联系人映射
4. **用户纠偏信息**：如“这个线程通常不是我负责”“这个发件人是机器人通知”“这类邮件必须看”
5. **人工确认事实**：如 owner、审批链、汇报节奏、SLA、对某类线程的优先级定义

### 读取与落盘规则

1. 如果存在可读取的本地材料，优先通过现有文档读取能力或 MCP 文档服务提取文本；拿不到结构化内容时，至少保留文件清单与用户摘要。
2. 所有人工补充信息都必须落入标准化文件，不允许只停留在对话里。
3. 外部材料与用户声明必须保留来源、时间、适用范围和新鲜度。
4. 邮件原始证据仍然是线程事实的基础；人工补充上下文用于增强解释、修正低置信推断、补足周期性任务与组织背景。
5. 人工补充信息可以提高置信度，但不能静默覆盖邮件原始记录；如发生冲突，必须在报告中显式标记。

### 标准化上下文产物

- `runtime/context/material-manifest.json`
- `runtime/context/material-extracts/`
- `runtime/context/manual-habits.yaml`
- `runtime/context/manual-facts.yaml`
- `runtime/context/context-pack.json`
- `docs/validation/context-brief.md`

### 标准证据标签

- `mail_evidence`
- `material_evidence`
- `user_declared_rule`
- `user_confirmed_fact`
- `agent_inference`

### 适用原则

1. `Phase 1` 可以忽略人工上下文，只做底层普查。
2. `Phase 2/3/4` 应优先吸收人工上下文，因为画像、流程、owner、节奏任务都可能依赖这些补充信息。
3. `Phase 5/6` 应显式记录哪些草稿风格、规则或待办判断来自人工声明，而不是来自邮件统计。

## 固定结果索引（本地链接）

- [实例校准备注](validation/instance-calibration-notes.md)
- [Context Brief](validation/context-brief.md)
- [Preflight 报告](validation/preflight-mailbox-smoke-report.md)
- [Phase 1 报告](validation/phase-1-report.md)
- [Phase 2 报告](validation/phase-2-report.md)
- [Phase 3 报告](validation/phase-3-report.md)
- [Phase 4 报告](validation/phase-4-report.md)
- [Preflight JSON](../runtime/validation/preflight/mailbox-smoke.json)
- [Phase 1 Census JSON](../runtime/validation/phase-1/mailbox-census.json)
- [Phase 2 Persona YAML](../runtime/validation/phase-2/persona-hypotheses.yaml)
- [Phase 3 Lifecycle YAML](../runtime/validation/phase-3/lifecycle-model.yaml)
- [Phase 3 Thread Samples JSON](../runtime/validation/phase-3/thread-stage-samples.json)
- [Phase 4 Daily Urgent YAML](../runtime/validation/phase-4/daily-urgent.yaml)
- [Phase 4 Pending Replies YAML](../runtime/validation/phase-4/pending-replies.yaml)
- [Phase 4 SLA Risks YAML](../runtime/validation/phase-4/sla-risks.yaml)
- [Phase 4 Weekly Brief](../runtime/validation/phase-4/weekly-brief.md)
- [Context Pack](../runtime/context/context-pack.json)
- [Manual Habits YAML](../runtime/context/manual-habits.yaml)
- [Manual Facts YAML](../runtime/context/manual-facts.yaml)
- [Phase 3 Lifecycle Overview (mermaid)](validation/diagrams/phase-3-lifecycle-overview.mmd)
- [Phase 3 Thread State Machine (mermaid)](validation/diagrams/phase-3-thread-state-machine.mmd)

## 固定执行约束

1. OpenClaw 仓库固定工作目录：`~/email-bot`（与 `~/.openclaw` 同级）
2. 只使用 `master` 分支开发，不创建阶段分支。
3. 每个阶段开始前都先 `git pull --ff-only origin master`，确保最新。
4. 每个阶段结束后直接提交到 `master`，提交信息带阶段号。
5. 前 3 个分析阶段必须只读：禁止 `send/move/delete/archive/flag`。

## 固定拉取命令

```bash
if [ ! -d ~/email-bot/.git ]; then
  git clone https://github.com/caapapx/email-bot.git ~/email-bot
fi
cd ~/email-bot
git checkout master
git pull --ff-only origin master
```

## 阶段通用前置提示（每次都贴）

```text
先执行仓库同步，不要开始功能开发：
1. 工作目录固定为 ~/email-bot
2. 如果目录不存在：git clone https://github.com/caapapx/email-bot.git ~/email-bot
3. 进入目录后切换 master：git checkout master
4. 拉取最新代码：git pull --ff-only origin master
5. 输出当前目录、当前分支、最近一次 pull 是否成功
6. 若 pull 失败，停止并报告错误，不要继续
7. 如果存在 `docs/validation/instance-calibration-notes.md`、`docs/validation/context-brief.md`、`runtime/context/context-pack.json` 或已有阶段输出，先读取它们，再决定本次初始化的优先顺序
8. 如果用户提供了本地工作材料、文本规则、截图或周期性任务说明，先把它们归档到标准化上下文文件，再进入当前阶段分析

后续所有改动都直接在 master 进行。
```

## 渐进式注意力预算（Progressive Attention Funnel）

目标：每个阶段在产出正向结论的同时，输出反向过滤结果，让下一阶段只关注值得关注的线程，从而系统性降低 token 开销和执行时长。

### 核心机制

每个阶段结束时，除了正向产物（报告、YAML、图表），还必须输出一份注意力预算文件：

- `runtime/validation/<phase>/attention-budget.yaml`

该文件记录三类线程集合：

1. `focus`：下一阶段必须关注的线程（高价值 / 高风险 / 待确认）
2. `deprioritize`：可降级处理的线程（低频 / 已归档 / 纯通知无需动作）
3. `skip`：可跳过的线程（已确认噪声 / bot 自动通知 / 重复 / 无关）

### 各阶段的注意力收敛逻辑

| 阶段 | 输入范围 | 正向产物 | 反向产物（注意力预算） |
|---|---|---|---|
| Phase 1 | 全量 envelope | 分布统计、intent 分类 | 标记 `noise_candidates`：纯机器通知、重复订阅、空线程 |
| Phase 2 | Phase 1 全量 - noise | 画像假设 | 输出 `exclusion_rules`：与画像无关的域名/发件人/intent 类型 |
| Phase 3 | Phase 2 存活集 | 生命周期模型 | 标记 `unmodeled`：无法归入任何流的线程，降低采样权重 |
| Phase 4 | Phase 3 归流线程 | urgent/pending/sla/brief | 标记 `low_signal`：归流但正文无可执行信号的线程 |
| Phase 5 | Phase 4 高置信线程 | 草稿候选 | 标记 `draft_excluded`：不适合草稿化的线程及原因 |

### 预算文件格式

```yaml
phase: "phase-N"
generated_at: "ISO timestamp"
input_thread_count: 74
output_budget:
  focus:
    count: 24
    thread_keys: [...]
    reason: "归流 + 高置信 + 有可执行信号"
  deprioritize:
    count: 30
    thread_keys: [...]
    reason: "归流但无即时动作需求"
  skip:
    count: 20
    thread_keys: [...]
    reason: "noise / bot / 重复 / 已归档"
token_saving_estimate: "跳过 skip 集后，下一阶段正文采样量减少约 40-60%"
```

### 约束

1. 注意力预算是建议性的，不是硬删除——被 skip 的线程仍保留在 raw 数据中，可随时回溯
2. 用户可以通过 `user_confirmed_fact` 把某条线程从 skip 拉回 focus（如"这个线程其实很重要"）
3. 每个阶段的报告必须包含一段"本阶段注意力收敛摘要"，说明输入了多少线程、输出了多少到 focus
4. 人工上下文通道的纠偏信息（如"这个发件人是 bot"）应直接更新注意力预算

## Preflight 0：邮箱登录与连通性冒烟测试（必须先过）

目标：先证明能连上邮箱并执行只读拉取，否则后续“读能力测试”无效。

通过标准：

1. `scripts/preflight_mailbox_smoke.sh` 可在 `--interactive` 或 `--headless` 模式执行
2. 脚本内部完成 `check_env + render_himalaya_config + himalaya` 只读拉取
3. 产出统一报告与 JSON 结果
4. 输出失败归因：配置/认证/网络/CLI 缺失

给 OpenClaw 的 prompt：

```text
先执行“阶段通用前置提示”里的仓库同步步骤，确认在 ~/email-bot 的 master 最新状态工作。

当前阶段：Preflight 0（邮箱冒烟测试）
硬性约束：
1. 只允许环境检查、配置渲染、只读拉取
2. 禁止发送、移动、删除、归档、标记邮件

执行步骤：
1. 阅读 README.md、SKILL.md、scripts/preflight_mailbox_smoke.sh
2. 如果是对话引导场景，先输出填写模板：
   bash scripts/preflight_mailbox_smoke.sh --chat-template
3. 如果可以在终端交互填写，运行：
   bash scripts/preflight_mailbox_smoke.sh --interactive
4. 如果是后台命令行（CI/无人值守）运行：
   bash scripts/preflight_mailbox_smoke.sh --headless
5. 脚本会自动做：
   - 环境字段检查
   - Himalaya 配置渲染
   - 只读 envelope list 冒烟
6. 生成：
   - docs/validation/preflight-mailbox-smoke-report.md
   - runtime/validation/preflight/mailbox-smoke.json
   - runtime/validation/preflight/mailbox-smoke.stderr.log
7. 报告结论：是否允许进入 Phase 1；失败时明确失败层级

完成后直接提交到 master：
git add .
git commit -m "preflight: mailbox smoke test"
git push origin master
```

## Phase 1：邮件分布普查（只读）

目标：验证“读大量邮件并给出整体分布”的能力。

给 OpenClaw 的 prompt：

```text
先执行“阶段通用前置提示”里的仓库同步步骤，确认在 ~/email-bot 的 master 最新状态工作。

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
   - runtime/validation/phase-1/attention-budget.yaml
   - docs/validation/phase-1-report.md
   - docs/validation/diagrams/phase-1-mailbox-overview.mmd
   - docs/validation/diagrams/phase-1-sender-network.mmd
4. 报告中区分：事实 / 高置信推断 / 待确认假设
5. 注意力预算（反向产物）：
   - 标记 noise_candidates：纯机器通知、重复订阅、空线程、无正文价值的系统邮件
   - 输出 attention-budget.yaml，包含 focus / deprioritize / skip 三类线程集合
   - 报告末尾附"注意力收敛摘要"：输入 N 封 → focus M 条线程 → 预计下阶段 token 节省比例

完成后直接提交到 master：
git add .
git commit -m "phase1: mailbox distribution census"
git push origin master
```

## Phase 2：用户画像与公司业务画像（只读）

目标：从邮件分布和样本推断“你是谁、公司在做什么”。

给 OpenClaw 的 prompt：

```text
先执行“阶段通用前置提示”里的仓库同步步骤，确认在 ~/email-bot 的 master 最新状态工作。

当前阶段：Phase 2（画像推断）
硬性约束：
1. 只读，不允许修改邮箱状态
2. 每条结论必须给证据
3. 低置信结论必须标记为待确认

任务：
1. 输出用户画像候选：角色、职责、决策参与、沟通对象、节奏压力、表达风格
2. 输出公司业务画像候选：业务活动、上下游对象、关键流程、邮件依赖点、AI 切入点
3. 如果存在 `runtime/context/context-pack.json`，将其作为补充证据使用，但必须在报告中区分：
   - 邮件证据
   - 外部材料证据
   - 用户声明/确认
4. 产出文件：
   - docs/validation/phase-2-report.md
   - runtime/validation/phase-2/persona-hypotheses.yaml
   - runtime/validation/phase-2/business-hypotheses.yaml
   - runtime/validation/phase-2/attention-budget.yaml
   - docs/validation/diagrams/phase-2-relationship-map.mmd
5. 最后给最多 7 个”最小确认问题”
6. 如果人工上下文里存在明确的周期性职责、固定汇报任务或术语映射，把它们单列为”外部补充上下文”，不要伪装成仅由邮件推断得到
7. 注意力预算（反向产物）：
   - 读取 Phase 1 的 attention-budget.yaml，在其 focus 集合基础上工作
   - 基于画像结论输出 exclusion_rules：与用户角色明显无关的域名、发件人、intent 类型
   - 更新 attention-budget.yaml，进一步收窄 focus 集合
   - 报告末尾附”注意力收敛摘要”

完成后直接提交到 master：
git add .
git commit -m "phase2: persona and business profile inference"
git push origin master
```

## Phase 3：生命周期建模与图示更新（只读）

目标：把邮件从“分类结果”升级为 `thread` 级生命周期状态机，并基于当前邮箱证据选出最值得建模的流程。

给 OpenClaw 的 prompt：

```text
先执行“阶段通用前置提示”里的仓库同步步骤，确认在 ~/email-bot 的 master 最新状态工作。

当前阶段：Phase 3（生命周期建模）
硬性约束：
1. 只读，不允许修改邮箱状态
2. 不能只列标签，必须做 thread 级阶段模型
3. 无法高置信建模的流程必须明确说明

任务：
1. 基于当前邮箱的 `Phase 1/2` 结果和实例备注，归纳至少 3 条主要生命周期流
2. 不要预设业务类型；应从证据中推导。可选示例包括：
   - 内部协同 / 审批 / 项目推进
   - 支持 / 工单 / 问题处理
   - 招聘 / 财务 / 商务 / 合作 / 外部跟进
3. 每条流至少定义 5 个阶段，并包含：
   - 阶段进入信号
   - 阶段退出信号
   - owner_guess / waiting_on / due_hint
   - 高风险信号
   - 推荐 AI 动作（仅 summarize/classify/remind/draft）
4. 如果存在人工补充上下文，可用于：
   - 校正 owner_guess
   - 注入周期性任务与固定截止习惯
   - 解释项目简称、流程别名、部门内隐规则
   但必须保留来源标签，不能把人工规则写成“纯邮件推断”
5. 产出文件：
   - runtime/validation/phase-3/lifecycle-model.yaml
   - runtime/validation/phase-3/thread-stage-samples.json
   - runtime/validation/phase-3/attention-budget.yaml
   - docs/validation/phase-3-report.md
   - docs/validation/diagrams/phase-3-lifecycle-overview.mmd
   - docs/validation/diagrams/phase-3-thread-state-machine.mmd
6. 指出哪 2 条线程流最值得直接进入 `Phase 4` 的用户可见输出，并说明原因
7. 给出 policy/profile/context 的 5 条建议（先写建议，不直接改配置）
8. 注意力预算（反向产物）：
   - 读取 Phase 2 的 attention-budget.yaml，在其 focus 集合基础上工作
   - 标记 unmodeled：无法归入任何生命周期流的线程，降低后续正文采样权重
   - 更新 attention-budget.yaml：归流线程进 focus，未归流线程进 deprioritize
   - Phase 4 只对 focus 集合做正文采样，skip 集合不消耗 token
   - 报告末尾附"注意力收敛摘要"

完成后直接提交到 master：
git add .
git commit -m "phase3: lifecycle modeling and diagrams"
git push origin master
```

## Phase 4：日报/周报价值输出（只读）

目标：验证用户能否在不读长报告的情况下，快速知道“今天该跟进什么”。

通过标准：

1. 用户应能在 3 分钟内理解当天最需要关注的线程
2. 每条输出都要带 evidence / confidence
3. 如果结果不够有用，必须回退继续优化 `Phase 3`，而不是直接进入 `Phase 5`

给 OpenClaw 的 prompt：

```text
先执行“阶段通用前置提示”里的仓库同步步骤，确认在 ~/email-bot 的 master 最新状态工作。

当前阶段：Phase 4（只读价值输出）
硬性约束：
1. 只读，不写发送动作
2. 输出必须短、准、可执行
3. 每条结论要可追溯

任务：
1. 生成：
   - 今日必须跟进线程
   - 待我拍板 / 待我回复线程
   - 已阻塞或 SLA 风险线程
   - 本周项目节奏摘要
2. 文件：
   - docs/validation/phase-4-report.md
   - runtime/validation/phase-4/daily-urgent.yaml
   - runtime/validation/phase-4/pending-replies.yaml
   - runtime/validation/phase-4/sla-risks.yaml
   - runtime/validation/phase-4/weekly-brief.md
   - runtime/validation/phase-4/attention-budget.yaml
3. 每条输出至少包含：
   - thread id 或 thread key
   - 为什么进入该列表
   - 证据定位
   - confidence
4. 如果存在人工习惯或周期任务（如”每周统计””每月固定总结”），可以进入对应输出，但必须额外标记其来源不是即时邮件，而是 `user_declared_rule` 或 `material_evidence`
5. 报告最后必须回答：这些输出是否已经足够让用户”愿意每天看一次”
6. 注意力预算（反向产物）：
   - 读取 Phase 3 的 attention-budget.yaml，只对 focus 集合做正文采样
   - 标记 low_signal：归流但正文无可执行信号的线程
   - 更新 attention-budget.yaml：高置信可执行线程进 focus，低信号线程进 deprioritize
   - Phase 5 草稿候选只从 Phase 4 focus 集合中选取
   - 报告末尾附”注意力收敛摘要”，包含 token 节省估算

完成后直接提交到 master：
git add .
git commit -m "phase4: daily and weekly read-only outputs"
git push origin master
```

## Phase 5：本地草稿生成（不发送）

目标：验证当前邮箱中最有价值的线程草稿，是否真的降低人工编辑负担，而不是单纯证明“能生成草稿”。

给 OpenClaw 的 prompt：

```text
先执行“阶段通用前置提示”里的仓库同步步骤，确认在 ~/email-bot 的 master 最新状态工作。

当前阶段：Phase 5（草稿不发送）
硬性约束：
1. 只允许写本地草稿到 runtime/drafts/
2. 禁止发送
3. 外部/法务/财务/附件场景默认 review_required=true
4. 优先选择 `Phase 4` 中高频、高价值、可解释的线程，不要为展示能力而扩大范围

任务：
1. 从 `Phase 4` 输出中选取最值得草稿化的线程样本
2. 如果存在人工补充上下文，可用来约束草稿目标、口径和汇报结构，但必须区分“邮件上下文”与“外部任务/习惯”
3. 产出：
   - runtime/validation/phase-5/draft-candidates.yaml
   - runtime/validation/phase-5/attention-budget.yaml
   - docs/validation/phase-5-report.md
   - runtime/drafts/<thread_id>.eml
4. 报告必须记录：
   - 原始上下文
   - AI 草稿
   - 人工修改点
   - 是否真的减少编辑负担
5. 注意力预算（反向产物）：
   - 读取 Phase 4 的 attention-budget.yaml，草稿候选只从 focus 集合中选取
   - 标记 draft_excluded：不适合草稿化的线程及排除原因（如风险过高、上下文不足、需人工判断）
   - 更新 attention-budget.yaml：成功草稿化的线程进 focus，排除的线程进 deprioritize 并记录原因
   - Phase 6 学习闭环只从已草稿化且有人工修改的线程中提取规则
   - 报告末尾附"注意力收敛摘要"

完成后直接提交到 master：
git add .
git commit -m "phase5: local draft generation without send"
git push origin master
```

## Phase 6：学习闭环（!learn / !rule / !edit）

目标：把已被证明有价值的人工修订稳定沉淀成规则，而不是学习所有编辑习惯。

给 OpenClaw 的 prompt：

```text
先执行“阶段通用前置提示”里的仓库同步步骤，确认在 ~/email-bot 的 master 最新状态工作。

当前阶段：Phase 6（学习闭环）
硬性约束：
1. 一次只提一条新规则
2. 必须有“草稿 vs 人工修改”证据
3. 先提议，确认后再落盘
4. 只学习已验证对当前高价值场景有帮助的规则

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

目标：仅在前面阶段已经证明有价值的前提下，再验证显式 `CONFIRM_SEND` 的发送守护。

给 OpenClaw 的 prompt：

```text
先执行“阶段通用前置提示”里的仓库同步步骤，确认在 ~/email-bot 的 master 最新状态工作。

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

如果当前重点是“尽快确认真实价值”，建议先跑：

1. `Preflight 0`
2. `Phase 1`
3. `Phase 2`
4. `Phase 3`
5. `Phase 4`

只有当 `Phase 4` 已经能稳定产出“今天该做什么”的可用结果，再进入草稿和发送环节。
