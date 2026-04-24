---

tag: API clients

comment: API WRAPPER

title: Build with

title_em: "ApiWrapper"

lead: |

  The highest-level integration surface. Subclass it and your endpoint methods stay thin — URL building, caching, response decoding, and model hydration are handled for you.

breadcrumb: "pypercache / apiwrapper"

---



## Basic subclass pattern

Override `get_session(){ref=ref-apiwrapper#get-session}` to set headers or auth, then add one method per endpoint.

```python
from typing import Annotated
from pypercache.api_wrapper import ApiWrapper
from pypercache.models.apimodel import Alias, apimodel

@apimodel(validate=True)
class Widget:
    id: int
    display_name: Annotated[str, Alias("displayName")]

class WidgetClient(ApiWrapper):
    def __init__(self) -> None:
        super().__init__(
            origins={"default": "https://api.example.com"},
            default_origin="default",
            cache_path="widget_cache.json",
            default_expiry=300,
        )

    def get_session(self):
        session = super().get_session()
        session.headers.update({"User-Agent": "widget-client/1.0"})
        return session

    def list_widgets(self) -> list[Widget]:
        return self.request("GET", "/widgets", expected="json", cast=list[Widget])

    def get_widget(self, widget_id: int) -> Widget:
        return self.request("GET", f"/widgets/{widget_id}", expected="json", cast=Widget)

    def create_widget(self, name: str) -> Widget:
        return self.request(
            "POST", "/widgets",
            expected="json",
            json_body={"name": name},
            use_cache=False,
            cast=Widget,
        )
```

## Constructor

```python
super().__init__(
    origins={"api": "https://api.example.com"},
    default_origin="api",
    cache_path="example.db",      # None disables caching
    default_expiry=300,
    request_log_path="reqs.log",  # None disables logging
    timeout=10,
)
```

## Multi-origin APIs

When your API spans multiple hosts, add each as an origin and select it per request with `origin=`.

```python
super().__init__(
    origins={
        "api": "https://api.example.com",
        "auth": "https://auth.example.com",
    },
    default_origin="api",
)

# In an endpoint method:
return self.request("GET", "/token", origin="auth", ...)
```

## Caching rules

The behavior is intentionally simple: only `GET` requests with `expected="auto"{ref=ref-apiwrapper#request}` or `expected="json"{ref=ref-apiwrapper#request}` are cached. Stale entries are refetched, not served. Pass `use_cache=False` to skip both lookup and writeback — always do this for `POST`, `PUT`, and `DELETE` requests.

## Error handling

```python
from pypercache.api_wrapper import ApiHTTPError

try:
    client.get_widget(404)
except ApiHTTPError as exc:
    print(exc.status_code)
    print(exc.url)
    print(exc.body)
```

## Lifecycle

```python
client = WidgetClient()
try:
    widgets = client.list_widgets()
finally:
    client.close()  # closes cache + session
```
