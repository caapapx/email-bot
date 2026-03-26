# Incremental Mail Processing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add UID watermark based Phase 1 incremental sync, user queue state filtering/reactivation, and the minimum orchestration and CLI wiring needed to make the new flow usable.

**Architecture:** Keep the existing Phase 2-4 pipeline intact and change only the Phase 1 loading path for `daytime-sync`. Introduce three focused modules: one for IMAP incremental fetch and watermark persistence, one for merging incremental envelopes into the existing context-pack, and one for user queue visibility state plus reactivation rules. Integrate the new behavior through tests first, then small wiring changes in orchestration, daytime slice, and task CLI.

**Tech Stack:** Python 3, `pytest`, `imaplib`, existing YAML/JSON runtime artifacts, shell orchestration scripts

**Execution Status (2026-03-26):** Task 1-4 are implemented in repo. `daytime-sync` now enters through `scripts/phase1_incremental.sh`, which calls the Python incremental driver and falls back to `phase1_loading.sh` when `UIDVALIDITY` requires a full rescan. Focused regression coverage has been added for driver behavior, merge stability, no-op handling, runtime artifact writes, and runtime schedule override commands (`twinbox schedule list/update/reset`), including platform-side OpenClaw cron sync for the Twinbox bridge jobs.

---

## File Map

- Create: `src/twinbox_core/imap_incremental.py`
- Create: `src/twinbox_core/merge_context.py`
- Create: `src/twinbox_core/user_queue_state.py`
- Create: `tests/test_imap_incremental.py`
- Create: `tests/test_merge_context.py`
- Create: `tests/test_user_queue_state.py`
- Modify: `src/twinbox_core/orchestration.py`
- Modify: `src/twinbox_core/daytime_slice.py`
- Modify: `src/twinbox_core/task_cli.py`
- Modify: `tests/test_orchestration.py`
- Modify: `tests/test_daytime_slice.py`
- Modify: `tests/test_task_cli.py`
- Create: `scripts/phase1_incremental.sh`

### Task 1: IMAP Incremental Fetch and Watermark Persistence

**Files:**
- Create: `src/twinbox_core/imap_incremental.py`
- Create: `tests/test_imap_incremental.py`

- [ ] **Step 1: Write the failing tests**

Add tests for:
- loading missing watermark file as empty state
- saving watermark file atomically
- treating a changed `UIDVALIDITY` as a rescan signal
- fetching only messages above `last_uid`
- returning updated `last_uid` and `last_sync_at`

- [ ] **Step 2: Run the targeted tests and verify RED**

Run: `pytest tests/test_imap_incremental.py -v`
Expected: FAIL because `twinbox_core.imap_incremental` does not exist yet

- [ ] **Step 3: Write the minimal implementation**

Implement:
- watermark load/save helpers
- IMAP folder select + UID search flow
- a small normalization helper that converts fetched UID rows into an internal envelope payload for later merging

- [ ] **Step 4: Run the targeted tests and verify GREEN**

Run: `pytest tests/test_imap_incremental.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_imap_incremental.py src/twinbox_core/imap_incremental.py
git commit -m "feat: add incremental imap sync helpers"
```

### Task 2: Incremental Context Merge

**Files:**
- Create: `src/twinbox_core/merge_context.py`
- Create: `tests/test_merge_context.py`

- [ ] **Step 1: Write the failing tests**

Add tests for:
- merging new envelopes into an existing context-pack
- deduping by `(id, folder)` with new rows overriding old rows
- keeping existing sampled bodies while adding new ones
- trimming expired envelopes outside the lookback window
- recomputing `generated_at` and stats

- [ ] **Step 2: Run the targeted tests and verify RED**

Run: `pytest tests/test_merge_context.py -v`
Expected: FAIL because `twinbox_core.merge_context` does not exist yet

- [ ] **Step 3: Write the minimal implementation**

Implement:
- `normalize_imap_envelope()`
- `merge_incremental_context()`
- a focused lookback filter shared by the merge path

