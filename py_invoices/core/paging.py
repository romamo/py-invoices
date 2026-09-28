"""Iterate over every record of a repository, one page at a time."""

from collections.abc import Iterator
from typing import Any, TypeVar

from pydantic_invoices.interfaces.base import BaseRepository

M = TypeVar("M")

PAGE_SIZE = 500


def iter_all(repo: BaseRepository[M, Any]) -> Iterator[M]:
    """Yield every record, paging through get_all so no default limit truncates results."""
    skip = 0
    while True:
        page = repo.get_all(skip=skip, limit=PAGE_SIZE)
        yield from page
        if len(page) < PAGE_SIZE:
            return
        skip += PAGE_SIZE
