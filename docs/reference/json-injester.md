# JsonInjester Selector Syntax

`JsonInjester` is a read-only query layer over in-memory dicts and lists. It is available on every `CacheRecord` via `.query`, and can also be instantiated directly.

```python
# From a cache record
q = cache.get("order:sample").query

# Directly from a dict or list
from pypercache.query import JsonInjester
q = JsonInjester({"meta": {"total": 5}})
```

`JsonInjester` accepts a `dict`, a `list`, or a JSON string that parses to either.

## `get()`

```python
q.get(selector, default_value=UNSET, select_first=False, cast=None)
```

- `default_value` — returned when the path is missing or resolves to `None`
- `select_first=True` — unwraps the first element of a list result; returns `UNSET` if the list is empty
- `cast` — hydrates a dict result into a model or type

```python
from pypercache.query.json_injester import UNSET

value = q.get("missing.path")
print(value is UNSET)                           # True
print(q.get("missing.path", default_value=0))   # 0
```

## Constructor options

`root` moves the starting cursor to a subtree:

```python
q = JsonInjester({"meta": {"total": 5}}, root="meta")
print(q.get("total"))   # 5
```

`default_tail` automatically follows one extra selector when the result is a dict:

```python
q = JsonInjester({"wrapper": {"value": 5}}, default_tail="value")
print(q.get("wrapper"))   # 5
```

## Selector reference

Selectors compose left to right. Each token narrows or transforms the current cursor before passing it to the next.

### Dot-separated paths

```python
q.get("meta.total")
q.get("user.profile.timezone")
```

If any key is missing, the result is `UNSET`.

### Quoted keys

Wrap in double quotes when a key contains characters that are not valid identifiers:

```python
q.get('"content-type".value')
```

### `?key=value` — match filter

Filter a list of dicts to elements where a key path equals a value. Appending a tail path plucks it from each match.

```python
q.get("users?role=admin")               # list of matching dicts
q.get("users?role=admin.name")          # pluck .name from each match
q.get("users?team.name=Platform")       # nested key path
```

For numeric comparisons, prefix the value with `#`:

```python
q.get("users?score=#42")
q.get("users?ratio=#3.14")
```

No matches returns an empty list.

### `?field*` — pluck

Pluck one field from every element in a list. Plucks can be chained.

```python
q.get("users?name*")
q.get("users?team.name*")
q.get("users?role*?label*")     # chained
```

### `?key` — exists filter

On a dict cursor — returns the dict if the key exists, `UNSET` if absent.
On a list cursor — returns only elements that contain the key.

```python
q.get("meta?total")
q.get("users?team")
```

## `has()`

`has(selector)` returns `True` when the selector resolves to something other than `UNSET`:

```python
q.has("meta.total")
```

## Full example

```python
from pypercache import Cache

cache = Cache(filepath="orders.pkl")
cache.store("order:sample", {
    "id": "ORD-2024-001",
    "status": "confirmed",
    "customer": {"name": "Sarah Johnson", "email": "sarah@example.com"},
    "items": [
        {"name": "Laptop", "price": 999.99, "category": "electronics"},
        {"name": "Mouse", "price": 59.99, "category": "electronics"},
        {"name": "Case", "price": 29.99, "category": "accessories"},
    ],
    "total": 1089.97,
})

q = cache.get("order:sample").query

print(q.get("customer.name"))               # "Sarah Johnson"
print(q.get("items?name*"))                 # ["Laptop", "Mouse", "Case"]
print(q.get("items?category=electronics"))  # [{"name": "Laptop", ...}, ...]
print(q.get("discount", default_value=0))   # 0

dashboard = {
    "customer": q.get("customer.name"),
    "order_value": q.get("total"),
    "item_count": len(q.get("items")),
    "categories": list(set(q.get("items?category*"))),
    "avg_price": sum(q.get("items?price*")) / len(q.get("items")),
}
```

## Quick selector reference

| Selector | Meaning |
|---|---|
| `key.key.key` | Dot-separated path navigation |
| `"content-type"` | Quoted key for non-identifier names |
| `list?key=value` | Filter list elements by exact match |
| `list?key=#42` | Numeric filter |
| `list?key=value.field` | Filter, then pluck a tail field from matches |
| `list?field*` | Pluck one field from each element |
| `key?field` | Exists filter on a dict or list cursor |

## Limits

- `JsonInjester` is read-only.
- Integer list indexing (`"users.0.name"`) is not supported.
- A bare path on a list root is not supported — use `?key*` or `?key=value`.
- Missing paths return `UNSET` unless `default_value` is provided.