- [ ] **Step 4: Run the targeted tests and verify GREEN**

Run: `pytest tests/test_merge_context.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_merge_context.py src/twinbox_core/merge_context.py
git commit -m "feat: merge incremental phase1 context"
```

### Task 3: User Queue State and Reactivation

**Files:**
- Create: `src/twinbox_core/user_queue_state.py`
- Create: `tests/test_user_queue_state.py`
- Modify: `src/twinbox_core/daytime_slice.py`
- Modify: `tests/test_daytime_slice.py`

- [ ] **Step 1: Write the failing tests**

Add tests for:
- dismissing a thread writes a snapshot entry
- completing a thread writes a completed entry
- restore removes entries from either list
- dismissed threads are filtered out of pulse output
- completed threads stay hidden even if the same fingerprint appears again
- dismissed threads reactivate when the fingerprint changes

- [ ] **Step 2: Run the targeted tests and verify RED**

Run: `pytest tests/test_user_queue_state.py tests/test_daytime_slice.py -v`
Expected: FAIL because the queue-state module and pulse integration do not exist yet

- [ ] **Step 3: Write the minimal implementation**

Implement:
- YAML load/save helpers
- dismiss/complete/restore functions
- fingerprint-based reactivation checks
- `daytime_slice` filtering so user queue state is applied after pulse dedupe

- [ ] **Step 4: Run the targeted tests and verify GREEN**

Run: `pytest tests/test_user_queue_state.py tests/test_daytime_slice.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_user_queue_state.py tests/test_daytime_slice.py src/twinbox_core/user_queue_state.py src/twinbox_core/daytime_slice.py
git commit -m "feat: add user queue visibility state"
```

### Task 4: Orchestration and CLI Wiring

**Files:**
- Create: `scripts/phase1_incremental.sh`
- Modify: `src/twinbox_core/orchestration.py`
- Modify: `src/twinbox_core/task_cli.py`
- Modify: `tests/test_orchestration.py`
- Modify: `tests/test_task_cli.py`

- [ ] **Step 1: Write the failing tests**

Add tests for:
- `daytime-sync` using the incremental Phase 1 script
- `nightly-full` keeping the existing full Phase 1 path
- CLI commands for `queue dismiss`, `queue complete`, `queue restore`
- JSON output for those commands

- [ ] **Step 2: Run the targeted tests and verify RED**

Run: `pytest tests/test_orchestration.py tests/test_task_cli.py -v`
Expected: FAIL because the new script path and CLI actions are not wired yet

- [ ] **Step 3: Write the minimal implementation**

Implement:
- incremental shell entrypoint
- orchestration step replacement for `daytime-sync`
- task CLI actions that call `user_queue_state`

- [ ] **Step 4: Run the targeted tests and verify GREEN**

Run: `pytest tests/test_orchestration.py tests/test_task_cli.py -v`
Expected: PASS

- [ ] **Step 5: Run focused regression coverage**

Run: `pytest tests/test_imap_incremental.py tests/test_merge_context.py tests/test_user_queue_state.py tests/test_daytime_slice.py tests/test_orchestration.py tests/test_task_cli.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add tests/test_imap_incremental.py tests/test_merge_context.py tests/test_user_queue_state.py tests/test_daytime_slice.py tests/test_orchestration.py tests/test_task_cli.py src/twinbox_core/imap_incremental.py src/twinbox_core/merge_context.py src/twinbox_core/user_queue_state.py src/twinbox_core/daytime_slice.py src/twinbox_core/orchestration.py src/twinbox_core/task_cli.py scripts/phase1_incremental.sh
git commit -m "feat: wire incremental daytime sync"
```

## Notes

- Keep `nightly-full` on the existing full-sync path for reconciliation.
- Do not change Phase 2/3 thinking behavior in this implementation slice.
- Apply user queue filtering after activity-pulse dedupe, matching the spec.
- This plan was reviewed locally only. I did not dispatch a plan-review subagent because this session was not authorized for subagent delegation.
