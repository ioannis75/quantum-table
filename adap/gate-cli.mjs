// Usage: echo '{"agentRole":"agt_lab_agent","tool":"submit_qpu_job","args":{...}}' | node gate-cli.mjs
// Prints the ADAP PolicyDecision as JSON. Any error prints a BLOCK decision (fail closed).
import { POLICY, FINANCE_POLICY, FINANCE_ID } from './qpu-policy.mjs'
const enginePath = process.env.ADAP_ENGINE ?? '../vendor/agent-delegated-authority/packages/policy-engine/dist/index.js'
let out
try {
  const { evaluateToolCall } = await import(new URL(enginePath, import.meta.url))
  let raw = ''; for await (const c of process.stdin) raw += c
  const { agentRole, tool, args } = JSON.parse(raw)
  out = evaluateToolCall({ policy: agentRole === FINANCE_ID ? FINANCE_POLICY : POLICY, toolName: tool, toolArgs: args ?? {}, agentRole })
} catch (e) {
  out = { matched: false, action: 'BLOCK', ruleId: 'gate_error', reason: String(e?.message ?? e), alertSeverity: 'CRITICAL' }
}
console.log(JSON.stringify(out))
