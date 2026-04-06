"""
Storage submodule: provides cache persistence backends, chunked storage,
and factory utilities.
"""

# Base interface
from .base import StorageMechanism

# Concrete backends
from .backends import JSONStorage, PickleStorage, ChunkedStorage

# Chunked storage core
from .chunked_dictionary import ChunkedDictionary

from .sqlite_storage import SQLiteStorage

# Factory
from .factory import get_storage_mechanism

__all__ = [
    "StorageMechanism",
    "JSONStorage",
    "PickleStorage",
    "ChunkedStorage",
    "ChunkedDictionary",
    "SQLiteStorage",
    "get_storage_mechanism",
]