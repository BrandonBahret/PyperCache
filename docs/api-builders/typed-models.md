# Typed Models With @apimodel

`@apimodel` is PyperCache's model decorator for raw API-shaped data.

Decorate a class and it gains a dict-accepting constructor, nested type hydration, `from_dict()`, `as_dict()`, field aliases, timestamp parsing, lazy fields, and optional validation.

Use it when you want:

- a constructor that accepts a raw `dict`
- nested type hydration from annotations
- `from_dict()` and `as_dict()`
- field aliases
- timestamp parsing
- optional strictness and runtime validation
- compatibility with `Cache.store(..., cast=MyModel)` and `ApiWrapper.request(..., cast=MyModel)`

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

## Nested models from raw dicts

This is the same shape used in the notebook walkthrough:

```python
from pypercache import Cache
from pypercache.models.apimodel import apimodel


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


cache = Cache(filepath="users_demo.pkl")
cache.store(
    "u",
    {
        "id": 1,
        "company": {"name": "Microsoft", "address": {"city": "Redmond"}},
        "previous": [{"city": "Phoenix"}, {"city": "Tempe"}],
    },
    cast=User,
)

u = cache.get_object("u")
print(type(u.company).__name__)
print(type(u.previous[0]).__name__)
print(u.company.address.city)
```

Annotated nested model types are hydrated automatically. You do not need to manually call nested constructors like `Address(raw["address"])`.

## `validate` and `strict`

The decorator signature is:

```python
@apimodel(validate=False, strict=False)
```

- `validate=True` checks hydrated values against the type annotations and raises `ApiModelValidationError` on mismatch.
- `strict=True` raises `ApiModelValidationError` when an annotated field is missing instead of storing `UNSET`.

Typical production model:

```python
@apimodel(validate=True)
class User:
    id: int
    name: str
```

If you want missing fields to fail immediately:

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

Use `Alias(...)` when the raw payload key is not the Python attribute name.

```python
from typing import Annotated

from pypercache.models.apimodel import Alias, apimodel


@apimodel(validate=True)
class User:
    display_name: Annotated[str, Alias("displayName")]
```

This is the exact pattern used throughout the JSONPlaceholder example:

```python
@apimodel(validate=True)
class Post:
    user_id: Annotated[int, Alias("userId")]
    title: str
    body: str


@apimodel(validate=True)
class Company:
    name: str
    catch_phrase: Annotated[str, Alias("catchPhrase")]
```

## `Timestamp`

Use `Timestamp(...)` when a raw field should become a `datetime`.

```python
from datetime import datetime
from typing import Annotated

from pypercache.models.apimodel import Alias, Timestamp, apimodel


@apimodel(validate=True)
class User:
    created_at: Annotated[datetime, Alias("createdAt"), Timestamp()]
```

`Timestamp()` supports:

- ISO 8601 strings
- numeric Unix timestamps
- millisecond timestamps with `unit="ms"`
- explicit formats like `Timestamp("%Y-%m-%d %H:%M:%S")`

Examples:

```python
@apimodel(validate=True)
class AuditRecord:
    created_at: Annotated[datetime, Timestamp()]
    refreshed_at: Annotated[datetime, Timestamp(unit="ms")]
```

## `Columns`

Use `Columns(...)` when the API returns a dict of parallel arrays and you want a `list[RowModel]`.

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
```

This is especially useful for time-series APIs such as Open-Meteo.

Short example with a row read:

```python
forecast = Forecast(
    {
        "hourly": {
            "time": [1713000000, 1713003600],
            "temperature_2m": [21.2, 22.5],
        }
    }
)

print(forecast.hourly[0].temperature_2m)
```

## `Lazy[...]`

Use `Lazy[T]` when a field is expensive or large and you do not want to hydrate it until first access.

```python
from pypercache.models.apimodel import Lazy, apimodel


@apimodel(validate=True)
class Profile:
    timezone: str


@apimodel(validate=True)
class User:
    id: int
    profile: Lazy[Profile]
```

You can combine `Lazy` with `Alias`, `Timestamp`, or `Columns`.

That is exactly what the Open-Meteo example does:

```python
from datetime import datetime
from typing import Annotated

from pypercache.models.apimodel import Alias, Columns, Lazy, Timestamp, apimodel


@apimodel(validate=True)
class HourlyPoint:
    time: Annotated[datetime, Timestamp(unit="seconds")]
    temperature_c: Annotated[float, Alias("temperature_2m")]


@apimodel(validate=True)
class Forecast:
    hourly: Lazy[
        Annotated[
            list[HourlyPoint],
            Columns(required=("time", "temperature_2m")),
        ]
    ]
```

## Using models with the cache

```python
from pypercache import Cache

cache = Cache(filepath="users.json")
cache.store("user:1", {"id": 1, "name": "Ada"}, cast=User)

user = cache.get_object("user:1")
print(user.name)
```

## Using models with `ApiWrapper`

```python
class UserClient(ApiWrapper):
    def get_user(self, user_id: int) -> User:
        return self.request("GET", f"/users/{user_id}", expected="json", cast=User)
```

## Practical advice

- Define models at module scope so they can be resolved reliably later.
- Prefer `validate=True` for external API payloads.
- Reach for `strict=True` only when missing fields should be a hard failure.
- Use `@Cache.cached` instead of `@apimodel` when you only need simple class registration and no field metadata.
