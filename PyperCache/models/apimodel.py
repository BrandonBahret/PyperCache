"""Small `@apimodel` decorator for simple API models.

This module provides a light-weight decorator that:
- registers the class with `ClassRepository` (short name and fqname)
- injects a constructor that accepts a raw dict and hydrates annotated
  fields (using `instantiate_type` for nested types)
- provides `from_dict` and `as_dict` helpers
"""
from __future__ import annotations

from typing import Any

from ..utils.patterns import ClassRepository
from ..query.json_injester import JsonInjester
from ..utils.typing_cast import instantiate_type


def apimodel(cls: type) -> type:
    """Decorator that makes a simple model from annotated fields.

    The generated constructor accepts a single positional ``data`` dict.
    Registered classes expose ``from_dict`` and ``as_dict`` for symmetry
    with other parts of the codebase.
    """
    ClassRepository().add_class(cls)

    annotations = getattr(cls, "__annotations__", {})

    def __init__(self, data: dict) -> None:
        ji = JsonInjester(data)
        object.__setattr__(self, "_Initial__Data", data)

        for field, annotated in annotations.items():
            raw = ji.get(field, default_value=None)
            value = instantiate_type(annotated, raw)
            setattr(self, field, value)

    def as_dict(self) -> dict:
        return getattr(self, "_Initial__Data")

    @classmethod
    def from_dict(cls2, data: dict) -> Any:
        return cls2(data)

    cls.__init__ = __init__
    cls.as_dict = as_dict
    cls.from_dict = from_dict

    return cls
