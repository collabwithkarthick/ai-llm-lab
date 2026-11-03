"""Local demo authentication backed by salted PBKDF2 password hashes."""

import getpass
import hashlib
import hmac
import json
import secrets
from dataclasses import dataclass
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
USER_STORE = ROOT_DIR / "data" / "demo_users.json"
PBKDF2_ITERATIONS = 600_000
MAX_LOGIN_ATTEMPTS = 3


@dataclass(frozen=True)
class DemoUser:
    username: str
    groups: tuple[str, ...]


def _read_users() -> dict[str, dict[str, object]]:
    if not USER_STORE.exists():
        raise RuntimeError(
            "No demo accounts exist. Create one with "
            "'python src/manage_demo_users.py add <username> <group> [<group> ...]'."
        )

    with USER_STORE.open("r", encoding="utf-8") as file:
        users = json.load(file)
    if not isinstance(users, dict):
        raise ValueError(f"Invalid demo user registry: {USER_STORE}")
    return users


def add_user(username: str, password: str, groups: tuple[str, ...]) -> None:
    """Add an account without writing its plaintext password to disk."""
    normalized_username = username.strip()
    normalized_groups = tuple(sorted(set(groups)))
    if not normalized_username:
        raise ValueError("Username cannot be empty.")
    if len(password) < 12:
        raise ValueError("Demo passwords must contain at least 12 characters.")
    if not normalized_groups:
        raise ValueError("Assign at least one access group.")

    users = _read_users() if USER_STORE.exists() else {}
    if normalized_username in users:
        raise ValueError(f"User '{normalized_username}' already exists.")

    salt = secrets.token_bytes(16)
    password_hash = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS
    )
    users[normalized_username] = {
        "salt": salt.hex(),
        "password_hash": password_hash.hex(),
        "groups": list(normalized_groups),
    }

    USER_STORE.parent.mkdir(parents=True, exist_ok=True)
    USER_STORE.write_text(json.dumps(users, indent=2) + "\n", encoding="utf-8")


def list_users() -> dict[str, tuple[str, ...]]:
    """Return usernames and their assigned groups, never password hashes."""
    users = _read_users()
    return {
        username: tuple(record["groups"])
        for username, record in users.items()
        if isinstance(record, dict) and isinstance(record.get("groups"), list)
    }


def remove_user(username: str) -> bool:
    """Remove a local demo account and report whether it existed."""
    users = _read_users()
    if username not in users:
        return False
    del users[username]
    USER_STORE.write_text(json.dumps(users, indent=2) + "\n", encoding="utf-8")
    return True


def authenticate(username: str, password: str) -> DemoUser | None:
    """Verify a password and return the authenticated user's groups."""
    users = _read_users()
    record = users.get(username)
    if not isinstance(record, dict):
        return None

    salt_value = record.get("salt")
    hash_value = record.get("password_hash")
    groups_value = record.get("groups")
    if (
        not isinstance(salt_value, str)
        or not isinstance(hash_value, str)
        or not isinstance(groups_value, list)
        or not all(isinstance(group, str) for group in groups_value)
    ):
        raise ValueError(f"Invalid account record for '{username}' in {USER_STORE}")

    try:
        salt = bytes.fromhex(salt_value)
        expected_hash = bytes.fromhex(hash_value)
    except ValueError as exc:
        raise ValueError(f"Invalid password hash for '{username}' in {USER_STORE}") from exc

    actual_hash = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS
    )
    if not hmac.compare_digest(actual_hash, expected_hash):
        return None
    return DemoUser(username=username, groups=tuple(groups_value))


def login_interactively() -> DemoUser | None:
    """Prompt for a terminal login and allow only a few password attempts."""
    username = input("Username: ").strip()
    for attempt in range(MAX_LOGIN_ATTEMPTS):
        password = getpass.getpass("Password: ")
        user = authenticate(username, password)
        if user is not None:
            return user
        remaining = MAX_LOGIN_ATTEMPTS - attempt - 1
        if remaining:
            print(f"Invalid username or password. {remaining} attempt(s) remaining.")
    return None
