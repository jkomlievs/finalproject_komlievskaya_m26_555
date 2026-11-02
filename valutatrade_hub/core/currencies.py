from abc import ABC, abstractmethod

from valutatrade_hub.core.exceptions import CurrencyNotFoundError


class Currency(ABC):

    def __init__(self, code: str, name: str) -> None:
        self._code = code.upper()
        self._name = name

    @property
    def code(self) -> str:
        return self._code

    @property
    def name(self) -> str:
        return self._name

    @property
    @abstractmethod
    def decimals(self) -> int:
        """Количество знаков после запятой для отображения баланса"""

    def format_amount(self, amount: float) -> str:
        return f"{amount:.{self.decimals}f} {self._code}"

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} {self._code}>"


class Fiat(Currency):
    """Фиатная валюта (USD, EUR и т.д.)."""

    def __init__(self, code: str, name: str, country: str = "") -> None:
        super().__init__(code, name)
        self._country = country

    @property
    def decimals(self) -> int:
        return 2

    @property
    def country(self) -> str:
        return self._country


class Crypto(Currency):
    """Криптовалюта (BTC, ETH и т.д.)."""

    def __init__(self, code: str, name: str, blockchain: str = "") -> None:
        super().__init__(code, name)
        self._blockchain = blockchain

    @property
    def decimals(self) -> int:
        return 8

    @property
    def blockchain(self) -> str:
        return self._blockchain


KNOWN_CURRENCIES: dict[str, Currency] = {
    "USD": Fiat("USD", "US Dollar", "USA"),
    "EUR": Fiat("EUR", "Euro", "EU"),
    "GBP": Fiat("GBP", "British Pound", "UK"),
    "RUB": Fiat("RUB", "Russian Ruble", "Russia"),
    "BTC": Crypto("BTC", "Bitcoin", "Bitcoin"),
    "ETH": Crypto("ETH", "Ethereum", "Ethereum"),
    "SOL": Crypto("SOL", "Solana", "Solana"),
}


def get_currency(code: str) -> Currency:

    currency = KNOWN_CURRENCIES.get((code or "").upper())
    if currency is None:
        raise CurrencyNotFoundError(f"Валюта '{code}' не поддерживается")
    return currency