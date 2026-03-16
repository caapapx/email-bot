---
name: email-himalaya-assistant
description: Sync mailbox messages through an IMAP/SMTP backend, classify business priority, and generate reply drafts/digests. Trigger when user asks to sync inbox, triage emails, generate a reply draft, or create an email digest.
metadata: {"openclaw":{"requires":{"env":["IMAP_HOST","IMAP_PORT","IMAP_LOGIN","IMAP_PASS","SMTP_HOST","SMTP_PORT","SMTP_LOGIN","SMTP_PASS"]},"primaryEnv":"IMAP_LOGIN"}}
---

Use this skill for email triage workflows with strict safety defaults.

## Scope

- Read and summarize mailbox messages
- Classify emails into urgent/important/normal
- Generate draft replies
- Build daily/weekly digest

## Out of Scope

- No auto-send unless user explicitly confirms
- No mailbox deletion action
- No third-party exfiltration of raw email body without approval

## Expected Environment

- Credentials loaded from `.env`
- Runtime config generated at `runtime/himalaya/config.toml`

## Suggested Tooling

- `scripts/check_env.sh`: validate env keys
- `scripts/render_himalaya_config.sh`: render backend config

## Trigger Phrases

- "sync my mailbox"
- "scan unread emails"
- "triage today's emails"
- "draft a reply to this sender"
- "generate weekly email digest"
