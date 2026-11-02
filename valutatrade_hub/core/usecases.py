from __future__ import annotations

from datetime import datetime, timedelta

from valutatrade_hub.core.currencies import get_currency
from valutatrade_hub.core.exceptions import (
    ApiRequestError,
    AuthError,
    InsufficientFundsError,
    ValidationError,
    WalletNotFoundError,
)
from valutatrade_hub.core.models import Portfolio, User
from valutatrade_hub.core.utils import (
    generate_salt,
    hash_password,
)
from valutatrade_hub.decorators import log_action
from valutatrade_hub.infra.database import db
from valutatrade_hub.infra.settings import settings

_current_user: User | None = None


def _load_users() -> list[User]:
    return [User.from_dict(u) for u in db.load("users")]


def _save_users(users: list[User]) -> None:
    db.save("users", [u.to_dict() for u in users])


def _load_portfolios() -> list[Portfolio]:
    return [Portfolio.from_dict(p) for p in db.load("portfolios")]


def _save_portfolios(portfolios: list[Portfolio]) -> None:
    db.save("portfolios", [p.to_dict() for p in portfolios])


def _get_portfolio(user_id: str) -> tuple[list[Portfolio], Portfolio]:
    portfolios = _load_portfolios()
    for p in portfolios:
        if p.user_id == user_id:
            return portfolios, p
    new_portfolio = Portfolio(user_id=user_id)
    portfolios.append(new_portfolio)
    return portfolios, new_portfolio


def _require_login() -> User:
    if _current_user is None:
        raise AuthError("Требуется авторизация. Выполните 'login'.")
    return _current_user


def _require_logout() -> None:

    if _current_user is not None:
        raise AuthError(
            f"Вы уже авторизованы как '{_current_user.username}'. "
            f"Выполните 'logout' перед этим действием."
        )


@log_action
def register(username: str, password: str) -> str:
    _require_logout()

    username = (username or "").strip()
    if not username:
        raise ValidationError("Имя пользователя не может быть пустым")
    if not password or len(password) < 4:
        raise ValidationError("Пароль должен быть не короче 4 символов")

    users = _load_users()
    if any(u.username == username for u in users):
        raise ValidationError(f"Пользователь '{username}' уже существует")

    salt = generate_salt()
    password_hash = hash_password(password, salt)
    user_id = f"user_{len(users) + 1}"

    new_user = User(user_id=user_id, username=username, password_hash=password_hash, salt=salt)
    users.append(new_user)
    _save_users(users)

    portfolios = _load_portfolios()
    portfolios.append(Portfolio(user_id=user_id))
    _save_portfolios(portfolios)

    return f"Пользователь '{username}' успешно зарегистрирован."


@log_action
def login(username: str, password: str) -> str:
    global _current_user

    _require_logout()

    users = _load_users()
    user = next((u for u in users if u.username == username), None)
    if user is None:
        raise AuthError("Неверное имя пользователя или пароль")

    if hash_password(password, user.salt) != user.password_hash:
        raise AuthError("Неверное имя пользователя или пароль")

    _current_user = user
    return f"Добро пожаловать, {username}!"


def logout() -> str:
    global _current_user
    if _current_user is None:
        return "Вы не были авторизованы."
    username = _current_user.username
    _current_user = None
    return f"Пользователь '{username}' вышел из системы."


def _get_cached_rate(from_code: str, to_code: str) -> tuple[float, str] | None:
    rates_cache = db.load("rates")
    pairs = rates_cache.get("pairs", {})
    key = f"{from_code}_{to_code}"
    item = pairs.get(key)
    if item is None:
        return None

    ttl = timedelta(seconds=settings.get("rates_ttl_seconds", 300))
    updated_at = datetime.fromisoformat(item["updated_at"].replace("Z", "+00:00"))
    now = datetime.now(updated_at.tzinfo) if updated_at.tzinfo else datetime.now()
    if now - updated_at < ttl:
        return item["rate"], item["updated_at"]
    return None


def _fetch_rate_fallback(from_code: str, to_code: str) -> float:
    base_usd = {"USD": 1.0, "EUR": 1.07, "GBP": 1.27, "RUB": 0.0102,
                "BTC": 59300.0, "ETH": 3200.0, "SOL": 145.0}
    f_rate, t_rate = base_usd.get(from_code), base_usd.get(to_code)
    if f_rate is None or t_rate is None:
        raise ApiRequestError(f"нет данных по паре {from_code}/{to_code}")
    return f_rate / t_rate


