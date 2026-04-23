# JsonInjester Selector Guide

All selectors are passed as strings to `q.get()`. They compose left to right, so each token narrows or transforms the current cursor before handing it to the next token.

`JsonInjester` can be created from:

- a `dict`
- a `list`
- a JSON string that parses to either of those

```python
from pypercache.query import JsonInjester

q = JsonInjester({"meta": {"total": 5}})
```

You will usually see it in one of two forms:

```python
from pypercache import Cache

cache = Cache(filepath="orders.pkl")
cache.store("order:sample", {"customer": {"name": "Sarah"}})

q = cache.get("order:sample").query
print(q.get("customer.name"))
```

or:

```python
from pypercache.query import JsonInjester

q = JsonInjester({"customer": {"name": "Sarah"}})
print(q.get("customer.name"))
```

## Constructor options

### `root`

Move the starting cursor to a subtree:

```python
q = JsonInjester({"meta": {"total": 5}}, root="meta")
print(q.get("total"))
```

### `default_tail`

If a selector resolves to a dict, `default_tail` automatically follows one extra selector before returning:

```python
q = JsonInjester({"wrapper": {"value": 5}}, default_tail="value")
print(q.get("wrapper"))
```

## `get()`

```python
q.get(selector, default_value=UNSET, select_first=False, cast=None)
```

- `default_value` is returned when the path is missing or resolves to `None`
- `select_first=True` unwraps the first element of a list result
- `cast` hydrates a dict result into a model or type

Import `UNSET` if you need to test for "not found" explicitly:

```python
from pypercache.query.json_injester import UNSET
```

Short example:

```python
value = q.get("missing.path")
print(value is UNSET)
print(q.get("missing.path", default_value=0))
```

## Path navigation

Use dot-separated keys:

```python
q.get("meta.total")
q.get("user.profile.timezone")
```

If any key is missing, the result is `UNSET` unless you supplied `default_value`.

Notebook-style examples:

```python
q.get("customer.name")
q.get("total")
q.get("id")
```

## Quoted keys

Wrap keys in double quotes when they contain characters that are not normal identifier characters:

```python
q.get('"content-type".value')
```

## `?key=value`: match filter

Filter a list of dicts down to elements where the key path equals the value:

```python
q.get("users?role=admin")
q.get("users?team.name=Platform")
```

If you add a tail path after the filter, the tail is plucked from each match:

```python
q.get("users?role=admin.name")
```

Numeric comparisons use a leading `#`:

```python
q.get("users?score=#42")
q.get("users?ratio=#3.14")
```

No matches returns an empty list.

Notebook-style example:

```python
q.get("items?category=electronics")
```

## `?key*`: pluck

Pluck a field from each element in a list:

```python
q.get("users?name*")
q.get("users?team.name*")
```

Plucks can be chained:

```python
q.get("users?role*?label*")
```

Notebook-style examples:

```python
q.get("items?name*")
q.get("items?price*")
q.get("items?category*")
```

## `?key`: exists filter

Check whether a key is present.

On a dict cursor:

- returns the dict unchanged if the key exists
- returns `UNSET` if the key is absent

On a list cursor:

- returns only the elements that contain that key

Examples:

```python
q.get("meta?total")
q.get("users?team")
```

## `has()`

`has(selector)` is shorthand for "did this selector resolve to something other than `UNSET`?"

```python
q.has("meta.total")
```

For optional data, `has()` is usually clearer than comparing against `None`:

```python
discount = q.get("discount", default_value=0)
has_discount = q.has("discount")
```

## `select_first`

Use this when you want the first list result instead of the whole list:

```python
first_admin = q.get("users?role=admin", select_first=True)
```

If the list is empty, the result is `UNSET`.

## `cast`

If the resolved result is a dict, `cast` can hydrate it into a type:

```python
admin = q.get("users?role=admin", select_first=True, cast=User)
```

## Quick selector reference

| Selector form | Meaning |
|---|---|
| `key.key.key` | Dot-separated path navigation |
| `"content-type"` | Quoted key for non-identifier names |
| `list?key=value` | Filter list elements by exact match |
| `list?key=#42` | Numeric filter |
| `list?key=value.field` | Filter, then pluck a tail path from matches |
| `list?field*` | Pluck one field from each element |
| `key?field` | Exists filter on a dict or list cursor |

## Recipe: inspect one cached order

This example is adapted directly from the notebook and shows a realistic small workflow.

```python
from pypercache import Cache

cache = Cache(filepath="query_demo.pkl")
cache.store(
    "order:sample",
    {
        "id": "ORD-2024-001",
        "status": "confirmed",
        "customer": {
            "name": "Sarah Johnson",
            "email": "sarah@example.com",
        },
        "items": [
            {"name": "Laptop", "price": 999.99, "category": "electronics"},
            {"name": "Mouse", "price": 59.99, "category": "electronics"},
            {"name": "Case", "price": 29.99, "category": "accessories"},
        ],
        "total": 1089.97,
    },
)

q = cache.get("order:sample").query

print(q.get("customer.name"))
print(q.get("items?name*"))
print(q.get("items?category=electronics"))
print(q.get("discount", default_value=0))
```

### Dashboard-style extraction

```python
dashboard_data = {
    "customer": q.get("customer.name"),
    "order_value": q.get("total"),
    "item_count": len(q.get("items")),
    "categories": list(set(q.get("items?category*"))),
    "avg_price": sum(q.get("items?price*")) / len(q.get("items")),
}

print(dashboard_data)
```

## Limits and edge cases

- `JsonInjester` is read-only.
- It works on one in-memory payload at a time.
- Integer list indexing like `"users.0.name"` is not supported.
- A bare path on a list root is not supported. Use `?key*` or `?key=value`.
- Missing paths return `UNSET` unless you pass `default_value`.

## Typical direct-use example

```python
from pypercache.query import JsonInjester
from pypercache.query.json_injester import UNSET

data = {
    "meta": {"total": 3},
    "hits": [
        {"name": "Alice", "role": "staff", "score": 92},
        {"name": "Bob", "role": "guest", "score": 74},
        {"name": "Carol", "role": "staff", "score": 88},
    ],
}

q = JsonInjester(data)

print(q.get("meta.total"))
print(q.get("hits?role=staff.name"))
print(q.get("hits?name*"))
print(q.get("hits?role=staff", select_first=True))
print(q.get("hits?role=contractor", select_first=True) is UNSET)
```
