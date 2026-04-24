---

tag: Query layer

comment: JSON INJESTER

title: JsonInjester

lead: |

  A small, read-only selector language for navigating nested dicts in memory. No mutations, no backend queries — just structured access over a payload you already have.

breadcrumb: "pypercache / jsoninjester"

---



## Standalone usage {id=standalone-usage}

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

Or access it directly from a `CacheRecord{ref=ref-cache#cache-record}`:

```python
q = cache.get("order:1").query
print(q.get("customer.name"))
```

## Constructor options {id=constructor-options}

**`root{ref=json-injester#constructor-options}`** — move the starting cursor to a subtree:

```python
q = JsonInjester({"meta": {"total": 5}}, root="meta")
print(q.get("total"))  # 5
```

**`default_tail{ref=json-injester#constructor-options}`** — when a selector resolves to a dict, automatically follow one more selector before returning:

```python
q = JsonInjester({"wrapper": {"value": 5}}, default_tail="value")
print(q.get("wrapper"))  # 5
```

## When selectors resolve to nothing {id=when-selectors-resolve-to-nothing}

```python
from pypercache.query.json_injester import UNSET

value = q.get("missing.path")
print(value is UNSET)                              # True
print(q.get("missing.path", default_value=0))  # 0
```

Use `has(){ref=json-injester#when-selectors-resolve-to-nothing}` when you just want a boolean — it's clearer than checking against `None{ref=json-injester#when-selectors-resolve-to-nothing}`:

```python
has_discount = q.has("discount")
discount = q.get("discount", default_value=0)
```

## Good fit / bad fit {id=good-fit-bad-fit}

:::cards
### ✓ Good fit
Loaded dicts and lists · API response inspection · Light in-memory filtering · Plucking fields from large payloads
### ✗ Bad fit
Cross-record searches · Relational queries · Mutating data · Backend-wide scans
:::
