from __future__ import annotations

import argparse
import sys

from valutatrade_hub.core.exceptions import (
    ApiRequestError,
    AuthError,
    CurrencyNotFoundError,
    InsufficientFundsError,
    ValidationError,
    ValutaTradeError,
    WalletNotFoundError,
)
from valutatrade_hub.core.usecases import (
    buy,
    get_rate_info,
    login,
    logout,
    register,
    sell,
    show_portfolio,
)
from valutatrade_hub.parser_service.api_clients import (
    CoinGeckoClient,
    ExchangeRateApiClient,
)
from valutatrade_hub.parser_service.storage import load_rates_cache
from valutatrade_hub.parser_service.updater import RatesUpdater


class FriendlyArgumentParser(argparse.ArgumentParser):


    def error(self, message: str) -> None:
        friendly = self._build_friendly_message(message)
        raise ValidationError(friendly)

    def _build_friendly_message(self, message: str) -> str:
        if "the following arguments are required" in message:
            missing = message.split("required:")[-1].strip()
            field_names = {
                "username": "имя пользователя",
                "password": "пароль",
                "currency": "код валюты",
                "amount": "количество",
                "from_currency": "исходная валюта",
                "to_currency": "целевая валюта",
            }
            readable = ", ".join(
                field_names.get(f.strip(), f.strip()) for f in missing.split(",")
            )
            return f"Некорректная команда: необходимо ввести: {readable}."

        if "invalid float value" in message:
            return "Некорректная команда: введите корректное числовое значение."

        if "invalid choice" in message and "command" in message:
            return (
                "Некорректная команда: неизвестная команда. Доступные команды — "
                "register, login, logout, buy, sell, get-rate, show-portfolio, "
                "update-rates, show-rates."
            )

        return "Некорректная команда: проверьте правильность введённых данных."


def build_parser() -> argparse.ArgumentParser:
    parser = FriendlyArgumentParser(
        prog="valutatrade",
        description="ValutaTrade Hub — консольное приложение для торговли валютами",
    )
    sub = parser.add_subparsers(
        dest="command", required=True, parser_class=FriendlyArgumentParser
    )

    p_register = sub.add_parser("register", help="Зарегистрировать нового пользователя")
    p_register.add_argument("username")
    p_register.add_argument("password")

    p_login = sub.add_parser("login", help="Войти в систему")
    p_login.add_argument("username")
    p_login.add_argument("password")

    sub.add_parser("logout", help="Выйти из системы")

    p_buy = sub.add_parser("buy", help="Купить валюту")
    p_buy.add_argument("currency")
    p_buy.add_argument("amount", type=float)

    p_sell = sub.add_parser("sell", help="Продать валюту")
    p_sell.add_argument("currency")
    p_sell.add_argument("amount", type=float)

    p_rate = sub.add_parser("get-rate", help="Показать курс пары валют")
    p_rate.add_argument("from_currency")
    p_rate.add_argument("to_currency")

    p_portfolio = sub.add_parser("show-portfolio", help="Показать текущий портфель")
    p_portfolio.add_argument("--base", default="USD")

    p_update = sub.add_parser("update-rates", help="Обновить курсы валют из внешних API")
    p_update.add_argument(
        "--source", choices=["coingecko", "exchangerate"], default=None,
        help="Обновить только из указанного источника",
    )

    p_show_rates = sub.add_parser("show-rates", help="Показать курсы из локального кеша")
    p_show_rates.add_argument("--currency")
    p_show_rates.add_argument("--top", type=int)
    p_show_rates.add_argument("--base", default="USD")

    return parser


def cmd_register(args: argparse.Namespace) -> str:
    return register(args.username, args.password)


def cmd_login(args: argparse.Namespace) -> str:
    return login(args.username, args.password)


def cmd_logout(_args: argparse.Namespace) -> str:
    return logout()


def cmd_buy(args: argparse.Namespace) -> str:
    return buy(args.currency, args.amount)


def cmd_sell(args: argparse.Namespace) -> str:
    return sell(args.currency, args.amount)


