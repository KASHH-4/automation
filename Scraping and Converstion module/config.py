"""Configuration for the DuckDuckGo-driven laptop price workflow."""

# Target country where prices should be converted.
TARGET_COUNTRY = "India"

# Laptop model to search.
LAPTOP_MODEL = "Lenovo LOQ"


# Country -> Currency.
COUNTRY_CURRENCY = {
    "India": "INR",
    "United States": "USD",
    "USA": "USD",
    "United Kingdom": "GBP",
    "Germany": "EUR",
    "France": "EUR",
    "Japan": "JPY",
    "Canada": "CAD",
    "Australia": "AUD",
}


# DuckDuckGo search is used first, then the supported store list is filtered.
DDG_RESULTS_LIMIT = 12

SUPPORTED_STORES = [
    {
        "name": "amazon",
        "display_name": "Amazon",
        "currency": "INR",
        "domains": ("amazon.", "amzn.to"),
        "search_url_template": "https://www.amazon.in/s?k={query}",
    },
    {
        "name": "flipkart",
        "display_name": "Flipkart",
        "currency": "INR",
        "domains": ("flipkart.com",),
        "search_url_template": "https://www.flipkart.com/search?q={query}",
    },
    {
        "name": "dell",
        "display_name": "Dell",
        "currency": "INR",
        "domains": ("dell.com",),
        "search_url_template": "https://www.dell.com/en-in/search/{query}",
    },
]
