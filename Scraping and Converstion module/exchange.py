"""Frankfurter Currency API helpers."""

from functools import lru_cache

import requests


BASE_URL = "https://api.frankfurter.app/latest"


@lru_cache(maxsize=32)
def get_exchange_rate(from_currency: str, to_currency: str) -> float:
    """Return the exchange rate between two currencies."""

    source_currency = from_currency.upper()
    target_currency = to_currency.upper()

    if source_currency == target_currency:
        return 1.0

    url = f"{BASE_URL}?from={source_currency}&to={target_currency}"
    response = requests.get(url, timeout=10)
    
    if response.status_code != 200:
        # Fallback for unsupported currencies (like EGP, ZAR)
        fallback_url = f"https://open.er-api.com/v6/latest/{source_currency}"
        fb_response = requests.get(fallback_url, timeout=10)
        if fb_response.status_code == 200:
            data = fb_response.json()
            return data["rates"].get(target_currency, 0.0)
        return 0.0

    data = response.json()
    return data["rates"].get(target_currency, 0.0)


def convert_currency(price: float, from_currency: str, to_currency: str) -> float:
    """Convert a price from one currency into another."""

    rate = get_exchange_rate(from_currency, to_currency)
    return round(price * rate, 2)


if __name__ == "__main__":
    usd = 729
    inr = convert_currency(usd, "USD", "INR")
    print(inr)