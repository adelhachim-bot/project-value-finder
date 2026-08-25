from __future__ import annotations

import json
import os
import re
from typing import Any

from openai import OpenAI

from categories import (
    CATEGORY_BY_ID,
    DEFAULT_CATEGORY_ID,
    DEFAULT_SUBCATEGORY_ID,
    SUBCATEGORY_BY_ID,
    subcategories_for,
)
from prompts import (
    TOPIC_IDS,
    build_categorize_prompt,
    build_system_prompt,
    empty_topic_status,
)


def _secret(name: str, default: str = "") -> str:
    try:
        import streamlit as st

        if name in st.secrets:
            return str(st.secrets[name]).strip()
    except Exception:
        pass
    return os.getenv(name, default).strip()


def get_client() -> OpenAI:
    api_key = _secret("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "Missing OPENAI_API_KEY. Add it in Streamlit Cloud Secrets, a .env file, "
            "or the sidebar."
        )

    kwargs: dict[str, Any] = {"api_key": api_key}
    base_url = _secret("OPENAI_BASE_URL")
    if base_url:
        kwargs["base_url"] = base_url
    return OpenAI(**kwargs)


def get_model() -> str:
    return _secret("OPENAI_MODEL", "gpt-4o-mini") or "gpt-4o-mini"


def _extract_json(text: str) -> dict[str, Any]:
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if not match:
            raise
        return json.loads(match.group(0))


def _normalize_status(raw: Any) -> dict[str, str]:
    allowed = {"uncovered", "partial", "covered"}
    status = empty_topic_status()
    if not isinstance(raw, dict):
        return status
    for topic_id in TOPIC_IDS:
        value = str(raw.get(topic_id, "uncovered")).lower()
        status[topic_id] = value if value in allowed else "uncovered"
    return status


def interview_turn(history: list[dict[str, str]]) -> dict[str, Any]:
    """Send the conversation to the model and return a structured interview turn."""
    client = get_client()
    messages = [{"role": "system", "content": build_system_prompt()}, *history]
    response = client.chat.completions.create(
        model=get_model(),
        messages=messages,
        response_format={"type": "json_object"},
        temperature=0.4,
    )
    content = response.choices[0].message.content or "{}"
    data = _extract_json(content)

    message = str(data.get("assistant_message") or "").strip()
    if not message:
        message = "Could you share a bit more about the project so I can ask better scoping questions?"

    complete = bool(data.get("interview_complete"))
    brief = data.get("scope_brief")
    brief = str(brief).strip() if brief else None

    return {
        "assistant_message": message,
        "topic_status": _normalize_status(data.get("topic_status")),
        "interview_complete": complete,
        "scope_brief": brief if complete else None,
    }


def _transcript(history: list[dict[str, str]]) -> str:
    lines = []
    for message in history:
        role = message.get("role", "user")
        content = (message.get("content") or "").strip()
        if content:
            lines.append(f"{role.upper()}: {content}")
    return "\n\n".join(lines)


def _normalize_related(raw: Any, primary_category_id: str, primary_subcategory_id: str) -> list[dict[str, str]]:
    related: list[dict[str, str]] = []
    if not isinstance(raw, list):
        return related

    seen = {(primary_category_id, primary_subcategory_id)}
    for item in raw:
        if not isinstance(item, dict):
            continue

        category_id = str(item.get("category_id") or item.get("id") or "").strip()
        if category_id not in CATEGORY_BY_ID:
            continue

        subcategory_id = str(item.get("subcategory_id") or "").strip()
        if subcategory_id and (
            subcategory_id not in SUBCATEGORY_BY_ID
            or SUBCATEGORY_BY_ID[subcategory_id]["category_id"] != category_id
        ):
            subcategory_id = ""

        key = (category_id, subcategory_id or "")
        if key in seen or (category_id, primary_subcategory_id) == (
            primary_category_id,
            primary_subcategory_id,
        ):
            continue
        seen.add(key)

        entry = {
            "category_id": category_id,
            "category_name": CATEGORY_BY_ID[category_id]["name"],
            "reason": str(item.get("reason") or "").strip(),
        }
        if subcategory_id:
            entry["subcategory_id"] = subcategory_id
            entry["subcategory_name"] = SUBCATEGORY_BY_ID[subcategory_id]["name"]
        related.append(entry)
        if len(related) == 3:
            break
    return related


def _resolve_classification(
    category_id: str | None,
    subcategory_id: str | None,
) -> tuple[str, str]:
    if subcategory_id and subcategory_id in SUBCATEGORY_BY_ID:
        subcategory = SUBCATEGORY_BY_ID[subcategory_id]
        return subcategory["category_id"], subcategory_id

    if category_id and category_id in CATEGORY_BY_ID:
        subs = subcategories_for(category_id)
        return category_id, subs[0]["id"]

    return DEFAULT_CATEGORY_ID, DEFAULT_SUBCATEGORY_ID


def categorize_project(
    description: str,
    history: list[dict[str, str]],
    scope_brief: str | None = None,
) -> dict[str, Any]:
    """Assign a primary value category and subcategory from the scoped project."""
    client = get_client()
    context_parts = [f"Project description:\n{description.strip()}"]
    if scope_brief:
        context_parts.append(f"Scope brief:\n{scope_brief.strip()}")
    transcript = _transcript(history)
    if transcript:
        context_parts.append(f"Scoping conversation:\n{transcript}")

    response = client.chat.completions.create(
        model=get_model(),
        messages=[
            {"role": "system", "content": build_categorize_prompt()},
            {"role": "user", "content": "\n\n".join(context_parts)},
        ],
        response_format={"type": "json_object"},
        temperature=0.2,
    )
    data = _extract_json(response.choices[0].message.content or "{}")

    category_id, subcategory_id = _resolve_classification(
        str(data.get("primary_category_id") or "").strip(),
        str(data.get("primary_subcategory_id") or "").strip(),
    )

    confidence = str(data.get("confidence") or "medium").lower()
    if confidence not in {"high", "medium", "low"}:
        confidence = "medium"

    category = CATEGORY_BY_ID[category_id]
    subcategory = SUBCATEGORY_BY_ID[subcategory_id]
    related_raw = data.get("related")
    if related_raw is None:
        related_raw = data.get("related_categories")

    return {
        "primary_category_id": category_id,
        "primary_name": category["name"],
        "primary_subcategory_id": subcategory_id,
        "primary_subcategory_name": subcategory["name"],
        "primary_description": subcategory["description"],
        "confidence": confidence,
        "rationale": str(data.get("rationale") or "").strip(),
        "related_categories": _normalize_related(
            related_raw, category_id, subcategory_id
        ),
        "confirmed": False,
        "source": "model",
    }


def category_override(
    category_id: str,
    subcategory_id: str | None = None,
    previous: dict[str, Any] | None = None,
) -> dict[str, Any]:
    category_id, subcategory_id = _resolve_classification(category_id, subcategory_id)
    category = CATEGORY_BY_ID[category_id]
    subcategory = SUBCATEGORY_BY_ID[subcategory_id]

    related = []
    if previous:
        related = [
            item
            for item in previous.get("related_categories", [])
            if not (
                item.get("category_id") == category_id
                and item.get("subcategory_id") == subcategory_id
            )
        ]

    return {
        "primary_category_id": category_id,
        "primary_name": category["name"],
        "primary_subcategory_id": subcategory_id,
        "primary_subcategory_name": subcategory["name"],
        "primary_description": subcategory["description"],
        "confidence": "high" if previous else "medium",
        "rationale": previous.get("rationale", "") if previous else "",
        "related_categories": related,
        "confirmed": True,
        "source": "user",
    }
