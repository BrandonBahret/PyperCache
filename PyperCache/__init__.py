"""PyperCache — API response cache with pluggable storage backends.

Primary public surface::

    from PyperCache import Cache, CacheRecord, RequestLogger
    from PyperCache.query import JsonInjester

Utility sub-packages are importable directly when needed::

    from PyperCache.utils import DataSerializer, PickleStore
    from PyperCache.storage import get_storage_mechanism
"""

from PyperCache.core.cache import Cache
from PyperCache.core.cache_record import CacheRecord
from PyperCache.core.request_logger import LogRecord, RequestLogger

__version__ = "0.1.2"

__all__ = [
    "Cache",
    "CacheRecord",
    "LogRecord",
    "RequestLogger",
]
