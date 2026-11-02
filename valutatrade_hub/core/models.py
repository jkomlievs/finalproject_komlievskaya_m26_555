from __future__ import annotations

from datetime import datetime
from typing import Any

from valutatrade_hub.core.exceptions import (
    ApiRequestError,
    CurrencyExistsError,
    InsufficientFundsError,
)
from valutatrade_hub.core.utils import (
    validate_amount,
    validate_currency_code,
)


class User:

    def __init__(
        self,
        user_id: str,
        username: str,
        password_hash: str,
        salt: str,
        created_at: str | None = None,
    ) -> None:
        self._user_id = user_id
        self._username = username
        self._password_hash = password_hash
        self._salt = salt
        self._created_at = created_at or datetime.now().isoformat()

    @property
    def user_id(self) -> str:
        return self._user_id

    @property
    def username(self) -> str:
        return self._username

    @property
    def password_hash(self) -> str:
        return self._password_hash

    @property
    def salt(self) -> str:
        return self._salt

    @property
    def created_at(self) -> str:
        return self._created_at

    def get_user_info(self) -> dict[str, Any]:
        return {
            "user_id": self._user_id,
            "username": self._username,
            "created_at": self._created_at,
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "user_id": self._user_id,
            "username": self._username,
            "password_hash": self._password_hash,
            "salt": self._salt,
            "created_at": self._created_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> User:
        return cls(
            user_id=data["user_id"],
            username=data["username"],
            password_hash=data["password_hash"],
            salt=data["salt"],
            created_at=data.get("created_at"),
        )

    def __repr__(self) -> str:
        return f"<User {self._username}>"


class Wallet:

    def __init__(self, currency_code: str, balance: float = 0.0) -> None:
        self._currency_code = validate_currency_code(currency_code)
        self._balance = 0.0
        if balance:
            self.deposit(balance)

    @property
    def currency_code(self) -> str:
        return self._currency_code

    @property
    def balance(self) -> float:
        return self._balance

    @balance.setter
    def balance(self, value: float) -> None:
        if value < 0:
            raise ValueError("Баланс не может быть отрицательным")
        self._balance = float(value)

    def deposit(self, amount: float) -> None:
        amount = validate_amount(amount)
        self.balance = self._balance + amount

    def withdraw(self, amount: float) -> None:
        amount = validate_amount(amount)
        if amount > self._balance:
            raise InsufficientFundsError(
                available=self._balance,
                required=amount,
                code=self._currency_code,
            )
        self.balance = self._balance - amount

    def get_balance_info(self) -> str:
        return f"{self._currency_code}: {self._balance:.4f}"

    def to_dict(self) -> dict[str, Any]:
        return {"currency_code": self._currency_code, "balance": self._balance}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Wallet:
        return cls(currency_code=data["currency_code"], balance=data["balance"])

    def __repr__(self) -> str:
        return f"<Wallet {self._currency_code}: {self._balance:.4f}>"


class Portfolio:

    def __init__(self, user_id: str, wallets: dict[str, Wallet] | None = None) -> None:
        self._user_id = user_id
        self._wallets: dict[str, Wallet] = wallets or {}

    @property
    def user_id(self) -> str:
        return self._user_id

    @property
    def wallets(self) -> dict[str, Wallet]:

        return dict(self._wallets)

    def get_wallet(self, currency_code: str) -> Wallet | None:
        return self._wallets.get(currency_code.upper())

    def add_currency(self, currency_code: str) -> Wallet:
        currency_code = validate_currency_code(currency_code)
        if currency_code in self._wallets:
            raise CurrencyExistsError(f"Кошелёк '{currency_code}' уже существует")
        wallet = Wallet(currency_code)
        self._wallets[currency_code] = wallet
        return wallet

    def get_total_value(self, base: str = "USD", rate_fetcher=None) -> float:

        if rate_fetcher is None:
            from valutatrade_hub.core.usecases import get_rate_pair as rate_fetcher

        total = 0.0
        for code, wallet in self._wallets.items():
            try:
                rate, _ = rate_fetcher(code, base)
                total += wallet.balance * rate
            except ApiRequestError:
                continue
        return total

    def to_dict(self) -> dict[str, Any]:
        return {
            "user_id": self._user_id,
            "wallets": {code: w.to_dict() for code, w in self._wallets.items()},
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Portfolio:
        wallets = {
            code: Wallet.from_dict(w_data)
            for code, w_data in data.get("wallets", {}).items()
        }
        return cls(user_id=data["user_id"], wallets=wallets)

    def __repr__(self) -> str:
        return f"<Portfolio {self._user_id}: {list(self._wallets.keys())}>"
