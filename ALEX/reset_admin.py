import sqlite3
from datetime import datetime, timezone

DB_PATH = "data/alex.db"
USERNAME = "admin"
PASSWORD = "Alex@2025!"

try:
    from passlib.hash import argon2
    password_hash = argon2.hash(PASSWORD)
except Exception:
    from argon2 import PasswordHasher
    password_hash = PasswordHasher().hash(PASSWORD)

con = sqlite3.connect(DB_PATH)
cur = con.cursor()

cur.execute("SELECT id FROM users WHERE username = ? COLLATE NOCASE", (USERNAME,))
row = cur.fetchone()

if row:
    cur.execute(
        """
        UPDATE users
        SET password_hash = ?, role = 'admin', is_active = 1
        WHERE username = ? COLLATE NOCASE
        """,
        (password_hash, USERNAME),
    )
else:
    cur.execute(
        """
        INSERT INTO users(username, password_hash, role, is_active, created_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (USERNAME, password_hash, "admin", 1, datetime.now(timezone.utc).isoformat()),
    )

cur.execute("DELETE FROM sessions")
con.commit()
con.close()

print(f"Reset OK: {USERNAME} / {PASSWORD}")
