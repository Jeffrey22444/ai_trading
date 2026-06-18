"""Thread-safe cache for derivative-market context such as OI and funding."""

from threading import RLock
from typing import Dict, Optional

from market.types import DerivativesSnapshot


class DerivativesCache:
    """Shared derivative-market snapshot cache."""

    def __init__(self):
        self.cache: Dict[str, DerivativesSnapshot] = {}
        self.previous_cache: Dict[str, DerivativesSnapshot] = {}
        self.lock = RLock()

    def update_snapshot(self, snapshot: DerivativesSnapshot) -> None:
        with self.lock:
            current = self.cache.get(snapshot.symbol)
            if current is not None:
                self.previous_cache[snapshot.symbol] = current
            self.cache[snapshot.symbol] = snapshot

    def get_snapshot(self, symbol: str) -> Optional[DerivativesSnapshot]:
        with self.lock:
            return self.cache.get(symbol)

    def get_previous_snapshot(self, symbol: str) -> Optional[DerivativesSnapshot]:
        with self.lock:
            return self.previous_cache.get(symbol)

    def clear(self) -> None:
        with self.lock:
            self.cache.clear()
            self.previous_cache.clear()


derivatives_cache = DerivativesCache()
