# Mailbox Validation Env Precedence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ensure immediate mailbox validation uses newly merged mailbox credentials instead of stale process environment secrets.

**Architecture:** Keep mailbox preflight's global `process-env-first` behavior intact. Fix only the callers that write mailbox config and immediately validate it by passing a validation env where merged mailbox values override stale process secrets while preserving other process env.

**Tech Stack:** Python, pytest, Twinbox CLI/onboarding flows

---

### Task 1: Add onboarding regression test

**Files:**
- Modify: `tests/test_openclaw_onboard.py`
- Test: `tests/test_openclaw_onboard.py`

- [ ] **Step 1: Write the failing test**
Add a test where process env contains stale mailbox passwords, onboarding updates the password, and the mailbox apply/preflight path must observe the new password.

- [ ] **Step 2: Run test to verify it fails**
Run: `pytest tests/test_openclaw_onboard.py -k stale_process_env -v`
Expected: FAIL because preflight still reads the stale password.

- [ ] **Step 3: Write minimal implementation**
Update onboarding mailbox apply flow to pass merged env into preflight.

- [ ] **Step 4: Run test to verify it passes**
Run: `pytest tests/test_openclaw_onboard.py -k stale_process_env -v`
Expected: PASS.

### Task 2: Add CLI regression test

**Files:**
- Modify: `tests/test_task_cli.py`
- Test: `tests/test_task_cli.py`
- Modify: `src/twinbox_core/task_cli.py`

- [ ] **Step 1: Write the failing test**
Add a test where process env contains stale mailbox passwords, `mailbox setup` writes new ones, and preflight must receive the merged env.

- [ ] **Step 2: Run test to verify it fails**
Run: `pytest tests/test_task_cli.py -k stale_process_env -v`
Expected: FAIL because preflight still receives the stale password.

- [ ] **Step 3: Write minimal implementation**
Update the CLI mailbox config flow to call preflight with merged env.

- [ ] **Step 4: Run test to verify it passes**
Run: `pytest tests/test_task_cli.py -k stale_process_env -v`
Expected: PASS.

### Task 3: Verify the full fix

**Files:**
- Modify: `src/twinbox_core/openclaw_onboard.py`
- Modify: `src/twinbox_core/task_cli.py`
- Test: `tests/test_openclaw_onboard.py`
- Test: `tests/test_task_cli.py`

- [ ] **Step 1: Run the targeted regression suite**
Run: `pytest tests/test_openclaw_onboard.py tests/test_task_cli.py -k "stale_process_env or set_mailbox" -v`
Expected: PASS.

- [ ] **Step 2: Review the diff**
Run: `git diff -- src/twinbox_core/openclaw_onboard.py src/twinbox_core/task_cli.py tests/test_openclaw_onboard.py tests/test_task_cli.py`
Expected: Only scoped env handoff and regression tests.

- [ ] **Step 3: Commit**
Run:
```bash
git add docs/superpowers/specs/2026-03-30-mailbox-validation-env-precedence-design.md \
        docs/superpowers/plans/2026-03-30-mailbox-validation-env-precedence.md \
        src/twinbox_core/openclaw_onboard.py \
        src/twinbox_core/task_cli.py \
        tests/test_openclaw_onboard.py \
        tests/test_task_cli.py
git commit -m "fix: use merged mailbox env for immediate validation"
```
