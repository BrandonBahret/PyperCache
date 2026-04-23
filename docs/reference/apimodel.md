# apimodel Reference

## Imports

```python
from pypercache.models.apimodel import Alias, Columns, Timestamp, apimodel
from pypercache.models.lazy import Lazy
from pypercache.models.validation import ApiModelValidationError
```

## Decorator signature

```python
apimodel(
    cls=None,
    *,
    validate: bool = False,
    strict: bool = False,
)
```

## What the decorator adds

For a decorated class, `apimodel`:

- registers the class with the shared class repository
- injects a constructor that accepts one raw `dict`
- adds `from_dict(cls, data)`
- adds `as_dict(self)`
- supports eager and lazy field hydration from annotations

## Field helpers

### `Alias(key)`

Read a field from another raw key.

### `Timestamp(fmt=None, *, unit="seconds", tz=timezone.utc)`

Parse raw timestamp values into `datetime`.

Supported sources:

- ISO 8601 strings
- numeric timestamps
- formatted strings when `fmt` is provided

### `Columns(required=())`

Convert a dict-of-arrays payload into `list[RowModel]`.

### `Lazy[T]`

Mark a field for deferred hydration on first access.

## Validation behavior

- `validate=True` checks values against type annotations
- `strict=True` rejects missing annotated fields instead of storing `UNSET`
- failures raise `ApiModelValidationError`

## Notes

- `as_dict()` returns the underlying raw dict representation
- assigning to a decorated field writes the converted value back into that raw dict
- lazy fields can also use `Alias`, `Timestamp`, and `Columns`
