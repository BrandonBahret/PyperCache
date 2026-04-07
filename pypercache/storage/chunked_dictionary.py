"""Disk-backed dictionary that splits its contents across multiple pickle chunk files.

A JSON manifest file tracks which chunk holds each key, allowing large datasets
to be stored and accessed without loading everything into memory at once.

Typical usage::

    # Build from an in-memory dict
    store = ChunkedDictionary.from_dict(data, "/path/to/dir", chunk_size_in_bytes=1_000_000)

    # Re-open an existing store
    store = ChunkedDictionary.from_disk("/path/to/dir/chunks.manifest")

    # Use like a regular dict
    store["my_key"] = {"some": "value"}
    value = store["my_key"]
"""

import json
import math
import os
import sys
import threading
from functools import cached_property as lazy_property
from pathlib import Path
from typing import Any, Dict, Generator, Iterator, List, Optional

from ..utils.fs import ensure_dirs_exist
from ..utils.serialization import PickleStore

# Private sentinel: distinguishes "no default supplied" from None in get().
_UNSET = object()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def get_size_of_dict(d: dict) -> int:
    """Return the byte-length of *d* when serialised to a compact JSON string."""
    return len(json.dumps(d))


def chunk_dictionary(
    data: dict,
    chunk_size_in_bytes: int,
) -> Generator[dict, None, None]:
    """Split *data* into sub-dictionaries whose estimated size stays under the limit."""
    chunk: dict = {}
    total_size: int = 0

    for key, value in data.items():
        item_size = sys.getsizeof(key) + get_size_of_dict(value)

        if total_size + item_size > chunk_size_in_bytes:
            yield chunk
            chunk = {}
            total_size = 0

        chunk[key] = value
        total_size += item_size

    if chunk or not data:
        yield chunk


# ---------------------------------------------------------------------------
# Manifest
# ---------------------------------------------------------------------------

class ChunkedDictionaryManifest:
    """Reads and writes the JSON manifest that describes a :class:`ChunkedDictionary`."""

    def __init__(self, manifest_filepath: str) -> None:
        self.lock = threading.Lock()
        self.filepath: Path = Path(manifest_filepath)

        with open(manifest_filepath, "r") as fp:
            manifest: dict = json.load(fp)

        self.chunks_map: Dict[str, str] = manifest["chunks_map"]
        self.chunk_size_in_bytes: int = manifest["chunk_size_in_bytes"]
        self.chunks_path: Path = Path(manifest["chunks_path"])
        self.chunks_count: int = manifest["chunks_count"]

    def is_chunk_filepath(self, file: str) -> bool:
        return file.startswith(str(self.chunks_path))

    @staticmethod
    def get_chunk_filename(index: int) -> str:
        return f"{index}-chunk.pkl"

    @staticmethod
    def get_chunk_index_from_filename(filename: str) -> int:
        return int(filename.replace("-chunk.pkl", ""))

    def remove_unused_chunks(self) -> None:
        with self.lock:
            for chunk_filename in os.listdir(self.chunks_path):
                if not chunk_filename.endswith("-chunk.pkl"):
                    continue
                index = ChunkedDictionaryManifest.get_chunk_index_from_filename(chunk_filename)
                if index + 1 > self.chunks_count:
                    filepath = self.chunks_path / chunk_filename
                    os.remove(filepath)

    def erase_all_chunks_nonreversable(self) -> None:
        with self.lock:
            for chunk_filename in os.listdir(self.chunks_path):
                if chunk_filename.endswith(".pkl"):
                    filepath = self.chunks_path / chunk_filename
                    os.remove(filepath)
            self.chunks_map = {}
            self.chunks_count = 0

    def save(self) -> None:
        with self.lock:
            manifest = {
                "chunk_size_in_bytes": self.chunk_size_in_bytes,
                "chunks_path": str(self.chunks_path),
                "chunks_count": self.chunks_count,
                "chunks_map": self.chunks_map,
            }
            with open(self.filepath, "w") as fp:
                json.dump(manifest, fp, indent=2)


# ---------------------------------------------------------------------------
# ChunkedDictionary
# ---------------------------------------------------------------------------

