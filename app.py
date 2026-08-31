"""
MediGuide AI — Streamlit user interface.

Run from the project root:
    streamlit run app.py

Backend logic lives in src/. This file only handles layout, forms, and display.
"""

from __future__ import annotations

import json
import time
from datetime import datetime

import streamlit as st

from src.cache_manager import configure_cache
from src.chains import (
    build_assessment_chain,
    build_llm,
    demo_system_human_ai,
    run_assessment,
    stream_narrative,
)
from src.config import (
    APP_NAME,
    APP_TAGLINE,
    AVAILABLE_MODELS,
    CACHE_OPTIONS,
    DEFAULT_MODEL,
    DISCLAIMER_LONG,
    DISCLAIMER_SHORT,
    DURATION_OPTIONS,
    EDUCATIONAL_LABEL,
    GENDER_OPTIONS,
    LANGUAGE_OPTIONS,
    SYMPTOM_OPTIONS,
    api_key_is_configured,
)
from src.prompts import build_patient_prompt_text
from src.utils import (
    format_symptom_list,
    parse_assessment_json,
    text_or_none,
    urgency_style,
    validate_age,
)

# ---------------------------------------------------------------------------
# Page chrome
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="MediGuide AI",
    page_icon="🩺",
    layout="wide",
    initial_sidebar_state="expanded",
)

