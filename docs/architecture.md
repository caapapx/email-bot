# Config-Driven Email Skill Architecture

## Goal

Build one stable email automation core that can serve many companies, roles, and individuals without forking the implementation.

The key is to separate:

- transport and mailbox IO
- normalized message model
- policy and routing rules
- prompt/profile customization
- action execution
- review and observability

## Design Principle

Hard things that should stay universal:

- mailbox connectivity
- message parsing
- thread reconstruction
- idempotent sync
- retries, timeouts, rate limiting
- logging and audit trail
- human approval workflow

Things that should stay customizable:

- sender priority
- team/role-specific rules
- reply tone and style
- approval threshold
- digest format
- escalation targets
- ignore/archive logic

## Six-Layer Model

### 1. Transport Layer

Purpose:

- connect to IMAP/SMTP
- fetch message metadata and body
- send or save drafts

Implementation:

- `himalaya` config generated from `.env`
- no business logic here

### 2. Canonical Data Layer

Purpose:

- convert provider-specific email data into one stable internal schema

Canonical fields:

- `message_id`
- `thread_id`
- `from`
- `to`
- `cc`
- `subject`
- `received_at`
- `body_text`
- `body_html`
- `attachments`
- `labels`
- `mailbox`

Why this matters:

- the core pipeline should not care whether mail came from Gmail, Exchange, or another IMAP server

### 3. Policy Layer

Purpose:

- decide what the system should do for a message

Inputs:

- sender identity
- domain
- keywords
- role profile
- current project focus
- risk rules

Outputs:

- priority
- category
- action plan
- review requirement

This layer should be config-driven, not hard-coded.

### 4. Profile Layer

Purpose:

- inject company-, team-, role-, and person-specific behavior

Examples:

- CEO profile
- sales profile
- recruiter profile
- project manager profile

Profile data should define:

- important senders
- ignored senders
- escalation conditions
- reply style
- digest sections
- SLA target

### 5. Action Layer

Purpose:

- run the selected business actions

Typical actions:

- `archive`
- `notify`
- `draft_reply`
- `create_task`
- `sync_crm`
- `build_digest`
- `hold_for_review`

Important rule:

- action executors should consume a structured action plan, not make policy decisions themselves

### 6. Review and Ops Layer

Purpose:

- keep the system safe, observable, and recoverable

Includes:

- approval gates
- retry rules
- audit log
- fallback model routing
- metrics
- dead-letter handling for failures

## Recommended Repository Shape

```text
email-bot/
├── SKILL.md
├── .env
├── docs/
│   └── architecture.md
├── scripts/
│   ├── check_env.sh
│   └── render_himalaya_config.sh
├── config/
│   ├── policy.default.yaml
│   └── profiles/
│       ├── executive.yaml
│       └── recruiter.yaml
└── runtime/
```

## Decision Flow

```text
mail sync
-> normalize message
-> load tenant profile
-> apply global policy
-> apply role profile overrides
-> produce action plan
-> check review threshold
-> execute action
-> log result
```

## Universal vs Customizable Split

Universal core:

- sync engine
- parser
- canonical schema
- action runner
- audit logging
- retry and fallback
- review gate

Customizable surface:

- policy YAML
- profile YAML
- prompt fragments
- digest templates
- sender priority lists
- escalation routing

## How to Achieve High Availability

- keep sync idempotent by `message_id`
- persist checkpoints for last successful fetch
- store action results separately from raw messages
- make classification and drafting re-runnable
- keep sending behind explicit approval by default
- support fallback model routing when primary model is limited
- separate transport failures from LLM failures

## How to Avoid Over-Customization Chaos

- allow config overrides only in defined fields
- do not let each tenant alter the core pipeline
- version policy/profile files
- provide a tested default profile
- introduce extension points, not one-off hacks

## Practical Implementation Rule

If a requirement changes for one person only, put it in profile config.

If a requirement changes for one department, put it in role policy.

If a requirement improves reliability for everyone, put it in the universal core.
