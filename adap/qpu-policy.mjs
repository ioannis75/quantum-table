// QPU spending policy for Quantum Table, evaluated by ADAP's policy engine.
// Units: estimated QPU seconds for the job, and seconds already used in this build.
export const AGENT_ID = 'agt_lab_agent'
export const FINANCE_ID = 'agt_finance'

export const POLICY = {
  version: '1.0.0',
  policyName: 'quantum-table-qpu-authority',
  description: 'Lab agent may run emulators freely. Real QPU jobs: small ones are allowed, medium ones wait for a person, large ones or ones over the total budget are blocked.',
  targetAgents: [AGENT_ID],
  defaultAction: 'BLOCK',
  rules: [
    { ruleId: 'qpu_block_over_job_cap',   action: 'BLOCK',         condition: "tool.name == 'submit_qpu_job' && args.est_qpu_seconds > 60", alertSeverity: 'CRITICAL' },
    { ruleId: 'qpu_block_over_budget',    action: 'BLOCK',         condition: "tool.name == 'submit_qpu_job' && args.budget_after_seconds > 120", alertSeverity: 'CRITICAL' },
    { ruleId: 'qpu_block_paid_plan',      action: 'BLOCK',         condition: "tool.name == 'submit_qpu_job' && args.paid_plan == true", alertSeverity: 'CRITICAL' },
    { ruleId: 'qpu_medium_needs_human',   action: 'REQUIRE_HUMAN', condition: "tool.name == 'submit_qpu_job' && args.est_qpu_seconds > 10", alertSeverity: 'MEDIUM' },
    { ruleId: 'qpu_small_allow',          action: 'ALLOW',         condition: "tool.name == 'submit_qpu_job'", alertSeverity: 'LOW' },
    { ruleId: 'emulator_allow',           action: 'ALLOW',         condition: "tool.name == 'run_emulator'", alertSeverity: 'LOW' },
    { ruleId: 'read_results_allow',       action: 'ALLOW',         condition: "tool.name == 'read_past_job'", alertSeverity: 'LOW' },
  ],
}

// The Financial agent may quote and write shadow invoices. It can never move money or submit QPU jobs.
export const FINANCE_POLICY = {
  version: '1.0.0',
  policyName: 'quantum-table-finance-authority',
  description: 'Financial agent may quote prices and write shadow invoices. Charging, selling Qredits and payouts are blocked. Everything else is blocked.',
  targetAgents: [FINANCE_ID],
  defaultAction: 'BLOCK',
  rules: [
    { ruleId: 'charge_blocked',       action: 'BLOCK', condition: "tool.name == 'charge_customer'", alertSeverity: 'CRITICAL' },
    { ruleId: 'sell_qredits_blocked', action: 'BLOCK', condition: "tool.name == 'sell_qredits'", alertSeverity: 'CRITICAL' },
    { ruleId: 'payout_blocked',       action: 'BLOCK', condition: "tool.name == 'payout'", alertSeverity: 'CRITICAL' },
    { ruleId: 'quote_allow',          action: 'ALLOW', condition: "tool.name == 'quote_qpu_job'", alertSeverity: 'LOW' },
    { ruleId: 'shadow_invoice_allow', action: 'ALLOW', condition: "tool.name == 'write_shadow_invoice'", alertSeverity: 'LOW' },
  ],
}
