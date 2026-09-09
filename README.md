# Project Value Finder

A Streamlit app that uses an LLM to understand projects and, later, find additional value in them.

## Current flow

1. Paste a project description **or upload a PDF/DOCX document**.
2. The app checks whether it has enough to classify.
3. The model classifies the project into one value category and subcategory from `data/Value_Categories.xlsx` (two-step: category, then subcategory).
4. Additional value-finding comes next, using that classification.

## Taxonomy

Loaded from `data/Value_Categories.xlsx`: 28 categories and 129 subcategories.

## Setup (local)

```bash
cd project-value-finder
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Put your OpenAI API key in `.env`:

```
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini
```

```bash
streamlit run app.py
```

## Deploy on Streamlit Community Cloud (free)

1. Push this repo to GitHub (public is simplest on the free tier).
2. Go to [share.streamlit.io](https://share.streamlit.io) and sign in with GitHub.
3. Click **New app**, pick this repository, branch `main`, and set **Main file path** to `app.py`.
4. Under **Advanced settings → Secrets**, add:

```toml
OPENAI_API_KEY = "sk-..."
OPENAI_MODEL = "gpt-4o-mini"
```

5. Deploy. Your app URL will look like `https://<app-name>.streamlit.app`.

Do not commit real API keys. Use Streamlit Secrets (or a local `.env` that stays gitignored).
