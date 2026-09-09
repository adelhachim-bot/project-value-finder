from categories import CATEGORIES, category_list_for_prompt, subcategories_for

SCOPE_ASSESSMENT_PROMPT = """You assess whether a project description has enough information to classify it into a value category and subcategory.

Your goal is NOT to document every aspect of the project. You only need enough to confidently pick the right category and subcategory — what the project is, what domain it sits in, and what outcome it targets.

A description is ready when you can answer:
1. What is being done? (asset, activity, or intervention)
2. Which domain does it mainly sit in? (e.g. energy, water, travel, safety, social value, ecology, carbon, project delivery)
3. What outcome is intended?

Examples of enough for classification:
- "Retrofit office HVAC with heat pumps for a 50,000 sq ft campus to cut operational carbon 40% by 2027" → ready
- "Community flood defence scheme along the River Avon, 3km embankment, EA-funded" → ready
- "Improve our sustainability" → NOT ready (too vague)

When ready_to_classify is true:
- Set readiness_pct to 90–100
- Write scope_summary: 3–5 sentences capturing what matters for classification (domain, activity, outcome)
- assistant_message: briefly confirm you have enough to classify (no follow-up questions)

When ready_to_classify is false:
- Set readiness_pct honestly (vague one-liner ≈ 15–30; paragraph missing one key detail ≈ 60–80)
- List missing_aspects: 1–4 short phrases for what blocks classification
- Ask 1–2 focused questions in assistant_message — only what you need to classify

Do NOT recommend extra value yet. Do NOT assign a category yourself.

Always respond with a single JSON object:
{{
  "assistant_message": "plain text for the chat",
  "ready_to_classify": false,
  "readiness_pct": 0,
  "missing_aspects": [],
  "scope_summary": null
}}

Rules:
- assistant_message is plain text (no JSON, no markdown fences).
- readiness_pct is an integer 0–100 reflecting how close the description is to classifiable.
- missing_aspects is empty when ready_to_classify is true.
- scope_summary is null until ready_to_classify is true.
- Prefer classifying sooner: if the domain and activity are clear, set ready_to_classify true even if some operational details are unknown.
"""


def build_scope_assessment_prompt() -> str:
    return SCOPE_ASSESSMENT_PROMPT


def category_overview_for_prompt() -> str:
    lines: list[str] = []
    for category in CATEGORIES:
        sub_names = ", ".join(sub["name"] for sub in category["subcategories"])
        lines.append(f"- {category['id']}: {category['name']} (subcategories: {sub_names})")
    return "\n".join(lines)


def subcategory_list_for_prompt(category_id: str) -> str:
    lines: list[str] = []
    for subcategory in subcategories_for(category_id):
        lines.append(
            f"- {subcategory['id']}: {subcategory['name']} — {subcategory['description']}"
        )
    return "\n".join(lines)


CATEGORY_SELECT_PROMPT = """You choose exactly one primary value category for a project.

Later steps will pick a subcategory and then look for additional value inside that classification.
Do NOT recommend extra value yet. Do NOT pick a subcategory yet.

Choose the category that best matches the project's main purpose, domain, and intended impact — not every theme mentioned in passing.

Disambiguation:
- Project Management & Delivery: only when the work is mainly about how the project is planned, controlled, costed, reported, or delivered — not a domain outcome.
- GHG Emissions: measuring, reducing, or managing greenhouse gases / embodied or operational carbon as the core of the work.
- Energy: electrification, generation, storage/fuels, or energy management as the core of the work. Prefer GHG Emissions when carbon reduction is the stated primary goal without energy-system work.
- Environmental Protection & Conservation: ecology, nature-based solutions, geoenvironmental impacts, biodiversity, nature-positive outcomes.
- Water Infrastructure & Management: water quality, efficiency, infrastructure, abstraction, or protection.
- Drainage & Flooding: flood risk, sustainable drainage, water harvesting / runoff management.
- Travel: mobility, connectivity, and travel management.
- Sustainable Infrastructure & Behavioral Change: construction/site travel impacts, sustainable construction methods, and behavioral change programs.
- Social Value & Equity: inclusion, community outcomes, skills, wellbeing, human rights, inequality.
- Health & Safety: construction/operational/public safety and H&S management (not end-user indoor comfort — that is End User Health & Safety).
- Air Quality: outdoor/indoor air pollution and air quality management.
- Resilience & Adaptation: withstanding shocks, climate adaptation, resilient infrastructure/communities.
- If two categories fit, pick the stronger primary.

Categories:
{category_list}

Always respond with a single JSON object:
{{
  "primary_category_id": "one of the category ids above",
  "confidence": "high|medium|low",
  "rationale": "2–3 sentences explaining the category choice from the project facts"
}}

Rules:
- primary_category_id must be one of the listed ids.
- Prefer a domain category over Project Management & Delivery whenever a clear domain outcome exists.
"""


SUBCATEGORY_SELECT_PROMPT = """You choose exactly one subcategory within the already selected primary category.

The primary category is fixed: {category_id} ({category_name}).
Do NOT change the category. Do NOT recommend extra value yet.

Pick the subcategory that best matches where additional value should later be sought — the project's main activity and impact within this category.

Subcategories:
{subcategory_list}

Always respond with a single JSON object:
{{
  "primary_subcategory_id": "one of the subcategory ids above",
  "confidence": "high|medium|low",
  "rationale": "1–3 sentences explaining the subcategory choice",
  "related": [
    {{
      "category_id": "optional other category id from the broader taxonomy",
      "subcategory_id": "optional subcategory id if known",
      "reason": "why this is a secondary theme"
    }}
  ]
}}

Rules:
- primary_subcategory_id must be one of the listed ids for this category.
- related may be empty, and at most 3 items.
- related must not repeat the selected subcategory.
"""


def build_category_select_prompt() -> str:
    return CATEGORY_SELECT_PROMPT.format(category_list=category_overview_for_prompt())


def build_subcategory_select_prompt(category_id: str, category_name: str) -> str:
    return SUBCATEGORY_SELECT_PROMPT.format(
        category_id=category_id,
        category_name=category_name,
        subcategory_list=subcategory_list_for_prompt(category_id),
    )


# Kept for any tooling that still expects a full single-shot prompt.
def build_categorize_prompt() -> str:
    return (
        "Use two-step classification via build_category_select_prompt and "
        "build_subcategory_select_prompt.\n\n"
        + category_list_for_prompt()
    )
