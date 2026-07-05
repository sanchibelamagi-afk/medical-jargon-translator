# Submission Write-Up — Medical Jargon Translator

## Problem Statement

Millions of patients receive medical reports, lab results, and discharge summaries filled with clinical terminology they don't understand. Terms like "hyperlipidemia," "arrhythmia," or "myocardial infarction" are alarming when you don't know what they mean. Patients are left confused, anxious, and unable to make informed decisions about their own health — until their next appointment.

The **Medical Jargon Translator** addresses this gap by providing an instant, plain-language translation of complex medical text, coupled with general wellness guidance, so patients can understand and act on their health information confidently and safely.

---

## Solution Architecture

```
  Patient Input (START)
        │
        ▼
┌───────────────────────────────┐
│  🛡️  Security Checkpoint       │  ← PII scrub (SSN, MRN)
│   security_checkpoint node    │    Injection detection
│   [ORANGE — audit every call] │    Emergency keyword guard
└───────────┬───────────────────┘
            │
   ┌─────────┴──────────┐
   │ route="safe"       │ route="blocked"
   ▼                    ▼
┌──────────────────┐  ┌──────────────────────┐
│  🧠 Orchestrator  │  │  ⛔ format_blocked   │
│  (LlmAgent)      │  │  (blocked message)   │
│                  │  └──────────────────────┘
│  delegates to:   │
│  ┌────────────┐  │        ┌──────────────────────────┐
│  │ translator │──┼───────▶│   MCP Server (stdio)     │
│  │  _agent    │  │        │  • lookup_medical_term   │
│  └────────────┘  │        │  • find_local_specialist │
│  ┌────────────┐  │        │  • get_drug_interactions │
│  │  coach     │──┼───────▶└──────────────────────────┘
│  │  _agent    │  │
│  └────────────┘  │
└──────────────────┘
```

---

## Concepts Used

| Concept | Where | File |
|---------|-------|------|
| **ADK Workflow graph** | Orchestrates the end-to-end flow | `app/agent.py` |
| **LlmAgent** | `translator_agent`, `coach_agent`, `orchestrator` | `app/agent.py` |
| **AgentTool** | Orchestrator delegates to sub-agents as tools | `app/agent.py` |
| **FunctionNode** | Wraps `security_checkpoint` and `format_blocked` | `app/agent.py` |
| **Edge (routed)** | Routes `safe`/`blocked` from security node | `app/agent.py` |
| **MCP Server** | Provides domain-specific medical tools via stdio | `app/mcp_server.py` |
| **MCPToolset** | Connects agents to MCP tools | `app/agent.py` |
| **ctx.state** | Shares `original_text` and `draft_response` between nodes | `app/agent.py` |
| **Agents CLI** | Scaffolded project structure | `agents-cli-manifest.yaml` |
| **config.py** | Universal config with env-based model selection | `app/config.py` |

---

## Security Design

| Control | Implementation | Why It Matters |
|---------|---------------|----------------|
| **PII Scrubbing** | Regex removes SSNs (`\d{3}-\d{2}-\d{4}`) and MRNs (`MRN-\d+`) | Medical records contain highly sensitive identifiers — these must never reach the LLM |
| **Prompt Injection Detection** | Keyword scan for "ignore all previous", "system prompt", "you are now", "disregard" | Prevents adversarial users from hijacking the system's instructions |
| **Emergency Keyword Guard** | Detects "heart attack", "stroke", "suicide", "emergency" | Redirects medical emergencies to 911 immediately rather than providing a delayed LLM response |
| **Structured Audit Log** | Every security decision emits JSON `{action, severity, reasons}` to stdout | Full traceability for compliance and debugging |

All checks run **before** any LLM call via the `security_checkpoint` FunctionNode — the system never sends unsafe or PII-containing content to the model.

---

## MCP Server Design

File: `app/mcp_server.py` — Uses FastMCP (stdio transport)

| Tool | Purpose |
|------|---------|
| `lookup_medical_term(term)` | Returns plain-language definitions for common medical terms (e.g. "hyperlipidemia" → "high cholesterol") |
| `find_local_specialist(zip_code, specialty)` | Suggests nearby specialists by location and specialty type |
| `get_drug_interactions(drug1, drug2)` | Checks for known interactions between two medications |

The `translator_agent` uses `lookup_medical_term` to ground translations in known definitions. The `coach_agent` uses all three tools to provide contextual health guidance and referrals.

---

## HITL Flow

The current implementation includes a `security_checkpoint` as an implicit human-safety gate — emergency content is immediately routed to a safe message without LLM involvement, protecting patients from receiving harmful AI-generated advice in a crisis.

A full Human-in-the-Loop review gate (`RequestInput`) was prototyped and can be re-enabled for clinical settings where a human clinician needs to approve the translation before it reaches the patient.

---

## Demo Walkthrough

Refer to the three sample test cases in `README.md`:

1. **Test Case 1** — Normal translation of "hyperlipidemia" and "arrhythmia" → demonstrates the full multi-agent pipeline
2. **Test Case 2** — PII scrubbing of SSN and MRN → demonstrates the security node's redaction
3. **Test Case 3** — Prompt injection attempt → demonstrates the block route and audit log

---

## Impact / Value Statement

**Who benefits:** Patients who receive complex medical documents — especially those with limited medical literacy, non-native English speakers, and elderly patients navigating the healthcare system alone.

**Why it matters:** Health literacy directly impacts patient outcomes. Studies show that patients who understand their diagnoses are more likely to follow treatment plans and attend follow-up care. This agent acts as a 24/7 health literacy companion — not a replacement for doctors, but a bridge between clinical language and patient understanding.

**Why ADK:** The multi-agent architecture allows each concern (translation accuracy, lifestyle coaching, security) to be independently developed, tested, and improved. The MCP server pattern makes it easy to swap in a real medical terminology database or EHR integration in production.
