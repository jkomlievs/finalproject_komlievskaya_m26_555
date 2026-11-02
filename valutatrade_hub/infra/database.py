import json
from pathlib import Path
from typing import Any

from valutatrade_hub.infra.settings import settings


class DatabaseManager:

    _instance: "DatabaseManager | None" = None

    def __new__(cls) -> "DatabaseManager":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._init_db()
        return cls._instance

    def _init_db(self) -> None:
        self._data_dir: Path = settings.get("data_dir")
        self._files = {
            "users": self._data_dir / settings.get("users_file"),
            "portfolios": self._data_dir / settings.get("portfolios_file"),
            "rates": self._data_dir / settings.get("rates_file"),
        }
        self._ensure_files()

    def _ensure_files(self) -> None:
        self._data_dir.mkdir(parents=True, exist_ok=True)
        for name, path in self._files.items():
            if not path.exists():
                default = {} if name == "rates" else []
                self._write(path, default)

    @staticmethod
    def _read(path: Path) -> Any:
        with open(path, encoding="utf-8") as f:
            return json.load(f)

    @staticmethod
    def _write(path: Path, data: Any) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False, default=str)

    def load(self, table: str) -> Any:
        return self._read(self._files[table])

    def save(self, table: str, data: Any) -> None:
        self._write(self._files[table], data)


db = DatabaseManager()