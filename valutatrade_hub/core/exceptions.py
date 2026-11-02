class ValutaTradeError(Exception):
    """Базовое исключение приложения."""


class ValidationError(ValutaTradeError):
    """Ошибка валидации входных данных."""


class AuthError(ValutaTradeError):
    """Ошибка аутентификации/авторизации."""


class CurrencyNotFoundError(ValutaTradeError):
    """Валюта с таким кодом не поддерживается приложением."""


class RateUnavailableError(ValutaTradeError):
    """Курс валюты недоступен ни в кеше, ни у Parser Service."""


class ApiRequestError(ValutaTradeError):
    """Ошибка обращения к внешнему API (сеть, таймаут, невалидный ответ)."""


class InsufficientFundsError(ValutaTradeError):
    """Недостаточно средств на кошельке."""

    def __init__(self, available: float, required: float, code: str) -> None:
        self.available = available
        self.required = required
        self.code = code
        message = (
            f"Недостаточно средств: доступно {available:.4f} {code}, "
            f"требуется {required:.4f} {code}"
        )
        super().__init__(message)


class WalletNotFoundError(ValutaTradeError):
    """Кошелёк с таким кодом валюты не найден."""


class CurrencyExistsError(ValutaTradeError):
    """Кошелёк с такой валютой уже есть в портфеле."""