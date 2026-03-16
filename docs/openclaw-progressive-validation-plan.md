# OpenClaw 渐进式开放测试方案

日期：2026-03-16
适用项目：`email-bot`
目标：让 OpenClaw 以“先读懂，再归纳，再建模，再起草，再学习”的顺序逐步验证本项目，而不是一上来就碰发送链路。

## 设计原则

1. 先验证“读和理解”，再验证“动作和自动化”。
2. 先验证仓库同步和邮箱登录，再进入读能力测试。
3. 前 3 个分析阶段全部只读，不允许发送、移动、删除、归档、标记邮件。
4. 每个阶段都要求 OpenClaw 产出可落盘的文档、结构化数据和图示，而不是只在对话里口头总结。
5. 每个阶段都要求 OpenClaw 明确“证据、假设、置信度、未知项”，避免它把主观猜测伪装成事实。
6. 每个阶段都必须给出“下一阶段是否可以继续”的判断。

## 半自动执行循环

这套流程的目标不是让 OpenClaw 在一个脏工作区里反复改，而是形成稳定的“同步 -> 开发 -> PR -> 审阅 -> 合并”循环。

每一阶段都遵循同一个节奏：

1. 在 OpenClaw 默认工作位置先获取最新仓库。
2. 如果仓库不存在就 `git clone`，存在就 `git pull --ff-only`。
3. 基于最新默认分支创建阶段分支，例如 `openclaw/phase-1-mailbox-census`。
4. 执行该阶段 prompt，所有输出落到仓库内约定目录。
5. 自检改动范围，只提交该阶段相关文件。
6. 推送分支并创建 PR，等待人工审阅。
7. 你审阅、合并后，再开始下一阶段。

这样做的原因：

- OpenClaw 每次都从最新仓库状态开始，避免上下文漂移
- 你能按阶段审阅，避免一次性混进太多实验性改动
- 每个阶段都有独立 PR，便于回滚和比较

## 阶段通用前置提示

下面这段提示，建议你在每个阶段 prompt 最开头都加上。

```text
在开始当前阶段之前，先确保工作区是最新代码，并在 OpenClaw 默认位置工作：

1. 如果当前默认工作位置还没有仓库，就从 https://github.com/caapapx/email-bot.git clone 最新代码。
2. 如果仓库已经存在，先执行 git pull --ff-only，确保和 GitHub 保持一致。
3. 不要在旧快照、旧副本、临时目录里继续工作。
4. 基于最新默认分支新建当前阶段分支，分支名使用 openclaw/<phase>-<short-topic>。
5. 当前阶段完成后，自检改动，只提交与本阶段相关的文件。
6. 推送分支并创建 PR，供人工审阅；未合并前不要开始下一阶段。

如果无法拉取、无法推送或无法创建 PR，要先明确报错并停止，不要假装已经同步成功。
```

## 目录约定

- 原始与中间数据：`runtime/validation/<phase>/`
- 报告：`docs/validation/<phase>-report.md`
- 图示：`docs/validation/diagrams/*.mmd`
- 结构化摘要：`runtime/validation/<phase>/*.json` 或 `*.yaml`

## 总体阶段

### Preflight A：仓库同步与阶段分支准备

目标：

- 确保 OpenClaw 工作在最新仓库快照上
- 固化“每阶段一个分支、每阶段一个 PR”的节奏
- 避免它在过期副本或错误目录里工作

通过标准：

- 成功定位 GitHub 仓库并拉取最新代码
- 成功新建当前阶段分支
- 输出当前分支、基线分支、工作目录和后续提交流程

建议你粘给 OpenClaw 的 prompt：

```text
你现在开始一个新的验证阶段。第一步不是写代码，而是同步仓库并准备阶段分支。

请严格执行：
1. 在 OpenClaw 默认工作位置检查是否已有 https://github.com/caapapx/email-bot.git。
2. 如果没有，就 clone。
3. 如果有，就进入仓库并执行 git pull --ff-only，保证与 GitHub 最新状态一致。
4. 基于默认分支创建当前阶段分支，命名为 openclaw/<phase>-<short-topic>。
5. 输出：
   - 当前工作目录
   - 当前默认分支
   - 当前阶段分支
   - 最近一次拉取是否成功
   - 当前工作树是否干净
6. 如果拉取失败、分支创建失败、或工作树不干净且会影响当前阶段，必须先报告并停止。

不要开始任何功能实现，直到仓库同步和分支准备完成。
```

