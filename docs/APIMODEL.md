# API Model

`@apimodel` is pypercache's lightweight annotation-driven model decorator for API-shaped data.

Use it when you want:

- a constructor that accepts a raw `dict`
- `.from_dict(...)` and `.as_dict()` helpers
- nested type hydration through annotations
- alias support for raw API field names
- timestamp parsing into `datetime`
- compatibility with `Cache.store(..., cast=MyModel)` and `ApiWrapper.request(..., cast=MyModel)`

For the cache lifecycle around typed values, see [CACHE.md](CACHE.md). For wrapper usage with typed API requests, see [API_WRAPPER.md](API_WRAPPER.md).

---

## Basic example

```python
from pypercache.models.apimodel import apimodel


@apimodel
class Widget:
    id: int
    name: str


widget = Widget({"id": 1, "name": "Gear"})
print(widget.id)    # 1
print(widget.name)  # Gear
print(Widget.from_dict({"id": 2, "name": "Bolt"}).name)  # Bolt
```

---

## Aliases

Use `Alias(...)` when the raw API field name does not match the Python attribute name.

```python
from typing import Annotated

from pypercache.models.apimodel import Alias, apimodel


@apimodel
class User:
    display_name: Annotated[str, Alias("displayName")]
```

```python
user = User({"displayName": "Ada"})
print(user.display_name)  # Ada
```

---

## Timestamps

Use `Timestamp(...)` when a raw field should hydrate as `datetime`.

```python
from datetime import datetime
from typing import Annotated

from pypercache.models.apimodel import Alias, Timestamp, apimodel


@apimodel
class User:
    created_at: Annotated[datetime, Alias("createdAt"), Timestamp()]
```

`Timestamp()` supports:

- ISO 8601 strings
- Unix timestamps
- millisecond timestamps
- explicit `datetime.strptime` formats

---

## Typed wrapper responses

`apimodel` works naturally with `ApiWrapper`:

```python
from pypercache.api_wrapper import ApiWrapper


class UserClient(ApiWrapper):
    def list_users(self) -> list[User]:
        return self.request("GET", "/users", expected="json", cast=list[User])
```

It also works with cache round-trips:

```python
cache.store("user:1", {"displayName": "Ada"}, cast=User)
user = cache.get_object("user:1")
```

---

## More detail

`@apimodel` also supports validation options, strict mode, lazy fields, and nested hydration. The fuller reference and examples currently live in the `@apimodel` section of [CACHE.md](CACHE.md).
