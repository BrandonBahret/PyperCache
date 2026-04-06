"""Concrete storage backends: JSON, Pickle, and ChunkedDictionary."""

import json
import jsonpickle
from collections.abc import MutableMapping
from pathlib import Path
from typing import Dict

from PyperCache.storage.base import StorageMechanism
from PyperCache.storage.chunked_dictionary import ChunkedDictionary
from PyperCache.utils.serialization import PickleStore


class JSONStorage(StorageMechanism):
    """Storage backend that serialises cache records as a single JSON file.

    Uses standard JSON for simple data, falls back to jsonpickle for complex
    Python objects to ensure serialization safety.
    """

    def _impl__touch_store(self, filepath: Path) -> bool:
        filepath.touch(exist_ok=True)
        return True

    def _impl__load(self, filepath: Path) -> Dict[str, dict]:
        with open(filepath, "r") as f:
            content = f.read().strip()
        return jsonpickle.decode(content) if content else {}

    def _impl__save(self, cache_records_dict: Dict[str, dict], filepath: Path):
        try:
            json_str = json.dumps(cache_records_dict)
        except (TypeError, ValueError):
            json_str = jsonpickle.encode(cache_records_dict)
        with open(filepath, "w") as fp:
            fp.write(json_str)

    def _impl__update_record(self, key: str, data: dict):
        record = self.get_record(key)
        record.update(data)
        self.save(self.records)

    def _impl__erase_everything(self):
        self.records = {}
        self.save(self.records)


class PickleStorage(StorageMechanism):
    """Storage backend that serialises cache records using Python's pickle format."""

    def _impl__touch_store(self, filepath: Path) -> bool:
        PickleStore.touch_file({}, filepath)
        return True

    def _impl__load(self, filepath: Path) -> Dict[str, dict]:
        return PickleStore.load_object(filepath)

    def _impl__save(self, cache_records_dict: Dict[str, dict], filepath: Path):
        PickleStore.save_object(cache_records_dict, filepath)

    def _impl__update_record(self, key: str, data: dict):
        record = self.get_record(key)
        record.update(data)
        self.save(self.records)

    def _impl__erase_everything(self):
        self.records = {}
        self.save(self.records)


class ChunkedStorage(StorageMechanism):
    """Storage backend backed by a :class:`ChunkedDictionary`.

    Records are written atomically per-key rather than flushing the entire
    dataset at once, making this backend suitable for large caches.
    """

    def _impl__touch_store(self, filepath: Path) -> bool:
        datastore_path = filepath.parent
        if not ChunkedDictionary.directory_contains_chunked_dictionary(datastore_path):
            self.chunked_dict = ChunkedDictionary.from_dict(
                {}, datastore_path, 15 * 1024 * 1024
            )
        return ChunkedDictionary.directory_contains_chunked_dictionary(datastore_path)

    def _impl__load(self, filepath: Path) -> MutableMapping[str, dict]:
        """Load from disk and return the live ChunkedDictionary as self.records.

        Unlike the JSON and Pickle backends, this returns the ChunkedDictionary
        itself rather than a plain dict snapshot. Writes made via
        self.records[key] = ... are therefore persisted atomically per-key
        without a full dataset flush.
        """
        self.chunked_dict = ChunkedDictionary.from_disk(filepath)
        return self.chunked_dict

    def _impl__save(self, cache_records_dict: Dict[str, dict], filepath: Path):
        self.chunked_dict.manifest.save()

    def _impl__update_record(self, key: str, data: dict):
        record = self.get_record(key)
        record.update(data)
        self.chunked_dict[key] = record.as_dict()

    def _impl__erase_everything(self):
        self.chunked_dict.erase_everything()
