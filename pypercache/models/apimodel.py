"""Small `@apimodel` decorator for simple API models.

This module provides a light-weight decorator that:
- registers the class with ``ClassRepository`` (short name and fqname)
- injects a constructor that accepts a raw dict and hydrates annotated
  fields (using ``instantiate_type`` for nested types)
- provides ``from_dict`` and ``as_dict`` helpers
- supports deferred hydration via ``Lazy[T]`` annotations
- supports raw-key aliases through ``Annotated[T, Alias("raw_key")]``
- supports datetime parsing through ``Annotated[datetime, Timestamp(...)]``

Lazy usage::

    @apimodel
    class Order:
        id:       int                   # eager - hydrated in __init__
        status:   str                   # eager
        customer: Lazy[Customer]        # lazy - hydrated on first access
        items:    Lazy[list[LineItem]]  # lazy
        tags:     Lazy[Annotated[list[Tag], Alias("tag_list")]]
        created:  Annotated[datetime, Timestamp()]
"""
from __future__ import annotations

import sys
from collections.abc import Callable
from typing import Annotated, Any, TypeVar, get_args, get_origin, get_type_hints

from ..utils.patterns import ClassRepository
from ..query.json_injester import JsonInjester
from ..utils.sentinel import UNSET
from ..utils.typing_cast import instantiate_type
from .field_transforms import (
    as_raw_value,
    instantiate_field_value,
    unwrap_field_config,
    unwrap_lazy_config,
    write_raw_value,
)
from .fields import Alias, Columns, Timestamp
from .lazy import Lazy
from .lazy_descriptor import LazyDescriptor
from .validation import ApiModelValidationError, raise_unset_field, validate_type


T = TypeVar("T")


__all__ = [
    "Alias",
    "ApiModelValidationError",
    "Columns",
    "Lazy",
    "Timestamp",
    "apimodel",
]


def _model_repr(self: Any) -> str:
    fields = getattr(self, "__annotations__", {})
    pairs = ", ".join(f"{name}={getattr(self, name, None)!r}" for name in fields)
    return f"{self.__class__.__name__}({pairs})"


def _model_eq(self: Any, other: Any) -> bool:
    if self.__class__ is not other.__class__:
        return False
    return self.as_dict() == other.as_dict()


def _unwrap_field_config(annotation: Any) -> tuple[Any, str | None, Timestamp | None, Columns | None]:
    """Return ``(base_annotation, raw_key_alias, timestamp_parser)``."""
    return unwrap_field_config(annotation)

def _unwrap_lazy_config(
    annotation: Any,
) -> tuple[Any, str | None, Timestamp | None, Columns | None] | None:
    """If *annotation* is ``Lazy[...]``, return its resolved field config."""
    return unwrap_lazy_config(annotation, Lazy)


def _instantiate_field_value(
    annotation: Any,
    raw: Any,
    timestamp: Timestamp | None = None,
    columns: Columns | None = None,
) -> Any:
    """Instantiate raw input, applying annotation metadata first."""
    return instantiate_field_value(
        annotation,
        raw,
        timestamp=timestamp,
        columns=columns,
        instantiator=instantiate_type,
    )

def _write_raw_value(data: dict, raw_key: str, value: Any) -> None:
    """Write *value* into *data*, respecting dot-separated raw key paths."""
    write_raw_value(data, raw_key, value)