def get_rate_pair(from_code: str, to_code: str) -> tuple[float, str]:
    from_currency = get_currency(from_code)
    to_currency = get_currency(to_code)

    cached = _get_cached_rate(from_currency.code, to_currency.code)
    if cached:
        return cached

    try:
        rate = _fetch_rate_fallback(from_currency.code, to_currency.code)
    except ApiRequestError:
        rates_cache = db.load("rates")
        stale = rates_cache.get("pairs", {}).get(f"{from_currency.code}_{to_currency.code}")
        if stale:
            return stale["rate"], stale["updated_at"]
        raise

    now_iso = datetime.now().isoformat()
    rates_cache = db.load("rates")
    rates_cache.setdefault("pairs", {})[f"{from_currency.code}_{to_currency.code}"] = {
        "rate": rate,
        "updated_at": now_iso,
        "source": "fallback",
    }
    rates_cache["last_refresh"] = now_iso
    db.save("rates", rates_cache)
    return rate, now_iso


@log_action
def get_rate_info(from_code: str, to_code: str) -> str:
    from_code = (from_code or "").strip().upper()
    to_code = (to_code or "").strip().upper()

    rate, updated_at = get_rate_pair(from_code, to_code)
    reverse_rate, _ = get_rate_pair(to_code, from_code)

    dt = datetime.fromisoformat(updated_at.replace("Z", "+00:00")).strftime("%Y-%m-%d %H:%M:%S")

    return (
        f"Курс {from_code}→{to_code}: {rate:.8g} (обновлено: {dt})\n"
        f"Обратный курс {to_code}→{from_code}: {reverse_rate:.2f}"
    )


@log_action
def buy(currency_code: str, amount: float, username: str | None = None) -> str:
    user = _require_login()
    currency = get_currency(currency_code)

    if not isinstance(amount, (int, float)) or isinstance(amount, bool) or amount <= 0:
        raise ValidationError("'amount' должен быть положительным числом")

    rate, _ = get_rate_pair(currency.code, settings.get("default_base_currency", "USD"))

    portfolios, portfolio = _get_portfolio(user.user_id)
    wallet = portfolio.get_wallet(currency.code) or portfolio.add_currency(currency.code)

    before = wallet.balance
    wallet.deposit(amount)
    _save_portfolios(portfolios)

    base = settings.get("default_base_currency", "USD")
    cost = amount * rate

    return (
        f"Покупка выполнена: {amount:.4f} {currency.code} "
        f"по курсу {rate:.2f} {base}/{currency.code}\n"
        f"Изменения в портфеле:\n"
        f"- {currency.code}: было {before:.4f} → стало {wallet.balance:.4f}\n"
        f"Оценочная стоимость покупки: {cost:,.2f} {base}"
    )


@log_action
def sell(currency_code: str, amount: float, username: str | None = None) -> str:
    user = _require_login()
    currency = get_currency(currency_code)

    if not isinstance(amount, (int, float)) or isinstance(amount, bool) or amount <= 0:
        raise ValidationError("'amount' должен быть положительным числом")

    rate, _ = get_rate_pair(currency.code, settings.get("default_base_currency", "USD"))

    portfolios, portfolio = _get_portfolio(user.user_id)
    wallet = portfolio.get_wallet(currency.code)
    if wallet is None:
        raise WalletNotFoundError(
            f"У вас нет кошелька '{currency.code}'. Он создаётся автоматически при первой покупке."
        )

    before = wallet.balance
    if amount > wallet.balance:
        raise InsufficientFundsError(available=wallet.balance, required=amount, code=currency.code)

    wallet.withdraw(amount)
    _save_portfolios(portfolios)

    base = settings.get("default_base_currency", "USD")
    proceeds = amount * rate

    return (
        f"Продажа выполнена: {amount:.4f} {currency.code} "
        f"по курсу {rate:.2f} {base}/{currency.code}\n"
        f"Изменения в портфеле:\n"
        f"- {currency.code}: было {before:.4f} → стало {wallet.balance:.4f}\n"
        f"Оценочная выручка: {proceeds:,.2f} {base}"
    )


def show_portfolio(base: str = "USD") -> str:
    user = _require_login()
    _, portfolio = _get_portfolio(user.user_id)

    base_currency = get_currency(base)

    if not portfolio.wallets:
        return f"Портфель пользователя '{user.username}' пуст."

    lines = [f"Портфель пользователя '{user.username}' (база: {base_currency.code}):"]
    for code, wallet in portfolio.wallets.items():
        lines.append(f"- {wallet.get_balance_info()}")

    total = portfolio.get_total_value(base=base_currency.code, rate_fetcher=get_rate_pair)
    lines.append(f"ИТОГО: {total:,.2f} {base_currency.code}")
    return "\n".join(lines)
