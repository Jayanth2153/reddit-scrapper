"""
accounts.py — Reddit account manager.
Stores credentials locally in accounts.json.
"""

import json
import uuid
from datetime import datetime
from pathlib import Path

ACCOUNTS_FILE = Path("accounts.json")


def _load() -> list:
    if not ACCOUNTS_FILE.exists():
        default = [
            {
                "id":       "acc_default",
                "username": "aptoridemo",
                "password": "Demo@1234",
                "active":   True,
                "note":     "Primary Aptori account",
                "added_at": datetime.utcnow().isoformat(),
            }
        ]
        _save(default)
        return default
    return json.loads(ACCOUNTS_FILE.read_text(encoding="utf-8"))


def _save(accounts: list) -> None:
    ACCOUNTS_FILE.write_text(
        json.dumps(accounts, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def get_all() -> list:
    return _load()


def get_active() -> dict | None:
    accounts = _load()
    for acc in accounts:
        if acc.get("active"):
            return acc
    return accounts[0] if accounts else None


def set_active(account_id: str) -> None:
    accounts = _load()
    for acc in accounts:
        acc["active"] = acc["id"] == account_id
    _save(accounts)


def add_account(username: str, password: str, note: str = "") -> dict:
    accounts = _load()
    for acc in accounts:
        if acc["username"].lower() == username.lower():
            raise ValueError(f"Account '{username}' already exists.")
    new_acc = {
        "id":       f"acc_{uuid.uuid4().hex[:8]}",
        "username": username,
        "password": password,
        "active":   False,
        "note":     note,
        "added_at": datetime.utcnow().isoformat(),
    }
    accounts.append(new_acc)
    _save(accounts)
    return new_acc


def delete_account(account_id: str) -> None:
    accounts = _load()
    was_active = any(a["id"] == account_id and a.get("active") for a in accounts)
    remaining  = [a for a in accounts if a["id"] != account_id]
    if remaining and was_active:
        remaining[0]["active"] = True
    _save(remaining)


def update_account(account_id: str, **kwargs) -> None:
    accounts = _load()
    for acc in accounts:
        if acc["id"] == account_id:
            for k, v in kwargs.items():
                if k not in ("id", "added_at"):
                    acc[k] = v
    _save(accounts)
