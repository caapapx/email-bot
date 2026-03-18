#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${ROOT_DIR}/.env"
PHASE_DIR="${ROOT_DIR}/runtime/validation/phase-1"
RAW_DIR="${PHASE_DIR}/raw"
DOC_DIR="${ROOT_DIR}/docs/validation"
DIAGRAM_DIR="${DOC_DIR}/diagrams"
CONFIG_FILE="${ROOT_DIR}/runtime/himalaya/config.toml"

MAX_PAGES_PER_FOLDER=20
PAGE_SIZE=50
SAMPLE_BODY_COUNT=30
FOLDER_FILTER=""
ACCOUNT_OVERRIDE=""

usage() {
  cat <<'USAGE'
Usage:
  bash scripts/phase1_mailbox_census.sh [options]

Options:
  --account <name>               Override MAIL_ACCOUNT_NAME
  --folder <name>                Only scan one folder (default: all folders)
  --max-pages-per-folder <n>     Max pages per folder (default: 20)
  --page-size <n>                Page size for envelope list (default: 50)
  --sample-body-count <n>        Number of envelopes to sample body text (default: 30)
  -h, --help                     Show this help
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --account)
      ACCOUNT_OVERRIDE="${2:-}"
      shift 2
      ;;
    --folder)
      FOLDER_FILTER="${2:-}"
      shift 2
      ;;
    --max-pages-per-folder)
      MAX_PAGES_PER_FOLDER="${2:-}"
      shift 2
      ;;
    --page-size)
      PAGE_SIZE="${2:-}"
      shift 2
      ;;
    --sample-body-count)
      SAMPLE_BODY_COUNT="${2:-}"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1"
      usage
      exit 1
      ;;
  esac
done

mkdir -p "${PHASE_DIR}" "${RAW_DIR}" "${DOC_DIR}" "${DIAGRAM_DIR}"

if [[ ! -f "${ENV_FILE}" ]]; then
  echo "Missing .env at ${ENV_FILE}"
  exit 1
fi

set -a
source "${ENV_FILE}"
set +a

bash "${ROOT_DIR}/scripts/check_env.sh"
bash "${ROOT_DIR}/scripts/render_himalaya_config.sh"

if ! command -v himalaya >/dev/null 2>&1; then
  if [[ -x "${ROOT_DIR}/runtime/bin/himalaya" ]]; then
    HIMALAYA_BIN="${ROOT_DIR}/runtime/bin/himalaya"
  else
    echo "himalaya CLI not found in PATH (or ${ROOT_DIR}/runtime/bin/himalaya)"
    exit 1
  fi
else
  HIMALAYA_BIN="$(command -v himalaya)"
fi

ACCOUNT="${ACCOUNT_OVERRIDE:-${MAIL_ACCOUNT_NAME}}"
FOLDERS_JSON="${RAW_DIR}/folders.json"
ENVELOPES_JSON="${RAW_DIR}/envelopes-merged.json"
BODIES_JSON="${RAW_DIR}/sample-bodies.json"

"${HIMALAYA_BIN}" -c "${CONFIG_FILE}" folder list --account "${ACCOUNT}" --output json > "${FOLDERS_JSON}"