### Preflight B：邮箱登录与连通性冒烟测试

目标：

- 验证 Himalaya 配置是否可用
- 验证 OpenClaw 是否具备最基础的邮箱读取入口
- 在不修改邮箱状态的前提下，先排除账号、配置、认证、网络层问题

通过标准：

- 环境检查通过
- Himalaya 配置渲染通过
- 至少完成一次只读登录或信封列表读取
- 明确记录失败点是配置、认证、网络还是 CLI 缺失

建议你粘给 OpenClaw 的 prompt：

```text
你现在执行邮箱登录与连通性冒烟测试。这个阶段比读能力测试更靠前，因为如果邮箱根本不能连通，后续分析都没有意义。

硬性约束：
1. 只允许做环境检查、配置渲染、登录验证和只读读取。
2. 严禁发送、移动、删除、归档、标记邮件。
3. 如果缺少 himalaya、配置文件、环境变量或认证信息，必须明确报告，不要跳过。

请按顺序完成：
1. 检查仓库里的 README.md、SKILL.md、scripts/check_env.sh、scripts/render_himalaya_config.sh，确认登录前置条件。
2. 执行环境检查脚本。
3. 渲染 runtime/himalaya/config.toml。
4. 验证 himalaya 是否已安装、是否能识别 account。
5. 进行一次最小只读验证，优先选择：
   - himalaya --account <account> envelope list --folder INBOX --page 1 --page-size 5 --output json
   如果该命令不可用，再退而求其次执行你能确认是只读的最小列表命令。
6. 产出：
   - docs/validation/preflight-mailbox-smoke-report.md
   - runtime/validation/preflight/mailbox-smoke.json
7. 报告中必须明确：
   - CLI 是否可用
   - 配置是否可用
   - 认证是否通过
   - 只读读取是否成功
   - 如果失败，失败点属于哪一层

采用对话式推进：
- 先列出你的测试顺序。
- 再执行验证并落盘结果。
- 最后给出“是否允许进入 Phase 0”的明确结论。
```

### Phase 0：护栏与验证工位初始化

目标：

- 让 OpenClaw 先读懂当前仓库约束
- 建立只读验证路径
- 确保后续分析统一落到固定目录

通过标准：

- 明确声明不会执行 `send / move / delete / archive / flag`
- 创建验证目录和阶段索引文档
- 输出一份当前能力与限制清单

建议你粘给 OpenClaw 的 prompt：

```text
在开始当前阶段之前，先执行仓库同步流程：确保在 OpenClaw 默认工作位置拉取到 https://github.com/caapapx/email-bot.git 的最新代码，并基于最新默认分支创建当前阶段分支；本阶段完成后推送分支并创建 PR，等待人工审阅。

你现在在项目 /home/caapap/iflytek/ltc-plan/email-bot 中工作。

目标：为这个项目建立“渐进式开放测试”的基础工位，当前阶段只做初始化，不做任何可能修改邮箱状态的操作。

硬性约束：
1. 严禁发送、移动、删除、归档、标记任何邮件。
2. 只允许使用 read/list/export 这类只读能力。
3. 不要假设已有验证目录；如果没有就创建。
4. 所有原始数据和中间结果只能写到 runtime/validation/ 下。
5. 所有报告和图示只能写到 docs/validation/ 下。

先读这些文件并总结约束：
- README.md
- SKILL.md
- config/policy.default.yaml
- docs/architecture.md

然后执行这些任务：
1. 创建验证目录结构和总索引文档。
2. 写一份 docs/validation/README.md，说明每个阶段的目标、输入、输出、禁止动作。
3. 写一份 docs/validation/phase-0-report.md，总结当前项目的邮件代理能力、只读能力、动作边界、安全约束、已知缺口。
4. 如果需要脚本，只能创建只读验证脚本，放在 scripts/validation/ 下。
5. 最后汇报：你创建了哪些文件、下一阶段应该验证什么、目前有哪些风险。

采用对话式推进：
- 先用 5-10 行说明你的执行计划。
- 然后实际创建文件并落盘。
- 最后给出简明结论，不要只讲概念。
```

### Phase 1：邮件分布普查与阅读能力验证

目标：

- 看 OpenClaw 能否从大量邮件中读出“分布”
- 不是挑几封典型邮件，而是给出整体画像
- 重点验证它能否把邮箱看成一个动态语料库，而不是单封邮件问答

