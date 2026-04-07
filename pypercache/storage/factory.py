"""Factory: map a file extension to the appropriate storage backend class."""

from pathlib import Path
from typing import Dict, Type

from .base import StorageMechanism
from .backends import ChunkedStorage, JSONStorage, PickleStorage
from .sqlite_storage import SQLiteStorage


# Maps file extensions to their corresponding storage backend class.
_EXTENSION_TO_STORAGE: Dict[str, Type[StorageMechanism]] = {
    ".manifest": ChunkedStorage,
    ".json":     JSONStorage,
    ".pkl":      PickleStorage,
    ".db":       SQLiteStorage,   # SQLite — zero-cost, stdlib, no server required
}


def get_storage_mechanism(filepath: str) -> Type[StorageMechanism]:
    """Return the :class:`StorageMechanism` subclass appropriate for *filepath*.

    The backend is selected solely from the file extension.

    Args:
        filepath: Path to the cache store file.

    Returns:
        The matching :class:`StorageMechanism` subclass (*not* an instance).

    Raises:
        ValueError: If no backend supports the given file extension.
    """
    extension = Path(filepath).suffix.lower()
    mechanism = _EXTENSION_TO_STORAGE.get(extension)
    if mechanism is None:
        raise ValueError(
            f"No storage mechanism found for file extension: {extension!r}"
        )
    return mechanism
