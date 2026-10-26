"""Human reviewer console: answer escalated questions and (optionally) teach the knowledge base.

Run:  python review.py
In a real deployment this must sit behind authentication and be limited to support/HR staff.
"""
import re
import time
from pathlib import Path
from escalation import pending_tickets, get_ticket, answer_ticket
from ingest import DOCS_DIR, ROLES, main as reindex


def write_kb_doc(ticket: dict, human_answer: str, roles: list, reviewer: str) -> Path:
    """Save a human-verified Q&A as a markdown doc the bot can retrieve next time."""
    title_q = re.sub(r"[#\n\r]", " ", ticket["question"]).strip()[:80]
    roles_str = "all" if set(roles) >= set(ROLES) else ", ".join(roles)
    path = Path(DOCS_DIR) / f"human_answer_{ticket['id']}.md"
    path.write_text(
        f"---\n"
        f"title: Human-verified answer: {title_q}\n"
        f"allowed_roles: {roles_str}\n"
        f"updated: {time.strftime('%Y-%m-%d')}\n"
        f"---\n"
        f"Question: {ticket['question']}\n\n"
        f"Answer (verified by {reviewer}): {human_answer}\n",
        encoding="utf-8",
    )
    return path


def ask_roles(default_role: str):
    raw = input(f"Which roles may see this? ({', '.join(ROLES)} or 'all') [default: {default_role}]: ").strip().lower()
    if not raw:
        return [default_role]
    if raw == "all":
        return list(ROLES)
    chosen = [r.strip() for r in raw.split(",") if r.strip() in ROLES]
    return chosen or [default_role]


def main():
    reviewer = input("Your name: ").strip() or "reviewer"
    while True:
        tickets = pending_tickets()
        if not tickets:
            print("\nNo pending tickets.")
            break
        print("\nPending tickets:")
        for t in tickets:
            print(f"  #{t['id']}  [{t['role']}] {t['user']}: {t['question']}")
        choice = input("\nTicket number to answer (Enter to quit): ").strip()
        if not choice:
            break
        if not choice.isdigit() or not get_ticket(int(choice)):
            print("Not a valid ticket number.")
            continue
        t = get_ticket(int(choice))
        if t["status"] != "pending":
            print("That ticket is already answered.")
            continue
        print(f"\nQuestion from {t['user']} ({t['role']}): {t['question']}")
        text = input("Your answer: ").strip()
        if not text:
            print("Empty answer, skipping.")
            continue
        answer_ticket(t["id"], text, reviewer)
        print(f"Ticket #{t['id']} answered.")
        if input("Add this to the knowledge base so the bot can answer next time? (y/N): ").strip().lower() == "y":
            roles = ask_roles(t["role"])
            path = write_kb_doc(t, text, roles, reviewer)
            print(f"Saved {path.name} (roles: {roles}). Re-indexing...")
            reindex()


if __name__ == "__main__":
    main()
