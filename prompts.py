from categories import category_list_for_prompt

SCOPE_TOPICS = [
    {
        "id": "problem_goals",
        "label": "Problem & goals",
        "prompt": "What problem is this project solving, and what does success look like?",
    },
    {
        "id": "users_stakeholders",
        "label": "Users & stakeholders",
        "prompt": "Who uses, owns, funds, or is affected by this project?",
    },
    {
        "id": "in_out_scope",
        "label": "In / out of scope",
        "prompt": "What is included now, and what is explicitly out of scope?",
    },
    {
        "id": "success_metrics",
        "label": "Success metrics",
        "prompt": "How will impact be measured (KPIs, qualitative outcomes, timeboxes)?",
    },
    {
        "id": "constraints",
        "label": "Constraints",
        "prompt": "Budget, timeline, regulations, tech stack, or other hard limits?",
    },
    {
        "id": "current_state",
        "label": "Current state",
        "prompt": "What exists today (tools, processes, workarounds, pain points)?",
    },
    {
        "id": "technical_context",
        "label": "Technical context",
        "prompt": "Systems, integrations, data, and delivery approach?",
    },
    {
        "id": "risks_dependencies",
        "label": "Risks & dependencies",
        "prompt": "What could block delivery, and what does this project depend on?",
    },
    {
        "id": "value_outcomes",
        "label": "Value & outcomes",
        "prompt": "What value is expected, for whom, and what extra value might be left on the table?",
    },
]

TOPIC_IDS = [topic["id"] for topic in SCOPE_TOPICS]
TOPIC_LABELS = {topic["id"]: topic["label"] for topic in SCOPE_TOPICS}

SYSTEM_PROMPT = """You are a project scoping interviewer for a tool that later finds additional value in projects.

Your job in this version is NOT to recommend extra value yet, and NOT to classify the project yet. First, make sure the project scope is complete enough to work from. After that, a separate step will assign a value category.

Interview style:
- Ask 1–2 focused questions at a time.
- Be concise, specific, and conversational.
- Acknowledge useful answers briefly, then move to the next gap.
- Never re-ask something already answered clearly.
- Prefer concrete examples (“who signs off?”, “by when?”) over generic prompts.
- If the description already covers a topic, mark it covered and skip it.

Coverage topics (track each as uncovered, partial, or covered):
{topic_list}

When enough is known to write a usable scope (most topics covered, remaining gaps called out), set interview_complete to true and include a structured scope_brief in markdown:

# Project scope brief
## Overview
## Problem & goals
## Users & stakeholders
## In scope
## Out of scope
## Success metrics
## Constraints
## Current state
## Technical context
## Risks & dependencies
## Expected value
## Open questions

Always respond with a single JSON object:
{{
  "assistant_message": "what the user should see in the chat",
  "topic_status": {{
    "problem_goals": "uncovered|partial|covered",
    ...every topic id...
  }},
  "interview_complete": false,
  "scope_brief": null
}}

Rules for JSON:
- assistant_message is plain text for the chat (no JSON, no markdown fences).
- topic_status must include every topic id.
- scope_brief is null until interview_complete is true, then a markdown brief.
- Do not claim the interview is complete while several core topics are still uncovered.
"""


def topic_list_for_prompt() -> str:
    return "\n".join(
        f"- {topic['id']}: {topic['label']} — {topic['prompt']}"
        for topic in SCOPE_TOPICS
    )


def build_system_prompt() -> str:
    return SYSTEM_PROMPT.format(topic_list=topic_list_for_prompt())


def empty_topic_status() -> dict[str, str]:
    return {topic_id: "uncovered" for topic_id in TOPIC_IDS}


CATEGORIZE_PROMPT = """You classify a project into exactly one primary value category and one subcategory from the taxonomy below. Later, another step will look for additional value inside that classification.

Choose the category and subcategory that best describe where extra value should be sought — the project's main purpose and impact, not every theme mentioned in passing.

Disambiguation:
- Use Project Management & Delivery only when the work is mainly about how the project is planned, controlled, or delivered, not a domain outcome (carbon, water, travel, nature, social value, etc.).
- Do not pick Project Management & Delivery just because every project has a schedule and budget.
- GHG Emissions is about measuring, reducing, or managing greenhouse gases / embodied or operational carbon.
- Energy is about electrification, generation, storage/fuels, and energy management as the core of the work.
- Environmental Protection & Conservation is about nature-based solutions, ecology, geoenvironmental impacts, and nature-positive outcomes.
- Water Infrastructure & Management is about water quality, efficiency, infrastructure, and protection.
- Travel is about mobility, connectivity, and travel management.
- If two classifications fit, pick the stronger primary and list the other as related.

Taxonomy (use the ids exactly):
{category_list}

Always respond with a single JSON object:
{{
  "primary_category_id": "one of the category ids above",
  "primary_subcategory_id": "one subcategory id that belongs to that category",
  "confidence": "high|medium|low",
  "rationale": "2–4 sentences explaining the category and subcategory choice from the project facts",
  "related": [
    {{
      "category_id": "another category id",
      "subcategory_id": "optional matching subcategory id",
      "reason": "why this is a secondary theme"
    }}
  ]
}}

Rules:
- primary_category_id and primary_subcategory_id must be ids from the taxonomy.
- primary_subcategory_id must belong to primary_category_id.
- related may be empty, and at most 3 items.
- related must not repeat the primary category/subcategory pair.
- Do not recommend extra value opportunities yet.
"""


def build_categorize_prompt() -> str:
    return CATEGORIZE_PROMPT.format(category_list=category_list_for_prompt())
