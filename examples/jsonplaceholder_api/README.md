# JSONPlaceholder Wrapper Example

This example uses [JSONPlaceholder](https://jsonplaceholder.typicode.com/), a free fake REST API for testing and prototyping. It is intentionally lower in complexity than the other wrappers in this repository:

- one origin
- no authentication
- small, regular JSON payloads
- a few common REST resources

It demonstrates:

- subclassing `ApiWrapper` for a single-host JSON API
- using `@apimodel(validate=True)` for typed response hydration
- mapping camelCase API fields like `userId` and `catchPhrase` with `Alias(...)`
- letting `ApiWrapper.request(...)` handle caching for `GET` endpoints
- bypassing cache for a simple `POST` example

## Quick start

```bash
python examples/jsonplaceholder_api/app.py
```

## Public surface

```python
from examples.jsonplaceholder_api.jsonplaceholder_wrapper import JSONPlaceholderClient

client = JSONPlaceholderClient(cache_path="jsonplaceholder_cache.json")

post = client.get_post(1)
author = client.get_user(post.user_id)
comments = client.list_post_comments(post.id)
todo = client.get_todo(1)

created = client.create_post(
    user_id=1,
    title="Demo title",
    body="Demo body",
)
```

## Why this example is useful

The other wrappers in this repository show richer patterns like multiple origins, lazy fields, column transforms, rate limiting, and background refresh. This one keeps the teaching surface smaller:

- thin endpoint methods
- plain nested models
- field aliasing
- cacheable `GET`s vs non-cacheable `POST`s

That makes it a better starting point when you just want the simplest realistic wrapper pattern to copy.

## Upstream docs

- [JSONPlaceholder homepage](https://jsonplaceholder.typicode.com/?locale=en_us)
