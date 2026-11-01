"""WorkforceOS Copilot prompt registry — one pack per vertical."""

from dataclasses import dataclass

from app.core.verticals import DEFAULT_VERTICAL, normalize_vertical


@dataclass(frozen=True)
class CopilotPack:
    system_prompt: str
    suggested_questions: tuple[str, ...]
    executive_questions: tuple[str, ...]


_GENERIC_SYSTEM = """You are WorkforceOS Copilot, an operations assistant for workforce-based service organizations.

Rules:
1. Answer ONLY using the OPERATIONAL DATA JSON in the user message. Never invent counts, names, or percentages.
2. If the data is insufficient for the question, say what is missing and what is available.
3. Be concise, professional, and actionable. Use short paragraphs and bullet lists.
4. Do not provide medical or legal advice unless the data explicitly supports operational guidance.
5. End with 1–3 concrete recommended next steps when appropriate."""

_ELDER_CARE_SYSTEM = """You are WorkforceOS Copilot for the Elder Care vertical, an operations assistant for home care agencies in India.

Rules:
1. Answer ONLY using the OPERATIONAL DATA JSON in the user message. Never invent counts, names, or percentages.
2. If the data is insufficient for the question, say what is missing and what is available.
3. Be concise, professional, and actionable. Use short paragraphs and bullet lists.
4. When comparing months, use assignments.placement_starts_* and assignments.started_* fields explicitly.
5. For attrition or resignation risk: explain that attrition ML is not available; cite proxies (bench size, verification gaps, open incidents) only if present in data.
6. Do not provide medical or legal advice. Focus on workforce operations.
7. End with 1–3 concrete recommended next steps when appropriate."""

_ELDER_SUGGESTED = (
    "Why are placements down this month compared to last month?",
    "Which caregivers are ready for deployment right now?",
    "How many elders still need an active caregiver assignment?",
    "What is our bench size and workforce utilization?",
    "Which cities have the largest bench population?",
    "Summarize our recruiting pipeline and overdue follow-ups.",
    "What should operations prioritize this week?",
    "Give me a short executive summary of workforce health.",
)

_ELDER_EXECUTIVE = (
    "Why is bench cost increasing?",
    "Which city has the largest bench population?",
    "Who is ready for placement right now?",
    "How can we reduce workforce carrying costs this month?",
    "What should we recruit based on current demand?",
    "Give me an executive summary of agency performance.",
)

_GENERIC_SUGGESTED = (
    "What is our bench size and workforce utilization?",
    "Which workers are ready for deployment right now?",
    "Summarize our recruiting pipeline and overdue follow-ups.",
    "What should operations prioritize this week?",
    "Give me a short executive summary of workforce health.",
)

_GENERIC_EXECUTIVE = (
    "Why is bench cost increasing?",
    "Who is ready for placement right now?",
    "How can we reduce workforce carrying costs this month?",
    "Give me an executive summary of agency performance.",
)

PACKS: dict[str, CopilotPack] = {
    "ELDER_CARE": CopilotPack(
        system_prompt=_ELDER_CARE_SYSTEM,
        suggested_questions=_ELDER_SUGGESTED,
        executive_questions=_ELDER_EXECUTIVE,
    ),
    "SECURITY": CopilotPack(
        system_prompt=_GENERIC_SYSTEM,
        suggested_questions=_GENERIC_SUGGESTED,
        executive_questions=_GENERIC_EXECUTIVE,
    ),
    "HOUSEKEEPING": CopilotPack(
        system_prompt=_GENERIC_SYSTEM,
        suggested_questions=_GENERIC_SUGGESTED,
        executive_questions=_GENERIC_EXECUTIVE,
    ),
    "DRIVER_SERVICES": CopilotPack(
        system_prompt=_GENERIC_SYSTEM,
        suggested_questions=_GENERIC_SUGGESTED,
        executive_questions=_GENERIC_EXECUTIVE,
    ),
    "HOME_HEALTHCARE": CopilotPack(
        system_prompt=_GENERIC_SYSTEM,
        suggested_questions=_GENERIC_SUGGESTED,
        executive_questions=_GENERIC_EXECUTIVE,
    ),
}


def get_copilot_pack(vertical: str | None) -> CopilotPack:
    key = normalize_vertical(vertical)
    return PACKS.get(key, PACKS[DEFAULT_VERTICAL])
