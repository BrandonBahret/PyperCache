---

tag: API clients

comment: TYPED MODELS

title: Typed models with

title_em: "@apimodel"

lead: |

  Decorate a class and it gains a dict-accepting constructor, nested type hydration, `from_dict(){ref=ref-apimodel#what-the-decorator-adds}`, `as_dict(){ref=ref-apimodel#what-the-decorator-adds}`, field aliases, timestamp parsing, lazy fields, and optional validation.

breadcrumb: "pypercache / typed models"

---



## Basic usage

```python
from pypercache.models.apimodel import apimodel

@apimodel
class Widget:
    id: int
    name: str

widget = Widget({"id": 1, "name": "Gear"})
print(widget.name)
print(Widget.from_dict({"id": 2, "name": "Bolt"}).id)
print(widget.as_dict())
```

## Nested hydration

Annotated nested model types are hydrated automatically — no explicit `Address(raw_dict)` calls needed.

```python
@apimodel
class Address:
    city: str

@apimodel
class Company:
    name: str
    address: Address

@apimodel
class User:
    id: int
    company: Company
    previous: list[Address]

u = User({
    "id": 1,
    "company": {"name": "ACME", "address": {"city": "Redmond"}},
    "previous": [{"city": "Phoenix"}, {"city": "Tempe"}],
})
print(u.company.address.city)  # "Redmond"
print(u.previous[0].city)     # "Phoenix"
```

## Validation and strictness

```python
@apimodel(validate=True)
class User:
    id: int
    name: str
```

`validate=True` checks hydrated values against type annotations. Add `strict=True` to also raise on missing annotated fields (instead of silently storing `UNSET{ref=ref-apimodel#validation}`).

```python
from pypercache.models.validation import ApiModelValidationError

@apimodel(validate=True, strict=True)
class StrictUser:
    id: int
    name: str

try:
    StrictUser({"id": 1})       # missing "name"
except ApiModelValidationError as exc:
    print(exc)
```

## Alias — mapping raw keys

Use when the raw payload uses a key you don't want on the Python object.

```python
from typing import Annotated
from pypercache.models.apimodel import Alias, apimodel

@apimodel(validate=True)
class Post:
    user_id: Annotated[int, Alias("userId")]
    title: str
    body: str
```

## Timestamp — parsing date fields

```python
from datetime import datetime
from pypercache.models.apimodel import Alias, Timestamp, apimodel

@apimodel(validate=True)
class AuditRecord:
    created_at: Annotated[datetime, Timestamp()]
    refreshed_at: Annotated[datetime, Alias("refreshedAt"), Timestamp(unit="ms")]
```

`Timestamp(){ref=ref-apimodel#timestamp}` handles ISO 8601 strings, numeric Unix timestamps, millisecond timestamps (`unit="ms"{ref=ref-apimodel#timestamp}`), and explicit format strings.

## Columns — parallel arrays to rows

Some APIs return data as a dict of parallel arrays. `Columns{ref=ref-apimodel#columns}` converts that into a list of row model instances.

```python
from pypercache.models.apimodel import Columns, apimodel

@apimodel(validate=True)
class HourRow:
    time: int
    temperature_2m: float

@apimodel(validate=True)
class Forecast:
    hourly: Annotated[list[HourRow], Columns(required=("time", "temperature_2m"))]

forecast = Forecast({
    "hourly": {
        "time": [1713000000, 1713003600],
        "temperature_2m": [21.2, 22.5],
    }
})
print(forecast.hourly[0].temperature_2m)  # 21.2
```

## Lazy — deferred hydration

Wrap a type in `Lazy[T]{ref=ref-apimodel#lazy}` and it won't be hydrated until first access. Useful for large or expensive nested fields.

```python
from pypercache.models.apimodel import Lazy, apimodel

@apimodel(validate=True)
class User:
    id: int
    profile: Lazy[Profile]
```

`Lazy{ref=ref-apimodel#lazy}` composes with `Alias{ref=ref-apimodel#alias}`, `Timestamp{ref=ref-apimodel#timestamp}`, and `Columns{ref=ref-apimodel#columns}`.
