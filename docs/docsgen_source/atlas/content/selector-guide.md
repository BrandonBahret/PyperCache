---

tag: Query layer

comment: SELECTOR GUIDE

title: Selector

title_em: "syntax"

lead: |

  All selectors are passed as strings to `q.get()`. They compose left to right — each token narrows or transforms the current cursor before passing it to the next.

breadcrumb: "pypercache / selector syntax"

---



## Reference {id=reference}

:::selector_list
### `key.key.key`
Dot-separated path navigation. Returns `UNSET{ref=json-injester#when-selectors-resolve-to-nothing}` if any key is missing.

### `"content-type"`
Quoted key — use double quotes when the key contains non-identifier characters like hyphens.

### `list?key=value`
Filter a list of dicts to elements where `key` equals `value`. Returns an empty list if nothing matches. Supports nested paths: `users?team.name=Platform`.

### `list?key=#42`
Numeric filter — prefix the value with `#` to compare as a number rather than a string.

### `list?key=value.field`
Filter then pluck: the tail path after `?key=value` is extracted from each matching element.

### `list?field*`
Pluck — extract a field from every element in the list. Supports nested paths: `users?team.name*`. Chains: `users?role*?label*`.

### `key?field`
Exists filter. On a dict: returns the dict if the key exists, `UNSET{ref=json-injester#when-selectors-resolve-to-nothing}` otherwise. On a list: returns only elements that contain the key.
:::

## get() options {id=get-options}

:::table
| Option | Behavior |
| --- | --- |
| `default_value{ref=selector-guide#get-options}` | Return this when the path is missing or resolves to `None{ref=json-injester#when-selectors-resolve-to-nothing}`. Without it, the result is `UNSET{ref=json-injester#when-selectors-resolve-to-nothing}`. |
| `select_first=True` | Unwrap the first element from a list result. Returns `UNSET{ref=json-injester#when-selectors-resolve-to-nothing}` if the list is empty. |
| `cast=Type{ref=selector-guide#get-options}` | Hydrate a dict result into a type or `@apimodel{ref=ref-apimodel#decorator}` class. |
:::

## Full example {id=full-example}

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

print(q.get("meta.total"))                               # 3
print(q.get("hits?role=staff.name"))                      # ["Alice", "Carol"]
print(q.get("hits?name*"))                                # ["Alice", "Bob", "Carol"]
print(q.get("hits?role=staff", select_first=True))        # Alice's dict
print(q.get("hits?role=contractor", select_first=True) is UNSET)  # True
```

## Limits {id=limits}

* Read-only — `JsonInjester{ref=json-injester#standalone-usage}` never mutates the payload.
* Integer indexing like `"users.0.name"` is not supported. Use `select_first=True` instead.
* A bare path on a list root is not supported. Use `?key*` or `?key=value`.
* Works on one in-memory payload at a time — no cross-record queries.
