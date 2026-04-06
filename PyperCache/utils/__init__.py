"""PyperCache.utils — public re-export surface.

All symbols that were previously importable from the flat ``utils`` module
remain importable from here, so existing ``from utils import X`` calls
continue to work after a simple search-and-replace of the import target.
"""

from PyperCache.utils.collections import convert_defaultdict_to_dict
from PyperCache.utils.fs import ensure_dirs_exist, open_folder
from PyperCache.utils.patterns import ClassRepository, singleton
from PyperCache.utils.profiling import Profiler
from PyperCache.utils.serialization import DataSerializer, PickleStore
from PyperCache.utils.sentinel import UNSET

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
