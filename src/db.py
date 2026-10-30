"""Database connection. Defaults match a local XAMPP install (user root, no password).

Override with environment variables if your setup differs:
    DB_USER, DB_PASSWORD, DB_HOST, DB_PORT, DB_NAME
"""
import os

from sqlalchemy import URL, create_engine


def get_engine(database=None):
    url = URL.create(
        "mysql+pymysql",
        username=os.getenv("DB_USER", "root"),
        password=os.getenv("DB_PASSWORD", ""),
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", "3306")),
        database=database or os.getenv("DB_NAME", "procurement_db"),
        query={"charset": "utf8mb4"},
    )
    return create_engine(url)
