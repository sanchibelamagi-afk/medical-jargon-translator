import json
import os
import sys
import re
import logging
from google.adk.workflow import Workflow, Edge, FunctionNode
from google.adk.agents.context import Context
from google.adk.events.event import Event
from google.adk.agents import LlmAgent
from google.adk.tools import AgentTool
from google.genai import types as genai_types
from app.config import config
from pydantic import BaseModel

from google.adk.tools.mcp_tool import McpToolset
from google.adk.tools.mcp_tool.mcp_session_manager import StdioConnectionParams
from mcp import StdioServerParameters

logger = logging.getLogger(__name__)

# ─── MCP Toolset ─────────────────────────────────────────────────────────────
server_path = os.path.join(os.path.dirname(__file__), "mcp_server.py")
mcp_toolset = McpToolset(
    connection_params=StdioConnectionParams(
        server_params=StdioServerParameters(
            command=sys.executable,
            args=[server_path],
        ),
    ),
)

# ─── Pydantic Schemas ─────────────────────────────────────────────────────────
class TranslationOutput(BaseModel):
    translation: str

class CoachOutput(BaseModel):
    advice: str

# ─── Sub-Agents ───────────────────────────────────────────────────────────────
translator_agent = LlmAgent(
    name="translator_agent",
    description="Translates complex medical jargon into simple plain English for a patient.",
    model=config.model,
    output_schema=TranslationOutput,
    output_key="translation",
    tools=[mcp_toolset],
    instruction="""You are a Medical Jargon Translator.
Translate complex medical terms, lab results, and clinical notes into
simple, reassuring plain language for a patient with no medical background.
Use the lookup_medical_term tool to look up any complex terms.
Do not give medical advice. Just translate the text."""
)

coach_agent = LlmAgent(
    name="coach_agent",
    description="Provides general lifestyle health tips based on translated medical information.",
    model=config.model,
    output_schema=CoachOutput,
    output_key="advice",
    instruction="""You are a Health Coach.
Based on the translated medical information, suggest 1-2 generic, helpful lifestyle tips.
ALWAYS end with: 'This is not medical advice. Please consult your doctor.'"""
)

# ─── AgentTools ───────────────────────────────────────────────────────────────
translator_tool = AgentTool(agent=translator_agent)
coach_tool = AgentTool(agent=coach_agent)

# ─── Orchestrator ─────────────────────────────────────────────────────────────
orchestrator = LlmAgent(
    name="orchestrator",
    model=config.model,
    instruction="""You are the coordinator of a medical translation system.
When a patient submits medical text, follow these steps IN ORDER:
1. Call translator_agent with the patient's text to get a plain-English translation.
2. Call coach_agent with the translation result to get health tips.
3. Combine both results into a warm, clear, helpful final response for the patient.
Never fabricate medical information.""",
    tools=[translator_tool, coach_tool],
)

# ─── Security & PII Checkpoint ────────────────────────────────────────────────
def _security_checkpoint(ctx: Context, node_input: str) -> Event:
    """Scrub PII and block injection / emergency keywords before hitting the LLM."""
    text = str(node_input)
    audit: dict = {"action": "allow", "reasons": []}

    # Emergency detection
    emergencies = ["suicide", "kill myself", "heart attack", "stroke", "emergency"]
    if any(kw in text.lower() for kw in emergencies):
        audit.update({"action": "block", "severity": "CRITICAL", "reason": "emergency keyword"})
        logger.warning(json.dumps(audit))
        return Event(
            output="⚠️ This tool is for educational translations only. For medical emergencies please call 911 immediately.",
            route="blocked",
        )

    # Prompt injection detection
    injections = ["ignore all previous", "system prompt", "you are now", "disregard"]
    if any(kw in text.lower() for kw in injections):
        audit.update({"action": "block", "severity": "WARNING", "reason": "injection attempt"})
        logger.warning(json.dumps(audit))
        return Event(output="🚫 Request blocked: security policy violation.", route="blocked")

    # PII redaction
    text = re.sub(r"\b\d{3}-\d{2}-\d{4}\b", "[REDACTED_SSN]", text)
    text = re.sub(r"\bMRN-\d+\b", "[REDACTED_MRN]", text)

    logger.info(json.dumps(audit))
    return Event(output=text, route="safe")


def _format_blocked(ctx: Context, node_input: str) -> Event:
    """Emit the blocked message as visible content in the UI."""
    msg = str(node_input)
    return Event(
        output=msg,
        content=genai_types.Content(
            role="model",
            parts=[genai_types.Part.from_text(text=msg)]
        ),
    )


# ─── Wrap plain functions as FunctionNodes ────────────────────────────────────
security_checkpoint = FunctionNode(func=_security_checkpoint, name="security_checkpoint")
format_blocked = FunctionNode(func=_format_blocked, name="format_blocked")

# ─── Workflow Graph ────────────────────────────────────────────────────────────
root_agent = Workflow(
    name="medical_jargon_translator",
    edges=[
        ("START", security_checkpoint),
        Edge(from_node=security_checkpoint, to_node=orchestrator, route="safe"),
        Edge(from_node=security_checkpoint, to_node=format_blocked, route="blocked"),
    ],
)
