"""Markdown, PDF, HTML, JSON, CSV, and a short shareable summary."""

from __future__ import annotations

import csv
import io
import json
from datetime import datetime
from typing import Any

from src.config import DISCLAIMER_SHORT

SAFETY_LINE = "NOT A DIAGNOSIS. Educational prototype only. Seek emergency help if you feel unsafe."


def _bullets(items: list) -> str:
    return "\n".join(f"- {x}" for x in items) or "- (none)"


def build_markdown(inputs: dict, assessment: dict, extra: dict | None = None) -> str:
    extra = extra or {}
    stamp = extra.get("created_at") or datetime.now().isoformat(timespec="seconds")
    conditions = assessment.get("possible_conditions") or []
    cond_lines = [f"- {c.get('name', '')}: {c.get('reason', '')}" for c in conditions]
    followup = extra.get("followup") or []
    return f"""# MediGuide AI — educational guidance (NOT a diagnosis)

Generated: {stamp}
Patient label: {extra.get('patient_name') or 'Not provided'}

**Safety:** {SAFETY_LINE}

- Age: {inputs.get('age')}
- Gender: {inputs.get('gender')}
- Symptoms: {inputs.get('symptoms')}
- Duration: {inputs.get('duration')}
- Severity: {inputs.get('severity')}/10
- Language: {inputs.get('language')}
- Urgency (educational estimate): {assessment.get('urgency_level', '')}
- Input completeness score (not medical confidence): {extra.get('confidence', 'n/a')}

## Summary
{assessment.get('summary', '')}

## Educational topics (not diagnoses)
{chr(10).join(cond_lines) or '- (none)'}

## Next steps
{_bullets(assessment.get('recommended_next_steps') or [])}

## Questions for a clinician
{_bullets(assessment.get('questions_for_doctor') or [])}

## Warning signs
{_bullets(assessment.get('warning_signs') or [])}

## Follow-up questions (educational)
{_bullets(followup)}

---
{DISCLAIMER_SHORT}
"""


def build_shareable_summary(inputs: dict, assessment: dict, created_at: str = "") -> str:
    """Short text a user can copy or send. Still not medical advice."""
    stamp = created_at or datetime.now().isoformat(timespec="seconds")
    return (
        f"MediGuide AI educational summary ({stamp}) — NOT a diagnosis.\n"
        f"Symptoms: {inputs.get('symptoms')}\n"
        f"Duration: {inputs.get('duration')}; severity {inputs.get('severity')}/10.\n"
        f"Urgency estimate: {assessment.get('urgency_level')}.\n"
        f"Summary: {assessment.get('summary')}\n"
        f"If this is an emergency, call local emergency services now.\n"
        f"{SAFETY_LINE}"
    )


