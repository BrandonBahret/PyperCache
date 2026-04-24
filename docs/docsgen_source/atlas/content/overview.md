---

tag: Getting started

comment: OVERVIEW

title: PyperCache

title_em: "."

lead: |

  A durable, file-backed cache for JSON-like Python data — with optional typed hydration, a query layer for navigating nested payloads, and an `ApiWrapper{ref=ref-apiwrapper#constructor}` base class for building HTTP clients.

breadcrumb: "pypercache / introduction"

---

## Installation

Install from [PyPI:](https://pypi.org/project/pypercache/)

```bash
pip install pypercache
```

Or install from source:

```bash
git clone https://github.com/BrandonBahret/PyperCache.git
cd PyperCache
pip install .
```

:::feature_grid
### Persistent storage {icon=💾}
Pickle, JSON, SQLite, or chunked backends
### TTL freshness {icon=⏱}
Per-record expiry with `is_data_fresh(){ref=ref-cache#is-data-fresh}`
### JsonInjester {icon=🔍}
Dot-path selector language for nested dicts
### Typed hydration {icon=🏷}
`@apimodel{ref=ref-apimodel#decorator}` for aliases, timestamps, lazy fields
### ApiWrapper {icon=🌐}
HTTP client base class with built-in cache integration
### Request logging {icon=📋}
JSONL audit records via `RequestLogger{ref=ref-storage#request-logger}`
:::

## How the pieces fit together

At the center is `Cache{ref=ref-cache#cache}`, which stores keyed records to disk and hands back `CacheRecord{ref=ref-cache#cache-record}` objects. Each record exposes a `.query{ref=ref-cache#attributes}` property — a `JsonInjester{ref=json-injester#standalone-usage}` over the stored payload — so you can navigate the data without writing chains of `dict.get()` calls.

`@apimodel{ref=ref-apimodel#decorator}` sits on top of that: decorate a class and it gains a dict-accepting constructor, automatic nested hydration, field aliases, timestamp parsing, and lazy fields. You pass a model as `cast=MyModel` when storing, then retrieve a fully typed object via `cache.get_object(){ref=ref-cache#get-object}`.

`ApiWrapper{ref=ref-apiwrapper#constructor}` composes everything — `requests`, `Cache{ref=ref-cache#cache}`, and optionally `RequestLogger{ref=ref-storage#request-logger}` — into a base class. Subclass it, add thin endpoint methods, and you have an HTTP client that caches `GET` responses and hydrates them automatically.

```python
from pypercache import Cache, RequestLogger
from pypercache.api_wrapper import ApiWrapper
from pypercache.models.apimodel import Alias, Columns, Lazy, Timestamp, apimodel
from pypercache.query import JsonInjester
```

## Choose your starting point

:::cards
### Just the cache {link=cache-basics}
Persist data between runs, check staleness, optionally hydrate into typed objects. No HTTP involved.
### Building an API client {link=api-wrapper}
Subclass `ApiWrapper{ref=ref-apiwrapper#constructor}` for HTTP clients with automatic GET caching and typed response models.
### Just the query layer {link=json-injester}
Use `JsonInjester{ref=json-injester#standalone-usage}` standalone to navigate large nested payloads without repetitive dict access.
### Custom integration {link=building-blocks}
Bring your own HTTP transport and compose `Cache{ref=ref-cache#cache}`, `@apimodel{ref=ref-apimodel#decorator}`, and `JsonInjester{ref=json-injester#standalone-usage}` yourself.
:::
