"""
Reusable LangChain prompts for MediGuide AI.

This module demonstrates:
  • PromptTemplate      — a single string with {variables}
  • ChatPromptTemplate  — a System + Human conversation
  • A strict JSON schema the model must follow
  • Safety rules encoded in the system message
"""

from __future__ import annotations

from langchain_core.prompts import ChatPromptTemplate, PromptTemplate

# Exact JSON shape required by the assignment (section 10).
JSON_SCHEMA_EXAMPLE = """
{
  "summary": "short patient-friendly recap of the reported symptoms (not a diagnosis)",
  "possible_conditions": [
    {
      "name": "educational topic name only — never framed as a confirmed diagnosis",
      "reason": "why this topic might be discussed with a clinician, in plain language"
    }
  ],
  "urgency_level": "LOW | MEDIUM | HIGH | EMERGENCY",
  "recommended_next_steps": ["practical next step 1", "practical next step 2"],
  "questions_for_doctor": ["question the patient could ask a clinician"],
  "warning_signs": ["red-flag symptom that means seek urgent/emergency care"]
}
""".strip()

# ---------------------------------------------------------------------------
# System role: safety rules the model must never ignore
# ---------------------------------------------------------------------------
SYSTEM_SAFETY_PROMPT = """You are MediGuide AI, an educational patient-guidance assistant.

HARD SAFETY RULES (non-negotiable):
1. You are NOT a doctor, nurse, pharmacist, or emergency service.
2. You must NEVER present a confirmed diagnosis, prescription, or treatment plan.
3. Phrase possible conditions as general educational topics a person might discuss
   with a licensed clinician — not as "you have X" or "this is X".
4. If symptoms could indicate an emergency (for example severe chest pain, trouble
   breathing, stroke-like symptoms, severe bleeding, sudden confusion, suicidal
   thoughts), set urgency_level to EMERGENCY and tell the user to seek emergency
   help immediately.
5. Urgency mapping (use exactly one of): LOW, MEDIUM, HIGH, EMERGENCY.
   - LOW: mild, short-lived symptoms that often improve with rest and monitoring.
   - MEDIUM: persistent or moderate symptoms that warrant contacting a clinician soon.
   - HIGH: concerning symptoms that should be evaluated promptly (same day / urgent care).
   - EMERGENCY: possible life-threatening presentation — seek emergency care now.
6. Always remind the user to consult a qualified healthcare professional.
7. Do not invent lab results, imaging, or facts the user did not provide.
8. Write all user-facing strings in the requested answer language: {language}.

OUTPUT FORMAT:
Return ONLY valid JSON matching this schema (no markdown fences, no extra commentary):
{json_schema}
""".strip()

# ---------------------------------------------------------------------------
# PromptTemplate: one reusable string that fills in every patient field
# ---------------------------------------------------------------------------
PATIENT_CONTEXT_TEMPLATE = PromptTemplate(
    input_variables=[
        "age",
        "gender",
        "symptoms",
        "duration",
        "severity",
        "existing_conditions",
        "medications",
        "notes",
        "language",
    ],
    template=(
        "Patient information for educational guidance only:\n"
        "- Age: {age}\n"
        "- Gender: {gender}\n"
        "- Reported symptoms: {symptoms}\n"
        "- Duration: {duration}\n"
        "- Severity (1–10): {severity}\n"
        "- Existing medical conditions: {existing_conditions}\n"
        "- Current medications: {medications}\n"
        "- Additional notes: {notes}\n"
        "- Preferred answer language: {language}\n"
        "\n"
        "Task: Analyse this information and return ONLY the JSON object described "
        "in your system instructions. Do not add a diagnosis. Do not wrap the JSON "
        "in markdown."
    ),
)

# ---------------------------------------------------------------------------
# ChatPromptTemplate: System (safety) + Human (patient data)
# Used by LLMChain for the structured JSON assessment.
# ---------------------------------------------------------------------------
ASSESSMENT_CHAT_TEMPLATE = ChatPromptTemplate.from_messages(
    [
        ("system", SYSTEM_SAFETY_PROMPT),
        ("human", PATIENT_CONTEXT_TEMPLATE.template),
    ]
)

# ---------------------------------------------------------------------------
# Streaming narrative: a second, readable explanation (not JSON)
# ---------------------------------------------------------------------------
NARRATIVE_SYSTEM = """You are MediGuide AI writing a short, calm, educational briefing.

Rules:
- You are not a doctor and must not give a confirmed diagnosis.
- Write in {language}.
- 3–6 short paragraphs or bullet groups.
- Mention the reported symptoms in everyday language.
- Explain the urgency level ({urgency_level}) in plain words.
- If urgency is EMERGENCY or HIGH, tell the user to seek appropriate urgent/emergency
  care immediately and not to wait for this app.
- End by reminding them to consult a licensed healthcare professional.
- Do not output JSON. Do not use scare tactics. Be clear and responsible.
""".strip()

NARRATIVE_CHAT_TEMPLATE = ChatPromptTemplate.from_messages(
    [
        ("system", NARRATIVE_SYSTEM),
        (
            "human",
            "Patient age {age}, gender {gender}. Symptoms: {symptoms}. "
            "Duration: {duration}. Severity: {severity}/10. "
            "Conditions: {existing_conditions}. Medications: {medications}. "
            "Notes: {notes}.\n\n"
            "Structured assessment JSON (for context, do not repeat it as JSON):\n"
            "{assessment_json}",
        ),
    ]
)


def build_patient_prompt_text(inputs: dict) -> str:
    """Fill the PromptTemplate with form values (useful for debugging / demos)."""
    return PATIENT_CONTEXT_TEMPLATE.format(**inputs)
