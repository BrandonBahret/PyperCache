# JsonInjester / record.query

`JsonInjester` is a read-only path and filter language for navigating a loaded dict payload. You almost always use it through `CacheRecord.query`; you can also instantiate it directly when you have a dict outside of a `CacheRecord`.

All selectors run **in memory** against the already-loaded blob. They never touch the storage backend.

---

## Getting a `JsonInjester`

Via a cache record (most common):

```python
record = cache.get("search:v1:python")
q = record.query   # JsonInjester, built once on first access and reused
```

Directly:

```python
from PyperCache.query import JsonInjester

q = JsonInjester({"meta": {"total": 5}, "hits": [...]})
```

---

## `get()` — the main method

```python
q.get(selector, default_value=UNSET, select_first=False, cast=None)
```

| Parameter | Type | Default | Effect |
|-----------|------|---------|--------|
| `selector` | `str` | required | Path and/or operator expression evaluated against the loaded blob. |
| `default_value` | any | `UNSET` | Returned when the path is missing or the resolved value is `None`. Falsy non-`None` values (`False`, `0`, `""`) pass through unchanged. |
| `select_first` | `bool` | `False` | When the result is a list, returns the first element. Returns `UNSET` on an empty list. |
| `cast` | callable / type | `None` | When the result is a `dict`, passes it to `cast(result)` before returning. |

`UNSET` is the library's sentinel for "not found". Import it if you need to test for it explicitly:

```python
from PyperCache.query.json_injester import UNSET
result = q.get("missing.path")
print(result is UNSET)   # True
```

### `has()` — existence check

```python
q.has("meta.total_hits")   # True / False
```

Equivalent to `q.get(selector) is not UNSET`.

---

## Constructor parameters

These shift the default starting point for every `get()` call on this instance.

| Parameter | Effect |
|-----------|--------|
| `root` | Dot-separated path applied before any `get()` call. Moves the cursor to a subtree. |
| `default_tail` | When `get()` resolves to a `dict`, automatically follows this additional selector before returning. |

```python
q = JsonInjester(data, root="meta")
q.get("total_hits")   # equivalent to q.get("meta.total_hits") with no root
```

---

## Path navigation

A bare `"key"` or `"key.nested.path"` walks dict keys separated by dots. Returns `UNSET` if any key along the path is absent.

```python
q.get("meta.total_hits")      # 5
q.get("meta.page")            # 1
q.get("meta.missing_key")     # UNSET
```

Keys containing hyphens or other non-identifier characters must be quoted with double quotes inside the selector string:

```python
q.get('"my-key".subkey')
```

Integer list indexing via dotted path (e.g. `"hits.0.name"`) is **not** supported. Use a filter or pluck instead.

---

## The three selector operators

All operators start with `?` and follow a path expression (or appear at the start of the selector if targeting the root).

### `?key=value` — match filter

Returns every element where `key` equals `value`. Works on a list of dicts or a dict-of-dicts (returns `(key, value)` tuples in the latter case).

A tail path written after the operator (e.g. `?role=staff.name`) plucks a field from each matched element.

```python
# Basic match
staff = q.get("hits?role=staff")
# [{"id":"1","name":"Alice",...}, {"id":"3","name":"Carol",...}]

# Tail pluck after match
names = q.get("hits?role=staff.name")
# ['Alice', 'Carol']

# Nested key in predicate
eng = q.get("hits?team.name=Engineering")
# all dicts where hits[i].team.name == "Engineering"

# Numeric match — prefix with #
q.get("hits?score=#42")     # integer match
q.get("hits?score=#3.14")   # float match

# No matches → empty list (not UNSET)
q.get("hits?role=contractor")   # []
```

### `?key*` — pluck

Extracts the value of `key` from each element and collects non-missing results. On a list cursor, applies to every element. On a dict cursor, navigates and returns the value (or `UNSET`). Plucks can be chained.

```python
q.get("hits?name*")
# ['Alice', 'Bob', 'Carol', 'Dave', 'Eve']

q.get("hits?team.name*")
# ['Engineering', 'Marketing', 'Engineering', 'Sales', 'Engineering']

# Chained plucks: pluck role dicts, then pluck label from each
q.get("hits?role*?label*")
```

### `?key` — exists filter

Does **not** extract values. On a **dict** cursor, returns the cursor unchanged if `key` is present, or `UNSET` if absent. On a **list** cursor, returns only the elements that contain `key`.

```python
# Dict cursor: returns the dict itself if key exists
q.get("meta?total_hits")          # returns the meta dict
q.get("meta?ghost")               # UNSET — key absent
q.get("meta?ghost", default_value=0)  # 0

# List cursor: filters to elements that have the key
q.get("hits?team")   # all hit dicts that contain a "team" key
```

---

## Combining operators: `select_first` and `default_value`

```python
from PyperCache.query.json_injester import UNSET

# First matching element, or UNSET if the list is empty
first_staff = q.get("hits?role=staff", select_first=True)
print(first_staff["name"])   # 'Alice'

no_match = q.get("hits?role=contractor", select_first=True)
print(no_match is UNSET)     # True

# Default when the path is missing
total = q.get("meta.missing", default_value=0)
print(total)   # 0
```

---

## Full example with a real payload

```python
from PyperCache import Cache
from PyperCache.query.json_injester import UNSET

cache = Cache(filepath="search-cache.json")
key = "search:v1:engineering+staff"

if not cache.is_data_fresh(key):
    cache.store(
        key,
        {
            "index": "people",
            "meta": {"total_hits": 5, "page": 1},
            "hits": [
                {"id": "1", "name": "Alice", "role": "staff",  "team": {"name": "Engineering"}},
                {"id": "2", "name": "Bob",   "role": "guest",  "team": {"name": "Marketing"}},
                {"id": "3", "name": "Carol", "role": "staff",  "team": {"name": "Engineering"}},
                {"id": "4", "name": "Dave",  "role": "guest",  "team": {"name": "Sales"}},
                {"id": "5", "name": "Eve",   "role": "viewer", "team": {"name": "Engineering"}},
            ],
        },
        expiry=3600,
    )

q = cache.get(key).query

# Path navigation
print(q.get("meta.total_hits"))      # 5
print(q.has("hits"))                 # True

# Match filter
staff = q.get("hits?role=staff")
print([h["name"] for h in staff])    # ['Alice', 'Carol']

eng = q.get("hits?team.name=Engineering")
print([h["name"] for h in eng])      # ['Alice', 'Carol', 'Eve']

# Pluck
print(q.get("hits?name*"))           # ['Alice', 'Bob', 'Carol', 'Dave', 'Eve']
print(q.get("hits?team.name*"))      # ['Engineering', 'Marketing', ...]

# Exists filter
has_team = q.get("hits?team")        # all 5 dicts (each has "team")

# select_first
first_staff = q.get("hits?role=staff", select_first=True)
print(first_staff["name"])           # 'Alice'

# No match with select_first
print(q.get("hits?role=contractor", select_first=True) is UNSET)  # True
```

---

## Known limitations

**Integer indexing** — `"list.0.key"` raises `AttributeError`. Use `?key=value` (match filter) or `?key*` (pluck) to access list elements by position or value.

**Unicode / non-ASCII keys** — The grammar uses ASCII identifiers. Non-ASCII key names raise a parse error. Keys with hyphens or other special characters must be quoted: `'"my-key".subkey'`.

**List root** — Navigating a top-level list with a bare path raises `TypeError`. Use `?key*` or `?key=value` instead.

**Scope** — `record.query` operates only on the single loaded payload for that key. It does not scan multiple records, cross keys, or touch the backend.