CUSTOM_CSS = """
<style>
    .stApp { background: linear-gradient(180deg, #f0fdfa 0%, #f8fafc 280px, #f8fafc 100%); }
    .hero-title { font-size: 2.1rem; font-weight: 750; color: #0f766e; margin-bottom: 0.2rem; }
    .hero-sub { color: #334155; font-size: 1.05rem; margin-bottom: 0.8rem; }
    .edu-chip {
        display: inline-block; background: #0f766e; color: white; padding: 0.25rem 0.7rem;
        border-radius: 999px; font-size: 0.8rem; font-weight: 600; letter-spacing: 0.02em;
    }
    .disclaimer-banner {
        background: #fff7ed; border: 2px solid #ea580c; border-radius: 12px;
        padding: 0.9rem 1rem; color: #7c2d12; font-size: 0.95rem; margin: 0.6rem 0 1.1rem 0;
    }
    .urgency-box {
        border-radius: 14px; padding: 1rem 1.1rem; border: 2px solid;
        text-align: center; margin-bottom: 0.8rem;
    }
    .urgency-label { font-size: 0.8rem; text-transform: uppercase; letter-spacing: 0.08em; }
    .urgency-value { font-size: 1.8rem; font-weight: 800; margin: 0.15rem 0; }
    .condition-card {
        background: white; border: 1px solid #ccfbf1; border-radius: 10px;
        padding: 0.75rem 0.9rem; margin-bottom: 0.5rem;
    }
    .footer-note { color: #64748b; font-size: 0.85rem; margin-top: 1.5rem; }
</style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


def init_state() -> None:
    """Session memory for history, last result, and cache timings."""
    defaults: dict = {
        "history": [],
        "last_result": None,
        "last_raw_json": "",
        "last_elapsed": None,
        "message_demo": None,
        "stream_pending": False,
        "last_narrative": "",
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def render_disclaimer(location: str) -> None:
    """Disclaimer appears in the sidebar, main area, and results (assignment §17)."""
    st.markdown(
        f'<div class="disclaimer-banner"><strong>{location}:</strong> {DISCLAIMER_SHORT}</div>',
        unsafe_allow_html=True,
    )


def collect_sidebar() -> dict:
    """Sidebar: name, description, disclaimer, model, cache, language."""
    with st.sidebar:
        st.markdown(f"### 🩺 {APP_NAME}")
        st.caption(APP_TAGLINE)
        st.markdown(f'<span class="edu-chip">{EDUCATIONAL_LABEL}</span>', unsafe_allow_html=True)
        st.divider()
        st.warning(DISCLAIMER_LONG)

        st.subheader("Model configuration")
        default_index = AVAILABLE_MODELS.index(DEFAULT_MODEL) if DEFAULT_MODEL in AVAILABLE_MODELS else 0
        model = st.selectbox("OpenAI model", AVAILABLE_MODELS, index=default_index)
        temperature = st.slider("Temperature", 0.0, 1.0, 0.2, 0.05)
        cache_label = st.selectbox("LLM cache", list(CACHE_OPTIONS.keys()))
        cache_mode = CACHE_OPTIONS[cache_label]
        cache_status = configure_cache(cache_mode)
        st.info(cache_status)

        st.subheader("Answer language")
        language = st.selectbox("Language", LANGUAGE_OPTIONS, index=0)

        st.divider()
        st.caption(
            "In-memory cache = RAM, fastest, gone after restart. "
            "SQLite cache = `.db` file on disk, reused across sessions."
        )

        if st.session_state["history"]:
            st.subheader("Session analytics")
            counts: dict[str, int] = {}
            for item in st.session_state["history"]:
                level = item.get("urgency_level") or "UNKNOWN"
                counts[level] = counts.get(level, 0) + 1
            st.write(counts)

        return {
            "model": model,
            "temperature": temperature,
            "cache_mode": cache_mode,
            "language": language,
        }


def render_hero() -> None:
    st.markdown(f'<p class="hero-title">🩺 {APP_NAME}</p>', unsafe_allow_html=True)
    st.markdown(f'<p class="hero-sub">{APP_TAGLINE}</p>', unsafe_allow_html=True)
    st.markdown(f'<span class="edu-chip">{EDUCATIONAL_LABEL}</span>', unsafe_allow_html=True)
    render_disclaimer("Main screen")


def build_form_inputs(language: str) -> tuple[dict | None, bool]:
    """
    Main intake form. Uses the required widgets:
    text_input, text_area, selectbox, multiselect, slider, button.
    """
    st.subheader("Patient information")
    st.caption("Fields marked with * are required. This is not a clinical intake form.")

    with st.form("assessment_form", clear_on_submit=False):
        col_a, col_b = st.columns(2)
        with col_a:
            age = st.text_input("Patient age *", placeholder="e.g. 25")
        with col_b:
            gender = st.selectbox("Gender *", GENDER_OPTIONS)

        symptoms = st.multiselect(
            "Symptoms * (select all that apply)",
            SYMPTOM_OPTIONS,
            help="You can also describe extra symptoms in the box below.",
        )
        extra_symptoms = st.text_input(
            "Additional symptoms (optional free text)",
            placeholder="e.g. ear pain, night sweats",
        )

        col_c, col_d = st.columns(2)
        with col_c:
            duration = st.selectbox("Duration of symptoms *", DURATION_OPTIONS)
        with col_d:
            severity = st.slider("Severity (1 = mild, 10 = worst) *", 1, 10, 3)

        existing_conditions = st.text_area(
            "Existing medical conditions",
            placeholder="e.g. asthma, diabetes — or leave blank",
            height=80,
        )
        medications = st.text_area(
            "Current medications",
            placeholder="e.g. inhaler, metformin — or leave blank",
            height=80,
        )
        notes = st.text_area(
            "Additional notes",
            placeholder="Anything else a clinician might need to know",
            height=80,
        )

        submitted = st.form_submit_button("Generate educational guidance", type="primary")

    if not submitted:
        return None, False

    age_value, age_error = validate_age(age)
    if age_error:
        st.error(age_error)
        return None, True

    symptom_text = format_symptom_list(symptoms, extra_symptoms)
    if not symptom_text:
        st.warning(
            "Please select or type at least one symptom. The app will not call the API "
            "until symptoms are provided."
        )
        return None, True

    payload = {
        "age": str(age_value),
        "gender": gender,
        "symptoms": symptom_text,
        "duration": duration,
        "severity": str(severity),
        "existing_conditions": text_or_none(existing_conditions),
        "medications": text_or_none(medications),
        "notes": text_or_none(notes),
        "language": language,
    }
    return payload, True


def render_urgency(level: str) -> None:
    style = urgency_style(level)
    st.markdown(
        f"""
        <div class="urgency-box" style="border-color:{style['color']};background:{style['bg']};color:{style['color']}">
            <div class="urgency-label">Educational urgency estimate</div>
            <div class="urgency-value">{style['emoji']} {level or "N/A"}</div>
            <div>{style['caption']}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_dashboard(assessment: dict, inputs: dict, elapsed: float | None, raw: str) -> None:
    """Results dashboard using metric, warning/info/error/success, expander, tabs, columns."""
    st.subheader("Guidance dashboard")
    render_disclaimer("Results")

    level = assessment.get("urgency_level") or ""
    if level == "EMERGENCY":
        st.error(
            "EMERGENCY: This educational estimate suggests possible emergency features. "
            "Seek emergency medical help immediately (local emergency number). "
            "Do not wait for this app or for an online answer."
        )
    elif level == "HIGH":
        st.error(
            "HIGH urgency: Contact urgent care or a clinician promptly. "
            "This is not a diagnosis — a licensed professional must evaluate you."
        )
    elif level == "MEDIUM":
        st.warning(
            "MEDIUM urgency: Consider booking a healthcare appointment soon. "
            "Worsening symptoms deserve earlier review."
        )
    elif level == "LOW":
        st.success(
            "LOW urgency: General monitoring advice only. If symptoms worsen, "
            "seek professional care. This is not a diagnosis."
        )
    else:
        st.info("Urgency could not be determined from the model output.")

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Age", inputs["age"])
    m2.metric("Severity", f"{inputs['severity']}/10")
    m3.metric("Urgency", level or "—")
    m4.metric("Response time", f"{elapsed:.2f}s" if elapsed is not None else "—")

    render_urgency(level)

    tab_summary, tab_conditions, tab_steps, tab_raw = st.tabs(
        [
            "1. Symptom summary",
            "2. Educational topics",
            "3. Next steps & questions",
            "4. Technical / JSON",
        ]
    )

    with tab_summary:
        st.info("AI-generated general information — not a medical opinion.")
        st.write(assessment.get("summary") or "No summary was returned.")
        with st.expander("Patient details sent to the model"):
            st.write(
                {
                    "age": inputs["age"],
                    "gender": inputs["gender"],
                    "symptoms": inputs["symptoms"],
                    "duration": inputs["duration"],
                    "severity": inputs["severity"],
                    "existing_conditions": inputs["existing_conditions"],
                    "medications": inputs["medications"],
                    "notes": inputs["notes"],
                    "language": inputs["language"],
                }
            )

    with tab_conditions:
        st.warning(
            "Possible conditions are listed for education only. They are NOT diagnoses "
            "and must never be treated as confirmation of a disease."
        )
        conditions = assessment.get("possible_conditions") or []
        if not conditions:
            st.write("No educational topics were returned.")
        for item in conditions:
            st.markdown(
                f'<div class="condition-card"><strong>{item.get("name", "")}</strong>'
                f"<br/>{item.get('reason', '')}</div>",
                unsafe_allow_html=True,
            )

    with tab_steps:
        left, right = st.columns(2)
        with left:
            st.markdown("**Recommended next steps**")
            steps = assessment.get("recommended_next_steps") or []
            if steps:
                for step in steps:
                    st.write(f"- {step}")
            else:
                st.write("None returned.")

            st.markdown("**Questions to ask a healthcare professional**")
            questions = assessment.get("questions_for_doctor") or []
            if questions:
                for q in questions:
                    st.write(f"- {q}")
            else:
                st.write("None returned.")
        with right:
            st.markdown("**Warning signs — seek urgent or emergency care**")
            signs = assessment.get("warning_signs") or []
            if signs:
                for sign in signs:
                    st.error(sign)
            else:
                st.info("No extra warning signs were listed. When in doubt, seek care.")

    with tab_raw:
        st.caption("Raw model JSON (for debugging parse issues).")
        st.code(raw or json.dumps(assessment, indent=2), language="json")
        with st.expander("PromptTemplate preview (single-string template)"):
            st.code(build_patient_prompt_text(inputs), language="text")

    report = _build_report(inputs, assessment)
    st.download_button(
        "Download guidance (Markdown)",
        data=report,
        file_name="mediguide_educational_guidance.md",
        mime="text/markdown",
    )


