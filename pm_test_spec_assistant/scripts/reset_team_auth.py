#!/usr/bin/env python3
"""Clear team login database and optionally recreate admin (forgot password recovery)."""

from __future__ import annotations

import argparse
import getpass
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from web.team_auth import create_user, init_user_db  # noqa: E402


def clear_auth_db(data_root: Path) -> Path:
    db_path = data_root / "alex_users.db"
    if db_path.exists():
        db_path.unlink()
        print(f"Removed {db_path}")
    init_user_db(data_root)
    print(f"Initialized empty team auth DB at {db_path}")
    return db_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Reset ALEX team login (clear all users + sessions)")
    parser.add_argument("--yes", action="store_true", help="Skip confirmation prompt")
    parser.add_argument("--username", default="admin", help="Admin username to create after clear")
    parser.add_argument("--password", default="", help="Password (min 8 chars); prompt if omitted")
    parser.add_argument("--role", default="admin", choices=["admin", "engineer"])
    args = parser.parse_args()

    data_root = ROOT / "web_data"
    db_path = data_root / "alex_users.db"

    if db_path.exists() and not args.yes:
        print(f"This will DELETE all users and sessions in:\n  {db_path}\n")
        confirm = input("Type yes to continue: ").strip().lower()
        if confirm != "yes":
            print("Cancelled.")
            return 1

    clear_auth_db(data_root)

    username = str(args.username).strip().lower()
    password = args.password or getpass.getpass(f"New password for `{username}`: ")
    confirm = args.password or getpass.getpass("Confirm password: ")
    if password != confirm:
        print("Passwords do not match.", file=sys.stderr)
        return 1

    try:
        user = create_user(username, password, role=args.role)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print(f"Created user '{user.username}' with role '{user.role}'.")
    print("Sign in at /login (use LAN URL if deployment.host is 0.0.0.0).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
