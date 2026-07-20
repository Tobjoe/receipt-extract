"""Minimal ISO-4217 currency code set (common subset)."""

ISO_4217: frozenset[str] = frozenset(
    {
        "CHF", "EUR", "USD", "GBP", "JPY", "CNY", "AUD", "CAD", "SEK",
        "NOK", "DKK", "PLN", "CZK", "HUF", "RON", "TRY", "RUB", "INR",
        "BRL", "MXN", "ZAR", "SGD", "HKD", "NZD", "KRW", "THB", "AED",
        "SAR", "ILS",
    }
)
