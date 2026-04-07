"""PyperCache.utils — public re-export surface.

All symbols that were previously importable from the flat ``utils`` module
remain importable from here, so existing ``from utils import X`` calls
continue to work after a simple search-and-replace of the import target.
"""

from .collections import convert_defaultdict_to_dict
from .fs import ensure_dirs_exist, open_folder
from .patterns import ClassRepository, singleton
from .profiling import Profiler
from .serialization import DataSerializer, PickleStore
from .sentinel import UNSET

__all__ = [
    "ClassRepository",
    "convert_defaultdict_to_dict",
    "DataSerializer",
    "ensure_dirs_exist",
    "open_folder",
    "PickleStore",
    "Profiler",
    "singleton",
    "UNSET",
]
