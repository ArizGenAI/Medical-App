"""
Rule-based safety checks that run even if the LLM is slow or wrong.

These rules do not diagnose. They only raise educational red flags and
validate form input so the app fails clearly instead of crashing.
"""

from __future__ import annotations

import re
from typing import Any

# Phrases that should never be ignored in an educational prototype.
EMERGENCY_PATTERNS = [
    r"chest pain",
    r"crushing (chest|pain)",
    r"pressure in (the )?chest",
    r"short(ness)? of breath",
    r"can'?t breathe",
    r"cannot breathe",
    r"difficulty breathing",
    r"not breathing",
    r"suicidal",
    r"kill myself",
    r"want to die",
    r"stroke",
    r"face droop",
    r"slurred speech",
    r"one[- ]sided weakness",
    r"severe bleeding",
    r"coughing (up )?blood",
    r"vomiting blood",
    r"unconscious",
    r"fainting",
    r"seizure",
    r"anaphylaxis",
    r"throat swell",
    r"blue lips",
    r"sudden confusion",
    r"worst headache",
    r"\bchest\b.*\bpain\b",
    r"\bpain\b.*\bchest\b",
]

URGENCY_RANK = {"LOW": 1, "MEDIUM": 2, "HIGH": 3, "EMERGENCY": 4}
RANK_TO_URGENCY = {1: "LOW", 2: "MEDIUM", 3: "HIGH", 4: "EMERGENCY"}

MAX_TEXT_LEN = 4000


def detect_emergency_phrases(*parts: str) -> list[str]:
    """Return matched emergency-like phrases found in free text."""
    blob = " ".join(p or "" for p in parts).lower()
    hits: list[str] = []
    for pattern in EMERGENCY_PATTERNS:
        match = re.search(pattern, blob, flags=re.IGNORECASE)
        if match:
            snippet = match.group(0)
            if snippet not in hits:
                hits.append(snippet)
    return hits


def merge_urgency(model_level: str, emergency_hits: list[str], severity: int) -> str:
    """
    Never let a rule-based red flag stay below HIGH/EMERGENCY.
    The model still runs; this only raises the displayed educational level.
    """
    rank = URGENCY_RANK.get((model_level or "").upper(), 0)
    if emergency_hits:
        floor = 4 if severity >= 7 else 3
        rank = max(rank, floor)
        # Classic red-flag combinations stay at EMERGENCY.
        joined = " ".join(emergency_hits).lower()
        if any(k in joined for k in ("chest", "breathe", "suicid", "stroke", "unconscious", "blood")):
            rank = max(rank, 4)
    return RANK_TO_URGENCY.get(rank, model_level or "")


def validate_form_fields(
    age_text: str,
    symptoms_text: str,
    extra: str,
    conditions: str,
    medications: str,
    notes: str,
) -> list[str]:
    """Return a list of human-readable validation errors (empty means OK)."""
    errors: list[str] = []
    from src.utils import validate_age

    _, age_error = validate_age(age_text)
    if age_error:
        errors.append(age_error)
    if not (symptoms_text or "").strip() and not (extra or "").strip():
        errors.append("symptoms_required")
    for label, value in (
        ("Additional symptoms", extra),
        ("Existing conditions", conditions),
        ("Medications", medications),
        ("Notes", notes),
    ):
        if value and len(value) > MAX_TEXT_LEN:
            errors.append(f"{label} is too long (max {MAX_TEXT_LEN} characters).")
    return errors


def completeness_score(inputs: dict[str, Any], emergency_hits: list[str]) -> float:
    """
    Heuristic 0–1 score: how complete the *input* is.
    This is NOT diagnostic confidence and must be labelled as such in the UI.
    """
    score = 0.35
    symptoms = [s.strip() for s in (inputs.get("symptoms") or "").split(",") if s.strip()]
    if len(symptoms) >= 1:
        score += 0.15
    if len(symptoms) >= 3:
        score += 0.10
    if inputs.get("duration") and inputs.get("duration") != "Not sure":
        score += 0.10
    try:
        severity = int(inputs.get("severity") or 0)
        if 1 <= severity <= 10:
            score += 0.08
    except ValueError:
        pass
    if inputs.get("existing_conditions") not in ("", "None reported"):
        score += 0.07
    if inputs.get("medications") not in ("", "None reported"):
        score += 0.05
    if inputs.get("notes") not in ("", "None reported"):
        score += 0.05
    if emergency_hits:
        score += 0.05  # more detail was present, still not certainty
    return round(min(0.92, max(0.20, score)), 2)
