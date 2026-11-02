import json
import os
import tempfile
from datetime import UTC, datetime
from pathlib import Path

from valutatrade_hub.parser_service.config import config

RATES_PATH = Path(config.RATES_FILE_PATH)
HISTORY_PATH = Path(config.HISTORY_FILE_PATH)


def _atomic_write(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        os.replace(tmp_path, path)
    except Exception:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        raise


def load_rates_cache() -> dict:
    if not RATES_PATH.exists():
        return {"pairs": {}, "last_refresh": None}
    with open(RATES_PATH, encoding="utf-8") as f:
        return json.load(f)


def save_rates_cache(pairs: dict[str, dict]) -> None:
    """pairs: {'BTC_USD': {'rate': 59337.21, 'source': 'CoinGecko', 'meta': {...}}, ...}"""
    cache = load_rates_cache()
    now = datetime.now(UTC).isoformat()

    for pair_key, payload in pairs.items():
        existing = cache["pairs"].get(pair_key)
        if existing and existing["updated_at"] >= now:
            continue  # апдейт "побеждает", только если он свежее
        cache["pairs"][pair_key] = {
            "rate": payload["rate"],
            "updated_at": now,
            "source": payload["source"],
        }

    cache["last_refresh"] = now
    _atomic_write(RATES_PATH, cache)


def append_history(pairs: dict[str, dict]) -> None:
    history = []
    if HISTORY_PATH.exists():
        with open(HISTORY_PATH, encoding="utf-8") as f:
            history = json.load(f)

    now = datetime.now(UTC)
    ts = now.strftime("%Y-%m-%dT%H:%M:%SZ")

    for pair_key, payload in pairs.items():
        from_cur, to_cur = pair_key.split("_")
        entry = {
            "id": f"{from_cur}_{to_cur}_{ts}",
            "from_currency": from_cur,
            "to_currency": to_cur,
            "rate": payload["rate"],
            "timestamp": ts,
            "source": payload["source"],
            "meta": payload.get("meta", {}),
        }
        history.append(entry)

    _atomic_write(HISTORY_PATH, history)
