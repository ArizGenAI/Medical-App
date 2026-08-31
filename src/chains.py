"""
LangChain model wiring for MediGuide AI.

Demonstrates:
  • ChatOpenAI          — OpenAI chat model
  • LLMChain            — reusable assessment pipeline
  • System / Human / AI messages
  • llm.stream()        — token-by-token narrative for Streamlit

LLMChain was moved out of the main `langchain` package in v1. We import it from
`langchain_classic` when available, then fall back to `langchain.chains`, then to
a small LCEL wrapper that still exposes `.invoke()` so the app never breaks.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from src.config import DEFAULT_MODEL, get_openai_api_key
from src.prompts import (
    ASSESSMENT_CHAT_TEMPLATE,
    JSON_SCHEMA_EXAMPLE,
    NARRATIVE_CHAT_TEMPLATE,
    SYSTEM_SAFETY_PROMPT,
    build_patient_prompt_text,
)

# ---------------------------------------------------------------------------
# LLMChain import (assignment requirement) with version-safe fallbacks
# ---------------------------------------------------------------------------
try:
    from langchain_classic.chains.llm import LLMChain  # LangChain 1.x
except Exception:  # pragma: no cover - older / newer package layouts
    try:
        from langchain.chains import LLMChain  # LangChain 0.2 / 0.3
    except Exception:  # Python 3.14 can fail the pydantic-v1 LLMChain class

        class LLMChain:  # type: ignore[no-redef]
            """
            Minimal stand-in: ChatPromptTemplate piped into ChatOpenAI (LCEL).

            `.invoke()` returns `{"text": ...}` just like classic LLMChain.
            """

            def __init__(self, llm: ChatOpenAI, prompt: Any, verbose: bool = False):
                self.llm = llm
                self.prompt = prompt
                self.verbose = verbose
                self._runnable = prompt | llm

            def invoke(self, inputs: dict[str, Any]) -> dict[str, str]:
                message = self._runnable.invoke(inputs)
                text = getattr(message, "content", str(message))
                return {"text": str(text)}


def build_llm(
    model: str | None = None,
    temperature: float = 0.2,
    streaming: bool = False,
) -> ChatOpenAI:
    """
    Create a ChatOpenAI client.

    temperature is kept low so JSON stays consistent.
    streaming=True is used for the live narrative generator.
    """
    kwargs: dict[str, Any] = {
        "model": model or DEFAULT_MODEL,
        "temperature": temperature,
        "api_key": get_openai_api_key() or None,
    }
    # Older langchain-openai versions still accept `streaming=`.
    if streaming:
        kwargs["streaming"] = True
    try:
        return ChatOpenAI(**kwargs)
    except TypeError:
        kwargs.pop("streaming", None)
        return ChatOpenAI(**kwargs)


def build_assessment_chain(llm: ChatOpenAI) -> LLMChain:
    """
    Reusable LLMChain: ChatPromptTemplate (system + human) → ChatOpenAI.

    This is the assignment's required assessment pipeline.
    """
    return LLMChain(
        llm=llm,
        prompt=ASSESSMENT_CHAT_TEMPLATE.partial(json_schema=JSON_SCHEMA_EXAMPLE),
        verbose=False,
    )


def run_assessment(chain: LLMChain, inputs: dict[str, Any]) -> str:
    """
    Run the assessment chain and return the raw model text (hopefully JSON).

    LLMChain.invoke returns a dict; the text lives under 'text'.
    """
    result = chain.invoke(inputs)
    if isinstance(result, dict):
        return str(result.get("text") or result.get("content") or "")
    return str(result)


def demo_system_human_ai(llm: ChatOpenAI, patient_inputs: dict[str, Any]) -> dict[str, str]:
    """
    Educational demo of the three core chat message types.

    1. SystemMessage — role, tone, and safety rules
    2. HumanMessage  — the patient's information
    3. AIMessage     — the model's reply (returned by llm.invoke)
    """
    human_text = build_patient_prompt_text(patient_inputs)
    system_text = SYSTEM_SAFETY_PROMPT.format(
        language=patient_inputs.get("language", "English"),
        json_schema=JSON_SCHEMA_EXAMPLE,
    )

    messages = [
        SystemMessage(content=system_text),
        HumanMessage(
            content=(
                "In 4 sentences, explain how you will treat this information as "
                "educational guidance only (no diagnosis). Then name the urgency "
                "category you would assign and why, without claiming certainty.\n\n"
                + human_text
            )
        ),
    ]

    ai_message = llm.invoke(messages)
    ai_content = ai_message.content if isinstance(ai_message, AIMessage) else str(ai_message)

    return {
        "system": "SystemMessage — safety rules and role (truncated in UI).",
        "human": messages[1].content,
        "ai": str(ai_content),
        "ai_type": type(ai_message).__name__,
    }


def stream_narrative(llm: ChatOpenAI, inputs: dict[str, Any]) -> Iterator[str]:
    """
    Yield narrative chunks so Streamlit can show a typing effect.

        messages = NARRATIVE_CHAT_TEMPLATE.format_messages(**inputs)
        for chunk in llm.stream(messages):
            if chunk.content:
                yield chunk.content
    """
    messages = NARRATIVE_CHAT_TEMPLATE.format_messages(**inputs)
    for chunk in llm.stream(messages):
        content = getattr(chunk, "content", None)
        if content:
            yield content
