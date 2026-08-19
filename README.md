# Week 3 — Recipes RAG (Task Set B)

Mini "ask my documents" app over recipe cards, plus the Task Set B chunking
experiment (two chunkers, hit-in-top-5 over 8 known-answer questions).

## Setup on a new machine

```powershell
git clone https://github.com/abiforgit-commits/week3-rag
cd week3-rag
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Then create a `.env` file in the project root (it is git-ignored, so it never
travels with the repo — you must recreate it by hand):

```
GEMINI_API_KEY=your-key-here
```

Finally rebuild the search index (also not in the repo; first run downloads
the ~80MB local embedding model):

```powershell
python ingest.py --strategy naive
python ingest.py --strategy structure
python measure.py        # should reproduce the 8/8 vs 8/8 table
```

## Setup (already done on the original machine)

- Python 3.12.10 (installed via winget, user scope)
- Virtual env in `.venv/` with: chromadb, anthropic, openai, python-dotenv, pypdf, python-docx
- Chroma's built-in local embedding model (all-MiniLM-L6-v2) — embeddings need **no API key**

## To work in this project

```powershell
cd "d:\AI Learning\week3-rag"
.venv\Scripts\Activate.ps1     # or: .venv\Scripts\activate in cmd
python --version               # should say 3.12.10
```

VS Code: select `.venv\Scripts\python.exe` as the interpreter (bottom-right corner).

## Before building

1. Put your LLM API key in `.env` (file exists, key slot is empty). Only the
   *generation* step needs it — retrieval runs fully local.
2. Drop the 6 supplied Set B recipe cards into `data/new_cards/`.

## Layout

```
data/new_cards/   <- the 6 recipe cards from the course go here
chroma_db/        <- persistent vector store (created on first ingest, git-ignored)
.env              <- your API key (git-ignored, never commit)
```
