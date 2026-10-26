import argparse
from assistant import answer
from escalation import create_ticket, unnotified_answers, mark_notified, user_tickets
from ingest import ROLES


def send_to_human(user, role, question):
    tid = create_ticket(user, role, question)
    print(f"\nAssistant: I couldn't find a reliable answer in the documents you have access to.")
    print(f"           I've sent your question to a human (ticket #{tid}).")
    print(f"           The reply will show up here once it's answered. Type /tickets to check.\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--role", default="employee", choices=ROLES)
    ap.add_argument("--user", default="demo-user", help="your name/ID, used to deliver ticket replies")
    args = ap.parse_args()
    role, user = args.role, args.user
    last_q = None

    print(f"Knowledge assistant  (user: {user}, role: {role})")
    print("Commands: /human = send last question to a person, /tickets = your tickets, quit\n")

    while True:
        for t in unnotified_answers(user):
            print(f"\n[Ticket #{t['id']} answered by {t['answered_by']}]")
            print(f"  Q: {t['question']}")
            print(f"  A: {t['human_answer']}\n")
            mark_notified(t["id"])

        q = input("You: ").strip()
        if q.lower() in {"quit", "exit"}:
            break
        if not q:
            continue
        if q == "/tickets":
            rows = user_tickets(user)
            if not rows:
                print("\nNo tickets yet.\n")
            for t in rows:
                print(f"\n  #{t['id']} [{t['status']}] {t['question']}")
                if t["status"] == "answered":
                    print(f"      -> {t['human_answer']} (by {t['answered_by']})")
            print()
            continue
        if q == "/human":
            if last_q:
                send_to_human(user, role, last_q)
            else:
                print("\nAsk a question first.\n")
            continue

        last_q = q
        r = answer(q, role)
        if r["error"]:
            print(f"\nAssistant: Sorry, the AI service had a problem ({r['error'][:150]}).")
            print("           Try again in a moment, or use /human to ask a person.\n")
        elif r["escalate"]:
            send_to_human(user, role, q)
        else:
            print(f"\nAssistant: {r['answer']}\n")
            for s in r["sources"]:
                print(f"  [{s['n']}] {s['title']} ({s['file']}, updated {s['updated']})")
            print("\n  (Not right? Type /human to send this question to a person.)\n")


if __name__ == "__main__":
    main()
