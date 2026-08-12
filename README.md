# Week 3 — Recipes RAG (Task Set B)

Mini "ask my documents" app over recipe cards, plus the Task Set B chunking
experiment (two chunkers, hit-in-top-5 over 8 known-answer questions).

## Setup (already done)

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
