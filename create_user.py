"""Create accounts.
  python create_user.py --demo
  python create_user.py alice --kind employee --role support
  python create_user.py rita --kind reviewer
"""
import argparse
import getpass
import os
import sqlite3
import db
from ingest import ROLES

ap = argparse.ArgumentParser()
ap.add_argument("username", nargs="?")
ap.add_argument("--kind", choices=["employee", "reviewer"], default="employee")
ap.add_argument("--role", choices=ROLES, default="employee", help="department; decides which documents an employee can see")
ap.add_argument("--demo", action="store_true", help="create demo accounts (password demo1234, or set DEMO_PASSWORD)")
a = ap.parse_args()

if a.demo:
    demo = [("alice", "employee", "support"), ("bob", "employee", "sales"),
            ("hana", "employee", "hr"), ("dev", "employee", "employee"), ("rita", "reviewer", "employee")]
    for name, kind, role in demo:
        try:
            db.create_user(name, (os.environ.get("DEMO_PASSWORD") or "demo1234"), kind, role)
            print(f"created {name} ({kind}, {role})")
        except sqlite3.IntegrityError:
            print(f"{name} already exists")
    print("\nDemo password is DEMO_PASSWORD if set, otherwise 'demo1234'. Do NOT use these accounts for real data.")
else:
    if not a.username:
        ap.error("give a username, or use --demo")
    pw = getpass.getpass("Password (min 8 chars): ")
    if len(pw) < 8:
        raise SystemExit("Password too short.")
    try:
        db.create_user(a.username, pw, a.kind, a.role)
        print(f"created {a.username} ({a.kind}, {a.role})")
    except sqlite3.IntegrityError:
        raise SystemExit("That username already exists.")
