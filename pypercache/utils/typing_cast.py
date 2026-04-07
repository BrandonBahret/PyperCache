from __future__ import annotations

import dataclasses
import typing
from typing import Any, Type


T = typing.TypeVar("T")

def _is_generic_alias(obj: Any) -> bool:
    try:
        from typing import get_origin

        return get_origin(obj) is not None
    except Exception:
        return hasattr(obj, "__origin__") and hasattr(obj, "__args__")


def instantiate_type(target_type: Type[T], data: Any) -> T:
    """Instantiate or cast *data* into *target_type*.

    Supports simple classes (preferring ``from_dict``), dataclasses, and
    basic generics: ``list[T]`` and ``dict[K, V]``. Falls back to returning
    the original *data* when no casting is possible.
    """
    if data is None:
        return None

    # Generic aliases (e.g., list[User], typing.List[User])
    origin = None
    args = ()
    try:
        origin = typing.get_origin(target_type)
        args = typing.get_args(target_type)
    except Exception:
        pass

    if origin is list or origin is typing.List:
        item_type = args[0] if args else Any
        return [instantiate_type(item_type, item) for item in (data or [])]

    if origin is dict or origin is typing.Dict:
        key_type, val_type = (args + (Any, Any))[:2]
        return {k: instantiate_type(val_type, v) for k, v in (data or {}).items()}

    # If a typing alias without origin (fallback), try basic handling
    if _is_generic_alias(target_type):
        # best-effort for simple single-arg generics
        try:
            inner = target_type.__args__[0]
            if target_type.__origin__ is list:
                return [instantiate_type(inner, item) for item in (data or [])]
        except Exception:
            pass

    # Concrete class handling
    if isinstance(target_type, type):
        # Prefer explicit from_dict constructor
        if hasattr(target_type, "from_dict") and callable(getattr(target_type, "from_dict")):
            return target_type.from_dict(data)

        # dataclass support
        if dataclasses.is_dataclass(target_type):
            if isinstance(data, dict):
                return target_type(**data)

        # Last resort: try calling the type with the data as positional arg
        try:
            return target_type(data)
        except Exception:
            return data

    # Not a class or supported generic — return as-is.
    return data
