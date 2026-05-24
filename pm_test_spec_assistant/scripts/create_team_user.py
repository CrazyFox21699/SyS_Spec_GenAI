#!/usr/bin/env python3
"""Create or reset a team login for ALEX (IT admin CLI)."""

from __future__ import annotations

import argparse
import getpass
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from web.team_auth import create_user, init_user_db, validate_role, validate_username  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Create an ALEX team user (username/password login)")
    parser.add_argument("--username", required=True, help="Login username (lowercase)")
    parser.add_argument("--role", default="engineer", choices=["engineer", "admin"])
    parser.add_argument("--password", default="", help="Password (min 8 chars); prompt if omitted")
    args = parser.parse_args()

    username = validate_username(args.username)
    role = validate_role(args.role)
    password = args.password or getpass.getpass("Password: ")
    confirm = args.password or getpass.getpass("Confirm password: ")
    if password != confirm:
        print("Passwords do not match.", file=sys.stderr)
        return 1

    data_root = ROOT / "web_data"
    init_user_db(data_root)
    try:
        user = create_user(username, password, role=role)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print(f"Created user '{user.username}' with role '{user.role}'.")
    print(f"Database: {data_root / 'alex_users.db'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
