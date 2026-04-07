"""Abstract base class for cache storage backends."""

import threading
from abc import ABC, abstractmethod
from collections.abc import MutableMapping
from pathlib import Path
from typing import Dict, Type

from ..core.cache_record import CacheRecord
from ..utils.fs import ensure_dirs_exist


class StorageMechanism(ABC):
    """Abstract base class defining the interface for cache storage backends.

    Subclasses implement the ``_impl__*`` methods to support different
    serialisation formats (JSON, Pickle, ChunkedDictionary).  All public
    methods acquire a threading lock so instances are safe to share across
    threads.

    ``self.records`` is typed as ``MutableMapping[str, dict]`` rather than
    ``dict`` so that :class:`ChunkedStorage` can back it with a
    :class:`ChunkedDictionary` — a disk-backed mapping that satisfies the
    same protocol without loading every record into memory at once.
    """

    def __init__(self, filepath: str):
        self.lock = threading.Lock()
        self.__filepath = filepath
        self.records: MutableMapping[str, dict] = self.load()

    @property
    def filepath(self) -> Path:
        return Path(self.__filepath)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load(self) -> MutableMapping[str, dict]:
        """Ensure the backing store exists, then load and return all records."""
        with self.lock:
            ensure_dirs_exist(self.filepath)
            self.touch_store()
            return self._impl__load(self.filepath)

    def save(self, data: dict):
        """Persist *data* to the backing store, creating it first if needed."""
        with self.lock:
            ensure_dirs_exist(self.filepath)
            self.touch_store()
            return self._impl__save(data, self.filepath)

    def get_record(self, key: str) -> CacheRecord:
        """Return the :class:`CacheRecord` associated with *key*."""
        return CacheRecord(self.records[key])

    def update_record(self, key: str, data: dict):
        """Merge *data* into the existing record at *key*."""
        self._impl__update_record(key, data)

    def store_record(self, key: str, cache_record_dict: dict):
        """Insert or overwrite the record at *key* and persist immediately."""
        key = str(key)
        self.records[key] = cache_record_dict
        self.save(self.records)

    def erase_everything(self):
        """Delete every record from the backing store."""
        self._impl__erase_everything()

    def touch_store(self):
        """Create the backing store at :attr:`filepath` if it does not exist."""
        if not self._impl__touch_store(self.filepath):
            raise Exception("New datastore could not be created.")

    # ------------------------------------------------------------------
    # Abstract implementation hooks
    # ------------------------------------------------------------------

    @abstractmethod
    def _impl__touch_store(self, filepath: Path) -> bool:
        """Create an empty store at *filepath* if one does not already exist."""

    @abstractmethod
    def _impl__load(self, filepath: Path) -> MutableMapping[str, dict]:
        """Deserialise and return all records from *filepath*.

        May return a plain ``dict`` or any ``MutableMapping`` implementation
        (e.g. :class:`ChunkedDictionary`) that satisfies the same protocol.
        """

    @abstractmethod
    def _impl__save(self, cache_records_dict: Dict[str, dict], filepath: Path):
        """Serialise *cache_records_dict* and write it to *filepath*."""

    @abstractmethod
    def _impl__update_record(self, key: str, data: dict):
        """Merge *data* into the record at *key* and persist the change."""

    @abstractmethod
    def _impl__erase_everything(self):
        """Remove every record from the backing store."""