class ChunkedDictionary:
    """A disk-backed dictionary whose entries are spread across pickle chunk files."""

    def __init__(self, manifest_filepath: str) -> None:
        self.lock = threading.Lock()
        self.manifest = ChunkedDictionaryManifest(manifest_filepath)
        self.manifest.remove_unused_chunks()
        self.chunks: Dict[str, dict] = {}

    # ------------------------------------------------------------------
    # Class-level constructors
    # ------------------------------------------------------------------

    @classmethod
    def from_dict(
        cls,
        data: dict,
        directory: str | Path,
        chunk_size_in_bytes: int,
    ) -> "ChunkedDictionary":
        """Build a new ChunkedDictionary on disk from an in-memory dict."""
        directory = Path(directory)
        ensure_dirs_exist(str(directory))
        manifest_filepath = str(directory / "chunks.manifest")

        chunks_path = directory
        chunks = list(chunk_dictionary(data, chunk_size_in_bytes))

        chunks_map: Dict[str, str] = {}
        for i, chunk in enumerate(chunks):
            chunk_filename = ChunkedDictionaryManifest.get_chunk_filename(i)
            chunk_filepath = chunks_path / chunk_filename
            PickleStore.save_object(chunk, str(chunk_filepath))
            for key in chunk:
                chunks_map[key] = chunk_filename

        manifest = {
            "chunk_size_in_bytes": chunk_size_in_bytes,
            "chunks_path": str(chunks_path),
            "chunks_count": len(chunks),
            "chunks_map": chunks_map,
        }
        with open(manifest_filepath, "w") as fp:
            json.dump(manifest, fp, indent=2)

        return cls(manifest_filepath)

    @classmethod
    def from_disk(cls, manifest_filepath: str | Path) -> "ChunkedDictionary":
        """Open an existing ChunkedDictionary from its manifest file."""
        return cls(str(manifest_filepath))

    @staticmethod
    def directory_contains_chunked_dictionary(directory: str | Path) -> bool:
        """Return True if *directory* contains a valid chunks.manifest file."""
        return (Path(directory) / "chunks.manifest").exists()

    # ------------------------------------------------------------------
    # Bulk access
    # ------------------------------------------------------------------

    def data(self) -> dict:
        return {k: self[k] for k in self.keys()}

    def erase_everything(self) -> None:
        with self.lock:
            self.chunks = {}
        self.manifest.erase_all_chunks_nonreversable()
        self.manifest.save()

    # ------------------------------------------------------------------
    # dict-like interface
    # ------------------------------------------------------------------

    def __contains__(self, key: str) -> bool:
        return key in self.keys()

    def __len__(self) -> int:
        return len(self.keys())

    def items(self) -> Iterator:
        return self.data().items()

    def keys(self) -> List[str]:
        return list(self.manifest.chunks_map.keys())

    def get(self, key: str, default_value: Any = _UNSET) -> Any:
        if default_value is not _UNSET and key not in self.keys():
            return default_value
        return self[key]

    def __getitem__(self, key: str) -> Any:
        chunk_filename: str = self.manifest.chunks_map[key]
        chunk = self.get_chunk(chunk_filename)
        return chunk[key]

    def __setitem__(self, key: str, value: Any) -> None:
        chunk_filename: Optional[str] = None

        if key in self.manifest.chunks_map:
            chunk_filename = self.manifest.chunks_map[key]
            chunk = self.get_chunk(chunk_filename)
            with self.lock:
                chunk[key] = value
        else:
            last_chunk_index = self.manifest.chunks_count - 1

            if last_chunk_index == -1:
                last_chunk_index = 0
                last_chunk_filename = self.create_new_chunk()
            else:
                last_chunk_filename = ChunkedDictionaryManifest.get_chunk_filename(last_chunk_index)

            last_chunk = self.get_chunk(last_chunk_filename)
            last_chunk_size = get_size_of_dict(last_chunk)

            if last_chunk_size + get_size_of_dict({key: value}) < self.manifest.chunk_size_in_bytes:
                chunk_filename = last_chunk_filename
            else:
                chunk_filename = self.create_new_chunk()

            with self.lock:
                self.manifest.chunks_map[key] = chunk_filename
                self.chunks[chunk_filename][key] = value

        assert chunk_filename is not None
        self.save_chunk(chunk_filename)

    # ------------------------------------------------------------------
    # Chunk management
    # ------------------------------------------------------------------

    def create_new_chunk(self) -> str:
        with self.lock:
            index = self.manifest.chunks_count
            chunk_filename = ChunkedDictionaryManifest.get_chunk_filename(index)
            chunk_filepath = self.manifest.chunks_path / chunk_filename
            PickleStore.save_object({}, str(chunk_filepath))
            self.chunks[chunk_filename] = {}
            self.manifest.chunks_count += 1
        return chunk_filename

    def get_chunk(self, chunk_filename: str) -> dict:
        chunk_filename = str(chunk_filename)
        assert not self.manifest.is_chunk_filepath(chunk_filename)
        if chunk_filename not in self.chunks:
            chunk_filepath = str(self.manifest.chunks_path / chunk_filename)
            self.chunks[chunk_filename] = PickleStore.load_object(chunk_filepath)
        return self.chunks[chunk_filename]

    def save_chunk(self, chunk_filename: str) -> None:
        with self.lock:
            chunk = self.chunks[chunk_filename]
            chunk_filepath = self.manifest.chunks_path / chunk_filename
            PickleStore.save_object(chunk, str(chunk_filepath))
        self.manifest.save()

    def resize_data_chunks(self, chunk_size_in_bytes: int) -> None:
        all_data = self.data()
        manifest_filepath = str(self.manifest.filepath)
        chunks_path = str(self.manifest.chunks_path)
        self.erase_everything()
        self.manifest.chunk_size_in_bytes = chunk_size_in_bytes
        new = ChunkedDictionary.from_dict(all_data, chunks_path, chunk_size_in_bytes)
        self.manifest = new.manifest
        self.chunks = new.chunks
