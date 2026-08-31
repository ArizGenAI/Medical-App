"""
Application settings and form options.

Loads the OpenAI API key from a local .env file using python-dotenv.
The key is NEVER hard-coded in source files.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# Project root = folder that contains app.py (one level above src/)
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Load .env from the project root so Streamlit finds it regardless of cwd.
load_dotenv(PROJECT_ROOT / ".env")

APP_NAME = "MediGuide AI"
APP_TAGLINE = "AI-Powered Medical Symptom Assessment and Patient Guidance Assistant"

# Short label used in the UI — this is an educational prototype, not a clinic.
EDUCATIONAL_LABEL = "Educational AI prototype — not a doctor, diagnosis, or emergency service."

DISCLAIMER_SHORT = (
    "MediGuide AI is an educational tool only. It is NOT a replacement for a licensed "
    "doctor, professional diagnosis, emergency service, or medical treatment. It never "
    "provides a confirmed diagnosis. Always consult a qualified healthcare professional. "
    "If this is an emergency, call your local emergency number immediately."
)

DISCLAIMER_LONG = (
    "IMPORTANT MEDICAL & SAFETY NOTICE: This application is an educational AI prototype "
    "built for a LangChain programming assignment. Output is general information only and "
    "may be incomplete or incorrect. MediGuide AI must never be used as a medical device, "
    "to confirm a diagnosis, to start or stop medication, or to delay seeking care. "
    "Possible conditions listed are for learning purposes — they are not diagnoses. "
    "Seek emergency help for severe chest pain, trouble breathing, sudden weakness, "
    "severe bleeding, suicidal thoughts, or any situation that feels like an emergency."
)

DEFAULT_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

# Models the sidebar can switch between (all OpenAI chat models).
AVAILABLE_MODELS = [
    "gpt-4o-mini",
    "gpt-4o",
    "gpt-4.1-mini",
    "gpt-4.1",
]

GENDER_OPTIONS = [
    "Prefer not to say",
    "Female",
    "Male",
    "Non-binary",
    "Other",
]

# Common symptoms for the multiselect. Users can also type extra symptoms.
SYMPTOM_OPTIONS = [
    "Fever",
    "Chills",
    "Cough",
    "Sore throat",
    "Runny nose",
    "Nasal congestion",
    "Sneezing",
    "Headache",
    "Severe headache",
    "Fatigue",
    "Muscle aches",
    "Joint pain",
    "Nausea",
    "Vomiting",
    "Diarrhea",
    "Abdominal pain",
    "Chest pain",
    "Shortness of breath",
    "Wheezing",
    "Dizziness",
    "Palpitations",
    "Rash",
    "Swelling",
    "Loss of smell or taste",
    "Difficulty swallowing",
    "Back pain",
    "Confusion",
    "Fainting or near-fainting",
]

DURATION_OPTIONS = [
    "Less than 24 hours",
    "1–3 days",
    "4–7 days",
    "1–2 weeks",
    "More than 2 weeks",
    "Ongoing / chronic",
    "Not sure",
]

# Required language plus extras (bonus: more than the minimum set).
LANGUAGE_OPTIONS = [
    "English",
    "Urdu",
    "Hindi",
    "Arabic",
    "Spanish",
    "French",
]

CACHE_OPTIONS = {
    "Off (always call the API)": "off",
    "In-memory (fast, RAM only)": "memory",
    "SQLite (persists on disk)": "sqlite",
}

# Where the SQLite cache file is stored (survives app restarts).
SQLITE_CACHE_PATH = PROJECT_ROOT / "cache" / "langchain_cache.db"


def get_openai_api_key() -> str:
    """Return the OpenAI key from the environment, or an empty string if missing."""
    return (os.getenv("OPENAI_API_KEY") or "").strip()


def api_key_is_configured() -> bool:
    """True when a non-placeholder API key is present."""
    key = get_openai_api_key()
    if not key:
        return False
    if "your-openai-api-key" in key.lower():
        return False
    return True
