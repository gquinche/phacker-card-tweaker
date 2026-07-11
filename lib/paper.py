"""Shared paper-stock colors for card fronts and backs."""

PAPER_STOCKS = {
    "cream": {"hex": "#F2ECE0", "edge": "#D9CFB9"},
    "white": {"hex": "#FFFFFF", "edge": "#D9D9D9"},
    "manila": {"hex": "#EFE7D2", "edge": "#CDBE9A"},
}
DEFAULT_PAPER = "white"


def paper_stock(name: str) -> dict[str, str]:
    return PAPER_STOCKS.get(name, PAPER_STOCKS[DEFAULT_PAPER])