def build_print_html(markdown_like_title: str, body_html: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <title>{markdown_like_title}</title>
  <style>
    body {{ font-family: Georgia, serif; max-width: 720px; margin: 2rem auto; color: #111; }}
    h1 {{ font-size: 1.4rem; }}
    .banner {{ border: 2px solid #b45309; background: #fff7ed; padding: 0.8rem; }}
    @media print {{
      a, button {{ display: none; }}
    }}
  </style>
</head>
<body>
  <p class="banner">{SAFETY_LINE}</p>
  {body_html}
  <p>{DISCLAIMER_SHORT}</p>
  <script>window.addEventListener("load", function() {{ /* print-friendly page */ }});</script>
</body>
</html>
"""


def assessment_to_html(inputs: dict, assessment: dict, extra: dict | None = None) -> str:
    extra = extra or {}
    conditions = "".join(
        f"<li><strong>{c.get('name','')}</strong> — {c.get('reason','')}</li>"
        for c in (assessment.get("possible_conditions") or [])
    )
    lis = lambda items: "".join(f"<li>{x}</li>" for x in (items or []))
    return f"""
    <h1>MediGuide AI educational report</h1>
    <p>Generated: {extra.get('created_at') or datetime.now().isoformat(timespec='seconds')}</p>
    <p>Name: {extra.get('patient_name') or 'Not provided'} · Age {inputs.get('age')} · {inputs.get('gender')}</p>
    <p>Symptoms: {inputs.get('symptoms')} · Duration: {inputs.get('duration')} · Severity: {inputs.get('severity')}/10</p>
    <p>Urgency (educational): <strong>{assessment.get('urgency_level')}</strong></p>
    <h2>Summary</h2><p>{assessment.get('summary') or ''}</p>
    <h2>Educational topics (not diagnoses)</h2><ul>{conditions or '<li>None</li>'}</ul>
    <h2>Next steps</h2><ul>{lis(assessment.get('recommended_next_steps')) or '<li>None</li>'}</ul>
    <h2>Questions for a clinician</h2><ul>{lis(assessment.get('questions_for_doctor')) or '<li>None</li>'}</ul>
    <h2>Warning signs</h2><ul>{lis(assessment.get('warning_signs')) or '<li>None</li>'}</ul>
    """


def _latin(text: str) -> str:
    """FPDF core fonts are Latin-1; replace unsupported glyphs instead of crashing."""
    return (text or "").encode("latin-1", "replace").decode("latin-1")


def build_pdf(inputs: dict, assessment: dict, extra: dict | None = None) -> bytes:
    extra = extra or {}
    from fpdf import FPDF

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=14)
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 16)
    pdf.multi_cell(0, 8, "MediGuide AI — educational report")
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(180, 40, 40)
    pdf.multi_cell(0, 6, _latin(SAFETY_LINE))
    pdf.set_text_color(0, 0, 0)
    pdf.ln(2)
    stamp = extra.get("created_at") or datetime.now().isoformat(timespec="seconds")
    meta = [
        f"Generated: {stamp}",
        f"Name: {extra.get('patient_name') or 'Not provided'}",
        f"Age: {inputs.get('age')}  Gender: {inputs.get('gender')}",
        f"Symptoms: {inputs.get('symptoms')}",
        f"Duration: {inputs.get('duration')}  Severity: {inputs.get('severity')}/10",
        f"Urgency (educational): {assessment.get('urgency_level')}",
        f"Completeness score (not medical confidence): {extra.get('confidence', 'n/a')}",
    ]
    for line in meta:
        pdf.multi_cell(0, 6, _latin(line))
    pdf.ln(2)
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, "Summary", ln=True)
    pdf.set_font("Helvetica", "", 11)
    pdf.multi_cell(0, 6, _latin(str(assessment.get("summary") or "")))
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, "Educational topics (NOT diagnoses)", ln=True)
    pdf.set_font("Helvetica", "", 11)
    for cond in assessment.get("possible_conditions") or []:
        pdf.multi_cell(0, 6, _latin(f"- {cond.get('name','')}: {cond.get('reason','')}"))
    for title, key in (
        ("Next steps", "recommended_next_steps"),
        ("Questions for a clinician", "questions_for_doctor"),
        ("Warning signs", "warning_signs"),
    ):
        pdf.set_font("Helvetica", "B", 12)
        pdf.cell(0, 8, title, ln=True)
        pdf.set_font("Helvetica", "", 11)
        for item in assessment.get(key) or []:
            pdf.multi_cell(0, 6, _latin(f"- {item}"))
    pdf.ln(4)
    pdf.set_font("Helvetica", "I", 9)
    pdf.multi_cell(0, 5, _latin(DISCLAIMER_SHORT))
    return bytes(pdf.output())


def history_csv(rows: list[dict[str, Any]]) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(
        ["id", "created_at", "patient_name", "age", "gender", "symptoms", "duration", "severity", "urgency", "confidence"]
    )
    for row in rows:
        writer.writerow(
            [
                row.get("id"),
                row.get("created_at"),
                row.get("patient_name"),
                row.get("age"),
                row.get("gender"),
                row.get("symptoms"),
                row.get("duration"),
                row.get("severity"),
                row.get("urgency"),
                row.get("confidence"),
            ]
        )
    return buffer.getvalue()


def bundle_json(inputs: dict, assessment: dict, extra: dict | None = None) -> str:
    extra = extra or {}
    payload = {
        "generated_at": extra.get("created_at") or datetime.now().isoformat(timespec="seconds"),
        "disclaimer": SAFETY_LINE,
        "inputs": inputs,
        "assessment": assessment,
        "confidence_input_completeness": extra.get("confidence"),
        "followup": extra.get("followup") or [],
        "narrative": extra.get("narrative") or "",
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)
