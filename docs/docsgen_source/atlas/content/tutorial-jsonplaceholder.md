---

tag: Tutorials

comment: CACHE BASICS

title: Walk through a small

title_em: "API client"

lead: |

  The `examples/jsonplaceholder_api` example is the shortest end-to-end wrapper in the repository. It shows the full PyperCache workflow: define typed models, subclass `ApiWrapper{ref=ref-apiwrapper#constructor}`, let `GET` requests cache automatically, and opt out of cache for a mutating `POST`.

breadcrumb: "pypercache / jsonplaceholder walkthrough"

---



## Why this example is the right starting point

JSONPlaceholder is intentionally simple in the best possible way. There is one base URL, no authentication, and small JSON payloads with predictable structure. That makes it a good teaching surface for the core wrapper pattern without introducing concerns like OAuth, pagination cursors, or multi-origin routing.

The goal of the example is not to exercise every PyperCache feature. It is to show the smallest realistic client you can copy into a real project and then extend.

## Start with models that match the payloads you already have

The wrapper begins with a few response models. Each one is decorated with `@apimodel(validate=True){ref=ref-apimodel#decorator}`, which means incoming JSON is hydrated into typed Python objects and checked against the annotated field types during construction.

Where the upstream API uses camelCase keys, the example maps them into snake_case attributes with `Alias(...){ref=ref-apimodel#alias}`. That keeps the Python surface conventional without forcing you to rewrite the raw payload format.

```python
from typing import Annotated
from pypercache.models.apimodel import Alias, apimodel

@apimodel(validate=True)
class Post:
    user_id: Annotated[int, Alias("userId")]
    id: int
    title: str
    body: str

@apimodel(validate=True)
class Company:
    name: str
    catch_phrase: Annotated[str, Alias("catchPhrase")]
    bs: str
```

Nested response objects work the same way. The `User` model contains an `Address`, which contains a `Geo`, and hydration recursively builds those child objects for you.

## Wrap the API in thin endpoint methods

Once the models exist, the wrapper class stays small. Its constructor passes a single origin, a cache path, and a default expiry to `ApiWrapper{ref=ref-apiwrapper#constructor}`. After that, each endpoint is just a thin method around `request(){ref=ref-apiwrapper#request}`.

```python
class JSONPlaceholderClient(ApiWrapper):
    def __init__(self) -> None:
        super().__init__(
            origins={"default": "https://jsonplaceholder.typicode.com"},
            default_origin="default",
            cache_path="jsonplaceholder_cache.json",
            default_expiry=300,
            request_log_path="jsonplaceholder_requests.log",
        )

    def get_post(self, post_id: int) -> Post:
        return self.request("GET", f"/posts/{post_id}", expected="json", cast=Post)

    def list_post_comments(self, post_id: int) -> list[Comment]:
        return self.request(
            "GET",
            f"/posts/{post_id}/comments",
            expected="json",
            cast=list[Comment],
        )
```

This is the part worth internalizing: the endpoint methods describe intent, not plumbing. You name the HTTP method, path, expected response type, and the model to hydrate into. URL joining, JSON decoding, cache lookup, cache writeback, and object construction are handled underneath.

:::callout info
**Related docs:** The pieces used here are documented in [`Build with ApiWrapper` | doc:api-wrapper] for the wrapper pattern, [`Typed models` | doc:typed-models] for `@apimodel{ref=ref-apimodel#decorator}` and `Alias{ref=ref-apimodel#alias}`, and [`ApiWrapper API` | doc:ref-apiwrapper#request] for the exact `request(){ref=ref-apiwrapper#request}` signature.
:::

## Let cached GETs make the second call boring

The companion `app.py` script demonstrates the runtime behavior. It first fetches post `#1`, then immediately fetches the same post again. Because the method is a `GET` with `expected="json"{ref=ref-apiwrapper#request}`, PyperCache stores the first response and serves the second one from the cache while the entry is still fresh.

```python
client = JSONPlaceholderClient(
    cache_path="jsonplaceholder_cache.json",
    request_log_path="jsonplaceholder_requests.log",
)

post = client.get_post(1)
cached_post = client.get_post(1)

author = client.get_user(post.user_id)
comments = client.list_post_comments(post.id)
todo = client.get_todo(1)
```

That sequence is the narrative center of the example. The first request proves the wrapper can fetch and hydrate a resource. The second request proves the cache is active. The follow-up calls show that once you have a typed object back, using fields like `post.user_id` to drive the next request feels like ordinary Python code rather than manual JSON plumbing.

## Treat writes differently from reads

The example ends with a `create_post()` method. This is where the code deliberately opts out of the cache:

```python
def create_post(self, *, user_id: int, title: str, body: str) -> CreatedPost:
    return self.request(
        "POST",
        "/posts",
        expected="json",
        json_body={
            "userId": user_id,
            "title": title,
            "body": body,
        },
        use_cache=False,
        cast=CreatedPost,
    )
```

This mirrors the documented caching rule for `ApiWrapper.request(){ref=ref-apiwrapper#request}`: cached responses are for read paths, not mutating calls. The explicit `use_cache=False` makes that policy visible in the method body, which is useful both as documentation for readers and as protection if the method grows later.

JSONPlaceholder itself does not persist the new record, so the point is not durable remote state. The point is to show how request encoding with `json_body=...{ref=ref-apiwrapper#request}` and typed response hydration still work cleanly on the write path.

## What to copy into your own project

If you are starting a real client, the practical pattern is straightforward: model the responses you care about, subclass `ApiWrapper{ref=ref-apiwrapper#constructor}`, make each endpoint method one call to `request(){ref=ref-apiwrapper#request}`, and let the cache cover repeatable `GET` traffic. Add custom headers in `get_session(){ref=ref-apiwrapper#get-session}` only when the API requires them.

When the process exits, call `client.close(){ref=ref-apiwrapper#close}`. That closes the wrapper's cache cleanly. For SQLite-backed caches, it also flushes pending writes if manual flush mode was enabled.
