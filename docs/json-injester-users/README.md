# JsonInjester Users

This section is for people who only want the query layer.

`JsonInjester` gives you a small, read-only selector language for navigating nested JSON-like data in memory.

It does not mutate data and it does not query a backend. It operates on one payload you already have in memory, either passed directly or loaded from `CacheRecord.query`.

Use it when you want to:

- safely walk deep dict structures
- filter lists of dicts
- pluck values from repeated objects
- avoid repetitive `if key in ...` navigation code

## Smallest example

```python
from pypercache.query import JsonInjester

data = {
    "meta": {"total": 2},
    "users": [
        {"name": "Ada", "role": "admin"},
        {"name": "Linus", "role": "member"},
    ],
}

q = JsonInjester(data)

print(q.get("meta.total"))
print(q.get("users?role=admin"))
print(q.get("users?name*"))
```

## Start here

- [Selector guide](./selector-guide.md)

## Good fit

- loaded dicts or lists
- API response inspection
- light in-memory filtering
- pulling fields out of large payloads

## Bad fit

- cross-record searches
- relational queries
- mutating data
- backend-wide scans
