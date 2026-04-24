---

tag: Reference

comment: "REF: APIWRAPPER"

title: ApiWrapper

title_em: "API"

lead: |

  Exact signatures for `ApiWrapper{ref=ref-apiwrapper#constructor}`, `ApiHTTPError{ref=ref-apiwrapper#api-http-error}`, and `SSEEvent{ref=ref-apiwrapper#sse-event}`.

breadcrumb: "pypercache / apiwrapper api"

---



```python
from pypercache.api_wrapper import ApiHTTPError, ApiWrapper, ApiWrapperError, SSEEvent
```

## Constructor {id=constructor}

:::method
ApiWrapper(*, origins: Mapping[str, str], default_origin: str, cache_path: str | None = None, default_expiry: int | float = math.inf, enable_cache: bool = True, request_log_path: str | None = None, timeout: int | float | None = 10, session: requests.Session | None = None,)
:::

## Methods {id=methods}

### get_session {id=get-session}

:::method
client.get_session() → requests.Session
:::

Override to centralize headers, auth, retries, or adapters.

### request {id=request}

:::method
client.request(method, path, *, params=None, json_body=None, data=None, files=None, expected="auto", use_cache=None, timeout=None, headers=None, expiry=None, cast=None, origin=None,)
:::

* `expected{ref=ref-apiwrapper#request}`: `"auto"{ref=ref-apiwrapper#request}`, `"json"{ref=ref-apiwrapper#request}`, `"text"{ref=ref-apiwrapper#request}`, or `"bytes"{ref=ref-apiwrapper#request}`
* Only `GET` requests with `expected="auto"{ref=ref-apiwrapper#request}` or `"json"{ref=ref-apiwrapper#request}` are cached
* Raises `ApiHTTPError{ref=ref-apiwrapper#api-http-error}` on HTTP 4xx/5xx

### download_to {id=download-to}

:::method
client.download_to(path, destination, *, params=None, use_cache=False, timeout=None, headers=None, origin=None)
:::

Downloads a bytes response and writes it to `destination{ref=ref-apiwrapper#download-to}`.

### stream_sse {id=stream-sse}

:::method
client.stream_sse(path, *, params=None, data=None, timeout=None, headers=None, method="GET", origin=None) → Iterator[SSEEvent]
:::

Parses a Server-Sent Events stream into `SSEEvent{ref=ref-apiwrapper#sse-event}` objects. Does not reconnect automatically.

### close {id=close}

:::method
client.close()
:::

Closes the cache and, if the wrapper created the session, the session too.

---

## ApiHTTPError {id=api-http-error}

Raised on HTTP 4xx and 5xx responses.

:::table
| Attribute | Description |
| --- | --- |
| status_code | HTTP status code as an integer. |
| url | The request URL. |
| body | The response body. |
:::

## SSEEvent {id=sse-event}

Frozen dataclass with fields: `event{ref=ref-apiwrapper#sse-event}`, `data{ref=ref-apiwrapper#sse-event}`, `id{ref=ref-apiwrapper#sse-event}`, `retry{ref=ref-apiwrapper#sse-event}`.
