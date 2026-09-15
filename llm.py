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
    build_category_select_prompt,
    build_scope_assessment_prompt,
    build_subcategory_select_prompt,
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
            "Missing OPENAI_API_KEY. Add it to Streamlit Secrets, a local .env file, "
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


def _normalize_readiness(raw: Any) -> int:
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return 0
    return max(0, min(100, value))


def _normalize_missing(raw: Any) -> list[str]:
    if not isinstance(raw, list):
        return []
    aspects = []
    for item in raw:
        text = str(item).strip()
        if text:
            aspects.append(text)
    return aspects[:4]


def _normalize_confidence(raw: Any) -> str:
    confidence = str(raw or "medium").lower().strip()
    if confidence not in {"high", "medium", "low"}:
        return "medium"
    return confidence


def _chat_json(system_prompt: str, user_content: str) -> dict[str, Any]:
    client = get_client()
    response = client.chat.completions.create(
        model=get_model(),
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ],
        response_format={"type": "json_object"},
        temperature=0,
    )
    return _extract_json(response.choices[0].message.content or "{}")


def assess_scope_turn(history: list[dict[str, str]]) -> dict[str, Any]:
    """Check if the project is ready to classify, or ask targeted follow-ups."""
    client = get_client()
    messages = [{"role": "system", "content": build_scope_assessment_prompt()}, *history]
    response = client.chat.completions.create(
        model=get_model(),
        messages=messages,
        response_format={"type": "json_object"},
        temperature=0.2,
    )
    content = response.choices[0].message.content or "{}"
    data = _extract_json(content)

    message = str(data.get("assistant_message") or "").strip()
    if not message:
        message = "Could you share a bit more about what this project is trying to achieve?"

    ready = bool(data.get("ready_to_classify"))
    readiness_pct = _normalize_readiness(data.get("readiness_pct"))
    if ready:
        readiness_pct = max(readiness_pct, 90)

    summary = data.get("scope_summary")
    summary = str(summary).strip() if summary else None
    missing = [] if ready else _normalize_missing(data.get("missing_aspects"))

    return {
        "assistant_message": message,
        "ready_to_classify": ready,
        "readiness_pct": readiness_pct,
        "missing_aspects": missing,
        "scope_summary": summary if ready else None,
    }


def _transcript(history: list[dict[str, str]]) -> str:
    lines = []
    for message in history:
        role = message.get("role", "user")
        content = (message.get("content") or "").strip()
        if content:
            lines.append(f"{role.upper()}: {content}")
    return "\n\n".join(lines)


def _project_context(
    description: str,
    history: list[dict[str, str]],
    scope_summary: str | None = None,
) -> str:
    parts = [f"Project description:\n{description.strip()}"]
    if scope_summary:
        parts.append(f"Scope summary:\n{scope_summary.strip()}")

    # Skip the first seed message — it already embeds the description.
    follow_ups = history[1:] if history else []
    transcript = _transcript(follow_ups)
    if transcript:
        parts.append(f"Follow-up conversation:\n{transcript}")
    return "\n\n".join(parts)


def _normalize_related(
    raw: Any,
    primary_category_id: str,
    primary_subcategory_id: str,
) -> list[dict[str, str]]:
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
        if key in seen:
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


def _match_category_id(raw: str) -> str | None:
    value = raw.strip()
    if value in CATEGORY_BY_ID:
        return value

    lowered = value.lower()
    for category_id, category in CATEGORY_BY_ID.items():
        if lowered in {category_id, category["name"].lower()}:
            return category_id
    return None


def _match_subcategory_id(raw: str, category_id: str) -> str | None:
    value = raw.strip()
    if value in SUBCATEGORY_BY_ID and SUBCATEGORY_BY_ID[value]["category_id"] == category_id:
        return value

    lowered = value.lower()
    for subcategory in subcategories_for(category_id):
        if lowered in {subcategory["id"], subcategory["name"].lower()}:
            return subcategory["id"]
    return None


def _select_category(context: str) -> tuple[str, str, str]:
    data = _chat_json(build_category_select_prompt(), context)
    category_id = _match_category_id(str(data.get("primary_category_id") or ""))

    if category_id is None:
        # One correction pass with clearer instruction.
        retry_context = (
            f"{context}\n\n"
            "Your previous category id was invalid. Reply again with a primary_category_id "
            "copied exactly from the category list."
        )
        data = _chat_json(build_category_select_prompt(), retry_context)
        category_id = _match_category_id(str(data.get("primary_category_id") or ""))

    if category_id is None:
        category_id = DEFAULT_CATEGORY_ID

    return (
        category_id,
        _normalize_confidence(data.get("confidence")),
        str(data.get("rationale") or "").strip(),
    )


def _select_subcategory(
    context: str,
    category_id: str,
) -> tuple[str, str, str, list[dict[str, str]]]:
    category = CATEGORY_BY_ID[category_id]
    prompt = build_subcategory_select_prompt(category_id, category["name"])
    data = _chat_json(prompt, context)
    subcategory_id = _match_subcategory_id(
        str(data.get("primary_subcategory_id") or ""),
        category_id,
    )

    if subcategory_id is None:
        retry_context = (
            f"{context}\n\n"
            "Your previous subcategory id was invalid. Reply again with a "
            "primary_subcategory_id copied exactly from the subcategory list."
        )
        data = _chat_json(prompt, retry_context)
        subcategory_id = _match_subcategory_id(
            str(data.get("primary_subcategory_id") or ""),
            category_id,
        )

    if subcategory_id is None:
        subcategory_id = (
            DEFAULT_SUBCATEGORY_ID
            if category_id == DEFAULT_CATEGORY_ID
            else subcategories_for(category_id)[0]["id"]
        )

    related_raw = data.get("related")
    if related_raw is None:
        related_raw = data.get("related_categories")

    return (
        subcategory_id,
        _normalize_confidence(data.get("confidence")),
        str(data.get("rationale") or "").strip(),
        _normalize_related(related_raw, category_id, subcategory_id),
    )


def categorize_project(
    description: str,
    history: list[dict[str, str]],
    scope_summary: str | None = None,
) -> dict[str, Any]:
    """Assign a primary value category and subcategory in two model steps."""
    context = _project_context(description, history, scope_summary)

    category_id, category_confidence, category_rationale = _select_category(context)
    subcategory_id, subcategory_confidence, subcategory_rationale, related = (
        _select_subcategory(context, category_id)
    )

    confidence_rank = {"low": 0, "medium": 1, "high": 2}
    confidence = min(
        (category_confidence, subcategory_confidence),
        key=lambda value: confidence_rank[value],
    )

    rationale_parts = [part for part in (category_rationale, subcategory_rationale) if part]
    rationale = " ".join(rationale_parts)

    category = CATEGORY_BY_ID[category_id]
    subcategory = SUBCATEGORY_BY_ID[subcategory_id]

    return {
        "primary_category_id": category_id,
        "primary_name": category["name"],
        "primary_subcategory_id": subcategory_id,
        "primary_subcategory_name": subcategory["name"],
        "primary_description": subcategory["description"],
        "confidence": confidence,
        "rationale": rationale,
        "related_categories": related,
        "source": "model",
    }
