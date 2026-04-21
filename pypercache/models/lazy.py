"""Lazy-loading primitives for use with ``@apimodel``.

Intended usage::

    from .fields import Alias
    from .lazy import Lazy
    from typing import Annotated

    @apimodel
    class Order:
        id:       int                    # eager - hydrated in __init__
        status:   str                    # eager
        customer: Lazy[Customer]         # lazy - hydrated on first access
        items:    Lazy[list[LineItem]]
        tags:     Lazy[Annotated[list[Tag], Alias("tag_list")]]
"""
from __future__ import annotations

from typing import Generic, TypeVar

T = TypeVar("T")


class Lazy(Generic[T]):
    """Marker generic that tells ``@apimodel`` to defer hydration of a field.

    ``Lazy[T]`` is a pure annotation - no instances are ever created at
    runtime.  The decorator unwraps it with ``typing.get_args`` and installs
    a :class:`LazyDescriptor` instead of hydrating eagerly in ``__init__``.

    Plain usage::

        customer: Lazy[Customer]

    With field metadata::

        customer: Lazy[Annotated[Customer, Alias("cust")]]
    """


