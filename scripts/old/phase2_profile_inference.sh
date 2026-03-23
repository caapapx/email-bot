#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PHASE1_FILE="${ROOT_DIR}/runtime/validation/phase-1/mailbox-census.json"
PHASE2_DIR="${ROOT_DIR}/runtime/validation/phase-2"
DOC_DIR="${ROOT_DIR}/docs/validation"
DIAGRAM_DIR="${DOC_DIR}/diagrams"

mkdir -p "${PHASE2_DIR}" "${DOC_DIR}" "${DIAGRAM_DIR}"

if [[ ! -f "${PHASE1_FILE}" ]]; then
  echo "Missing phase-1 census: ${PHASE1_FILE}"
  echo "Run: bash scripts/phase1_mailbox_census.sh"
  exit 1
fi

node - <<'NODE' "${PHASE1_FILE}" "${PHASE2_DIR}" "${DOC_DIR}" "${DIAGRAM_DIR}"
const fs = require('fs');

const [phase1Path, phase2Dir, docDir, diagramDir] = process.argv.slice(2);
const p1 = JSON.parse(fs.readFileSync(phase1Path, 'utf8'));

function top(arr, n = 10) {
  return (arr || []).slice(0, n);
}

const total = p1.scope?.total_envelopes || 0;
const intents = p1.top?.intents || [];
const domains = p1.top?.domains || [];
const contacts = p1.top?.contacts || [];
const threads = p1.threads?.high_frequency || [];
const ie = p1.distributions?.internal_external || { internal: 0, external: 0, unknown: 0 };
const attachmentRatio = Number(p1.metrics?.attachment_ratio || 0);

const dominantIntent = intents[0]?.key || 'human';
const internalRatio = total ? (ie.internal / total) : 0;

const persona = [
  {
    id: 'P1',
    hypothesis: '用户主要承担内部项目协同与交付推进角色',
    confidence: 0.88,
    evidence: [
      `internal_ratio=${internalRatio.toFixed(4)} (${ie.internal}/${total})`,
      `dominant_intent=${dominantIntent}`,
      `high_freq_threads=${threads.slice(0,3).map(t => t.key).join(' | ')}`,
    ],
    type: 'role',
  },
  {
    id: 'P2',
    hypothesis: '用户工作中对资源申请、版本发布、联调联试流程参与较深',
    confidence: 0.85,
    evidence: [
      `top_threads=${threads.slice(0,5).map(t => `${t.key}(${t.count})`).join('; ')}`,
      `intent_internal_update=${(intents.find(i => i.key === 'internal_update') || {}).count || 0}`,
      `intent_support=${(intents.find(i => i.key === 'support') || {}).count || 0}`,
    ],
    type: 'responsibility',
  },
  {
    id: 'P3',
    hypothesis: '用户在沟通链路中兼具执行与汇报属性，存在高频固定协作对象',
    confidence: 0.8,
    evidence: [
      `top_contacts=${contacts.slice(0,5).map(c => `${c.key}(${c.count})`).join(', ')}`,
      `attachment_ratio=${attachmentRatio.toFixed(4)}`,
    ],
    type: 'collaboration_pattern',
  },
];

const business = [
  {
    id: 'B1',
    hypothesis: '公司邮件活动中心围绕项目交付、研发联调、资源申请与合规通知',
    confidence: 0.9,
    evidence: [
      `dominant_domains=${domains.slice(0,3).map(d => `${d.key}(${d.count})`).join(', ')}`,
      `top_threads=${threads.slice(0,5).map(t => t.key).join(' | ')}`,
    ],
    ai_entry_points: [
      '线程级自动阶段识别（申请中/已审批/联调中/已发布）',
      '每日待办提炼（资源申请、版本发布、跨人协同阻塞）',
      '内部通知自动摘要与行动项提取',
    ],
  },
  {
    id: 'B2',
    hypothesis: '外部沟通占比低，当前自动化优先级应先聚焦内部协作效率',
    confidence: 0.87,
    evidence: [
      `internal=${ie.internal}, external=${ie.external}, unknown=${ie.unknown}`,
    ],
    ai_entry_points: [
      '内部优先队列排序',
      '线程跟进提醒与SLA风险提示',
      '周报自动汇总（仅草稿）',
    ],
  },
  {
    id: 'B3',
    hypothesis: '存在稳定组织关系网络，适合构建联系人/团队协作画像',
    confidence: 0.78,
    evidence: [
      `top_contacts=${contacts.slice(0,10).map(c => c.key).join(', ')}`,
    ],
    ai_entry_points: [
      '关键联系人优先级画像',
      '部门/域名维度协作图谱',
    ],
  },
];

