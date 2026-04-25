# Typed Models With @apimodel

`@apimodel` is PyperCache's model decorator for raw API-shaped data. Decorate a class and it gains a dict-accepting constructor, nested type hydration, `from_dict()`, `as_dict()`, field aliases, timestamp parsing, lazy fields, and optional validation.

Use it when you want typed round-trips with `Cache.store(..., cast=MyModel)` / `cache.get_object()`, or typed responses with `ApiWrapper.request(..., cast=MyModel)`.

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

## Nested models

Annotated nested model types are hydrated automatically — you do not need to call nested constructors manually:

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


user = User({
    "id": 1,
    "company": {"name": "Microsoft", "address": {"city": "Redmond"}},
    "previous": [{"city": "Phoenix"}, {"city": "Tempe"}],
})

print(user.company.address.city)   # "Redmond"
print(user.previous[0].city)       # "Phoenix"
```

## `validate` and `strict`

```python
@apimodel(validate=False, strict=False)
```

- `validate=True` — checks hydrated values against type annotations; raises `ApiModelValidationError` on mismatch
- `strict=True` — raises `ApiModelValidationError` when an annotated field is missing, instead of storing `UNSET`

```python
from pypercache.models.validation import ApiModelValidationError


@apimodel(validate=True, strict=True)
class StrictUser:
    id: int
    name: str


try:
    StrictUser({"id": 1})
except ApiModelValidationError as exc:
    print(exc)
```

## `Alias`

Use `Alias(...)` when the raw payload key differs from the Python attribute name:

```python
from typing import Annotated
from pypercache.models.apimodel import Alias, apimodel


@apimodel(validate=True)
class Post:
    user_id: Annotated[int, Alias("userId")]
    title: str
    body: str
```

## `Timestamp`

Use `Timestamp(...)` when a raw field should become a `datetime`:

```python
from datetime import datetime
from typing import Annotated
from pypercache.models.apimodel import Alias, Timestamp, apimodel


@apimodel(validate=True)
class User:
    created_at: Annotated[datetime, Alias("createdAt"), Timestamp()]
```

`Timestamp()` supports ISO 8601 strings, numeric Unix timestamps, millisecond timestamps (`unit="ms"`), and explicit format strings (`Timestamp("%Y-%m-%d %H:%M:%S")`).

## `Columns`

Use `Columns(...)` when the API returns a dict of parallel arrays and you want a `list[RowModel]`. This is especially useful for time-series APIs like Open-Meteo.

```python
from typing import Annotated
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

## `Lazy[T]`

Use `Lazy[T]` when a field is expensive or large and you do not want to hydrate it until first access. `Lazy` can be combined with `Alias`, `Timestamp`, and `Columns`:

```python
from pypercache.models.apimodel import Lazy, apimodel


@apimodel(validate=True)
class User:
    id: int
    profile: Lazy[Profile]
```

Use `Shallow()` with `Lazy` to defer `validate=True` / `strict=True` checks for that specific field until it is accessed. Other fields keep normal init-time validation.

## Using models with Cache and ApiWrapper

```python
# Cache
cache.store("user:1", {"id": 1, "name": "Ada"}, cast=User)
user = cache.get_object("user:1")

# ApiWrapper
class UserClient(ApiWrapper):
    def get_user(self, user_id: int) -> User:
        return self.request("GET", f"/users/{user_id}", expected="json", cast=User)
```

## Practical advice

- Define models at module scope so they can be resolved reliably by the cache.
- Prefer `validate=True` for external API payloads.
- Use `strict=True` only when missing fields should be a hard failure.
- Use `@Cache.cached` instead of `@apimodel` when you only need simple class registration with no field metadata.
