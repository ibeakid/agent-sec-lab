import sqlite3

conn = sqlite3.connect(":memory:")


def query_db_fstring(name: str) -> str:
    # ruleid: llm-tool-arg-to-sql
    return conn.execute(f"SELECT * FROM users WHERE name = '{name}'").fetchall()


def query_db_concat(name):
    sql = "SELECT * FROM users WHERE name = '" + name + "'"
    # ruleid: llm-tool-arg-to-sql
    return conn.execute(sql).fetchall()


def query_db_param(name: str) -> str:
    # ok: llm-tool-arg-to-sql
    return conn.execute("SELECT * FROM users WHERE name = ?", (name,)).fetchall()


def list_users() -> str:
    # ok: llm-tool-arg-to-sql
    return conn.execute("SELECT * FROM users").fetchall()

def query_db_script(name: str) -> str:
    # ruleid: llm-tool-arg-to-sql
    return conn.executescript(f"SELECT * FROM users WHERE name = '{name}'")