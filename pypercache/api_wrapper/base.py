from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict, dataclass, is_dataclass
from pathlib import Path
from typing import Any, BinaryIO, Iterator, Mapping
from urllib.parse import quote

import requests

from ..core.cache import Cache
from ..core.request_logger import RequestLogger
from ..utils.typing_cast import instantiate_type


PathLike = str | Path
_CACHE_MISS = object()


class ApiWrapperError(Exception):
    """Base exception for api_wrapper failures."""


class ApiHTTPError(ApiWrapperError):
    """Raised when an HTTP request returns a non-success status."""

    def __init__(self, status_code: int, url: str, body: Any = None) -> None:
        self.status_code = int(status_code)
        self.url = url
        self.body = body
        super().__init__(f"HTTP {self.status_code} for {self.url}")


@dataclass(frozen=True)
class SSEEvent:
    """Parsed server-sent event."""

    event: str | None = None
    data: str = ""
    id: str | None = None
    retry: int | None = None


class ApiWrapper:
    """Sync API wrapper with typed response casting and optional caching."""

    def __init__(
        self,
        *,
        origins: Mapping[str, str],
        default_origin: str,
        cache_path: str | None = None,
        default_expiry: int | float = math.inf,
        enable_cache: bool = True,
        request_log_path: str | None = None,
        timeout: int | float | None = 10,
        session: requests.Session | None = None,
    ) -> None:
        if not origins:
            raise ValueError("origins must be non-empty")
        if default_origin not in origins:
            raise ValueError(f"default_origin {default_origin!r} is not present in origins")

        self.origins = {name: url.rstrip("/") for name, url in origins.items()}
        self.default_origin = default_origin
        self.default_expiry = default_expiry
        self.enable_cache = enable_cache
        self.timeout = timeout
        self.cache = Cache(filepath=cache_path) if cache_path is not None else None
        self.request_logger = (
            RequestLogger(filepath=request_log_path)
            if request_log_path is not None
            else None
        )
        self._owns_session = session is None
        self.session = session or self.get_session()

    def get_session(self) -> requests.Session:
        """Return the requests session used for network calls."""
        return requests.Session()

    def close(self) -> None:
        """Close the owned session and flush/close cache storage when present."""
        if self.cache is not None:
            close_cache = getattr(self.cache, "close", None)
            if callable(close_cache):
                close_cache()
        if self._owns_session and hasattr(self.session, "close"):
            self.session.close()

    def request(
        self,
        method: str,
        path: str,
        *,
        params: Mapping[str, Any] | None = None,
        json_body: Any = None,
        data: Mapping[str, Any] | None = None,
        files: Mapping[str, Any] | None = None,
        expected: str = "auto",
        use_cache: bool | None = None,
        timeout: int | float | None = None,
        headers: Mapping[str, str] | None = None,
        expiry: int | float | None = None,
        cast: type[Any] | None = None,
        origin: str | None = None,
    ) -> Any:
        """Send a request and return decoded JSON, text, bytes, or None."""
        method = method.upper()
        selected_origin = self.default_origin if origin is None else origin
        url = self._url(path, origin=selected_origin)
        request_params = self._drop_none(params)
        request_json = self._jsonable(json_body)
        request_data = self._drop_none(data)
        should_cache = (
            self.enable_cache if use_cache is None else bool(use_cache)
        ) and self.cache is not None
        cache_ttl = self.default_expiry if expiry is None else expiry
        cache_key = self._cache_key(method, selected_origin, url, request_params, request_json)

        if should_cache and self._should_cache_response(method, expected):
            cached = self._get_cached_value(cache_key)
            if cached is not _CACHE_MISS:
                return self._coerce_response(cached, cast)

        response = None
        try:
            response = self.session.request(
                method,
                url,
                params=request_params,
                json=request_json,
                data=request_data,
                files=files,
                timeout=timeout if timeout is not None else self.timeout,
                headers=dict(headers) if headers is not None else None,
            )
            self._log(response.url, response.status_code)

            if response.status_code >= 400:
                raise ApiHTTPError(
                    response.status_code,
                    response.url,
                    self._error_body(response),
                )

            result = self._decode_response(response, expected)

            if (
                should_cache
                and self._should_cache_response(method, expected)
                and self._is_json_cacheable(result)
            ):
                self.cache.store(cache_key, {"value": result}, expiry=cache_ttl)

            return self._coerce_response(result, cast)
        finally:
            if files is not None:
                self._close_files(files)
            if response is not None and hasattr(response, "close"):
                response.close()

    def download_to(
        self,
        path: str,
        destination: PathLike,
        *,
        params: Mapping[str, Any] | None = None,
        use_cache: bool = False,
        timeout: int | float | None = None,
        headers: Mapping[str, str] | None = None,
        origin: str | None = None,
    ) -> Path:
        """Download a bytes response to the given destination path."""
        content = self.request(
            "GET",
            path,
            params=params,
            expected="bytes",
            use_cache=use_cache,
            timeout=timeout,
            headers=headers,
            origin=origin,
        )
        output = Path(destination)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(content)
        return output

    def stream_sse(
        self,
        path: str,
        *,
        params: Mapping[str, Any] | None = None,
        data: Mapping[str, Any] | None = None,
        timeout: int | float | None = None,
        headers: Mapping[str, str] | None = None,
        method: str = "GET",
        origin: str | None = None,
    ) -> Iterator[SSEEvent]:
        """Yield parsed server-sent events from a streaming endpoint."""
        stream_headers = {"Accept": "text/event-stream"}
        if headers is not None:
            stream_headers.update(dict(headers))

        response = self.session.request(
            method.upper(),
            self._url(path, origin=self.default_origin if origin is None else origin),
            params=self._drop_none(params),
            data=self._drop_none(data),
            timeout=timeout if timeout is not None else self.timeout,
            headers=stream_headers,
            stream=True,
        )
        self._log(response.url, response.status_code)

        if response.status_code >= 400:
            try:
                raise ApiHTTPError(
                    response.status_code,
                    response.url,
                    self._error_body(response),
                )
            finally:
                response.close()

        def _iter_events() -> Iterator[SSEEvent]:
            pending: list[str] = []
            try:
                for raw_line in response.iter_lines(decode_unicode=True):
                    line = raw_line if isinstance(raw_line, str) else raw_line.decode("utf-8")
                    if line == "":
                        event = self._parse_sse_event(pending)
                        if event is not None:
                            yield event
                        pending = []
                        continue
                    pending.append(line)

                event = self._parse_sse_event(pending)
                if event is not None:
                    yield event
            finally:
                response.close()

        return _iter_events()

    def _url(self, path: str, *, origin: str | None = None) -> str:
        if path.startswith("http://") or path.startswith("https://"):
            return path
        selected_origin = self.default_origin if origin is None else origin
        base_url = self.origins[selected_origin]
        return f"{base_url}/{path.lstrip('/')}"

    def _cache_key(
        self,
        method: str,
        origin: str | None,
        url: str,
        params: Mapping[str, Any] | None,
        json_body: Any,
    ) -> str:
        payload = {
            "wrapper": f"{self.__class__.__module__}.{self.__class__.__name__}",
            "origin": origin,
            "method": method.upper(),
            "url": url,
            "params": params,
            "json": json_body,
        }
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
        digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        origin_key = "none" if origin is None else str(origin)
        return f"api:{origin_key}:{digest}"

    def _get_cached_value(self, cache_key: str) -> Any:
        if self.cache is None or not self.cache.is_data_fresh(cache_key):
            return _CACHE_MISS
        return self.cache.get(cache_key).data.get("value")

    def _should_cache_response(self, method: str, expected: str) -> bool:
        return method == "GET" and expected in {"auto", "json"}

    def _log(self, uri: str, status: int) -> None:
        if self.request_logger is not None:
            self.request_logger.log(uri=uri, status=status)

    @staticmethod
    def _coerce_response(value: Any, cast: type[Any] | None) -> Any:
        return instantiate_type(cast, value) if cast is not None else value

    @staticmethod
    def _path_value(value: str) -> str:
        return quote(str(value), safe="")

    @staticmethod
    def _drop_none(values: Mapping[str, Any] | None) -> dict[str, Any] | None:
        if values is None:
            return None
        return {key: value for key, value in values.items() if value is not None}

    @classmethod
    def _jsonable(cls, value: Any) -> Any:
        if value is None:
            return None
        if is_dataclass(value):
            return asdict(value)
        if hasattr(value, "as_dict") and callable(getattr(value, "as_dict")):
            return cls._jsonable(value.as_dict())
        if isinstance(value, Mapping):
            return {str(key): cls._jsonable(val) for key, val in value.items()}
        if isinstance(value, (list, tuple)):
            return [cls._jsonable(item) for item in value]
        return value

    @staticmethod
    def _decode_response(response: requests.Response, expected: str) -> Any:
        if expected == "bytes":
            return response.content
        if expected == "text":
            return response.text
        if not response.content:
            return None

        content_type = response.headers.get("content-type", "")
        if expected == "json" or "application/json" in content_type:
            return response.json()
        if content_type.startswith("text/"):
            return response.text
        return response.content

    @staticmethod
    def _error_body(response: requests.Response) -> Any:
        try:
            return response.json()
        except ValueError:
            return response.text

    @classmethod
    def _is_json_cacheable(cls, value: Any) -> bool:
        if not isinstance(value, (dict, list, str, int, float, bool)) and value is not None:
            return False
        try:
            json.dumps(cls._jsonable(value))
            return True
        except (TypeError, ValueError):
            return False

    @staticmethod
    def _file_tuple(
        path: PathLike,
        content_type: str | None = None,
    ) -> tuple[str, BinaryIO, str] | tuple[str, BinaryIO]:
        file_path = Path(path)
        handle = file_path.open("rb")
        if content_type:
            return (file_path.name, handle, content_type)
        return (file_path.name, handle)

    @staticmethod
    def _close_files(files: Mapping[str, Any]) -> None:
        for value in files.values():
            handle = value[1] if isinstance(value, tuple) and len(value) > 1 else None
            if hasattr(handle, "close"):
                handle.close()

    @staticmethod
    def _parse_sse_event(lines: list[str]) -> SSEEvent | None:
        if not lines:
            return None

        event_type = None
        event_id = None
        retry = None
        data_lines: list[str] = []
        saw_field = False

        for line in lines:
            if not line or line.startswith(":"):
                continue

            field, sep, value = line.partition(":")
            if sep:
                if value.startswith(" "):
                    value = value[1:]
            else:
                value = ""

            saw_field = True
            if field == "event":
                event_type = value
            elif field == "data":
                data_lines.append(value)
            elif field == "id":
                event_id = value
            elif field == "retry":
                try:
                    retry = int(value)
                except ValueError:
                    pass

        if not saw_field:
            return None

        return SSEEvent(
            event=event_type,
            data="\n".join(data_lines),
            id=event_id,
            retry=retry,
        )
