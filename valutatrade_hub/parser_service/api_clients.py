import time
from abc import ABC, abstractmethod

import requests

from valutatrade_hub.core.exceptions import ApiRequestError
from valutatrade_hub.logging_config import logger
from valutatrade_hub.parser_service.config import config


class BaseApiClient(ABC):
    source_name: str = "unknown"

    @abstractmethod
    def fetch_rates(self) -> dict[str, dict]:
        """Возвращает {'BTC_USD': {'rate': 59337.21, 'meta': {...}}, ...}."""


class CoinGeckoClient(BaseApiClient):
    source_name = "CoinGecko"

    def fetch_rates(self) -> dict[str, dict]:
        ids = ",".join(config.CRYPTO_ID_MAP[code] for code in config.CRYPTO_CURRENCIES)
        params = {"ids": ids, "vs_currencies": config.BASE_CURRENCY.lower()}

        start = time.perf_counter()
        try:
            resp = requests.get(
                config.COINGECKO_URL, params=params, timeout=config.REQUEST_TIMEOUT
            )
        except requests.exceptions.RequestException as exc:
            raise ApiRequestError(f"CoinGecko недоступен: {exc}") from exc

        request_ms = round((time.perf_counter() - start) * 1000, 2)
        logger.debug(f"CoinGecko responded in {request_ms}ms")

        if resp.status_code != 200:
            raise ApiRequestError(f"CoinGecko вернул статус {resp.status_code}")

        data = resp.json()
        result: dict[str, dict] = {}
        reverse_map = {v: k for k, v in config.CRYPTO_ID_MAP.items()}

        for coin_id, payload in data.items():
            code = reverse_map.get(coin_id)
            rate = payload.get(config.BASE_CURRENCY.lower())
            if code and rate is not None:
                result[f"{code}_{config.BASE_CURRENCY}"] = {
                    "rate": float(rate),
                    "meta": {
                        "raw_id": coin_id,
                        "request_ms": request_ms,
                        "status_code": resp.status_code,
                        "etag": resp.headers.get("ETag", ""),
                    },
                }
        return result


class ExchangeRateApiClient(BaseApiClient):
    source_name = "ExchangeRate-API"

    def fetch_rates(self) -> dict[str, dict]:
        if not config.EXCHANGERATE_API_KEY:
            raise ApiRequestError("Не задан EXCHANGERATE_API_KEY (переменная окружения)")

        url = (
            f"{config.EXCHANGERATE_API_URL}/{config.EXCHANGERATE_API_KEY}"
            f"/latest/{config.BASE_CURRENCY}"
        )
        start = time.perf_counter()
        try:
            resp = requests.get(url, timeout=config.REQUEST_TIMEOUT)
        except requests.exceptions.RequestException as exc:
            raise ApiRequestError(f"ExchangeRate-API недоступен: {exc}") from exc

        request_ms = round((time.perf_counter() - start) * 1000, 2)

        if resp.status_code == 429:
            raise ApiRequestError("Превышен лимит запросов ExchangeRate-API")
        if resp.status_code != 200:
            raise ApiRequestError(f"ExchangeRate-API вернул статус {resp.status_code}")

        data = resp.json()
        if data.get("result") != "success":
            raise ApiRequestError(f"ExchangeRate-API вернул ошибку: {data.get('error-type')}")

        rates = data.get("rates", {})
        result: dict[str, dict] = {}

        for code in config.FIAT_CURRENCIES:
            if code in rates:
                result[f"{code}_{config.BASE_CURRENCY}"] = {
                    "rate": 1 / rates[code],
                    "meta": {
                        "raw_id": code,
                        "request_ms": request_ms,
                        "status_code": resp.status_code,
                        "etag": resp.headers.get("ETag", ""),
                    },
                }
        return result
