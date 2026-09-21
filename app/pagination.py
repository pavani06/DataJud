"""Bounded cursor traversal; never infer a complete snapshot from search_after."""
from dataclasses import dataclass, field
import hashlib
import json


@dataclass
class PaginationGuard:
    max_pages: int = 100
    pages: int = 0
    cursors: set[str] = field(default_factory=set)
    pages_seen: set[str] = field(default_factory=set)

    def observe(self, identities: list[str], cursor: list | None) -> str | None:
        self.pages += 1
        fingerprint = hashlib.sha256(json.dumps(identities, sort_keys=True).encode()).hexdigest()
        if fingerprint in self.pages_seen:
            return 'repeated_page'
        self.pages_seen.add(fingerprint)
        if cursor is None or not isinstance(cursor, list) or not cursor:
            return 'missing_cursor'
        encoded = json.dumps(cursor, sort_keys=True, allow_nan=False)
        if encoded in self.cursors:
            return 'repeated_cursor'
        self.cursors.add(encoded)
        if self.pages >= self.max_pages:
            return 'max_pages'
        return None