def _build_report(inputs: dict, assessment: dict) -> str:
    conditions = assessment.get("possible_conditions") or []
    cond_lines = [
        f"- {c.get('name', '')}: {c.get('reason', '')}" for c in conditions
    ]
    def bullets(items: list) -> str:
        return "\n".join(f"- {x}" for x in items) or "- (none)"

    return f"""# MediGuide AI — educational guidance (NOT a diagnosis)

**Safety:** This file was generated by an educational prototype. It is not medical advice.

- Age: {inputs['age']}
- Gender: {inputs['gender']}
- Symptoms: {inputs['symptoms']}
- Duration: {inputs['duration']}
- Severity: {inputs['severity']}/10
- Language: {inputs['language']}
- Urgency (educational estimate): {assessment.get('urgency_level', '')}

## Summary
{assessment.get('summary', '')}

## Educational topics (not diagnoses)
{chr(10).join(cond_lines) or '- (none)'}

## Next steps
{bullets(assessment.get('recommended_next_steps') or [])}

## Questions for a clinician
{bullets(assessment.get('questions_for_doctor') or [])}

## Warning signs
{bullets(assessment.get('warning_signs') or [])}

---
{DISCLAIMER_SHORT}
"""


def execute_assessment(inputs: dict, settings: dict) -> None:
    """Form → cache → LLMChain JSON → parse. Streaming happens once in the UI layer."""
    if not api_key_is_configured():
        st.error(
            "OPENAI_API_KEY is missing. Copy `.env.example` to `.env` and paste your key. "
            "The app will not call OpenAI until a key is configured."
        )
        return

    json_llm = build_llm(model=settings["model"], temperature=settings["temperature"], streaming=False)
    chain = build_assessment_chain(json_llm)

    with st.spinner("Running LangChain LLMChain (structured JSON)…"):
        started = time.perf_counter()
        try:
            raw = run_assessment(chain, inputs)
        except Exception as exc:  # network / auth errors should not crash Streamlit
            st.error(f"The language model could not be reached: {exc}")
            return
        elapsed = time.perf_counter() - started

    assessment, parse_error = parse_assessment_json(raw)
    st.session_state["last_elapsed"] = elapsed
    st.session_state["last_raw_json"] = raw

    if parse_error or assessment is None:
        st.error(
            "The model did not return valid JSON, so the dashboard cannot be filled. "
            f"{parse_error or ''}"
        )
        st.info("Raw output is shown below for debugging. The app did not crash.")
        st.code(raw or "(empty)", language="json")
        return

    st.session_state["last_result"] = {"inputs": inputs, "assessment": assessment, "raw": raw}
    st.session_state["stream_pending"] = True
    st.session_state["history"].append(
        {
            "time": datetime.now().strftime("%H:%M:%S"),
            "symptoms": inputs["symptoms"],
            "urgency_level": assessment.get("urgency_level"),
            "elapsed": round(elapsed, 3),
        }
    )


