# Project Value Finder

Streamlit + OpenAI app that takes a project description (typed or uploaded), checks whether there is enough detail to classify it, then assigns a **value category** and **subcategory**.

A later step (not built yet) will suggest **additional value** opportunities based on that classification.

You can run it **locally** or deploy it on **Streamlit Community Cloud**. Never commit API keys.

---

## Features

- Paste a project description, or upload **PDF / DOCX / TXT / MD**
- LLM readiness check: classify immediately if clear, otherwise ask a few follow-ups
- Two-step classification against `data/Value_Categories.xlsx` (28 categories, 129 subcategories)
- Category is model-assigned (no manual override in the UI)
- Short scope summary after classification

---

## Requirements

- Python 3.10+
- An OpenAI API key (or compatible API with `OPENAI_BASE_URL`)

---

## Quick start (local)

```bash
git clone <this-repo-url>
cd project-value-finder

python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
```

Edit `.env` and set your key:

```
OPENAI_API_KEY=your-key-here
OPENAI_MODEL=gpt-4o-mini
```

Run:

```bash
streamlit run app.py
```

Open [http://localhost:8501](http://localhost:8501).

You can also paste the API key in the sidebar instead of using `.env`.

---

## Deploy on Streamlit Community Cloud

The GitHub repo is private. Streamlit Cloud can still deploy it if you authorize access to the repo.

1. Go to [share.streamlit.io](https://share.streamlit.io) and sign in with GitHub.
2. Click **Create app** / **New app**.
3. Choose:
   - **Repository:** `adelhachim-bot/project-value-finder`
   - **Branch:** `main`
   - **Main file path:** `app.py`
4. If the private repo is not listed, click **Manage app access** / authorize the Streamlit GitHub App for this repository.
5. Under **Advanced settings → Secrets**, add:

```toml
OPENAI_API_KEY = "your-key-here"
OPENAI_MODEL = "gpt-4o-mini"
```

6. Click **Deploy**. The app URL will look like `https://<app-name>.streamlit.app`.

After each `git push` to `main`, Streamlit Cloud usually redeploys automatically.

---

## How the app works

1. **Input** — user pastes text or uploads a document (`document_loader.py` extracts text).
2. **Readiness assessment** — `assess_scope_turn()` asks the model if the description is enough to classify. If not, it asks 1–2 targeted questions and updates a readiness %.
3. **Classification** — when ready, `categorize_project()` runs two LLM calls:
   - pick a **category**
   - pick a **subcategory** inside that category
4. **Display** — chat, category panel, related themes, and a short scope summary.

Prompts live in `prompts.py`. Taxonomy is loaded from Excel by `categories.py`.

---

## Project structure

```
project-value-finder/
├── app.py                 # Streamlit UI and session flow
├── llm.py                 # OpenAI client, readiness + classification calls
├── prompts.py             # System prompts
├── categories.py          # Loads and indexes Value_Categories.xlsx
├── document_loader.py     # PDF / DOCX / text extraction
├── data/
│   └── Value_Categories.xlsx
├── requirements.txt
├── .env.example           # Copy to .env (never commit .env)
└── .streamlit/
    └── config.toml        # Local Streamlit UI settings
```

---

## Configuration

| Variable | Required | Default | Notes |
|----------|----------|---------|--------|
| `OPENAI_API_KEY` | Yes | — | From `.env`, Streamlit Secrets, or sidebar |
| `OPENAI_MODEL` | No | `gpt-4o-mini` | Any chat-completions model your key supports |
| `OPENAI_BASE_URL` | No | OpenAI default | Optional proxy / compatible endpoint |

`.env` is gitignored. Never commit real keys.

---

## Updating the taxonomy

Edit `data/Value_Categories.xlsx` (columns: `Category`, `Sub-category`, `Description`). Restart the app so `categories.py` reloads the file.

You may also need to update disambiguation rules in `prompts.py` if categories overlap.

---

## Suggested next step (for the next developer)

Build an **additional value** step that runs after classification:

- Inputs: project description, scope summary, confirmed category + subcategory
- Output: concrete value opportunities for that taxonomy node
- Keep classification read-only in the UI (already the case)

Natural place to add this: a new function in `llm.py`, a new prompt in `prompts.py`, and a panel in `app.py` after `st.session_state.category` is set.

---

## Security / company use

- Prefer a **private** GitHub repo (this one is private)
- Put the OpenAI key in Streamlit **Secrets** or a local `.env` — never in git
- Rotate any key that was previously shared or used in an old public deployment
- Prefer company-managed secrets where possible

---

## Troubleshooting

| Issue | Fix |
|-------|-----|
| `Missing OPENAI_API_KEY` | Add it to `.env`, Streamlit Secrets, or the sidebar |
| Upload fails for `.doc` | Save as `.docx` and retry |
| Empty text from PDF | PDF may be scanned/image-only; paste text instead |
| Wrong category | Click **Reclassify**, or improve the description / taxonomy prompts |
| Port 8501 in use | `streamlit run app.py --server.port 8502` |
| Private repo not listed on Streamlit | Authorize the Streamlit GitHub App for this repository |