def apimodel(
    cls: T | None = None,
    *,
    validate: bool = False,
    strict: bool = False,
    _localns: dict[str, Any] | None = None,
) -> T | Callable[[T], T]:
    """Decorator that makes a simple model from annotated fields.

    The generated constructor accepts a single positional ``data`` dict.
    Registered classes expose ``from_dict`` and ``as_dict`` for symmetry
    with other parts of the codebase. Pass ``strict=True`` to reject
    missing annotated fields instead of storing ``UNSET``. Pass
    ``validate=True`` to reject values that do not match their annotations.

    Fields annotated with ``Lazy[T]`` are not hydrated in ``__init__``;
    instead a :class:`LazyDescriptor` is installed on the class and the
    value is produced on first attribute access. Use annotation metadata to
    configure field hydration. ``Alias`` reads a field from another raw key and
    ``Timestamp`` parses raw API timestamps into ``datetime`` fields::

        name:     Lazy[str]                                # plain lazy
        customer: Lazy[Annotated[Customer, Alias("cust")]]
        created:  Annotated[datetime, Timestamp()]
    """
    caller_locals = _localns
    if caller_locals is None:
        try:
            caller_locals = sys._getframe(1).f_locals.copy()
        except (AttributeError, ValueError):
            caller_locals = {}

    if cls is None:
        return lambda decorated_cls: apimodel(
            decorated_cls,
            validate=validate,
            strict=strict,
            _localns=caller_locals,
        )

    ClassRepository().add_class(cls)
    original_setattr = getattr(cls, "__setattr__", object.__setattr__)

    # get_type_hints resolves stringified annotations (from `from __future__ import annotations`)
    # using the class's own module globals as the evaluation namespace.
    module = sys.modules.get(cls.__module__, None)
    globalns = getattr(module, "__dict__", {}) if module else {}
    localns = {**(caller_locals or {}), cls.__name__: cls}
    own_annotations = getattr(cls, "__annotations__", {})
    try:
        resolved_annotations = get_type_hints(
            cls,
            globalns=globalns,
            localns=localns,
            include_extras=True,
        )
        annotations = {
            field: resolved_annotations.get(field, annotation)
            for field, annotation in own_annotations.items()
        }
    except Exception:
        annotations = own_annotations

    # ------------------------------------------------------------------ #
    # Split annotations into eager vs lazy at decoration time -          #
    # this work is done once, not on every instantiation.                #
    # ------------------------------------------------------------------ #
    eager_fields: dict[str, tuple[Any, str | None, Timestamp | None, Columns | None]] = {}
    lazy_fields: dict[str, tuple[Any, str | None, Timestamp | None, Columns | None]] = {}

    for field, annotation in annotations.items():
        unwrapped = _unwrap_lazy_config(annotation)
        if unwrapped is not None:
            lazy_fields[field] = unwrapped
        else:
            eager_fields[field] = _unwrap_field_config(annotation)

    # Install one descriptor per lazy field directly on the class.
    for field, (inner_type, alias, timestamp, columns) in lazy_fields.items():
        setattr(
            cls,
            field,
            LazyDescriptor(
                field,
                inner_type,
                alias,
                timestamp=timestamp,
                columns=columns,
                validate=validate,
                strict=strict,
            ),
        )

    # ------------------------------------------------------------------ #
    # Generated methods                                                  #
    # ------------------------------------------------------------------ #

    def __init__(self, data: dict) -> None:
        ji = JsonInjester(data)
        # Store the raw dict so LazyDescriptors can reach it later.
        object.__setattr__(self, "_Initial__Data", data)

        # Only hydrate eager fields; lazy fields are handled by descriptors.
        for field, (annotation, alias, timestamp, columns) in eager_fields.items():
            raw_key = field if alias is None else alias
            raw = ji.get(raw_key, default_value=UNSET)
            if strict and raw is UNSET:
                raise_unset_field(self, field)
            value = _instantiate_field_value(annotation, raw, timestamp, columns)
            if validate:
                validate_type(self, field, annotation, value)
            object.__setattr__(self, field, value)

        if strict or validate:
            for field, (inner_type, alias, timestamp, columns) in lazy_fields.items():
                raw_key = field if alias is None else alias
                raw = ji.get(raw_key, default_value=UNSET)
                if strict and raw is UNSET:
                    raise_unset_field(self, field)
                if validate:
                    value = _instantiate_field_value(inner_type, raw, timestamp, columns)
                    validate_type(self, field, inner_type, value)
                    object.__setattr__(self, cls.__dict__[field]._cache_key, value)

        post_init = getattr(self, "__post_init__", None)
        if post_init is not None:
            post_init()

    def as_dict(self) -> dict:
        return getattr(self, "_Initial__Data")

    def __setattr__(self, name: str, value: Any) -> None:
        if name.startswith("_") or not hasattr(self, "_Initial__Data"):
            original_setattr(self, name, value)
            return

        field_config = eager_fields.get(name)
        is_lazy = False
        if field_config is None:
            field_config = lazy_fields.get(name)
            is_lazy = field_config is not None

        if field_config is None:
            original_setattr(self, name, value)
            return

        annotation, alias, timestamp, columns = field_config
        raw_key = name if alias is None else alias
        assigned = _instantiate_field_value(annotation, value, timestamp, columns)
        if strict and assigned is UNSET:
            raise_unset_field(self, name)
        validate_type(self, name, annotation, assigned)
        _write_raw_value(
            getattr(self, "_Initial__Data"),
            raw_key,
            as_raw_value(assigned, timestamp=timestamp, columns=columns),
        )

        if is_lazy:
            object.__setattr__(self, cls.__dict__[name]._cache_key, assigned)
        else:
            object.__setattr__(self, name, assigned)

    @classmethod
    def from_dict(cls2, data: dict) -> Any:
        return cls2(data)

    cls.__init__ = __init__
    cls.__setattr__ = __setattr__
    cls.as_dict = as_dict
    cls.from_dict = from_dict
    cls.__repr__ = _model_repr
    cls.__eq__ = _model_eq

    return cls
