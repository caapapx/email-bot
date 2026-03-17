# Phase 1 Report: Mailbox Distribution Census

## Scope
- Folders scanned: INBOX, Sent Items, Trash, 辽宁
- Total envelopes: 471
- Sampled message bodies: 30
- Read-only safeguards: only `folder list`, `envelope list`, `message read --preview` used

## Facts
- Sender domain Top: kxdigit.com(428)、iflytek.com(41)、vip.baiwang.com(2)
- Intent candidate Top: human(333)、internal_update(71)、support(43)、newsletter(11)、scheduling(7)
- Attachment ratio: 22.08% (104/471)
- Internal vs external: internal=469, external=2, unknown=0
- High-frequency threads: rdg货架-授权申请审核结果(8)；tjnlzx_v1.5.0build1002中间版本升级资源申请(7)；dy04-cq0qwjx-tk-2024项目北京云平台部署资源申请(5)；工时填报提醒(5)；aq01-tj0s2z-bbt-2025项目系统资源申请表0313(4)

## High-Confidence Inferences
- Current mailbox has a strong internal-collaboration communication signal.
- Dominant intent candidates are suitable for downstream automation baselines in triage and summarization.
- Repeated thread subjects indicate opportunities for thread-level state modeling in Phase 3.

## Hypotheses To Confirm
- Some newsletter/internal-update categories may overlap and need manual calibration with a labeled sample set.
- Internal domain set currently uses a conservative static allowlist and may require extension for subsidiaries/partners.
- Week-level distribution should be rechecked with a larger sample window for seasonality stability.

## Outputs
- `runtime/validation/phase-1/mailbox-census.json`
- `runtime/validation/phase-1/intent-distribution.yaml`
- `runtime/validation/phase-1/contact-distribution.json`
- `docs/validation/diagrams/phase-1-mailbox-overview.mmd`
- `docs/validation/diagrams/phase-1-sender-network.mmd`
