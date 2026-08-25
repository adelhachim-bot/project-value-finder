from __future__ import annotations

import os

import streamlit as st
from dotenv import load_dotenv

from llm import categorize_project, category_override, interview_turn
from prompts import SCOPE_TOPICS, empty_topic_status
from categories import CATEGORIES, subcategories_for


def _configured_secret(name: str, default: str = "") -> str:
    try:
        if name in st.secrets:
            return str(st.secrets[name]).strip()
    except Exception:
        pass
    return os.getenv(name, default).strip()


load_dotenv()

st.set_page_config(
    page_title="Project Scope Chat",
    page_icon="🧭",
    layout="wide",
)


def init_state() -> None:
    defaults = {
        "started": False,
        "project_description": "",
        "messages": [],
        "topic_status": empty_topic_status(),
        "interview_complete": False,
        "scope_brief": None,
        "pending_error": None,
        "category": None,
        "category_error": None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def reset_interview() -> None:
    st.session_state.started = False
    st.session_state.project_description = ""
    st.session_state.messages = []
    st.session_state.topic_status = empty_topic_status()
    st.session_state.interview_complete = False
    st.session_state.scope_brief = None
    st.session_state.pending_error = None
    st.session_state.description_input = ""
    st.session_state.category = None
    st.session_state.category_error = None


def coverage_score(status: dict[str, str]) -> float:
    weights = {"uncovered": 0.0, "partial": 0.5, "covered": 1.0}
    if not status:
        return 0.0
    return sum(weights.get(value, 0.0) for value in status.values()) / len(status)


def apply_turn(turn: dict) -> None:
    st.session_state.messages.append(
        {"role": "assistant", "content": turn["assistant_message"]}
    )
    st.session_state.topic_status = turn["topic_status"]
    st.session_state.interview_complete = turn["interview_complete"]
    if turn.get("scope_brief"):
        st.session_state.scope_brief = turn["scope_brief"]


def run_categorization() -> None:
    try:
        result = categorize_project(
            st.session_state.project_description,
            st.session_state.messages,
            st.session_state.scope_brief,
        )
        st.session_state.category = result
        st.session_state.category_error = None
        if "category_select" in st.session_state:
            del st.session_state.category_select
        for key in list(st.session_state.keys()):
            if str(key).startswith("subcategory_select_"):
                del st.session_state[key]
        st.session_state.messages.append(
            {
                "role": "assistant",
                "content": (
                    f"I've classified this project as **{result['primary_name']} → "
                    f"{result['primary_subcategory_name']}** "
                    f"({result['confidence']} confidence). "
                    "You can confirm or change that in the Category panel before we "
                    "look for additional value."
                ),
            }
        )
    except Exception as exc:
        st.session_state.category_error = str(exc)


def run_model(history: list[dict[str, str]]) -> None:
    try:
        just_completed = not st.session_state.interview_complete
        turn = interview_turn(history)
        apply_turn(turn)
        st.session_state.pending_error = None
        if just_completed and turn["interview_complete"] and st.session_state.category is None:
            run_categorization()
    except Exception as exc:
        st.session_state.pending_error = str(exc)


def render_category_panel() -> None:
    st.header("Category")
    category = st.session_state.category

    if st.session_state.category_error:
        st.error(st.session_state.category_error)

    if not category:
        if st.session_state.interview_complete:
            st.caption("Scope is ready. Classify the project before looking for additional value.")
            if st.button("Classify project", type="primary"):
                with st.spinner("Classifying the project…"):
                    run_categorization()
                st.rerun()
        else:
            st.caption(
                "After the interview, the project is classified into a value category "
                "and subcategory. Additional value-finding will use that next."
            )
        return

    st.subheader(category["primary_name"])
    st.markdown(f"**{category['primary_subcategory_name']}**")
    st.caption(category["primary_description"])

    confidence_label = {
        "high": "High confidence",
        "medium": "Medium confidence",
        "low": "Low confidence",
    }.get(category["confidence"], category["confidence"])
    if category.get("confirmed"):
        st.success(f"Confirmed · {confidence_label}")
    else:
        st.warning(f"Suggested · {confidence_label} · confirm before value-finding")

    if category.get("rationale"):
        st.write(category["rationale"])

    related = category.get("related_categories") or []
    if related:
        st.markdown("**Related**")
        for item in related:
            label = item["category_name"]
            if item.get("subcategory_name"):
                label = f"{label} → {item['subcategory_name']}"
            reason = f" — {item['reason']}" if item.get("reason") else ""
            st.write(f"- {label}{reason}")

    category_names = [item["name"] for item in CATEGORIES]
    category_ids = [item["id"] for item in CATEGORIES]
    current_category_index = category_ids.index(category["primary_category_id"])
    selected_category_name = st.selectbox(
        "Change category",
        category_names,
        index=current_category_index,
        key="category_select",
    )
    selected_category_id = category_ids[category_names.index(selected_category_name)]

    subcategory_options = subcategories_for(selected_category_id)
    subcategory_names = [item["name"] for item in subcategory_options]
    subcategory_ids = [item["id"] for item in subcategory_options]
    if selected_category_id == category["primary_category_id"]:
        current_sub_index = subcategory_ids.index(category["primary_subcategory_id"])
    else:
        current_sub_index = 0
    selected_subcategory_name = st.selectbox(
        "Change subcategory",
        subcategory_names,
        index=current_sub_index,
        key=f"subcategory_select_{selected_category_id}",
    )
    selected_subcategory_id = subcategory_ids[
        subcategory_names.index(selected_subcategory_name)
    ]

    if (
        selected_category_id != category["primary_category_id"]
        or selected_subcategory_id != category["primary_subcategory_id"]
    ):
        st.session_state.category = category_override(
            selected_category_id,
            selected_subcategory_id,
            category,
        )
        st.rerun()

    col_confirm, col_refresh = st.columns(2)
    with col_confirm:
        if not category.get("confirmed") and st.button(
            "Confirm category", type="primary", use_container_width=True
        ):
            st.session_state.category["confirmed"] = True
            st.rerun()
    with col_refresh:
        if st.button("Reclassify", use_container_width=True):
            with st.spinner("Classifying the project…"):
                run_categorization()
            st.rerun()


init_state()

with st.sidebar:
    st.title("Project Scope Chat")
    st.caption(
        "Scope the project, classify it, then look for extra value."
    )

    api_key_input = st.text_input(
        "OpenAI API key",
        value=_configured_secret("OPENAI_API_KEY"),
        type="password",
        help="Prefer Streamlit Cloud Secrets or a local .env. Sidebar value is session-only.",
    )
    if api_key_input:
        os.environ["OPENAI_API_KEY"] = api_key_input

    model_input = st.text_input(
        "Model",
        value=_configured_secret("OPENAI_MODEL", "gpt-4o-mini") or "gpt-4o-mini",
    )
    if model_input:
        os.environ["OPENAI_MODEL"] = model_input

    st.divider()
    score = coverage_score(st.session_state.topic_status)
    st.subheader("Scope coverage")
    st.progress(score, text=f"{int(score * 100)}% understood")

    if st.session_state.interview_complete:
        st.success("Scope looks complete enough to summarize.")

    st.subheader("Category")
    category = st.session_state.category
    if category:
        st.write(f"**{category['primary_name']}**")
        st.caption(category.get("primary_subcategory_name", ""))
        st.caption(f"{category['confidence']} confidence")
        if category.get("confirmed"):
            st.success("Category confirmed.")
        else:
            st.info("Needs confirmation before value-finding.")
    else:
        st.caption("Assigned after the scope interview is complete.")

    st.divider()
    if st.button("Start over", use_container_width=True):
        reset_interview()
        st.rerun()

st.markdown(
    """
    <style>
    .block-container { padding-top: 1.5rem; }
    </style>
    """,
    unsafe_allow_html=True,
)

if not st.session_state.started:
    st.header("Describe the project")
    st.write(
        "Paste what you know today. The chatbot will ask follow-up questions until "
        "the scope is clear, then classify the project into a value category."
    )
    description = st.text_area(
        "Project description",
        height=220,
        key="description_input",
        placeholder=(
            "Example: We are replacing a manual invoicing process for a mid-size "
            "logistics company. Finance wants fewer errors and faster month-end close. "
            "We have 8 weeks and must keep the current ERP."
        ),
        label_visibility="collapsed",
    )
    start = st.button("Start scoping interview", type="primary")
    with st.expander("Value categories used after scoping"):
        for item in CATEGORIES:
            st.markdown(f"**{item['name']}**")
            for sub in item["subcategories"]:
                st.caption(f"• {sub['name']}")
    if start:
        if not description.strip():
            st.warning("Add a project description first.")
        elif not os.getenv("OPENAI_API_KEY", "").strip():
            st.error("Add an OpenAI API key in the sidebar or a .env file.")
        else:
            st.session_state.project_description = description.strip()
            st.session_state.started = True
            st.session_state.messages = [
                {
                    "role": "user",
                    "content": (
                        "Here is the initial project description. Start the scoping "
                        "interview based on what is already known and what is missing.\n\n"
                        f"{st.session_state.project_description}"
                    ),
                }
            ]
            with st.spinner("Reading the description and preparing questions..."):
                run_model(st.session_state.messages)
            st.rerun()
else:
    left, right = st.columns((1.35, 1), gap="large")

    with left:
        st.header("Scoping interview")
        if st.session_state.pending_error:
            st.error(st.session_state.pending_error)

        st.info(st.session_state.project_description)

        for message in st.session_state.messages[1:]:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])

    with right:
        render_category_panel()
        st.header("Scope brief")
        if st.session_state.scope_brief:
            st.markdown(st.session_state.scope_brief)
            st.download_button(
                "Download brief",
                st.session_state.scope_brief,
                file_name="project-scope-brief.md",
                mime="text/markdown",
            )
        else:
            st.caption(
                "A structured brief appears here once the interview has enough coverage. "
                "Keep answering until the coverage meter on the left fills in."
            )
            still_open = [
                topic["label"]
                for topic in SCOPE_TOPICS
                if st.session_state.topic_status.get(topic["id"]) != "covered"
            ]
            if still_open:
                st.write("Still thin on:")
                for label in still_open:
                    st.write(f"- {label}")

    prompt = st.chat_input("Answer the latest question…")
    if prompt:
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.spinner("Working…"):
            run_model(st.session_state.messages)
        st.rerun()
