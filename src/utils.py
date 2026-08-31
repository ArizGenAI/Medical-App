"""
Small helpers: safe JSON parsing, input formatting, and urgency display.

Invalid JSON must never crash the app — that is an assignment requirement.
"""

from __future__ import annotations

import json
import re
from typing import Any

# Canonical urgency labels from the assignment.
VALID_URGENCY = ("LOW", "MEDIUM", "HIGH", "EMERGENCY")

# Empty structure so the dashboard can still render after a parse failure.
EMPTY_ASSESSMENT: dict[str, Any] = {
    "summary": "",
    "possible_conditions": [],
    "urgency_level": "",
    "recommended_next_steps": [],
    "questions_for_doctor": [],
    "warning_signs": [],
}


def format_symptom_list(selected: list[str], extra_text: str) -> str:
    """Combine multiselect symptoms with optional free-text into one string."""
    extra_parts = [part.strip() for part in extra_text.replace(";", ",").split(",") if part.strip()]
    combined: list[str] = []
    for item in [*selected, *extra_parts]:
        if item and item not in combined:
            combined.append(item)
    return ", ".join(combined)


def text_or_none(value: str) -> str:
    """Use a readable placeholder when a text area is left blank."""
    cleaned = (value or "").strip()
    return cleaned if cleaned else "None reported"


def strip_json_fences(raw: str) -> str:
    """
    Models sometimes wrap JSON in ```json ... ``` even when told not to.
    Remove those fences and any leading/trailing chatter.
    """
    text = (raw or "").strip()
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text, flags=re.IGNORECASE)
    if fence:
        return fence.group(1).strip()

    # If extra prose surrounds the object, keep the outermost { ... }.
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return text[start : end + 1]
    return text


def _normalise_conditions(value: Any) -> list[dict[str, str]]:
    """Accept a list of objects or strings and return [{name, reason}, ...]."""
    if not isinstance(value, list):
        return []
    normalised: list[dict[str, str]] = []
    for item in value:
        if isinstance(item, dict):
            normalised.append(
                {
                    "name": str(item.get("name") or "Not specified"),
                    "reason": str(item.get("reason") or ""),
                }
            )
        elif isinstance(item, str) and item.strip():
            normalised.append({"name": item.strip(), "reason": ""})
    return normalised


def _as_string_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def normalise_assessment(data: dict[str, Any]) -> dict[str, Any]:
    """Fill missing keys and clamp urgency_level to the allowed set."""
    urgency = str(data.get("urgency_level") or "").strip().upper()
    if urgency not in VALID_URGENCY:
        urgency = "MEDIUM" if data else ""

    return {
        "summary": str(data.get("summary") or "").strip(),
        "possible_conditions": _normalise_conditions(data.get("possible_conditions")),
        "urgency_level": urgency,
        "recommended_next_steps": _as_string_list(data.get("recommended_next_steps")),
        "questions_for_doctor": _as_string_list(data.get("questions_for_doctor")),
        "warning_signs": _as_string_list(data.get("warning_signs")),
    }


def parse_assessment_json(raw: str) -> tuple[dict[str, Any] | None, str | None]:
    """
    Parse model output into the assignment JSON schema.

    Returns (assessment_dict, error_message).
    On failure, assessment_dict is None and error_message explains why.
    """
    cleaned = strip_json_fences(raw)
    if not cleaned:
        return None, "The model returned an empty response."

    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        return None, f"Could not parse JSON ({exc})."

    if not isinstance(parsed, dict):
        return None, "The model returned JSON that was not an object."

    return normalise_assessment(parsed), None


def urgency_style(level: str) -> dict[str, str]:
    """Colours and Streamlit-friendly labels for the urgency badge."""
    mapping = {
        "LOW": {
            "emoji": "🟢",
            "caption": "Low urgency — general monitoring advice only",
            "color": "#0f766e",
            "bg": "#ccfbf1",
        },
        "MEDIUM": {
            "emoji": "🟡",
            "caption": "Medium urgency — contact a clinician for advice",
            "color": "#a16207",
            "bg": "#fef9c3",
        },
        "HIGH": {
            "emoji": "🟠",
            "caption": "High urgency — seek prompt medical evaluation",
            "color": "#c2410c",
            "bg": "#ffedd5",
        },
        "EMERGENCY": {
            "emoji": "🔴",
            "caption": "Emergency — seek emergency help immediately",
            "color": "#991b1b",
            "bg": "#fee2e2",
        },
    }
    return mapping.get(
        (level or "").upper(),
        {
            "emoji": "⚪",
            "caption": "Urgency not determined",
            "color": "#334155",
            "bg": "#e2e8f0",
        },
    )


def validate_age(age_text: str) -> tuple[int | None, str | None]:
    """Age comes from text_input — make sure it is a sensible whole number."""
    raw = (age_text or "").strip()
    if not raw:
        return None, "Please enter the patient's age."
    try:
        age = int(raw)
    except ValueError:
        return None, "Age must be a whole number (for example 25)."
    if age < 0 or age > 120:
        return None, "Please enter an age between 0 and 120."
    return age, None
