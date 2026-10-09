"""Agent tools. Every tool here is deliberately vulnerable -- see the VULN comments."""

import sqlite3
from pathlib import Path

import httpx

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = REPO_ROOT / "data"
DB_PATH = DATA_DIR / "lab.db"


def read_file(path: str) -> str:
    # VULN (LLM06 excessive agency / path traversal): no normalisation or
    # containment check, so "../.env" escapes data/.
    return (DATA_DIR / path).read_text()


def init_db() -> None:
    conn = sqlite3.connect(DB_PATH)
    conn.executescript((DATA_DIR / "seed.sql").read_text())
    conn.commit()
    conn.close()


def query_db(name: str) -> str:
    conn = sqlite3.connect(DB_PATH)
    # VULN (SQL injection): model-supplied value formatted straight into SQL.
    rows = conn.execute(f"SELECT name, email, role FROM users WHERE name = '{name}'").fetchall()
    conn.close()
    return "\n".join(", ".join(map(str, r)) for r in rows) or "no rows"


def calculate(expr: str) -> str:
    # VULN (LLM05 improper output handling): eval() on model output.
    return str(eval(expr))


def fetch_url(url: str) -> str:
    # VULN (SSRF + LLM01 indirect prompt injection): any URL, including
    # internal addresses; the body goes straight back into the model context.
    return httpx.get(url, timeout=10, follow_redirects=True).text[:4000]


TOOLS = {
    "read_file": read_file,
    "query_db": query_db,
    "calculate": calculate,
    "fetch_url": fetch_url,
}


def _schema(name: str, description: str, param: str, param_desc: str) -> dict:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": {param: {"type": "string", "description": param_desc}},
                "required": [param],
            },
        },
    }


TOOL_SCHEMAS = [
    _schema("read_file", "Read a file from the data directory.", "path", "Path relative to data/"),
    _schema("query_db", "Look up a user by name.", "name", "User name"),
    _schema("calculate", "Evaluate a math expression.", "expr", "Python expression"),
    _schema("fetch_url", "Fetch a web page and return its text.", "url", "URL to fetch"),
]


def run_tool(name: str, args: dict) -> str:
    try:
        return TOOLS[name](**args)
    except Exception as e:  # errors go back to the model as text
        return f"error: {e}"
