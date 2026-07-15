// ============================================================================
// V1 REFERENCE-ONLY — NOT the executed research path.
// The authoritative weekly-research flow is the candidate-only v2 runbook at
// Research/engine/research-brief.md, driven by Research/engine/new-candidate.ps1.
// This harness — together with Research/engine/state.json and changelog.md — is
// retained for reference only. It is NOT invoked by /weekly-research, and its
// 12-topic TOPICS list is historical (state.json tracks the 8 v1 topics). Do not
// treat this file as the source of truth for current run behavior.
// ============================================================================
//
// Candidate-only research workflow for a Workflow-compatible Claude runtime.
// This file does not write stable guidance. The caller must persist the returned
// artifacts only inside Research/candidate-packages/<run-id>/.

export const meta = {
  name: 'agentic-bp-candidate-research',
  description: 'Research, independently verify, and package atomic claims without modifying stable rules',
  phases: [
    { title: 'Research', detail: 'registered sources first, then bounded discovery' },
    { title: 'Verify', detail: 'one independent verdict for every atomic claim' },
    { title: 'Package', detail: 'candidate claims, source patch, eval plan, linked report' },
  ],
}

const TOPICS = [
  'agentic-loops', 'hooks', 'session-management', 'repo-setup',
  'verification-self-checking', 'subagent-orchestration',
  'workstream-logging', 'permissions-security', 'knowledge-routing',
  'objective-integrity', 'windows-onedrive', 'human-productivity',
]

const selected = args?.topics?.length ? args.topics : TOPICS
const registeredSources = args?.registeredSources || []

const sourceSchema = {
  type: 'object', additionalProperties: false,
  properties: {
    id: { type: 'string' }, title: { type: 'string' }, url: { type: 'string' },
    tier: { type: 'integer', minimum: 1, maximum: 5 }, accessed_at: { type: 'string' },
  }, required: ['id', 'title', 'url', 'tier', 'accessed_at'],
}

const researchSchema = {
  type: 'object', additionalProperties: false,
  properties: {
    topic: { type: 'string' },
    claims: { type: 'array', items: { type: 'object', additionalProperties: false, properties: {
      id: { type: 'string' }, statement: { type: 'string' }, applicability: { type: 'string' },
      candidate_guidance: { type: 'string' }, sources: { type: 'array', minItems: 1, items: sourceSchema },
      version_sensitive: { type: 'boolean' },
    }, required: ['id', 'statement', 'applicability', 'candidate_guidance', 'sources', 'version_sensitive'] } },
    proposed_sources: { type: 'array', items: sourceSchema },
    open_questions: { type: 'array', items: { type: 'string' } },
  }, required: ['topic', 'claims', 'proposed_sources', 'open_questions'],
}

const verifySchema = {
  type: 'object', additionalProperties: false,
  properties: {
    topic: { type: 'string' },
    verdicts: { type: 'array', items: { type: 'object', additionalProperties: false, properties: {
      claim_id: { type: 'string' },
      verdict: { type: 'string', enum: ['confirmed', 'corrected', 'unsupported', 'refuted', 'expired'] },
      corrected_statement: { type: 'string' }, corrected_guidance: { type: 'string' },
      evidence_sources: { type: 'array', items: sourceSchema },
      confidence: { type: 'string', enum: ['high', 'medium', 'low'] },
      reason: { type: 'string' }, expires_at: { type: 'string' },
    }, required: ['claim_id', 'verdict', 'corrected_statement', 'corrected_guidance', 'evidence_sources', 'confidence', 'reason', 'expires_at'] } },
  }, required: ['topic', 'verdicts'],
}

function researchPrompt(topic) {
  return `Research atomic claims for topic ${topic}.

Start with this durable registered-source snapshot:
${JSON.stringify(registeredSources)}

Recheck registered sources that are due. Only then perform bounded discovery for new sources. Official docs/changelogs and primary research outrank media and practitioner signals. YouTube, podcasts and social profiles may produce leads but cannot alone establish version-sensitive mechanics or mandatory security policy.

Return atomic, independently verifiable claims. Give every claim a unique ID, applicability/version context, direct sources and candidate guidance. Do not write stable rules.`
}

function verifyPrompt(research) {
  return `Independently verify EVERY claim below. Do not sample only the important ones.

${JSON.stringify(research)}

For each claim ID return exactly one verdict. Version-sensitive mechanics require a current tier-1 source. Citations must directly support the statement. Correct imprecise claims; reject unsupported, refuted or expired claims. Media/practitioner material is a lead, not sufficient technical authority.`
}

phase('Research')
const researched = await parallel(selected.map(topic => () => agent(researchPrompt(topic), {
  label: `research:${topic}`, phase: 'Research', agentType: 'general-purpose', schema: researchSchema,
})))

if (researched.length !== selected.length || researched.some(x => !x)) {
  throw new Error(`Coverage failure: expected ${selected.length} research results, received ${researched.filter(Boolean).length}`)
}

phase('Verify')
const verified = await parallel(researched.map(item => () => agent(verifyPrompt(item), {
  label: `verify:${item.topic}`, phase: 'Verify', agentType: 'general-purpose', schema: verifySchema,
})))

if (verified.length !== researched.length || verified.some(x => !x)) {
  throw new Error('Verification coverage failure')
}

const accepted = []
const rejected = []
for (let i = 0; i < researched.length; i++) {
  const research = researched[i]
  const verification = verified[i]
  const verdictById = new Map(verification.verdicts.map(v => [v.claim_id, v]))
  for (const claim of research.claims) {
    const v = verdictById.get(claim.id)
    if (!v) throw new Error(`Missing verifier verdict for ${claim.id}`)
    const record = {
      id: claim.id, topic: research.topic,
      statement: v.verdict === 'corrected' ? v.corrected_statement : claim.statement,
      applicability: claim.applicability,
      sources: v.evidence_sources,
      verification_verdict: v.verdict, confidence: v.confidence,
      reason: v.reason, expires_at: v.expires_at,
      candidate_guidance: v.verdict === 'corrected' ? v.corrected_guidance : claim.candidate_guidance,
    }
    if (v.verdict === 'confirmed' || v.verdict === 'corrected') accepted.push(record)
    else rejected.push(record)
  }
}

phase('Package')
const report = await agent(`Write a candidate research report from the accepted and rejected claim ledgers below.

ACCEPTED:
${JSON.stringify(accepted)}

REJECTED:
${JSON.stringify(rejected)}

State clearly that this is not stable guidance. Cover scope, method, claim coverage, findings, proposed changes, risks, eval/ablation plan and rollback. End with a complete "## Sources" appendix containing clickable Markdown links for every unique source, with tier and access date. Do not claim every source is primary unless that is literally true.`, {
  label: 'candidate:report', phase: 'Package', agentType: 'general-purpose',
})

return {
  status: 'awaiting-eval',
  topics: selected,
  claims: accepted,
  rejectedClaims: rejected,
  proposedSources: researched.flatMap(x => x.proposed_sources),
  report,
  stableChangesApplied: false,
  commitOrPushPerformed: false,
}
