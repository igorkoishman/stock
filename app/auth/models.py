from flask_login import UserMixin
from app.db import get_db_connection

class User(UserMixin):
    def __init__(self, id_, username):
        self.id = id_
        self.username = username

    @staticmethod
    def get(user_id):
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT id, username FROM users WHERE id=%s", (user_id,))
                row = cur.fetchone()
                return User(row[0], row[1]) if row else None

    @staticmethod
    def find_by_username(username):
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT id, username FROM users WHERE username=%s", (username,))
                row = cur.fetchone()
                return User(row[0], row[1]) if row else None

    @staticmethod
    def get_password_hash(username):
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT password_hash FROM users WHERE username=%s", (username,))
                row = cur.fetchone()
                return row[0] if row else None