要验证的能力：

- 发件人域名分布
- 内外部邮件比例
- 时间分布
- 主题聚类
- 意图分类候选集
- 附件、会议、财务、招聘、客户沟通等比例
- 高价值联系人与高频线程

通过标准：

- 输出一份 corpus census 报告
- 输出至少 3 份结构化统计文件
- 输出至少 2 个 Mermaid 图
- 所有结论都附带证据和样本范围

建议你粘给 OpenClaw 的 prompt：

```text
在开始当前阶段之前，先执行仓库同步流程：确保在 OpenClaw 默认工作位置拉取到 https://github.com/caapapx/email-bot.git 的最新代码，并基于最新默认分支创建当前阶段分支；本阶段完成后推送分支并创建 PR，等待人工审阅。

你现在进入 Phase 1。目标不是写回复，也不是自动化动作，而是验证你是否真的“读懂我的邮箱分布”。

硬性约束：
1. 只能读取邮件，不能发送、移动、删除、归档、标记。
2. 先从较小样本开始，再决定是否扩大样本。
3. 所有原始邮件内容只能留在 runtime/validation/phase-1/ 下。
4. 写入 docs 的报告必须做适度脱敏，不能直接暴露完整敏感正文。
5. 如果你的结论没有足够证据，必须明确标注为“假设”。

请基于当前项目架构，自主完成以下任务：
1. 设计一个“邮箱普查”流程，优先读取 envelope 列表，再按需要抽样读取正文。
2. 统计并输出：
   - 发件人域名 Top N
   - 联系人/组织 Top N
   - 主题关键词 Top N
   - 时间分布（日/周）
   - 内部 vs 外部邮件占比
   - newsletter / human / finance / recruiting / scheduling / support / internal_update 等意图候选分布
   - 附件邮件占比
   - 长线程 / 高频往来线程
3. 生成以下文件：
   - runtime/validation/phase-1/mailbox-census.json
   - runtime/validation/phase-1/intent-distribution.yaml
   - runtime/validation/phase-1/contact-distribution.json
   - docs/validation/phase-1-report.md
   - docs/validation/diagrams/phase-1-mailbox-overview.mmd
   - docs/validation/diagrams/phase-1-sender-network.mmd
4. 在报告里区分：
   - 已证实事实
   - 高置信推断
   - 低置信待确认项
5. 报告最后必须回答：
   - 这个邮箱最像什么类型的工作流？
   - 用户主要把时间花在哪几类邮件上？
   - 哪些类别最适合成为 Day-1 的 AI 价值切入口？

采用对话式推进：
- 先写出你的采样策略和统计方案。
- 再执行并落盘结果。
- 最后给出最重要的 10 条发现和 5 个待确认问题。
```

### Phase 2：用户画像与公司业务画像推断

目标：

- 看 OpenClaw 能否从邮箱整体沟通模式中识别“我是谁、公司在做什么、对外关系如何运转”
- 重点不是精确命名岗位，而是抽出角色、业务链条、沟通职责和优先级机制

要验证的能力：

- 用户画像推断
- 公司业务类型推断
- 业务对象与关系网推断
- 沟通风格和决策模式推断
- 风险/机会点识别

通过标准：

- 每条画像判断必须有证据链
- 至少给出 2 个竞争性假设，而不是单一路径
- 明确列出需要用户确认的问题

建议你粘给 OpenClaw 的 prompt：

