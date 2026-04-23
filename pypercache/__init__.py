"""PyperCache — API response cache with pluggable storage backends.

Primary public surface::

    from pypercache import Cache, CacheRecord, RequestLogger
    from pypercache.query import JsonInjester

Utility sub-packages are importable directly when needed::

    from pypercache.utils import DataSerializer, PickleStore
    from pypercache.storage import get_storage_mechanism
"""

from .api_wrapper import ApiHTTPError, ApiWrapper, ApiWrapperError, SSEEvent
from .core.cache import Cache
from .core.cache_record import CacheRecord
from .core.request_logger import LogRecord, RequestLogger

__version__ = "0.1.5"

__all__ = [
    "ApiHTTPError",
    "ApiWrapper",
    "ApiWrapperError",
    "Cache",
    "CacheRecord",
    "LogRecord",
    "RequestLogger",
    "SSEEvent",
]
