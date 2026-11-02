from valutatrade_hub.core.exceptions import ApiRequestError
from valutatrade_hub.logging_config import logger
from valutatrade_hub.parser_service.storage import append_history, save_rates_cache


class RatesUpdater:
    def __init__(self, clients: list) -> None:
        self._clients = clients

    def run_update(self, source_filter: str | None = None) -> dict:
        logger.info("Starting rates update...")
        all_pairs: dict[str, dict] = {}
        errors: list[str] = []

        for client in self._clients:
            name = client.source_name
            if source_filter and source_filter.lower() not in name.lower():
                continue
            try:
                rates = client.fetch_rates()
                for key, payload in rates.items():
                    all_pairs[key] = {
                        "rate": payload["rate"],
                        "source": name,
                        "meta": payload.get("meta", {}),
                    }
                logger.info("Fetching from %s... OK (%d rates)", name, len(rates))
            except ApiRequestError as exc:
                logger.error("Failed to fetch from %s: %s", name, exc)
                errors.append(f"{name}: {exc}")

        if all_pairs:
            save_rates_cache(all_pairs)
            append_history(all_pairs)
            logger.info("Writing %d rates to rates.json...", len(all_pairs))

        return {"updated": len(all_pairs), "errors": errors}
