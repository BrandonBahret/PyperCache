"""CacheRecord: a single cached API response with expiry and optional type casting."""

import inspect
import math
import time
from typing import Callable, Optional

from PyperCache.query import JsonInjester
from PyperCache.utils.patterns import ClassRepository
from PyperCache.utils.sentinel import UNSET


# Maps primitive type name strings to their corresponding Python types.
PRIMITIVE_TYPES_MAP = {
    'bool': bool,
    'bytearray': bytearray,
    'bytes': bytes,
    'complex': complex,
    'dict': dict,
    'float': float,
    'frozenset': frozenset,
    'int': int,
    'list': list,
    'object': object,
    'set': set,
    'str': str,
    'tuple': tuple,
    'type': type,
}


def look_up_class(class_name: str) -> type:
    """Resolve a class by name, checking primitives first then the class repository.

    Args:
        class_name: The name of the class to look up.

    Returns:
        The resolved class type.

    Raises:
        NameError: If the class name is not registered.
        TypeError: If the resolved object is not a class.
    """
    if class_name in PRIMITIVE_TYPES_MAP:
        return PRIMITIVE_TYPES_MAP[class_name]

    # Primitive types (short names) map directly to builtins.
    if class_name in PRIMITIVE_TYPES_MAP:
        return PRIMITIVE_TYPES_MAP[class_name]

    classes = ClassRepository()
    # Try resolving via the repository first (supports short and fqnames)
    cls = classes.get_class(class_name)
    if cls is not None and inspect.isclass(cls):
        return cls

    # If class_name looks like a fully-qualified path, try importing it.
    if '.' in class_name:
        module_name, _, attr = class_name.rpartition('.')
        try:
            module = __import__(module_name, fromlist=[attr])
            obj = getattr(module, attr)
            if inspect.isclass(obj):
                return obj
        except Exception:
            pass

    raise NameError(f'{class_name!r} is not defined')


class CacheRecord:
    """Represents a single cached API response with expiry and optional type casting.

    Records are stored and serialized as plain dicts, with ``math.inf``
    represented as the string ``'math.inf'`` to support JSON-safe serialization.

    The :attr:`query` property exposes the cached data through a
    :class:`~cache_module.query.JsonInjester`, enabling dotted-path access
    and filter queries without altering the underlying data::

        record = cache.get_record("org:acme")
        record.query.get("meta.total_users")
        record.query.get("users?role=admin")
        record.query.has("users")

    Args:
        record:           Raw dict with keys ``timestamp``, ``expiry``, ``data``,
                          and optionally ``cast``.
        class_resolver:   Optional callable used to resolve the cast type name to
                          an actual type.  Defaults to :func:`look_up_class`, which
                          consults :class:`ClassRepository`.  Pass a custom resolver
                          in tests to avoid touching the global registry.
    """

    def __init__(
        self,
        record: dict,
        class_resolver: Optional[Callable[[str], type]] = None,
    ) -> None:
        self.__record_dict = record
        self.__class_resolver = class_resolver or look_up_class

        self.timestamp: float = record['timestamp']
        self.data: dict = record['data']
        self.expiry: float = math.inf if record['expiry'] == 'math.inf' else record['expiry']
        self.cast_str: Optional[str] = record.get('cast')
        self.__cast: object = UNSET   # Unresolved until first access.
        self.__query: Optional[JsonInjester] = None  # Built lazily on first access.

    @staticmethod
    def from_data(data: dict, expiry: float = math.inf, cast: type = None) -> 'CacheRecord':
        """Construct a new CacheRecord from raw data.

        Args:
            data:   The payload to cache.
            expiry: Seconds until the record is considered stale. Defaults to never.
            cast:   Optional type to cast the data to on retrieval.

        Returns:
            A new CacheRecord instance.
        """
        # Store short builtin names (e.g. 'dict') for primitive types to
        # preserve compatibility with earlier cache files; otherwise store
        # fully-qualified name for user classes.
        if isinstance(cast, type) and cast.__module__ == 'builtins':
            cast_str = cast.__name__
        else:
            cast_str = (f"{cast.__module__}.{cast.__name__}" if isinstance(cast, type) else None)

        record = {
            'cast': cast_str,
            'expiry': expiry,
            'timestamp': time.time(),
            'data': data,
        }
        return CacheRecord(record)

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def cast(self) -> Optional[type]:
        """Lazily resolve the cast type from its stored class name string."""
        if self.__cast is UNSET:
            self.__cast = (
                self.__class_resolver(self.cast_str)
                if isinstance(self.cast_str, str)
                else None
            )
        return self.__cast

    @property
    def query(self) -> JsonInjester:
        """A :class:`~cache_module.query.JsonInjester` view over :attr:`data`.

        Built once on first access and reused.  Supports dotted-path lookup,
        existence checks, filtered list queries, and default values — all
        without modifying the underlying cached data.

        Example::

            record.query.get("meta.total_users")          # nested key
            record.query.get("users?role=admin")          # filter list
            record.query.get("users?dept.name=Engineering")
            record.query.has("meta.total_users")          # existence check
            record.query.get("missing_key", default_value=0)

        Note: if :attr:`data` has been replaced via :meth:`update`, call
        ``record.query`` again — the injester is rebuilt automatically because
        :meth:`update` clears the cached instance.
        """
        if self.__query is None:
            self.__query = JsonInjester(self.data)
        return self.__query

    @property
    def should_convert_type(self) -> bool:
        """True if a valid cast type is set and data should be converted on retrieval."""
        return isinstance(self.cast, type)

    @property
    def is_data_stale(self) -> bool:
        """True if the record has lived past its expiry window."""
        return time.time() > self.timestamp + self.expiry

    # ------------------------------------------------------------------
    # Mutation
    # ------------------------------------------------------------------

    def update(self, data: dict):
        """Replace the cached data and refresh the timestamp.

        Also invalidates the cached :attr:`query` injester so the next access
        reflects the new data.
        """
        self.data = data
        self.timestamp = time.time()
        self.__record_dict['data'] = data
        self.__record_dict['timestamp'] = self.timestamp
        self.__query = None   # invalidate so next .query access wraps new data

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

    def as_dict(self) -> dict:
        """Serialize the record to a plain dict, encoding infinity as 'math.inf'."""
        return {
            k: ('math.inf' if v == math.inf else v)
            for k, v in self.__record_dict.items()
        }

    def __repr__(self) -> str:
        label = 'data_stale' if self.is_data_stale else 'data_fresh'
        return f'<{self.cast_str}::{label}>'