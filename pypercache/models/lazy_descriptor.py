"""Descriptor that backs lazy fields produced by ``@apimodel``.

You never instantiate this directly - the decorator creates and installs one
per ``Lazy[T]``-annotated field when the class is defined.
"""
from __future__ import annotations

from typing import Any

from ..query.json_injester import JsonInjester
from ..utils.sentinel import UNSET
from ..utils.typing_cast import instantiate_type
from .field_transforms import as_raw_value, instantiate_field_value, write_raw_value
from .fields import Columns, Timestamp
from .validation import raise_unset_field, validate_type


_MISSING = object()

class LazyDescriptor:
    """Data descriptor that hydrates a field on first access then caches it.

    Installed by ``@apimodel`` at *class-definition* time for every field
    whose annotation is ``Lazy[T]``.  The descriptor stores per-instance
    state in a private attribute on the instance itself, so there is no
    shared mutable state between instances.

    Lifecycle
    ---------
    1. ``@apimodel`` calls ``setattr(cls, field_name, LazyDescriptor(...))``
       once, when the class body is executed.
    2. On first attribute access the descriptor reads from ``_Initial__Data``,
       runs ``instantiate_type``, and writes the result to a private cache
       attribute on the instance.
    3. On every subsequent access the cached value is returned.
    """

    def __init__(
        self,
        field: str,
        inner_type: type,
        alias: str | None = None,
        timestamp: Timestamp | None = None,
        columns: Columns | None = None,
        validate: bool = False,
        strict: bool = False,
    ) -> None:
        self.field = field
        self.inner_type = inner_type
        self.alias = alias
        self.timestamp = timestamp
        self.columns = columns
        self.validate = validate
        self.strict = strict

        # The key used to stash the hydrated value on the instance.
        self._cache_key = f"_lazycache_{field}"

    # ------------------------------------------------------------------
    # Descriptor protocol
    # ------------------------------------------------------------------

    def __set_name__(self, owner: type, name: str) -> None:
        """Called by Python when the descriptor is assigned inside a class body.

        We rely on ``@apimodel`` calling ``setattr`` *after* the class is
        created, so ``__set_name__`` is not invoked automatically.  The
        decorator sets ``self.field`` explicitly; this method is here as a
        safety net if the descriptor is ever placed directly in a class body.
        """
        self.field = name
        self._cache_key = f"_lazycache_{name}"

    def __get__(self, obj: Any, objtype: type | None = None) -> Any:
        if obj is None:
            # Accessed on the class itself - return the descriptor.
            return self

        cache = getattr(obj, self._cache_key, _MISSING)

        if cache is not _MISSING:
            return cache

        return self._hydrate(obj)

    def __set__(self, obj: Any, value: Any) -> None:
        """Allow explicit assignment to override the lazy value."""
        assigned = self._instantiate(value)
        if self.strict and assigned is UNSET:
            raise_unset_field(obj, self.field)
        validate_type(obj, self.field, self.inner_type, assigned)
        object.__setattr__(obj, self._cache_key, assigned)
        raw_data = getattr(obj, "_Initial__Data", None)
        if isinstance(raw_data, dict):
            raw_key = self.field if self.alias is None else self.alias
            write_raw_value(
                raw_data,
                raw_key,
                as_raw_value(assigned, timestamp=self.timestamp, columns=self.columns),
            )

    def __delete__(self, obj: Any) -> None:
        """Deleting the attribute clears the cache, forcing re-hydration."""
        try:
            object.__delattr__(obj, self._cache_key)
        except AttributeError:
            pass

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _hydrate(self, obj: Any) -> Any:
        """Read from the raw data dict, instantiate, and cache the result."""
        raw_key = self.field if self.alias is None else self.alias
        raw = JsonInjester(obj._Initial__Data).get(raw_key, default_value=UNSET)
        if self.strict and raw is UNSET:
            raise_unset_field(obj, self.field)
        value = self._instantiate(raw)
        if self.validate:
            validate_type(obj, self.field, self.inner_type, value)
        object.__setattr__(obj, self._cache_key, value)
        return value

    def _instantiate(self, raw: Any) -> Any:
        return instantiate_field_value(
            self.inner_type,
            raw,
            timestamp=self.timestamp,
            columns=self.columns,
            instantiator=instantiate_type,
        )