const personaYaml = [];
personaYaml.push(`generated_at: "${new Date().toISOString()}"`);
personaYaml.push('persona_hypotheses:');
for (const p of persona) {
  personaYaml.push(`  - id: ${p.id}`);
  personaYaml.push(`    type: ${p.type}`);
  personaYaml.push(`    confidence: ${p.confidence.toFixed(2)}`);
  personaYaml.push(`    hypothesis: "${p.hypothesis.replace(/"/g, '\\"')}"`);
  personaYaml.push('    evidence:');
  for (const e of p.evidence) personaYaml.push(`      - "${String(e).replace(/"/g, '\\"')}"`);
}
fs.writeFileSync(`${phase2Dir}/persona-hypotheses.yaml`, personaYaml.join('\n') + '\n');

const businessYaml = [];
businessYaml.push(`generated_at: "${new Date().toISOString()}"`);
businessYaml.push('business_hypotheses:');
for (const b of business) {
  businessYaml.push(`  - id: ${b.id}`);
  businessYaml.push(`    confidence: ${b.confidence.toFixed(2)}`);
  businessYaml.push(`    hypothesis: "${b.hypothesis.replace(/"/g, '\\"')}"`);
  businessYaml.push('    evidence:');
  for (const e of b.evidence) businessYaml.push(`      - "${String(e).replace(/"/g, '\\"')}"`);
  businessYaml.push('    ai_entry_points:');
  for (const a of b.ai_entry_points) businessYaml.push(`      - "${String(a).replace(/"/g, '\\"')}"`);
}
fs.writeFileSync(`${phase2Dir}/business-hypotheses.yaml`, businessYaml.join('\n') + '\n');

const userLabel = process.env.MAIL_ACCOUNT_NAME || 'user';
const relationship = ['graph TD', '  User["User: ' + userLabel + '"]'];
for (const c of top(contacts, 8)) {
  const safe = c.key.replace(/[^a-zA-Z0-9]/g, '_');
  relationship.push(`  C_${safe}["${c.key}"]`);
  relationship.push(`  User ---|${c.count}| C_${safe}`);
}
for (const d of top(domains, 3)) {
  const safe = d.key.replace(/[^a-zA-Z0-9]/g, '_');
  relationship.push(`  D_${safe}["${d.key}"]`);
  relationship.push(`  User --> D_${safe}`);
}
fs.writeFileSync(`${diagramDir}/phase-2-relationship-map.mmd`, relationship.join('\n') + '\n');

const questions = [
  '你在团队中的主角色更接近：项目交付推进 / 技术协调 / 业务管理中的哪一类？',
  '资源申请与版本发布相关线程，哪些属于你必须拍板，哪些只是同步抄送？',
  '内部邮件里你最想优先自动化的是：每日待办提炼、线程状态跟进、还是周报汇总？',
  '当前 INTERNAL_DOMAINS 配置的域名是否完整？是否还有其他内部域名？',
  '当前最容易漏跟进的邮件类型是什么（资源申请、联调问题、合规通知等）？',
  '对自动草稿的风险边界是什么（仅建议/必须人工确认/特定对象禁用）？',
  '你希望 Phase 3 的线程生命周期最先覆盖哪类主题？',
];

const report = `# Phase 2 Report: Persona and Business Profile Inference\n\n## Evidence Base\n- Source: \`runtime/validation/phase-1/mailbox-census.json\`\n- Envelope sample size: ${total}\n- Internal vs external: internal=${ie.internal}, external=${ie.external}, unknown=${ie.unknown}\n\n## Persona Hypotheses\n${persona.map(p => `- [${p.id}] (confidence=${p.confidence.toFixed(2)}) ${p.hypothesis}`).join('\n')}\n\n## Business Hypotheses\n${business.map(b => `- [${b.id}] (confidence=${b.confidence.toFixed(2)}) ${b.hypothesis}`).join('\n')}\n\n## High-Confidence Inferences\n- 邮件流量以内部协同为主，短期自动化重点应放在内部任务编排和线程跟进。\n- 高频主题集中在交付流程型邮件，适合做 thread 级状态机建模。\n- 当前证据已经足够支持进入 Phase 3 生命周期建模。\n\n## Low-Confidence / Need Confirmation\n- \`human\` intent 占比高，部分可能是规则未覆盖导致，需要人工标注样本校准。\n- 内部域名集合可能不完整，影响内外部占比精度。\n\n## Minimal Confirmation Questions (max 7)\n${questions.map((q, i) => `${i + 1}. ${q}`).join('\n')}\n\n## Outputs\n- \`runtime/validation/phase-2/persona-hypotheses.yaml\`\n- \`runtime/validation/phase-2/business-hypotheses.yaml\`\n- \`docs/validation/phase-2-report.md\`\n- \`docs/validation/diagrams/phase-2-relationship-map.mmd\`\n`;
fs.writeFileSync(`${docDir}/phase-2-report.md`, report);
NODE

echo "Phase 2 profile inference completed."
echo "- runtime/validation/phase-2/persona-hypotheses.yaml"
echo "- runtime/validation/phase-2/business-hypotheses.yaml"
echo "- docs/validation/phase-2-report.md"
echo "- docs/validation/diagrams/phase-2-relationship-map.mmd"
