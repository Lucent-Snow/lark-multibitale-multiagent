"""
Bot/App Authentication for Feishu Base.

Design:
  - AppRegistry:   Create new bot apps via device registration flow.
  - Credentials:  Persistent storage for multiple bots' app_id + app_secret.
  - get_token():   Obtain app_access_token from app_id + app_secret.
  - BaseClient:    Feishu Base API client using bot credentials.
"""

import json
import os
import time
import webbrowser
from dataclasses import dataclass, asdict
from pathlib import Path

import requests

# ─── Paths ────────────────────────────────────────────────────────────────────

CONFIG_DIR = Path(__file__).parent.parent.parent
CREDENTIALS_FILE = CONFIG_DIR / ".credentials.json"

# ─── Feishu Endpoints ─────────────────────────────────────────────────────────

REG_BASE = "https://accounts.feishu.cn"
REG_DEVICE_URL = f"{REG_BASE}/oauth/v1/app/registration"
TOKEN_URL = "https://open.feishu.cn/open-apis/auth/v3/app_access_token/internal"

# ─── Dataclasses ──────────────────────────────────────────────────────────────

@dataclass
class BotCredential:
    name: str
    app_id: str
    app_secret: str


@dataclass
class AppRegistryResult:
    app_id: str
    app_secret: str


# ─── Credentials Store ────────────────────────────────────────────────────────

class Credentials:
    """
    Persistent store for multiple bots' credentials.
    Saved as JSON: { "bots": [ {"name": "manager", "app_id": "...", "app_secret": "..."}, ... ] }
    """

    def __init__(self):
        self.bots: list[BotCredential] = []
        self._load()

    def _load(self):
        if CREDENTIALS_FILE.exists():
            with open(CREDENTIALS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                self.bots = [
                    BotCredential(name=b["name"], app_id=b["app_id"], app_secret=b["app_secret"])
                    for b in data.get("bots", [])
                ]

    def _save(self):
        with open(CREDENTIALS_FILE, "w", encoding="utf-8") as f:
            json.dump({"bots": [asdict(b) for b in self.bots]}, f, indent=2, ensure_ascii=False)

    def add(self, name: str, app_id: str, app_secret: str) -> BotCredential:
        """Add or update a bot credential."""
        # Remove existing if duplicate name
        self.bots = [b for b in self.bots if b.name != name]
        bot = BotCredential(name=name, app_id=app_id, app_secret=app_secret)
        self.bots.append(bot)
        self._save()
        return bot

    def get(self, name: str) -> BotCredential | None:
        return next((b for b in self.bots if b.name == name), None)

    def list_names(self) -> list[str]:
        return [b.name for b in self.bots]

    def remove(self, name: str):
        self.bots = [b for b in self.bots if b.name != name]
        self._save()


# ─── App Registry (Device Flow) ───────────────────────────────────────────────

def register_app(name: str, brand: str = "feishu") -> AppRegistryResult:
    """
    Create a new bot app via device registration flow.
    Opens browser for user to confirm, blocks until registration completes.

    Returns AppRegistryResult with app_id + app_secret.
    """
    print(f"\n[AppRegistry] Creating new bot app '{name}'...")

    # Step 1: Begin device registration
    resp = requests.post(
        REG_DEVICE_URL,
        data={
            "action": "begin",
            "archetype": "PersonalAgent",
            "auth_method": "client_secret",
            "request_user_info": "open_id tenant_brand",
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=10,
    )
    data = resp.json()

    if err := data.get("error"):
        raise Exception(f"Registration begin failed: {data.get('error_description', err)}")

    device_code = data["device_code"]
    user_code = data["user_code"]
    verification_uri = data.get("verification_uri_complete") or data["verification_uri"]
    expires_in = data.get("expires_in", 300)
    interval = data.get("interval", 5)

    # Step 2: Show verification URL
    print(f"\n[AppRegistry] Please authorize in your browser:")
    print(f"  URL: {verification_uri}")
    print(f"  Code: {user_code}")
    print(f"  Expires in: {expires_in}s\n")

    try:
        webbrowser.open(verification_uri)
    except Exception:
        pass

    print("Waiting for registration (polling)... (Ctrl+C to cancel)\n")

    # Step 3: Poll until user confirms
    deadline = time.time() + expires_in

    for attempt in range(200):
        if time.time() > deadline:
            raise Exception("Registration timed out")

        time.sleep(interval)

        poll_resp = requests.post(
            REG_DEVICE_URL,
            data={
                "action": "poll",
                "device_code": device_code,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=10,
        )
        poll_data = poll_resp.json()

        app_id = poll_data.get("client_id")
        app_secret = poll_data.get("client_secret")

        if app_id and app_secret:
            print(f"[AppRegistry] Bot '{name}' created successfully!")
            print(f"  app_id: {app_id}")
            print(f"  app_secret: {app_secret}")
            return AppRegistryResult(app_id=app_id, app_secret=app_secret)

        err = poll_data.get("error", "")

        if err == "authorization_pending":
            dots = "." * ((attempt % 10) + 1)
            print(f"\r  Waiting{dots:<10}", end="", flush=True)
            continue
        elif err == "slow_down":
            interval = min(interval + 5, 60)
            print(f"\n[AppRegistry] Slow down, interval: {interval}s")
            continue
        elif err == "access_denied":
            raise Exception("Registration denied by user")
        elif err in ("expired_token", "invalid_grant"):
            raise Exception("Device code expired, please try again")

        desc = poll_data.get("error_description", err)
        raise Exception(f"Registration poll failed: {desc}")

    raise Exception("Max poll attempts reached")


def register_and_save(name: str) -> BotCredential:
    """Create app and save credentials to store."""
    result = register_app(name)
    creds = Credentials()
    return creds.add(name, result.app_id, result.app_secret)


# ─── Token Management ─────────────────────────────────────────────────────────

_token_cache: dict[str, tuple[str, float]] = {}  # name -> (token, expires_at)


def get_token(name: str) -> str:
    """
    Get a valid app_access_token for the named bot.
    Uses in-memory cache, refreshes when within 5 minutes of expiry.
    """
    global _token_cache

    now = time.time()

    if name in _token_cache:
        token, expires_at = _token_cache[name]
        if expires_at > now + 300:  # valid for > 5 more minutes
            return token

    creds = Credentials()
    bot = creds.get(name)
    if not bot:
        raise Exception(f"Bot '{name}' not found. Run: python -m src.auth.app_auth --register {name}")

    resp = requests.post(
        TOKEN_URL,
        json={"app_id": bot.app_id, "app_secret": bot.app_secret},
        timeout=10,
    )
    data = resp.json()
    if data.get("code") != 0:
        raise Exception(f"Failed to get app_access_token: {data.get('msg')}")

    token = data["app_access_token"]
    expires_in = data.get("expire", 7200)
    _token_cache[name] = (token, now + expires_in)
    return token


def clear_cache():
    """Clear the token cache."""
    global _token_cache
    _token_cache = {}