```text
在开始当前阶段之前，先执行仓库同步流程：确保在 OpenClaw 默认工作位置拉取到 https://github.com/caapapx/email-bot.git 的最新代码，并基于最新默认分支创建当前阶段分支；本阶段完成后推送分支并创建 PR，等待人工审阅。

你现在进入 Phase 2。基于 Phase 1 的邮件分布结果，推断“用户画像”和“公司业务画像”。

硬性约束：
1. 仍然只读，不允许执行任何会修改邮箱状态的动作。
2. 不允许把主观猜测直接写成事实。
3. 每条核心判断都必须给出证据来源，至少来自以下之一：
   - 发件人/组织分布
   - 邮件主题模式
   - 时间与频率模式
   - 抽样正文中的任务、业务、决策语气
4. 任何低于中等置信度的结论，必须列成“待用户确认假设”。

请完成以下任务：
1. 写出用户画像报告，至少包括：
   - 角色候选
   - 对外职责
   - 决策参与程度
   - 常见沟通对象
   - 工作节奏和响应压力
   - 偏好的表达风格线索
2. 写出公司业务画像报告，至少包括：
   - 公司主要业务活动候选
   - 上下游对象类型
   - 关键业务流程候选
   - 哪些业务流程最依赖邮件
   - 哪些流程最适合先被 AI 辅助
3. 产出文件：
   - docs/validation/phase-2-report.md
   - runtime/validation/phase-2/persona-hypotheses.yaml
   - runtime/validation/phase-2/business-hypotheses.yaml
   - docs/validation/diagrams/phase-2-relationship-map.mmd
4. 报告中必须包含：
   - 结论
   - 证据
   - 反证或替代解释
   - 置信度
   - 待确认问题
5. 最后整理出一组最小确认问题，最多 7 个，优先问最能改变后续策略的问题。

采用对话式推进：
- 先展示你打算如何从邮件分布走到画像推断。
- 再执行分析并落盘。
- 最后给出“如果用户只回答 3 个问题，应该回答哪 3 个”的清单。
```

### Phase 3：分类体系、生命周期跟踪与图示更新

目标：

- 验证 OpenClaw 能否把离散邮件组织成“业务生命周期”
- 这是从“分类”升级到“过程理解”
- 重点看它能不能将 thread 变成状态机，而不是只做标签堆叠

要验证的能力：

- 线程归并
- 生命周期阶段定义
- 阶段跳转条件
- 风险点识别
- 图示生成与持续更新

建议优先覆盖的生命周期：

- 对外商务/销售
- 招聘
- 合作推进
- 财务回执/付款
- 内部同步与决策

通过标准：

- 至少形成 3 条主要生命周期流
- 每条流至少定义 5 个阶段
- 每条阶段图都有入口条件、退出条件、风险信号

建议你粘给 OpenClaw 的 prompt：

```text
在开始当前阶段之前，先执行仓库同步流程：确保在 OpenClaw 默认工作位置拉取到 https://github.com/caapapx/email-bot.git 的最新代码，并基于最新默认分支创建当前阶段分支；本阶段完成后推送分支并创建 PR，等待人工审阅。

你现在进入 Phase 3。目标是把邮箱从“静态分类集合”提升为“动态生命周期系统”。

硬性约束：
1. 仍然只读。
2. 你不能只输出标签列表，必须输出 thread 级别的阶段模型。
3. 你不能强行套固定模板；应先从实际邮件语料中归纳，再映射到可复用结构。
4. 如果某些生命周期无法高置信建立，必须明确说明原因。

请完成以下任务：
1. 基于已有统计和抽样阅读结果，归纳至少 3 条主要邮件生命周期流。
2. 对每条生命周期流定义：
   - 名称
   - 适用线程类型
   - 阶段列表
   - 阶段进入信号
   - 阶段退出信号
   - 高风险信号
   - 推荐 AI 动作（仅限 summarize / classify / remind / draft，不包含 send）
3. 生成以下文件：
   - runtime/validation/phase-3/lifecycle-model.yaml
   - runtime/validation/phase-3/thread-stage-samples.json
   - docs/validation/phase-3-report.md
   - docs/validation/diagrams/phase-3-lifecycle-overview.mmd
   - docs/validation/diagrams/phase-3-thread-state-machine.mmd
4. 在报告中回答：
   - 哪些生命周期最频繁？
   - 哪些生命周期最消耗用户精力？
   - 哪些阶段最适合先做提醒、先做摘要、先做草稿？
5. 最后提出对 policy.default.yaml 和 profile 规则最值得新增的 5 条建议，但先不要直接改代码，先写成建议列表。

采用对话式推进：
- 先给出你观察到的线程模式。
- 再归纳生命周期并落盘。
- 最后给出“哪些地方仍然需要人工定义”的边界说明。
```

### Phase 4：只读智能摘要与日报周报验证

目标：

- 在不碰草稿和发送的前提下，验证 OpenClaw 能否把复杂邮箱压缩成用户真正会看的输出
- 这是“价值感知”测试，不是“准确率论文测试”

要验证的能力：

- 今日紧急清单
- 等待我回复清单
- SLA 风险清单
- 周报摘要
- 关系变化提醒

通过标准：

- 输出内容短、准、可执行
- 用户能在 3 分钟内看完
- 报告必须能追溯到来源线程

建议你粘给 OpenClaw 的 prompt：

