from __future__ import annotations

import os

import streamlit as st
from dotenv import load_dotenv

from llm import assess_scope_turn, categorize_project
from categories import CATEGORIES
from document_loader import SUPPORTED_EXTENSIONS, extract_text


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
        "readiness_pct": 0,
        "missing_aspects": [],
        "ready_to_classify": False,
        "scope_summary": None,
        "pending_error": None,
        "category": None,
        "category_error": None,
        "source_document": None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def reset_interview() -> None:
    st.session_state.started = False
    st.session_state.project_description = ""
    st.session_state.messages = []
    st.session_state.readiness_pct = 0
    st.session_state.missing_aspects = []
    st.session_state.ready_to_classify = False
    st.session_state.scope_summary = None
    st.session_state.pending_error = None
    st.session_state.description_input = ""
    st.session_state.category = None
    st.session_state.category_error = None
    st.session_state.source_document = None
    if "uploaded_file_id" in st.session_state:
        del st.session_state.uploaded_file_id


def apply_turn(turn: dict) -> None:
    st.session_state.messages.append(
        {"role": "assistant", "content": turn["assistant_message"]}
    )
    st.session_state.readiness_pct = turn["readiness_pct"]
    st.session_state.missing_aspects = turn["missing_aspects"]
    st.session_state.ready_to_classify = turn["ready_to_classify"]
    if turn.get("scope_summary"):
        st.session_state.scope_summary = turn["scope_summary"]


def run_categorization() -> None:
    try:
        result = categorize_project(
            st.session_state.project_description,
            st.session_state.messages,
            st.session_state.scope_summary,
        )
        st.session_state.category = result
        st.session_state.category_error = None
        st.session_state.messages.append(
            {
                "role": "assistant",
                "content": (
                    f"I've classified this project as **{result['primary_name']} → "
                    f"{result['primary_subcategory_name']}** "
                    f"({result['confidence']} confidence)."
                ),
            }
        )
    except Exception as exc:
        st.session_state.category_error = str(exc)


def run_model(history: list[dict[str, str]]) -> None:
    try:
        was_ready = st.session_state.ready_to_classify
        turn = assess_scope_turn(history)
        apply_turn(turn)
        st.session_state.pending_error = None
        if not was_ready and turn["ready_to_classify"] and st.session_state.category is None:
            run_categorization()
    except Exception as exc:
        st.session_state.pending_error = str(exc)


def render_category_panel() -> None:
    st.header("Category")
    category = st.session_state.category

    if st.session_state.category_error:
        st.error(st.session_state.category_error)
        if st.button("Retry classification", type="primary"):
            with st.spinner("Classifying the project…"):
                run_categorization()
            st.rerun()
        return

    if not category:
        if st.session_state.ready_to_classify:
            st.caption("Ready to classify.")
            if st.button("Classify project", type="primary"):
                with st.spinner("Classifying the project…"):
                    run_categorization()
                st.rerun()
        else:
            st.caption("Classified once there is enough detail about the project.")
        return

    st.subheader(category["primary_name"])
    st.markdown(f"**{category['primary_subcategory_name']}**")
    st.caption(category["primary_description"])

    confidence_label = {
        "high": "High confidence",
        "medium": "Medium confidence",
        "low": "Low confidence",
    }.get(category["confidence"], category["confidence"])
    st.success(f"Classified · {confidence_label}")

    if category.get("rationale"):
        st.write(category["rationale"])

    related = category.get("related_categories") or []
    if related:
        st.markdown("**Related themes**")
        for item in related:
            label = item["category_name"]
            if item.get("subcategory_name"):
                label = f"{label} → {item['subcategory_name']}"
            reason = f" — {item['reason']}" if item.get("reason") else ""
            st.write(f"- {label}{reason}")

    if st.button("Reclassify", use_container_width=True):
        with st.spinner("Classifying the project…"):
            run_categorization()
        st.rerun()


init_state()

with st.sidebar:
    st.title("Project Scope Chat")
    st.caption("Describe the project, classify it, then look for extra value.")

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
    st.subheader("Classification readiness")
    readiness = st.session_state.readiness_pct / 100
    st.progress(readiness, text=f"{st.session_state.readiness_pct}% ready")

    if st.session_state.ready_to_classify:
        st.success("Enough detail to classify.")
    elif st.session_state.missing_aspects:
        st.caption("Still need:")
        for aspect in st.session_state.missing_aspects:
            st.write(f"- {aspect}")

    st.subheader("Category")
    category = st.session_state.category
    if category:
        st.write(f"**{category['primary_name']}**")
        st.caption(category.get("primary_subcategory_name", ""))
        st.caption(f"{category['confidence']} confidence")
    else:
        st.caption("Assigned once the description is clear enough.")

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
        "Paste a description or upload a document. If it's enough to classify, we'll "
        "assign a category right away. Otherwise the chatbot will ask a few targeted questions."
    )

    input_tab, upload_tab = st.tabs(["Write", "Upload document"])

    with input_tab:
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

    with upload_tab:
        supported = ", ".join(ext.upper() for ext in sorted(SUPPORTED_EXTENSIONS))
        uploaded = st.file_uploader(
            "Project document",
            type=sorted(ext.lstrip(".") for ext in SUPPORTED_EXTENSIONS),
            help=f"Supported formats: {supported}. Legacy .doc is not supported — use .docx.",
        )
        if uploaded is not None:
            if st.session_state.get("uploaded_file_id") != uploaded.file_id:
                try:
                    with st.spinner("Extracting text from document…"):
                        extracted = extract_text(uploaded.name, uploaded.getvalue())
                    st.session_state.description_input = extracted
                    st.session_state.uploaded_file_id = uploaded.file_id
                    st.session_state.source_document = uploaded.name
                except Exception as exc:
                    st.error(str(exc))
            st.success(f"Loaded **{uploaded.name}** into the description field.")
            with st.expander("Preview extracted text"):
                st.text(st.session_state.get("description_input", "")[:3000])

    description = st.session_state.get("description_input", "")
    start = st.button("Analyze project", type="primary")
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
                        "Here is the project description. Assess whether it is enough "
                        "to classify into a value category, or ask only what is missing.\n\n"
                        f"{st.session_state.project_description}"
                    ),
                }
            ]
            with st.spinner("Reading the description…"):
                run_model(st.session_state.messages)
            st.rerun()
else:
    left, right = st.columns((1.35, 1), gap="large")

    with left:
        st.header("Project chat")
        if st.session_state.pending_error:
            st.error(st.session_state.pending_error)

        if st.session_state.source_document:
            st.caption(f"Source document: {st.session_state.source_document}")

        with st.expander("Project description", expanded=False):
            st.markdown(st.session_state.project_description)

        for message in st.session_state.messages[1:]:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])

    with right:
        render_category_panel()
        st.header("Scope summary")
        if st.session_state.scope_summary:
            st.markdown(st.session_state.scope_summary)
            st.download_button(
                "Download summary",
                st.session_state.scope_summary,
                file_name="project-scope-summary.md",
                mime="text/markdown",
            )
        elif not st.session_state.ready_to_classify:
            st.caption("A short summary appears here once there is enough to classify.")

    if not st.session_state.ready_to_classify:
        prompt = st.chat_input("Answer the latest question…")
        if prompt:
            st.session_state.messages.append({"role": "user", "content": prompt})
            with st.spinner("Working…"):
                run_model(st.session_state.messages)
            st.rerun()
