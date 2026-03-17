# Phase 2 Report: Persona and Business Profile Inference

## Evidence Base
- Source: `runtime/validation/phase-1/mailbox-census.json`
- Envelope sample size: 471
- Internal vs external: internal=469, external=2, unknown=0

## Persona Hypotheses
- [P1] (confidence=0.88) 用户主要承担内部项目协同与交付推进角色
- [P2] (confidence=0.85) 用户工作中对资源申请、版本发布、联调联试流程参与较深
- [P3] (confidence=0.80) 用户在沟通链路中兼具执行与汇报属性，存在高频固定协作对象

## Business Hypotheses
- [B1] (confidence=0.90) 公司邮件活动中心围绕项目交付、研发联调、资源申请与合规通知
- [B2] (confidence=0.87) 外部沟通占比低，当前自动化优先级应先聚焦内部协作效率
- [B3] (confidence=0.78) 存在稳定组织关系网络，适合构建联系人/团队协作画像

## High-Confidence Inferences
- 邮件流量以内部协同为主，短期自动化重点应放在内部任务编排和线程跟进。
- 高频主题集中在交付流程型邮件，适合做 thread 级状态机建模。
- 当前证据已经足够支持进入 Phase 3 生命周期建模。

## Low-Confidence / Need Confirmation
- `human` intent 占比高，部分可能是规则未覆盖导致，需要人工标注样本校准。
- 内部域名集合可能不完整，影响内外部占比精度。

## Minimal Confirmation Questions (max 7)
1. 你在团队中的主角色更接近：项目交付推进 / 技术协调 / 业务管理中的哪一类？
2. 资源申请与版本发布相关线程，哪些属于你必须拍板，哪些只是同步抄送？
3. 内部邮件里你最想优先自动化的是：每日待办提炼、线程状态跟进、还是周报汇总？
4. iflytek.com 与 kxdigit.com 是否都应被视为内部域名？是否还有其他内部域名？
5. 当前最容易漏跟进的邮件类型是什么（资源申请、联调问题、合规通知等）？
6. 对自动草稿的风险边界是什么（仅建议/必须人工确认/特定对象禁用）？
7. 你希望 Phase 3 的线程生命周期最先覆盖哪类主题？

## Outputs
- `runtime/validation/phase-2/persona-hypotheses.yaml`
- `runtime/validation/phase-2/business-hypotheses.yaml`
- `docs/validation/phase-2-report.md`
- `docs/validation/diagrams/phase-2-relationship-map.mmd`