```text
在开始当前阶段之前，先执行仓库同步流程：确保在 OpenClaw 默认工作位置拉取到 https://github.com/caapapx/email-bot.git 的最新代码，并基于最新默认分支创建当前阶段分支；本阶段完成后推送分支并创建 PR，等待人工审阅。

你现在进入 Phase 4。目标是验证这个项目最先能让用户感知到的价值输出，而不是做复杂自动化。

硬性约束：
1. 只读，不发送，不写草稿邮件。
2. 输出必须面向最终用户，而不是面向开发者。
3. 每条结论必须可追溯到线程或统计来源。

请完成以下任务：
1. 设计并生成 4 类只读输出：
   - 今日紧急清单
   - 今日等待我回复清单
   - SLA 风险清单
   - 本周摘要
2. 每类输出都要说明：
   - 选择标准
   - 置信度
   - 为什么对用户有价值
3. 生成文件：
   - docs/validation/phase-4-report.md
   - runtime/validation/phase-4/daily-urgent.yaml
   - runtime/validation/phase-4/pending-replies.yaml
   - runtime/validation/phase-4/sla-risks.yaml
   - runtime/validation/phase-4/weekly-brief.md
4. 在报告最后评估：
   - 哪 3 类输出最可能成为 Day-1 价值时刻？
   - 哪些输出目前信息不足，不应过度承诺？

采用对话式推进：
- 先写你的筛选规则。
- 再生成输出样例并落盘。
- 最后按“最值得上线 / 暂缓上线”给出建议。
```

### Phase 5：草稿建议但不发送

目标：

- 从“读懂”过渡到“起草”
- 仍然不碰真实发送，只验证本地草稿质量和人工复核负担

通过标准：

- 草稿全部落到本地 `runtime/drafts/`
- 对每份草稿说明为什么值得起草
- 明确哪些草稿必须人工重写

建议你粘给 OpenClaw 的 prompt：

```text
在开始当前阶段之前，先执行仓库同步流程：确保在 OpenClaw 默认工作位置拉取到 https://github.com/caapapx/email-bot.git 的最新代码，并基于最新默认分支创建当前阶段分支；本阶段完成后推送分支并创建 PR，等待人工审阅。

你现在进入 Phase 5。允许生成本地草稿，但仍然禁止发送。

硬性约束：
1. 只能生成本地草稿，不能发送。
2. 所有草稿必须保存到 runtime/drafts/。
3. 所有外部、高风险、法务、财务、附件相关回复默认标记为 review_required=true。
4. 必须复用本项目已有 SKILL.md 和 policy.default.yaml 的动作与约束。

请完成以下任务：
1. 从 Phase 4 的输出中选出最值得起草的线程。
2. 生成候选草稿，并为每份草稿输出：
   - thread_id
   - 起草原因
   - 风险等级
   - 是否建议人工重写
3. 生成文件：
   - runtime/validation/phase-5/draft-candidates.yaml
   - docs/validation/phase-5-report.md
   - runtime/drafts/<thread_id>.eml
4. 不要实现发送，只验证：
   - 草稿是否够快
   - 草稿是否够像用户
   - 草稿是否能明显减轻编辑负担

采用对话式推进：
- 先说明你选择哪些线程起草、为什么。
- 再落地草稿。
- 最后评估“哪些草稿真的帮到了用户，哪些只是看起来聪明”。
```

### Phase 6：学习闭环与规则沉淀

目标：

- 验证 `!learn / !rule / !edit` 机制是否真的能从人工修订中抽象出稳定规则

通过标准：

- 一次只提议一条规则
- 规则具体、可执行、可复用
- 规则能落到 profile 文件而不是停留在口头描述

建议你粘给 OpenClaw 的 prompt：

```text
在开始当前阶段之前，先执行仓库同步流程：确保在 OpenClaw 默认工作位置拉取到 https://github.com/caapapx/email-bot.git 的最新代码，并基于最新默认分支创建当前阶段分支；本阶段完成后推送分支并创建 PR，等待人工审阅。

你现在进入 Phase 6。目标是验证学习闭环，而不是追求“自动变聪明”的幻觉。

硬性约束：
1. 一次只允许提出一条新规则。
2. 规则必须来源于“AI 草稿 vs 用户修改”的明确差异。
3. 没有充分证据时，不要提议抽象空话规则。
4. 先提议，等确认，再写入 profile 规则文件。

请完成以下任务：
1. 对比若干草稿与人工修改版。
2. 推断修改背后的稳定偏好。
3. 输出：
   - 候选规则
   - 证据样本
   - 适用范围
   - 可能副作用
4. 生成文件：
   - docs/validation/phase-6-report.md
   - runtime/validation/phase-6/learned-rule-candidates.yaml
5. 如果规则被确认，再把它追加到 config/profiles/rules/<profile>.md。

采用对话式推进：
- 先展示差异和你的解释。
- 再给出单条规则提议。
- 最后等待确认，不要擅自落盘。
```

