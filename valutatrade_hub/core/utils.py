import hashlib
import secrets
from datetime import datetime, timedelta

from valutatrade_hub.core.exceptions import RateUnavailableError, ValidationError
from valutatrade_hub.infra.database import db
from valutatrade_hub.infra.settings import settings

RATE_TTL = timedelta(minutes=settings.get("rate_ttl_minutes"))

BASE_USD_RATES = {"USD": 1.0, "EUR": 1.07, "BTC": 59300.0, "ETH": 3200.0}


def generate_salt() -> str:
    return secrets.token_hex(8)


def hash_password(password: str, salt: str) -> str:
    return hashlib.sha256((password + salt).encode("utf-8")).hexdigest()


def validate_currency_code(code: str) -> str:
    code = (code or "").strip().upper()
    if not code or not code.isalpha():
        raise ValidationError(f"Некорректный код валюты: '{code}'")
    return code


def validate_amount(amount: float) -> float:
    if not isinstance(amount, (int, float)) or isinstance(amount, bool) or amount <= 0:
        raise ValidationError("'amount' должен быть положительным числом")
    return float(amount)


def _parser_service_fetch(from_cur: str, to_cur: str) -> float | None:
    from_rate = BASE_USD_RATES.get(from_cur)
    to_rate = BASE_USD_RATES.get(to_cur)
    if from_rate is None or to_rate is None:
        return None
    return from_rate / to_rate


def get_pair_rate(from_cur: str, to_cur: str) -> tuple[float, str]:
    from_cur, to_cur = from_cur.upper(), to_cur.upper()
    key = f"{from_cur}_{to_cur}"

    rates = db.load("rates")
    cached = rates.get(key)

    if cached:
        updated_at = datetime.fromisoformat(cached["updated_at"])
        if datetime.now() - updated_at < RATE_TTL:
            return cached["rate"], cached["updated_at"]

    rate = _parser_service_fetch(from_cur, to_cur)
    if rate is None:
        if cached:
            return cached["rate"], cached["updated_at"]
        raise RateUnavailableError(
            f"Курс {from_cur}→{to_cur} недоступен. Повторите попытку позже."
        )

    now_iso = datetime.now().isoformat()
    rates[key] = {"rate": rate, "updated_at": now_iso}
    db.save("rates", rates)
    return rate, now_iso


def get_rate(currency_code: str) -> float | None:
    try:
        rate, _ = get_pair_rate(currency_code, "USD")
        return rate
    except RateUnavailableError:
        return None