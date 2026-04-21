"""Validation helpers shared by API model construction and lazy hydration."""
from __future__ import annotations

import dataclasses
import types
import typing
from typing import Annotated, Any, Literal, get_args, get_origin


class ApiModelValidationError(ValueError):
    """Raised when API model data does not satisfy configured validation."""


def raise_unset_field(model: Any, field: str) -> None:
    """Raise a consistent validation error for a missing model field."""
    model_name = model.__name__ if isinstance(model, type) else model.__class__.__name__
    raise ApiModelValidationError(f"{model_name}.{field} is UNSET")


def raise_type_mismatch(model: Any, field: str, annotation: Any, value: Any) -> None:
    """Raise a consistent validation error for a type mismatch."""
    model_name = model.__name__ if isinstance(model, type) else model.__class__.__name__
    raise ApiModelValidationError(
        f"{model_name}.{field} expected {annotation!r}, got {type(value).__name__}"
    )


def validate_type(model: Any, field: str, annotation: Any, value: Any) -> None:
    """Validate that *value* matches *annotation*.

    ``UNSET`` is intentionally accepted here. Presence checks are owned by
    ``strict=True`` so callers can choose type validation without requiring
    every annotated field to be present.
    """
    if not _matches_type(annotation, value):
        raise_type_mismatch(model, field, annotation, value)


def _matches_type(annotation: Any, value: Any) -> bool:
    from ..utils.sentinel import UNSET

    if value is UNSET:
        return True

    if annotation is Any:
        return True

    if annotation is None or annotation is type(None):
        return value is None

    origin = get_origin(annotation)
    args = get_args(annotation)

    if origin is Annotated:
        return _matches_type(args[0], value)

    if origin is Literal:
        return value in args

    if origin is typing.Union:
        return any(_matches_type(arg, value) for arg in args)

    union_type = getattr(types, "UnionType", None)
    if union_type is not None and origin is union_type:
        return any(_matches_type(arg, value) for arg in args)

    if origin is list:
        if not isinstance(value, list):
            return False
        item_type = args[0] if args else Any
        return all(_matches_type(item_type, item) for item in value)

    if origin is dict:
        if not isinstance(value, dict):
            return False
        key_type, val_type = (args + (Any, Any))[:2]
        return all(
            _matches_type(key_type, key) and _matches_type(val_type, val)
            for key, val in value.items()
        )

    if isinstance(annotation, type):
        if hasattr(annotation, "from_dict") and callable(getattr(annotation, "from_dict")):
            return isinstance(value, (annotation, dict))

        if dataclasses.is_dataclass(annotation):
            return isinstance(value, (annotation, dict))

        return isinstance(value, annotation)

    return True
