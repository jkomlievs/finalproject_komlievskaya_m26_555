from pathlib import Path
from typing import Any


class SettingsLoader:

    _instance: "SettingsLoader | None" = None

    def __new__(cls) -> "SettingsLoader":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._init_settings()
        return cls._instance

    def _init_settings(self) -> None:
        base_dir = Path(__file__).resolve().parent.parent.parent
        self._settings: dict[str, Any] = {
            "data_dir": base_dir / "data",
            "users_file": "users.json",
            "portfolios_file": "portfolios.json",
            "rates_file": "rates.json",
            "rate_ttl_minutes": 5,
            "default_base_currency": "USD",
        }

    def get(self, key: str, default: Any = None) -> Any:
        return self._settings.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self._settings[key] = value


settings = SettingsLoader()