### Phase 7：受控发送演练

目标：

- 最后才碰发送
- 核心不是把邮件发出去，而是验证 `CONFIRM_SEND` 和审计边界

通过标准：

- 没有确认令牌就绝不发送
- 审计记录完整
- 发送动作与草稿、线程、确认记录可以对应

建议你粘给 OpenClaw 的 prompt：

```text
在开始当前阶段之前，先执行仓库同步流程：确保在 OpenClaw 默认工作位置拉取到 https://github.com/caapapx/email-bot.git 的最新代码，并基于最新默认分支创建当前阶段分支；本阶段完成后推送分支并创建 PR，等待人工审阅。

你现在进入 Phase 7。只有在明确看到 CONFIRM_SEND 时，才允许调用发送动作。

硬性约束：
1. 如果没有明确的 CONFIRM_SEND，禁止发送。
2. 发送前必须再次汇报：
   - 将发送哪封草稿
   - 发给谁
   - 风险等级
   - 为什么认为满足发送条件
3. 必须记录审计信息。

请完成以下任务：
1. 检查本地草稿与确认令牌。
2. 如果条件不足，明确拒绝发送并说明缺什么。
3. 如果条件满足，执行一次受控发送演练，并记录审计日志。
4. 生成文件：
   - docs/validation/phase-7-report.md
   - runtime/validation/phase-7/send-audit.json

采用对话式推进：
- 先复述发送前条件。
- 再检查是否满足。
- 只有明确满足后才执行。
```

## 建议的初始化测试重点

如果你现在只想验证“读的能力”，建议至少先跑完 `Preflight A`、`Preflight B`，再只跑到 `Phase 3`，不要急着进入草稿和发送。

最有价值的顺序是：

1. `Preflight A` 仓库同步与分支准备
2. `Preflight B` 邮箱登录与连通性冒烟测试
3. `Phase 0` 建工位和护栏
4. `Phase 1` 看它能否读出邮箱整体分布
5. `Phase 2` 看它能否推断你的角色与公司业务画像
6. `Phase 3` 看它能否把离散邮件组织成生命周期和图示

这样做的原因：

- 这三个阶段最能暴露 OpenClaw 是否真的理解语料，而不是只会调用 CLI
- 如果仓库同步或邮箱登录都不稳定，后续任何“读懂邮件”的结论都不可靠
- 如果这三阶段做不好，后面的 draft/send 都只是把误解自动化
- 一旦画像、生命周期和图示做出来，后续 policy/profile 优化会快很多

## 我建议你优先盯的 6 个验收问题

1. 它能不能给出“整体分布”，而不是只挑典型案例讲故事？
2. 它能不能区分事实、推断和猜测？
3. 它能不能识别出你真正高价值的业务线程？
4. 它能不能把 thread 组织成生命周期，而不是平铺分类标签？
5. 它生成的图示是不是能随着新增样本稳定更新？
6. 它提出的策略建议是不是能直接映射到 `policy.default.yaml` 或 profile 规则？

## 哪些部分建议先让 OpenClaw 自主做，哪些部分建议直接让我写

适合先让 OpenClaw 自主做：

- 目录初始化
- 报告模板
- 邮箱普查与统计
- 画像推断报告
- Mermaid 图示草稿
- policy/profile 建议列表

更适合让我直接写的“难点代码”：

- 线程级生命周期推断脚本
- 邮件语料标准化与去重脚本
- Mermaid 自动更新脚本
- “AI 草稿 vs 用户修改版”差异学习脚本
- 评估指标计算脚本，例如 `estimated_minutes_saved`

如果你愿意，我下一步可以直接给你两样东西：

1. 一版“只针对 Phase 0-3 的超精炼 prompt 套装”，适合你一段段粘给 OpenClaw。
2. 一版我直接代写的关键脚本清单，优先把“生命周期跟踪 + 图示更新”这两个难点做出来。
