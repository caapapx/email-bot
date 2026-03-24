# Thread-State Runtime Specification

## Purpose

Define the minimal extension model for `email-bot` without forcing the project to commit to a full runtime implementation yet.

This spec is intentionally compatible with the repository's existing architecture:

- thread-centric workflow state
- progressive validation gates
- human context plane
- controlled automation

## Source Of Truth

This document is the authoritative runtime-extension contract for the repository.

The previous top-level `agent/` skeleton was intentionally spec-first, but it made the repository root look heavier than the actual implementation state. Its contract content is now folded into this reference so the current root stays focused on:

- `src/` for implementation
- `scripts/` for thin entrypoints and compatibility wrappers
- `config/` for static policy and templates
- `runtime/` for local state and generated artifacts

Until a real long-running listener/action runtime exists, examples in this document should be treated as illustrative contract sketches rather than committed executable plugin paths.

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
- `weekly_digest_time`
- `context_updated`
- `confidence_below_threshold`

These are intentionally different from raw `email_received` and `email_sent` events.

Cadence rules:

- daily and weekly value surfaces should be precomputed on schedule by default
- `context_updated` and explicit user actions may trigger targeted recomputation of affected objects
- if a scheduled surface is stale or failed, the runtime may serve the last successful result marked `stale` and enqueue a background refresh

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
- `build_weekly_digest`
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

### Example Weekly Listener

- `weekly_digest_time`
- input: unresolved focus threads plus recent important state transitions
- output: refresh a layered `weekly-brief` with `action_now`, `backlog`, and `important_changes`

### Example Action Template

- `build_weekly_digest`
- allowed from `Preflight-Phase 4`
- requires cadence-aware projection rules and explainable inclusion reasons

### Example Draft Action Template

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

- [architecture.md](./architecture.md) defines the system layers and invariants
- [validation-framework.md](../archive/validation-framework.md) defines when each capability may be activated
- [scheduling.md](./scheduling.md) describes cadence-driven triggering and future listener integration
