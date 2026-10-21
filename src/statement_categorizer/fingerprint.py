import hashlib
import re
import unicodedata
from collections import Counter

from statement_categorizer.parsers.base import ParsedTransaction


def normalize_description(text: str) -> str:
    """Case, accents and spacing differences should not create a "new" transaction."""
    decomposed = unicodedata.normalize("NFKD", text)
    without_accents = "".join(c for c in decomposed if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", without_accents).strip().lower()


def fingerprints(account: str, transactions: list[ParsedTransaction]) -> list[str]:
    """
    Stable id per transaction, so importing the same file twice inserts nothing the second time.

    Two identical purchases on the same day (two coffees, same price) are both real, so the
    occurrence number inside the file is part of the key: the 1st and 2nd coffee get different
    fingerprints, and re-importing the file reproduces exactly the same ones.

    When the bank provides its own id (OFX FITID), that id is used instead.
    """
    seen: Counter[str] = Counter()
    result: list[str] = []
    for tx in transactions:
        if tx.external_id:
            key = f"{account}|fitid|{tx.external_id}"
        else:
            base = f"{account}|{tx.posted_on.isoformat()}|{tx.amount}|"
            base += normalize_description(tx.description)
            seen[base] += 1
            key = f"{base}#{seen[base]}"
        result.append(hashlib.sha256(key.encode()).hexdigest())
    return result