def render_streamed_briefing(inputs: dict, assessment: dict, settings: dict) -> None:
    """Stream the human-readable narrative once per successful submit."""
    st.success(
        f"JSON assessment ready in {st.session_state.get('last_elapsed', 0):.2f} seconds. "
        "Streaming the readable briefing next."
    )
    if settings["cache_mode"] != "off":
        st.info(
            "Caching is on. Submit the same form again — the second run should be faster "
            "if the prompt is identical."
        )

    st.subheader("Live educational briefing")
    st.caption("Streamed with ChatOpenAI.stream() and st.write_stream().")
    stream_llm = build_llm(model=settings["model"], temperature=0.4, streaming=True)
    narrative_inputs = {
        **inputs,
        "urgency_level": assessment.get("urgency_level", ""),
        "assessment_json": json.dumps(assessment, ensure_ascii=False, indent=2),
    }
    try:
        st.session_state["last_narrative"] = st.write_stream(
            stream_narrative(stream_llm, narrative_inputs)
        )
    except Exception as exc:
        st.warning(f"Streaming failed ({exc}). The JSON dashboard below is still available.")


def render_message_demo(inputs: dict, settings: dict) -> None:
    """Optional SystemMessage / HumanMessage / AIMessage walkthrough."""
    with st.expander("LangChain message types (SystemMessage / HumanMessage / AIMessage)"):
        st.caption(
            "This optional demo shows the three chat roles. It makes one extra model call."
        )
        if st.button("Run message-role demo"):
            try:
                llm = build_llm(
                    model=settings["model"],
                    temperature=settings["temperature"],
                    streaming=False,
                )
                st.session_state["message_demo"] = demo_system_human_ai(llm, inputs)
            except Exception as exc:
                st.error(str(exc))
        demo = st.session_state.get("message_demo")
        if demo:
            st.markdown("**SystemMessage** — role and safety rules")
            st.info(demo["system"])
            st.markdown("**HumanMessage** — patient payload")
            preview = demo["human"][:1500] + ("…" if len(demo["human"]) > 1500 else "")
            st.write(preview)
            st.markdown(f"**AIMessage** (`{demo['ai_type']}`) — model reply")
            st.write(demo["ai"])


def render_history() -> None:
    if not st.session_state["history"]:
        return
    with st.expander("Patient session history (this browser session only)"):
        st.table(st.session_state["history"])
        if st.button("Clear session history"):
            st.session_state["history"] = []
            st.session_state["last_result"] = None
            st.session_state["message_demo"] = None
            st.session_state["last_narrative"] = ""
            st.session_state["stream_pending"] = False
            st.rerun()


def main() -> None:
    init_state()
    settings = collect_sidebar()
    render_hero()

    if not api_key_is_configured():
        st.error(
            "No OpenAI API key loaded. Create a `.env` file from `.env.example` "
            "with OPENAI_API_KEY=sk-... then restart Streamlit."
        )

    inputs, attempted = build_form_inputs(settings["language"])
    if attempted and inputs:
        execute_assessment(inputs, settings)

    saved = st.session_state.get("last_result")
    if saved:
        if st.session_state.get("stream_pending"):
            render_streamed_briefing(saved["inputs"], saved["assessment"], settings)
            st.session_state["stream_pending"] = False
        elif st.session_state.get("last_narrative"):
            st.subheader("Live educational briefing")
            st.caption("Last streamed briefing from this session (re-submit to stream again).")
            st.write(st.session_state["last_narrative"])
        render_dashboard(
            saved["assessment"],
            saved["inputs"],
            st.session_state.get("last_elapsed"),
            saved["raw"],
        )
        render_message_demo(saved["inputs"], settings)

    render_history()
    st.markdown(
        f'<p class="footer-note">{DISCLAIMER_SHORT}</p>',
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
