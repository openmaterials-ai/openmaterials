"""Tiny .env loader and key redaction, no new dependency.

Reads the repo-root .env (KEY=VALUE lines) into os.environ if ANTHROPIC_API_KEY
is unset. Never prints or logs the key: redact_key() scrubs it from any string
before it reaches a log, artifact, or exception message.
"""
from __future__ import annotations

import os
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]

# The single secret this package must never leak. Cached at load time so
# redaction works even if os.environ is later mutated.
_KEY_ENV = "ANTHROPIC_API_KEY"


def load_env(dotenv_path: Path | None = None) -> None:
    """Populate ANTHROPIC_API_KEY from the repo-root .env if it is unset.

    A minimal KEY=VALUE parser: blank lines and '#' comments are skipped, an
    optional leading 'export ' is stripped, surrounding quotes are removed. Only
    sets a variable that is not already present in the environment, so an
    explicit export always wins over the file. Missing file is a no-op.
    """
    path = dotenv_path or (_REPO_ROOT / ".env")
    if not path.exists():
        return
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export "):].strip()
        if "=" not in line:
            continue
        name, _, value = line.partition("=")
        name = name.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
            value = value[1:-1]
        if name and name not in os.environ:
            os.environ[name] = value


def get_key() -> str | None:
    """Return the API key from the environment, or None if unset."""
    return os.environ.get(_KEY_ENV)


def has_key() -> bool:
    """True if an API key is available (env or after load_env)."""
    return bool(os.environ.get(_KEY_ENV))


def redact_key(text: str) -> str:
    """Replace any occurrence of the live API key in `text` with a placeholder.

    Reads the current key from the environment; if the key is present in the
    text (as it can be inside an SDK exception dump), it is masked. A no-op when
    no key is set or the key does not appear.
    """
    key = os.environ.get(_KEY_ENV)
    if not key:
        return text
    return text.replace(key, "<redacted-api-key>")
