from __future__ import annotations

from typing import Annotated, Any, get_args, get_origin

from ..utils.sentinel import UNSET
from ..utils.typing_cast import instantiate_type as _default_instantiate_type
from .fields import Alias, Columns, Timestamp
from .validation import ApiModelValidationError


def unwrap_field_config(annotation: Any) -> tuple[Any, str | None, Timestamp | None, Columns | None]:
    """Return ``(base_annotation, alias, timestamp, columns)``."""
    if get_origin(annotation) is not Annotated:
        return annotation, None, None, None

    args = get_args(annotation)
    alias = next((item.key for item in args[1:] if isinstance(item, Alias)), None)
    timestamp = next((item for item in args[1:] if isinstance(item, Timestamp)), None)
    columns = next((item for item in args[1:] if isinstance(item, Columns)), None)
    return args[0], alias, timestamp, columns


def unwrap_lazy_config(annotation: Any, lazy_type: Any) -> tuple[Any, str | None, Timestamp | None, Columns | None] | None:
    """Return the resolved field config for ``Lazy[...]`` annotations."""
    if get_origin(annotation) is not lazy_type:
        return None

    (inner,) = get_args(annotation)
    return unwrap_field_config(inner)


def instantiate_field_value(
    annotation: Any,
    raw: Any,
    *,
    timestamp: Timestamp | None = None,
    columns: Columns | None = None,
    instantiator=_default_instantiate_type,
) -> Any:
    """Hydrate a raw field value according to annotation metadata."""
    if columns is not None:
        return _hydrate_columns(annotation, raw, columns, instantiator=instantiator)

    if timestamp is not None:
        return _hydrate_timestamped(annotation, raw, timestamp, instantiator=instantiator)

    return instantiator(annotation, raw)


def as_raw_value(
    value: Any,
    *,
    timestamp: Timestamp | None = None,
    columns: Columns | None = None,
) -> Any:
    """Serialize a Python-facing value back into the raw payload shape."""
    if columns is not None:
        return _columnize_rows(_serialize_basic(value))

    if timestamp is not None:
        return _serialize_timestamped(value, timestamp)

    return _serialize_basic(value)


def write_raw_value(data: dict[str, Any], raw_key: str, value: Any) -> None:
    """Write *value* into *data*, respecting dot-separated raw key paths."""
    if "." not in raw_key:
        data[raw_key] = value
        return

    cursor = data
    parts = raw_key.split(".")
    for part in parts[:-1]:
        next_cursor = cursor.get(part)
        if not isinstance(next_cursor, dict):
            next_cursor = {}
            cursor[part] = next_cursor
        cursor = next_cursor
    cursor[parts[-1]] = value


def _hydrate_columns(annotation: Any, raw: Any, columns: Columns, *, instantiator) -> Any:
    if raw is UNSET:
        return UNSET

    origin = get_origin(annotation)
    args = get_args(annotation)
    item_type = args[0] if origin is list and args else Any
    if isinstance(raw, list):
        return [instantiator(item_type, row) for row in raw]

    rows = _rows_from_columns(raw, required=columns.required)
    return [instantiator(item_type, row) for row in rows]


def _hydrate_timestamped(annotation: Any, raw: Any, timestamp: Timestamp, *, instantiator) -> Any:
    if raw is UNSET or raw is None:
        return raw

    origin = get_origin(annotation)
    args = get_args(annotation)
    if origin is list:
        if not isinstance(raw, list):
            return raw
        item_type = args[0] if args else Any
        values = []
        for item in raw:
            try:
                parsed = timestamp.parse(item)
            except (OSError, TypeError, ValueError):
                parsed = item
            values.append(instantiator(item_type, parsed))
        return values

    try:
        return timestamp.parse(raw)
    except (OSError, TypeError, ValueError):
        return raw


def _serialize_timestamped(value: Any, timestamp: Timestamp) -> Any:
    if isinstance(value, list):
        return [timestamp.serialize(item) for item in value]
    return timestamp.serialize(value)


def _serialize_basic(value: Any) -> Any:
    if hasattr(value, "as_dict") and callable(getattr(value, "as_dict")):
        return value.as_dict()

    if isinstance(value, list):
        return [_serialize_basic(item) for item in value]

    if isinstance(value, dict):
        return {key: _serialize_basic(item) for key, item in value.items()}

    return value


def _rows_from_columns(payload: Any, *, required: tuple[str, ...]) -> list[dict[str, Any]]:
    if payload is None:
        raise ApiModelValidationError("Columns() expected a dict payload, got NoneType")
    if not isinstance(payload, dict):
        raise ApiModelValidationError(
            f"Columns() expected a dict payload, got {type(payload).__name__}"
        )

    for key in required:
        if key not in payload:
            raise ApiModelValidationError(f"Columns() missing required column {key!r}")

    lengths: dict[str, int] = {}
    for key, value in payload.items():
        if not isinstance(value, list):
            raise ApiModelValidationError(
                f"Columns() expected list values, got {type(value).__name__} for {key!r}"
            )
        lengths[key] = len(value)

    if not lengths:
        return []

    size_set = set(lengths.values())
    if len(size_set) != 1:
        detail = ", ".join(f"{key}={size}" for key, size in sorted(lengths.items()))
        raise ApiModelValidationError(f"Columns() column lengths differ: {detail}")

    size = next(iter(size_set))
    return [{key: payload[key][index] for key in payload} for index in range(size)]


def _columnize_rows(value: Any) -> Any:
    if value is UNSET or value is None:
        return value
    if not isinstance(value, list):
        return value

    rows: list[dict[str, Any]] = []
    all_keys: list[str] = []
    seen: set[str] = set()

    for item in value:
        if not isinstance(item, dict):
            return value
        rows.append(item)
        for key in item:
            if key not in seen:
                seen.add(key)
                all_keys.append(key)

    return {key: [row.get(key) for row in rows] for key in all_keys}
