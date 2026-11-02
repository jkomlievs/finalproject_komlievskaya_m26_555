import threading

from valutatrade_hub.logging_config import logger
from valutatrade_hub.parser_service.updater import RatesUpdater


class RatesScheduler:
    """Простой планировщик на threading.Timer — без внешних зависимостей."""

    def __init__(self, updater: RatesUpdater, interval_seconds: int = 300) -> None:
        self._updater = updater
        self._interval = interval_seconds
        self._timer: threading.Timer | None = None
        self._running = False

    def _tick(self) -> None:
        logger.info("Scheduler: запуск периодического обновления курсов")
        self._updater.run_update()
        if self._running:
            self._schedule_next()

    def _schedule_next(self) -> None:
        self._timer = threading.Timer(self._interval, self._tick)
        self._timer.daemon = True
        self._timer.start()

    def start(self) -> None:
        self._running = True
        self._schedule_next()

    def stop(self) -> None:
        self._running = False
        if self._timer:
            self._timer.cancel()