# PyperCache Docs

PyperCache is a durable, file-backed cache for JSON-like Python data.

## Installation

Install from PyPI:

```bash
pip install pypercache
```

Or install from source:

```bash
git clone https://github.com/BrandonBahret/PyperCache.git
cd PyperCache
pip install .
```

It gives you:

- persistent storage
- TTL-based freshness checks
- optional typed hydration for cached payloads
- JSON structure navigation with `JsonInjester`
- optional request logging
- api-wrapper base template

## How the pieces fit together

At the center is `Cache`, which stores keyed records to disk and returns `CacheRecord` objects. Each record exposes `.query`, which gives you a `JsonInjester` over the loaded payload so you can navigate nested data without writing long chains of `dict.get(...)` calls.

`@apimodel` sits on top of that. Decorate a class and it gains a dict-accepting constructor, nested hydration, aliases, timestamp parsing, and lazy fields. Store with `cast=MyModel`, then retrieve a typed object later with `cache.get_object()`.

`ApiWrapper` composes `requests`, `Cache`, and optionally `RequestLogger` into a higher-level base class for HTTP clients. Subclass it, add thin endpoint methods, and let the wrapper handle URL joining, cache lookup, response decoding, and model hydration.

```python
from pypercache import Cache, RequestLogger
from pypercache.api_wrapper import ApiWrapper
from pypercache.models.apimodel import Alias, Columns, Lazy, Timestamp, apimodel
from pypercache.query import JsonInjester
```

## Choose your starting point

### 1. I am building an API client

Use this when your project is request/response oriented and you want caching plus typed responses without repeating the same fetch-or-cache code in every method.

- [API builders overview](./api-builders/README.md)
- [Build with `ApiWrapper`](./api-builders/using-api-wrapper.md)
- [Build from the lower-level pieces](./api-builders/using-building-blocks.md)
- [Typed models with `@apimodel`](./api-builders/typed-models.md)

### 2. I just want a durable cache

Use this when you want to persist data between runs, check staleness, and optionally hydrate records into typed Python objects. No HTTP layer required.

- [Cache users overview](./cache-users/README.md)
- [Serialize and retrieve data](./cache-users/serialize-your-data.md)
- [Choose a storage backend](./cache-users/storage-backends.md)

### 3. I just want the JSON query layer

Use this when your data is already loaded and you only need a small read-only selector language for nested dicts and lists.

- [JsonInjester users overview](./json-injester-users/README.md)
- [Selector guide](./json-injester-users/selector-guide.md)

### 4. I want custom integration

Use this when you already have your own transport or orchestration layer and only want selected PyperCache pieces like `Cache`, `@apimodel`, `JsonInjester`, or `RequestLogger`.

- [Build from the lower-level pieces](./api-builders/using-building-blocks.md)

## Shared examples

If you prefer to learn from code first:

- [`examples/jsonplaceholder_api`](../examples/jsonplaceholder_api/README.md) is the smallest realistic `ApiWrapper` example.
- [`examples/news_api`](../examples/news_api/README.md) shows API-key authentication, typed article models, and cacheable search endpoints.
- [`examples/weather_api`](../examples/weather_api/README.md) shows multi-origin wrappers, aliases, timestamps, column transforms, and lazy fields.

## Reference

When you need exact signatures instead of tutorials:

- [Reference index](./reference/README.md)
