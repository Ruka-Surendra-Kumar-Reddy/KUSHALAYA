"""CSV formula-injection guard for every CSV the app hands out.

A spreadsheet treats a cell that starts with ``= + - @`` (or a tab / carriage
return) as a formula. Text cells that start that way are prefixed with ``'``.
Plain numbers (``-3068.00``) are left alone so money columns stay numeric.
"""

from __future__ import annotations

import re

_TRIGGERS = ("=", "+", "-", "@", "\t", "\r")
_NUMBER = re.compile(r"^[+-]?\d+(\.\d+)?$")


def csv_safe(value):
    if not isinstance(value, str) or not value or not value.startswith(_TRIGGERS):
        return value
    if _NUMBER.match(value):
        return value
    return "'" + value


def csv_safe_row(row) -> list:
    return [csv_safe(v) for v in row]


class SafeWriter:
    """Drop-in for ``csv.writer`` that escapes formula-looking cells."""

    def __init__(self, f, **kwargs):
        import csv

        self._w = csv.writer(f, **kwargs)

    def writerow(self, row):
        return self._w.writerow(csv_safe_row(row))

    def writerows(self, rows):
        for row in rows:
            self.writerow(row)
