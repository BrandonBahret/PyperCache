---

tag: Reference

comment: "REF: APIMODEL"

title: @apimodel

title_em: "API"

lead: |

  Exact signatures for the decorator and all field helpers.

breadcrumb: "pypercache / @apimodel api"

---



```python
from pypercache.models.apimodel import Alias, Columns, Lazy, Shallow, Timestamp, apimodel
from pypercache.models.validation import ApiModelValidationError
```

## Decorator {id=decorator}

:::method
@apimodel(cls=None, *, validate: bool = False, strict: bool = False)
:::

Can be used bare (`@apimodel{ref=ref-apimodel#decorator}`) or with keyword arguments (`@apimodel(validate=True){ref=ref-apimodel#decorator}`).

## What the decorator adds {id=what-the-decorator-adds}

* Registers the class in the shared class repository
* Injects a constructor that accepts one raw `dict`
* Adds `from_dict(cls, data){ref=ref-apimodel#what-the-decorator-adds}` classmethod
* Adds `as_dict(self){ref=ref-apimodel#what-the-decorator-adds}` instance method
* Handles eager and lazy field hydration from annotations

## Field helpers {id=field-helpers}

### Alias {id=alias}

:::method
Alias(key: str)
:::

Read the field from a different raw key name.

### Timestamp {id=timestamp}

:::method
Timestamp(fmt=None, *, unit="seconds", tz=timezone.utc)
:::

Parses raw timestamp values into `datetime`. Handles ISO 8601 strings, numeric Unix timestamps, millisecond timestamps (`unit="ms"{ref=ref-apimodel#timestamp}`), and explicit format strings.

### Columns {id=columns}

:::method
Columns(required=())
:::

Converts a dict-of-parallel-arrays payload into `list[RowModel]{ref=ref-apimodel#columns}`.

### Lazy {id=lazy}

:::method
Lazy[T]
:::

Defers hydration of a field until first access. Composes with `Alias{ref=ref-apimodel#alias}`, `Timestamp{ref=ref-apimodel#timestamp}`, and `Columns{ref=ref-apimodel#columns}`.

### Shallow {id=shallow}

:::method
Shallow()
:::

Use with `Lazy[Annotated[T, Shallow()]]` to defer `validate=True` / `strict=True` checks for that lazy field until it is accessed. Other model fields keep normal init-time validation.

## Validation {id=validation}

* `validate=True` — checks values against type annotations; raises `ApiModelValidationError{ref=ref-apimodel#validation}` on mismatch
* `strict=True` — raises `ApiModelValidationError{ref=ref-apimodel#validation}` when an annotated field is missing instead of storing `UNSET{ref=ref-apimodel#validation}`

## Notes {id=notes}

* `as_dict(){ref=ref-apimodel#what-the-decorator-adds}` returns the underlying raw dict representation
* Assigning to a decorated field writes the converted value back into that raw dict
* Define models at module scope so they can be resolved reliably by the class repository
