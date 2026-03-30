# Mailbox Validation Env Precedence Design

## Goal

Fix OpenClaw onboarding and mailbox configuration update flows so immediate mailbox validation uses the newly provided credentials instead of stale process environment secrets.

## Context

Twinbox mailbox preflight currently resolves effective environment in `process-env-first` order. That is correct for standalone preflight and runtime override scenarios.

The bug appears in flows that:
1. collect new mailbox values from the user,
2. write them to the state-root `.env`, then
3. immediately call `run_preflight()` from the same process.

If the current process still has old `IMAP_PASS` / `SMTP_PASS` values, preflight reads those stale secrets and can fail even though the new credentials were just written.

## Options Considered

### 1. Scoped caller fix
Pass the freshly merged mailbox environment into `run_preflight(env=...)` from the update flows.

Pros:
- Fixes the exact bug.
- Preserves `mailbox preflight` process-env override behavior.
- Small change surface.

Cons:
- Requires each immediate-validation caller to be explicit.

### 2. Global precedence change
Make `.env` override process env inside mailbox preflight.

Pros:
- Centralized behavior change.

Cons:
- Changes existing semantics for standalone preflight and runtime overrides.
- Higher regression risk.

## Decision

Use option 1.

## Design

- Keep `build_effective_env()` and `run_preflight()` semantics unchanged.
- In `openclaw_onboard._apply_mailbox_updates()`, after merging mailbox updates, call `run_preflight()` with a validation env that preserves process env but lets merged mailbox keys win.
- In `task_cli.cmd_config_mailbox_set()`, after merging mailbox updates, call `run_preflight()` with the same validation env strategy.
- Add regression tests proving stale process env no longer overrides freshly written mailbox secrets in those two flows.

## Testing

- Add one onboarding regression test that simulates old process env passwords plus a new password entered in the wizard; assert the preflight runner receives the new password.
- Add one CLI regression test that simulates old process env passwords plus new setup env secrets; assert preflight receives the new password.