def cmd_get_rate(args: argparse.Namespace) -> str:
    return get_rate_info(args.from_currency, args.to_currency)


def cmd_show_portfolio(args: argparse.Namespace) -> str:
    return show_portfolio(base=args.base)


def cmd_update_rates(args: argparse.Namespace) -> str:
    updater = RatesUpdater([CoinGeckoClient(), ExchangeRateApiClient()])
    result = updater.run_update(source_filter=args.source)
    if result["errors"]:
        return (
            "Update completed with errors. Check logs/actions.log for details.\n"
            f"Обновлено: {result['updated']}. Ошибки: {'; '.join(result['errors'])}"
        )
    return f"Update successful. Total rates updated: {result['updated']}."


def cmd_show_rates(args: argparse.Namespace) -> str:
    cache = load_rates_cache()
    pairs = cache.get("pairs", {})

    if not pairs:
        return "Локальный кеш курсов пуст. Выполните 'update-rates', чтобы загрузить данные."

    if args.currency:
        key = f"{args.currency.upper()}_{args.base.upper()}"
        if key not in pairs:
            return f"Курс для '{args.currency}' не найден в кеше."
        item = pairs[key]
        return f"Rates from cache (updated at {item['updated_at']}):\n- {key}: {item['rate']}"

    items = sorted(pairs.items(), key=lambda kv: kv[1]["rate"], reverse=True)
    if args.top:
        items = items[: args.top]

    lines = [f"Rates from cache (updated at {cache.get('last_refresh')}):"]
    for key, item in items:
        lines.append(f"- {key}: {item['rate']}")
    return "\n".join(lines)


COMMAND_HANDLERS = {
    "register": cmd_register,
    "login": cmd_login,
    "logout": cmd_logout,
    "buy": cmd_buy,
    "sell": cmd_sell,
    "get-rate": cmd_get_rate,
    "show-portfolio": cmd_show_portfolio,
    "update-rates": cmd_update_rates,
    "show-rates": cmd_show_rates,
}


def dispatch(args: argparse.Namespace) -> str:
    handler = COMMAND_HANDLERS.get(args.command)
    if handler is None:
        return f"Неизвестная команда: {args.command}"
    return handler(args)


def _handle_domain_errors(exc: Exception) -> str:

    if isinstance(exc, InsufficientFundsError):
        return str(exc)
    if isinstance(exc, CurrencyNotFoundError):
        return f"{exc}. Подсказка: поддерживаемые коды — USD, EUR, GBP, RUB, BTC, ETH, SOL."
    if isinstance(exc, ApiRequestError):
        return f"{exc}. Повторите попытку позже или проверьте подключение к сети."
    if isinstance(exc, WalletNotFoundError):
        return str(exc)
    if isinstance(exc, AuthError):
        return str(exc)
    if isinstance(exc, ValidationError):
        return str(exc)
    if isinstance(exc, ValutaTradeError):
        return f"Ошибка: {exc}"
    raise exc


def run_cli(argv: list[str] | None = None) -> int:
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
    except ValidationError as exc:
        print(str(exc))
        return 1

    try:
        result = dispatch(args)
        print(result)
        return 0
    except (
        InsufficientFundsError,
        CurrencyNotFoundError,
        ApiRequestError,
        WalletNotFoundError,
        AuthError,
        ValidationError,
        ValutaTradeError,
    ) as exc:
        print(_handle_domain_errors(exc))
        return 1


def run_repl() -> None:

    parser = build_parser()
    print("ValutaTrade Hub — интерактивный режим. Введите 'exit' для выхода.")

    while True:
        try:
            raw = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nЗавершение работы.")
            break

        if not raw:
            continue
        if raw.lower() in ("exit", "quit"):
            print("До встречи!")
            break

        try:
            args = parser.parse_args(raw.split())
            result = dispatch(args)
            print(result)
        except (
            InsufficientFundsError,
            CurrencyNotFoundError,
            ApiRequestError,
            WalletNotFoundError,
            AuthError,
            ValidationError,
            ValutaTradeError,
        ) as exc:
            print(_handle_domain_errors(exc))


if __name__ == "__main__":
    sys.exit(run_cli())
