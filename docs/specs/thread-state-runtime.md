# Thread-State Runtime Specification

## Purpose

Define the minimal extension model for `email-bot` without forcing the project to commit to a full runtime implementation yet.

This spec is intentionally compatible with the repository's existing architecture:

- thread-centric workflow state
- progressive validation gates
- human context plane
- controlled automation

## Design Rules

1. `Thread state first`
   Listeners and actions should consume normalized thread snapshots, not raw provider payloads.
2. `Read-only before action`
   Early listeners should only summarize, classify, rank, or remind.
3. `Evidence required`
   Every important state transition or action suggestion must carry evidence refs.
4. `Context typed, not pasted`
   User materials and habits must arrive as normalized context facts.
5. `Phase-gated automation`
   An action that is invalid in `Phase 4` must not bypass the gate just because a listener fired.

## Event Model

The runtime should center on stateful, reusable event types:

- `thread_entered_state`
- `thread_sla_risk`
- `daily_digest_time`
- `context_updated`
- `confidence_below_threshold`

These are intentionally different from raw `email_received` and `email_sent` events.

## Listener Contract

A listener is a low-risk trigger handler that watches a specific event type and emits one of:

- a value-surface refresh request
- a reminder candidate
- an action-instance candidate
- a human-review request

A listener must declare:

- `id`
- `name`
- `event_types`
- `enabled_by_default`
- `minimum_phase`
- `risk_level`
- `input_requirements`
- `output_types`

## Action Template Contract

An action template defines a reusable capability.

Examples:

- `summarize_thread`
- `build_daily_digest`
- `remind_owner`
- `draft_reply`
- `send_reply`

A template should declare:

- `id`
- `name`
- `description`
- `minimum_phase`
- `risk_level`
- `requires_human_review`
- `required_thread_fields`
- `required_context_types`
- `result_schema`

## Action Instance Contract

An action instance is a concrete proposal generated from one template plus one execution context.

Typical fields:

- `instance_id`
- `template_id`
- `thread_key`
- `workflow_type`
- `state`
- `why`
- `confidence`
- `risk_level`
- `due_hint`
- `evidence_refs`
- `context_refs`
- `proposed_payload`
- `requires_review`
- `phase_gate`

## Audit Contract

Every listener emission and action execution should be auditable.

Minimum audit fields:

- `record_id`
- `record_type`
- `occurred_at`
- `phase`
- `actor`
- `listener_id`
- `template_id`
- `instance_id`
- `thread_key`
- `decision`
- `result`
- `evidence_refs`
- `context_refs`

Recommended storage:

- `runtime/audit/listeners.jsonl`
- `runtime/audit/actions.jsonl`
- `runtime/audit/reviews.jsonl`

## Phase Gates

The runtime must respect the validation program.

- `Preflight-Phase 4`: read-only listeners and value surfaces only
- `Phase 5`: draft-capable actions allowed, but review required
- `Phase 6`: learning from approved edits only
- `Phase 7`: controlled send only after explicit policy and review gates

## Minimal V1 Examples

### Example Listener

- `daily_digest_time`
- input: top `focus` threads from the latest attention budget
- output: refresh `daily-urgent` and `pending-replies`

### Example Action Template

- `draft_reply`
- allowed from `Phase 5`
- requires `state_confidence >= 0.75`
- requires `requires_human_review = true`

### Example Action Instance

- template: `remind_owner`
- thread: `resource-application-123`
- reason: `thread entered waiting_on_me with due_hint in 24h`
- output: reminder card, not outbound email

## Relationship To Other Docs

- [architecture.md](../architecture.md) defines the system layers and invariants
- [progressive-validation-framework.md](../plans/progressive-validation-framework.md) defines when each capability may be activated
- [agent/custom_scripts/types.ts](../../agent/custom_scripts/types.ts) contains the first committed typed contracts