mapfile -t FOLDERS < <(node -e '
  const fs = require("fs");
  const p = process.argv[1];
  const rows = JSON.parse(fs.readFileSync(p, "utf8"));
  for (const r of rows) console.log(r.name);
' "${FOLDERS_JSON}")

if [[ -n "${FOLDER_FILTER}" ]]; then
  FOLDERS=("${FOLDER_FILTER}")
fi

: > "${RAW_DIR}/all-pages.ndjson"

for folder in "${FOLDERS[@]}"; do
  safe_folder="$(printf '%s' "${folder}" | tr '/ ' '__')"
  for ((page=1; page<=MAX_PAGES_PER_FOLDER; page++)); do
    page_out="${RAW_DIR}/envelopes-${safe_folder}-p${page}.json"
    page_err="${RAW_DIR}/envelopes-${safe_folder}-p${page}.stderr.log"

    if ! "${HIMALAYA_BIN}" -c "${CONFIG_FILE}" envelope list --account "${ACCOUNT}" --folder "${folder}" --page "${page}" --page-size "${PAGE_SIZE}" --output json > "${page_out}" 2> "${page_err}"; then
      if rg -qi "out of bound|out-of-bound|out of range" "${page_err}"; then
        break
      fi
      echo "Warn: envelope list failed for folder=${folder}, page=${page}. See ${page_err}" >&2
      break
    fi

    count="$(node -e 'const fs=require("fs"); const a=JSON.parse(fs.readFileSync(process.argv[1],"utf8")); console.log(Array.isArray(a)?a.length:0);' "${page_out}")"
    if [[ "${count}" -eq 0 ]]; then
      break
    fi

    printf '{"folder":%s,"page":%s,"path":%s}\n' "$(node -p 'JSON.stringify(process.argv[1])' "${folder}")" "${page}" "$(node -p 'JSON.stringify(process.argv[1])' "${page_out}")" >> "${RAW_DIR}/all-pages.ndjson"

    if [[ "${count}" -lt "${PAGE_SIZE}" ]]; then
      break
    fi
  done
done

node - <<'NODE' "${RAW_DIR}/all-pages.ndjson" "${ENVELOPES_JSON}"
const fs = require('fs');
const [ndjsonPath, outPath] = process.argv.slice(2);
const lines = fs.readFileSync(ndjsonPath, 'utf8').trim();
const items = [];
if (lines) {
  for (const line of lines.split('\n')) {
    const ref = JSON.parse(line);
    const rows = JSON.parse(fs.readFileSync(ref.path, 'utf8'));
    for (const r of rows) {
      items.push({ ...r, folder: ref.folder, source_page: ref.page });
    }
  }
}
fs.writeFileSync(outPath, JSON.stringify(items, null, 2));
NODE

node - <<'NODE' "${ENVELOPES_JSON}" "${BODIES_JSON}" "${SAMPLE_BODY_COUNT}" "${HIMALAYA_BIN}" "${CONFIG_FILE}" "${ACCOUNT}"
const fs = require('fs');
const cp = require('child_process');
const [envPath, outPath, sampleCountRaw, bin, config, account] = process.argv.slice(2);
const envelopes = JSON.parse(fs.readFileSync(envPath, 'utf8'));
const sampleCount = Number(sampleCountRaw);
const samples = envelopes.slice(0, Math.max(0, sampleCount));
const out = [];
for (const e of samples) {
  const id = String(e.id);
  const folder = e.folder || 'INBOX';
  try {
    const cmd = [
      bin, '-c', config,
      'message', 'read', '--preview', '--no-headers',
      '--account', account,
      '--folder', folder,
      id,
      '--output', 'json',
    ];
    const raw = cp.execFileSync(cmd[0], cmd.slice(1), { encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'] });
    let body = '';
    try { body = JSON.parse(raw); } catch { body = ''; }
    out.push({ id, folder, body: String(body).slice(0, 3000) });
  } catch {
    out.push({ id, folder, body: '' });
  }
}
fs.writeFileSync(outPath, JSON.stringify(out, null, 2));
NODE

node - <<'NODE' "${ENVELOPES_JSON}" "${BODIES_JSON}" "${PHASE_DIR}" "${DOC_DIR}" "${DIAGRAM_DIR}" "${MAIL_ADDRESS}"
const fs = require('fs');

const [envelopesPath, bodiesPath, phaseDir, docDir, diagramDir, mailAddress] = process.argv.slice(2);
const envelopes = JSON.parse(fs.readFileSync(envelopesPath, 'utf8'));
const bodies = JSON.parse(fs.readFileSync(bodiesPath, 'utf8'));
const bodyMap = new Map(bodies.map(b => [String(b.id), b.body || '']));

const ownDomain = (mailAddress.split('@')[1] || '').toLowerCase();
const internalDomains = new Set([ownDomain, ...(process.env.INTERNAL_DOMAINS || '').split(',').map(d => d.trim()).filter(Boolean)]);

const stopWords = new Set(['re','fw','fwd','回复','转发','关于','通知','请','公司','关于为','the','and','for','with','to','of','in']);

function senderAddr(e) { return ((e.from && e.from.addr) || '').toLowerCase(); }
function senderName(e) { return ((e.from && e.from.name) || '').trim(); }
function senderDomain(e) {
  const addr = senderAddr(e);
  const i = addr.lastIndexOf('@');
  return i >= 0 ? addr.slice(i + 1) : 'unknown';
}
function parseTs(s) {
  if (!s) return null;
  const t = s.replace(' ', 'T');
  const d = new Date(t);
  return Number.isNaN(d.getTime()) ? null : d;
}
function ymd(d) { return d ? d.toISOString().slice(0,10) : 'unknown'; }
function isoWeek(d) {
  if (!d) return 'unknown';
  const t = new Date(Date.UTC(d.getUTCFullYear(), d.getUTCMonth(), d.getUTCDate()));
  const dayNum = t.getUTCDay() || 7;
  t.setUTCDate(t.getUTCDate() + 4 - dayNum);
  const yearStart = new Date(Date.UTC(t.getUTCFullYear(), 0, 1));
  const weekNo = Math.ceil((((t - yearStart) / 86400000) + 1) / 7);
  return `${t.getUTCFullYear()}-W${String(weekNo).padStart(2,'0')}`;
}
function normThread(subject) {
  const s = String(subject || '').toLowerCase()
    .replace(/^(\s*(re|fw|fwd|回复|转发)\s*[:：])+\s*/gi, '')
    .replace(/\s+/g, ' ')
    .trim();
  return s || '(no-subject)';
}
function extractTokens(text) {
  const m = String(text || '').match(/[A-Za-z0-9\u4e00-\u9fff]{2,}/g) || [];
  return m.map(x => x.toLowerCase()).filter(x => !stopWords.has(x));
}
function classifyIntent(subject, body) {
  const t = `${subject || ''}\n${body || ''}`.toLowerCase();
  const rules = [
    ['support', [/支持|故障|报错|问题|support|ticket|help/]],
    ['finance', [/发票|报销|付款|对账|预算|财务|合同|invoice|payment/]],
    ['recruiting', [/招聘|面试|候选人|简历|offer|猎头|hr/]],
    ['scheduling', [/会议|日程|邀约|安排|时间|calendar|meeting/]],
    ['receipt', [/回执|收据|receipt|confirmation|确认函/]],
    ['newsletter', [/newsletter|digest|报名开启|活动|分享|讲座|课程/]],
    ['internal_update', [/通知|公告|政策|制度|周报|月报|合规|宣导|培训/]],
    ['human', [/.*/]],
  ];
  for (const [intent, pats] of rules) {
    if (pats.some(p => p.test(t))) return intent;
  }
  return 'human';
}

const total = envelopes.length;
const byFolder = {};
const byDomain = {};
const bySender = {};
const byIntent = {};
const byDate = {};
const byWeek = {};
const byInternalExternal = { internal: 0, external: 0, unknown: 0 };
let withAttachment = 0;
const threadCounts = {};
const tokenCounts = {};

for (const e of envelopes) {
  const folder = e.folder || 'INBOX';
  byFolder[folder] = (byFolder[folder] || 0) + 1;

  const domain = senderDomain(e);
  byDomain[domain] = (byDomain[domain] || 0) + 1;

  const sender = senderAddr(e) || senderName(e) || 'unknown';
  bySender[sender] = (bySender[sender] || 0) + 1;

  const date = parseTs(e.date);
  const d = ymd(date);
  const w = isoWeek(date);
  byDate[d] = (byDate[d] || 0) + 1;
  byWeek[w] = (byWeek[w] || 0) + 1;

  const internalKey = domain === 'unknown' ? 'unknown' : (internalDomains.has(domain) ? 'internal' : 'external');
  byInternalExternal[internalKey] = (byInternalExternal[internalKey] || 0) + 1;

  if (e.has_attachment) withAttachment++;

  const thread = normThread(e.subject || '');
  threadCounts[thread] = (threadCounts[thread] || 0) + 1;

  for (const tok of extractTokens(e.subject || '')) {
    tokenCounts[tok] = (tokenCounts[tok] || 0) + 1;
  }

  const body = bodyMap.get(String(e.id)) || '';
  const intent = classifyIntent(e.subject || '', body);
  byIntent[intent] = (byIntent[intent] || 0) + 1;
}

function topN(obj, n = 10) {
  return Object.entries(obj).sort((a,b) => b[1]-a[1]).slice(0, n).map(([k,v]) => ({ key: k, count: v }));
}

const threadsTop = topN(threadCounts, 15);
const longThreads = threadsTop.filter(t => t.count >= 3);

const census = {
  generated_at: new Date().toISOString(),
  scope: {
    folders_scanned: Object.keys(byFolder),
    total_envelopes: total,
    sampled_bodies: bodies.length,
  },
  distributions: {
    by_folder: byFolder,
    by_sender_domain: byDomain,
    by_sender_contact: bySender,
    by_subject_keyword: tokenCounts,
    by_date: byDate,
    by_week: byWeek,
    internal_external: byInternalExternal,
    intent_candidates: byIntent,
  },
  metrics: {
    attachment_ratio: total ? Number((withAttachment / total).toFixed(4)) : 0,
    attachment_count: withAttachment,
    total_count: total,
  },
  threads: {
    high_frequency: threadsTop.slice(0, 10),
    long_threads: longThreads,
  },
  top: {
    domains: topN(byDomain, 10),
    contacts: topN(bySender, 10),
    keywords: topN(tokenCounts, 20),
    intents: topN(byIntent, 10),
  },
};

fs.writeFileSync(`${phaseDir}/mailbox-census.json`, JSON.stringify(census, null, 2));

const intentYaml = [
  `generated_at: "${new Date().toISOString()}"`,
  `total_envelopes: ${total}`,
  'intent_distribution:'
];
for (const { key, count } of topN(byIntent, 20)) {
  intentYaml.push(`  - intent: ${key}`);
  intentYaml.push(`    count: ${count}`);
  intentYaml.push(`    ratio: ${total ? (count/total).toFixed(4) : '0.0000'}`);
}
fs.writeFileSync(`${phaseDir}/intent-distribution.yaml`, intentYaml.join('\n') + '\n');

const contactDist = {
  generated_at: new Date().toISOString(),
  top_contacts: topN(bySender, 30),
  top_domains: topN(byDomain, 30),
};
fs.writeFileSync(`${phaseDir}/contact-distribution.json`, JSON.stringify(contactDist, null, 2));

const overviewMmd = [
  'pie title Phase 1 Mailbox Overview',
  `  "Internal" : ${byInternalExternal.internal || 0}`,
  `  "External" : ${byInternalExternal.external || 0}`,
  `  "Unknown" : ${byInternalExternal.unknown || 0}`,
].join('\n') + '\n';
fs.writeFileSync(`${diagramDir}/phase-1-mailbox-overview.mmd`, overviewMmd);

const senderTop = topN(byDomain, 8);
const senderMmd = ['graph LR', '  Mailbox["Mailbox"]'];
for (const { key, count } of senderTop) {
  const safe = key.replace(/[^a-zA-Z0-9]/g, '_') || 'unknown';
  senderMmd.push(`  D_${safe}["${key}"]`);
  senderMmd.push(`  Mailbox -->|${count}| D_${safe}`);
}
fs.writeFileSync(`${diagramDir}/phase-1-sender-network.mmd`, senderMmd.join('\n') + '\n');

const factDomains = topN(byDomain, 5).map(x => `${x.key}(${x.count})`).join('、');
const factIntents = topN(byIntent, 5).map(x => `${x.key}(${x.count})`).join('、');
const factThreads = threadsTop.slice(0, 5).map(x => `${x.key}(${x.count})`).join('；');

const report = `# Phase 1 Report: Mailbox Distribution Census\n\n## Scope\n- Folders scanned: ${Object.keys(byFolder).join(', ')}\n- Total envelopes: ${total}\n- Sampled message bodies: ${bodies.length}\n- Read-only safeguards: only \`folder list\`, \`envelope list\`, \`message read --preview\` used\n\n## Facts\n- Sender domain Top: ${factDomains || 'N/A'}\n- Intent candidate Top: ${factIntents || 'N/A'}\n- Attachment ratio: ${(census.metrics.attachment_ratio * 100).toFixed(2)}% (${withAttachment}/${total})\n- Internal vs external: internal=${byInternalExternal.internal || 0}, external=${byInternalExternal.external || 0}, unknown=${byInternalExternal.unknown || 0}\n- High-frequency threads: ${factThreads || 'N/A'}\n\n## High-Confidence Inferences\n- Current mailbox has a strong ${byInternalExternal.internal > byInternalExternal.external ? 'internal-collaboration' : 'external-collaboration'} communication signal.\n- Dominant intent candidates are suitable for downstream automation baselines in triage and summarization.\n- Repeated thread subjects indicate opportunities for thread-level state modeling in Phase 3.\n\n## Hypotheses To Confirm\n- Some newsletter/internal-update categories may overlap and need manual calibration with a labeled sample set.\n- Internal domain set currently uses a conservative static allowlist and may require extension for subsidiaries/partners.\n- Week-level distribution should be rechecked with a larger sample window for seasonality stability.\n\n## Outputs\n- \`runtime/validation/phase-1/mailbox-census.json\`\n- \`runtime/validation/phase-1/intent-distribution.yaml\`\n- \`runtime/validation/phase-1/contact-distribution.json\`\n- \`docs/validation/diagrams/phase-1-mailbox-overview.mmd\`\n- \`docs/validation/diagrams/phase-1-sender-network.mmd\`\n`;
fs.writeFileSync(`${docDir}/phase-1-report.md`, report);
NODE

echo "Phase 1 census completed."
echo "- runtime/validation/phase-1/mailbox-census.json"
echo "- runtime/validation/phase-1/intent-distribution.yaml"
echo "- runtime/validation/phase-1/contact-distribution.json"
echo "- docs/validation/phase-1-report.md"
echo "- docs/validation/diagrams/phase-1-mailbox-overview.mmd"
echo "- docs/validation/diagrams/phase-1-sender-network.mmd"
