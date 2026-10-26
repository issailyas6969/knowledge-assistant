# Internal Knowledge Assistant: web dashboard

Employee portal (ask questions) + Reviewer portal (human-in-the-loop, document management),
permission-aware RAG, Groq LLM.

## Run
    pip install -r requirements.txt
    # .env file in this folder:
    #   GROQ_API_KEY=your_key
    #   MODEL=openai/gpt-oss-120b
    python create_user.py --demo           # demo accounts, password demo1234
    uvicorn server:app --port 8000

Open:
- http://localhost:8000            employee portal
- http://localhost:8000/reviewer   reviewer portal

The first start builds the index from data/docs (downloads a small embedding model once).

## Demo accounts (password demo1234)
| user  | portal   | department | sees                          |
|-------|----------|------------|-------------------------------|
| alice | employee | support    | general docs                  |
| bob   | employee | sales      | general + sales docs          |
| hana  | employee | hr         | general + HR docs             |
| dev   | employee | employee   | general docs only             |
| rita  | reviewer | -          | tickets + document management |

Create real accounts with:  python create_user.py NAME --kind employee --role sales

## Try it
1. alice: ask "What is the refund policy for enterprise customers?" -> cited answer.
2. dev: ask "What is the maximum discount sales can give?" -> escalated (sales-only doc).
3. rita (reviewer portal): Tickets tab -> answer it, tick "Add to knowledge base", pick roles.
4. alice/dev: "My questions" tab shows the human reply. Ask again -> bot now answers from it.
5. rita: Documents tab -> upload a PDF/MD/TXT and choose which roles may see it.

## Storage
- Accounts, sessions, chat history: SQLite (app.db)
- Tickets: SQLite (tickets.db)
- Vectors: Chroma (chroma_db/)
- Documents: data/docs/*.md (uploaded PDFs/TXT are converted to .md with a permissions header)

## Security notes
- Employee role/department comes from the server-side account, never from the browser.
- Uploaded files cannot set their own permissions; the upload form decides.
- Passwords are salted PBKDF2 hashes; sessions are HttpOnly cookies; login is throttled.
- Before real use: serve over HTTPS and set secure=True on the cookie in server.py, don't use demo accounts.
- Don't run ingest.py or review.py while the server is running; manage documents in the portal.
