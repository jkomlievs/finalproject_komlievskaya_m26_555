import functools
import time

from valutatrade_hub.logging_config import logger


def log_action(func):

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        start = time.perf_counter()
        logger.info("Вызов %s(args=%s, kwargs=%s)", func.__name__, args, kwargs)
        try:
            result = func(*args, **kwargs)
        except Exception as exc:
            elapsed = (time.perf_counter() - start) * 1000
            logger.error("%s завершился ошибкой за %.2f мс: %s", func.__name__, elapsed, exc)
            raise
        else:
            elapsed = (time.perf_counter() - start) * 1000
            logger.info("%s выполнен успешно за %.2f мс", func.__name__, elapsed)
            return result

    return wrapper


def confirm_action(prompt: str = "Вы уверены? (y/n): "):

    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            answer = input(prompt).strip().lower()
            if answer not in ("y", "yes", "да"):
                logger.info("Действие %s отменено пользователем", func.__name__)
                return "Операция отменена."
            return func(*args, **kwargs)

        return wrapper

    return decorator