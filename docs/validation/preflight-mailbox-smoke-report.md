# Preflight Mailbox Smoke Report

- time: 2026-03-17 12:45:02 +0800
- mode: headless
- account: zjma12
- folder: INBOX
- page_size: 5
- status: success
- output_json: runtime/validation/preflight/mailbox-smoke.json
- stderr_log: runtime/validation/preflight/mailbox-smoke.stderr.log

## Command

```bash
/home/caapap/iflytek/ltc-plan/email-bot/runtime/bin/himalaya -c /home/caapap/iflytek/ltc-plan/email-bot/runtime/himalaya/config.toml envelope list --account zjma12 --folder INBOX --page 1 --page-size 5 --output json
```

## Notes

- This preflight runs read-only envelope listing.
- It does not send, move, delete, archive, or flag messages.
