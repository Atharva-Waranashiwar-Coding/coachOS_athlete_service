"""Pagination helpers."""

from math import ceil


def total_pages(total: int, page_size: int) -> int:
    """Return the total number of pages for a result set."""
    if total == 0:
        return 0
    return ceil(total / page_size)
