# Instance Calibration Notes

日期：2026-03-17  
适用对象：当前邮箱实例初始化  
维护原则：本文件可以被覆盖、迭代或重生成；不要把这些实例化结论合并回主模板

## 用途

这个文件承载“当前邮箱实例”的阶段结论、价值判断、当前优先方向和跳转链接。  
主模板 [openclaw-progressive-validation-plan.md](../openclaw-progressive-validation-plan.md) 只负责通用流程，不负责保存这些实时结论。

## 当前结果入口

- [Preflight 报告](preflight-mailbox-smoke-report.md)
- [Phase 1 报告](phase-1-report.md)
- [Phase 2 报告](phase-2-report.md)
- [Phase 3 报告](phase-3-report.md)
- [Preflight JSON](../../runtime/validation/preflight/mailbox-smoke.json)
- [Phase 1 Census JSON](../../runtime/validation/phase-1/mailbox-census.json)
- [Phase 1 Intent YAML](../../runtime/validation/phase-1/intent-distribution.yaml)
- [Phase 1 Contact JSON](../../runtime/validation/phase-1/contact-distribution.json)
- [Phase 2 Persona YAML](../../runtime/validation/phase-2/persona-hypotheses.yaml)
- [Phase 2 Business YAML](../../runtime/validation/phase-2/business-hypotheses.yaml)
- [Phase 3 Lifecycle YAML](../../runtime/validation/phase-3/lifecycle-model.yaml)
- [Phase 3 Thread Samples JSON](../../runtime/validation/phase-3/thread-stage-samples.json)
- [Phase 3 Lifecycle Overview (mermaid)](diagrams/phase-3-lifecycle-overview.mmd)
- [Phase 3 Thread State Machine (mermaid)](diagrams/phase-3-thread-state-machine.mmd)

## 当前实例的自我批判结论

### 1. 价值清晰度

当前实例的真正价值点已经比较清楚：不是“泛化邮箱自动化”，而是“内部协同线程副驾”。

更具体地说，是帮助用户：

- 少漏跟进
- 少手工找状态
- 少重复整理汇报材料

### 2. 价值时间线

如果要让用户尽快感知价值，应优先看到：

- 今天必须跟进的线程
- 等待我拍板或回复的线程
- 被卡住的项目线程

而不是先追求复杂动作或发送能力。

### 3. 价值感知

对当前实例来说，最容易感知的价值不是更多分析文件，而是更短、更准、能直接行动的队列和摘要。

### 4. 价值发现

`Phase 1/2` 已帮助当前实例把方向收束到“内部项目协同与交付推进”的场景。  
这说明后续 `Phase 3/4/5` 应继续围绕当前高频流程深入，而不是重新发散成宽泛行业模板。

## 当前实例的工作假设

1. 当前邮箱以内协同为主，不是对外销售或客服主导邮箱。
2. 高频线程更像流程线程，而不是一次性消息。
3. 生命周期建模和可执行清单，会比发送能力更早带来真实价值。
4. 草稿能力要在只读价值被证明之后再放大。

## Phase 3 价值自评（四维度）

### 1. 价值清晰度 🟡

Phase 3 把 471 封邮件归纳成 5 条生命周期流、25 个阶段，并给出了 entry/exit/risk 信号定义。

**做到的**：用户现在可以说”我的邮箱主要跑 5 个流程”，比 Phase 2 的”内部协同为主”更具体。5 条 policy 建议直接映射到可执行动作。

**没做到的**：
- 缺少 `owner_guess / waiting_on / due_hint`，因为仅从主题推断这三个字段置信度不够，需要正文抽样。这意味着用户看到 lifecycle-model.yaml 时，知道”有哪些流程和阶段”，但不知道”现在谁在等谁”。
- 5 条流全部来自主题关键词匹配，没有正文语义分析。LF1/LF2 的阶段切换信号（如”已批准”/”驳回”）是假设而非验证。
- 状态机图（mermaid）可读性还行，但没有在真实线程上跑过一遍端到端验证。

**结论**：价值方向清晰（”少漏跟进 + 少手工找状态”），但离”用户打开就知道该做什么”还差一层具体数据填充（Phase 4 的事）。

### 2. 价值时间线 🟡

Phase 3 本身是分析产物，不直接面向最终用户。真正让用户感知价值的是 Phase 4 的 daily-urgent / pending-replies 输出。

