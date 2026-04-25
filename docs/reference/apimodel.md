# @apimodel Reference

## Imports

```python
from pypercache.models.apimodel import Alias, Columns, Lazy, Shallow, Timestamp, apimodel
from pypercache.models.validation import ApiModelValidationError
```

## Decorator signature

```python
@apimodel(validate=False, strict=False)
class MyModel:
    ...
```

Can also be applied without arguments: `@apimodel`.

## What the decorator adds

- Registers the class with the shared class repository
- Injects a constructor that accepts one raw `dict`
- Adds `from_dict(cls, data)` class method
- Adds `as_dict(self)` instance method
- Supports eager and lazy field hydration from annotations

`as_dict()` returns the underlying raw dict representation. Assigning to a decorated field writes the converted value back into that raw dict.

## Parameters

| Parameter | Default | Description |
|---|---|---|
| `validate` | `False` | Check hydrated values against type annotations. Raises `ApiModelValidationError` on mismatch. |
| `strict` | `False` | Raise `ApiModelValidationError` when an annotated field is missing, instead of storing `UNSET`. |

## Field helpers

### `Alias(key)`

Read a field from a different raw key.

```python
display_name: Annotated[str, Alias("displayName")]
```

### `Timestamp(fmt=None, *, unit="seconds", tz=timezone.utc)`

Parse a raw field into a `datetime`. Supports ISO 8601 strings, numeric Unix timestamps, millisecond timestamps (`unit="ms"`), and explicit format strings.

```python
created_at: Annotated[datetime, Timestamp()]
refreshed_at: Annotated[datetime, Timestamp(unit="ms")]
created_at: Annotated[datetime, Alias("createdAt"), Timestamp()]
```

### `Columns(required=())`

Convert a dict-of-parallel-arrays payload into `list[RowModel]`. Useful for time-series APIs.

```python
hourly: Annotated[list[HourRow], Columns(required=("time", "temperature_2m"))]
```

### `Lazy[T]`

Defer hydration of a field until first access.

```python
profile: Lazy[Profile]
```

Can be combined with `Alias`, `Timestamp`, and `Columns`.

### `Shallow()`

Use with `Lazy[Annotated[T, Shallow()]]` to defer `validate=True` / `strict=True` checks for that lazy field until it is accessed. Other model fields keep normal init-time validation.