Phase 3 的价值时间线是 **延迟的**——它是 Phase 4 的前置依赖。如果 Phase 4 产出不可用，Phase 3 的 lifecycle model 只是一堆 YAML 文件。

**风险**：如果 Phase 4 跑出来发现 LF3 日报摘要不够有用，Phase 3 的建模就需要回退重做。这是正常的——但要意识到 Phase 3 的价值目前是”承诺”而非”已交付”。

### 3. 价值感知 🟡

Phase 3 产出了 2 张 mermaid 图（lifecycle-overview + thread-state-machine），视觉上比 Phase 1/2 的纯文本更容易感知。

**可见的**：
- 5 条流的总览图，一眼能看出 LF1→LF2 的关联触发
- 状态机图展示了每个阶段的 AI 动作和风险信号
- 15 条线程样本标注，可追溯

**不可见的**：
- 用户在日常工作中不会打开 mermaid 文件看状态机。真正能感知的是 Phase 4 的”今天该做什么”推送
- lifecycle-model.yaml 对开发者/架构师可读，对最终邮箱用户不可读

**结论**：Phase 3 的价值感知主要面向产品构建者（我们自己），不面向最终用户。这是合理的——它是基础设施层，不是用户层。

### 4. 价值发现 🟢

Phase 3 最大的发现是：**LF3（日报摘要）和 LF1（SLA 提醒）是进入 Phase 4 的最佳切入点**。

- LF3 日报占邮箱总量 16%，完全只读，自动摘要零风险
- LF1 资源申请线程长度长（rdg=8），漏跟进痛点从数据上可验证
- LF5 周报虽然频次最高，但是用户自己发出的，Phase 4 对它的适用性不如接收侧的 LF3/LF1

这个发现本身就是 Phase 3 的核心价值——它把”下一步做什么”从模糊变成了有数据支撑的优先级排序。

### Phase 3 四维度总评

| 维度 | 状态 | 说明 |
|---|---|---|
| 价值清晰度 | 🟡 | 方向清晰但缺 owner/waiting_on 细节 |
| 价值时间线 | 🟡 | 延迟价值，依赖 Phase 4 兑现 |
| 价值感知 | 🟡 | 面向构建者可见，面向用户不可见 |
| 价值发现 | 🟢 | 成功排序出 LF3/LF1 为最优切入点 |

**核心判断**：Phase 3 完成了它该做的事（建模 + 排序），但它的价值需要 Phase 4 来兑现。如果 Phase 4 的 daily-urgent 输出让用户觉得有用，Phase 3 就是成功的基础设施；如果 Phase 4 不行，Phase 3 需要回退补充正文级分析。

## 当前实例的自我批判补充

### Phase 3 特有的批判

1. **信号假设未验证**：LF1 的”已批准”/”驳回” 切换信号是从主题词猜的，没有在真实邮件正文里跑过匹配。Phase 4 应该在生成 daily-urgent 时顺便验证这些信号是否真的出现在正文中。

2. **LF1-LF2 关联是推测**：资源批准后是否自动触发版本发布流，这个结论没有证据支撑（只是逻辑推测）。需要人工确认或找到至少 2 条跨流线程证据。

3. **LF4 合规通知的截止日期提取**：当前只知道”工时填报提醒”是周期性的，但不知道截止日期具体在正文哪个位置。Phase 4 需要正文抽样才能做。

4. **lifecycle-model.yaml 缺字段**：计划模板要求 `owner_guess / waiting_on / due_hint`，当前版本没有。这不是偷懒——是因为从 envelope 主题推断这些字段准确率太低。但 Phase 4 应该用正文抽样补上。

## 当前实例的下一步建议

1. ~~优先用 `Phase 3` 把当前高频流程做成线程状态机。~~ ✅ 已完成
2. 紧接着用 `Phase 4` 验证”今天该做什么”是否已经足够有用。优先切入 LF3（日报摘要）和 LF1（SLA 提醒）。
3. Phase 4 中顺便验证 Phase 3 的阶段信号假设（正文级匹配）。
4. 如果 `Phase 4` 不够有用，先修生命周期和证据链，不要急着进入 `Phase 5`。
5. lifecycle-model.yaml 的 `owner_guess / waiting_on / due_hint` 字段在 Phase 4 正文抽样后回填。
