from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from pypercache.api_wrapper import ApiHTTPError, ApiWrapper, SSEEvent
from pypercache.models.apimodel import apimodel


class DummyResponse:
    def __init__(
        self,
        *,
        status_code: int = 200,
        url: str = "https://api.example.com/items",
        json_data: Any = None,
        text: str = "",
        content: bytes | None = None,
        headers: dict[str, str] | None = None,
        lines: list[str] | None = None,
    ) -> None:
        self.status_code = status_code
        self.url = url
        self._json_data = json_data
        self._text = text
        self.headers = headers or {}
        self._lines = lines or []
        self.closed = False

        if content is not None:
            self.content = content
        elif json_data is not None:
            import json

            self.content = json.dumps(json_data).encode("utf-8")
        else:
            self.content = text.encode("utf-8")

    @property
    def text(self) -> str:
        if self._text:
            return self._text
        return self.content.decode("utf-8")

    def json(self) -> Any:
        if self._json_data is None:
            raise ValueError("No JSON body")
        return self._json_data

    def iter_lines(self, decode_unicode: bool = False):
        for line in self._lines:
            yield line if decode_unicode else line.encode("utf-8")

    def close(self) -> None:
        self.closed = True


class DummySession:
    def __init__(self, responses: list[DummyResponse]) -> None:
        self.responses = list(responses)
        self.calls: list[dict[str, Any]] = []
        self.closed = False

    def request(self, method: str, url: str, **kwargs):
        self.calls.append({"method": method, "url": url, **kwargs})
        if not self.responses:
            raise AssertionError("No more dummy responses configured")
        return self.responses.pop(0)

    def close(self) -> None:
        self.closed = True


@apimodel
class Widget:
    id: int
    name: str


@dataclass
class Payload:
    name: str
    count: int


def make_wrapper(
    tmp_path,
    session,
    *,
    origins: dict[str, str] | None = None,
    default_origin: str = "default",
    **kwargs,
):
    return ApiWrapper(
        origins=origins or {"default": "https://api.example.com"},
        default_origin=default_origin,
        cache_path=str(tmp_path / "cache.pkl"),
        session=session,
        **kwargs,
    )


def test_get_json_response_is_cached_and_reused_while_fresh(tmp_path):
    session = DummySession(
        [
            DummyResponse(
                json_data={"id": 1, "name": "alpha"},
                headers={"content-type": "application/json"},
            )
        ]
    )
    wrapper = make_wrapper(tmp_path, session)

    first = wrapper.request("GET", "/items", expected="json")
    second = wrapper.request("GET", "/items", expected="json")

    assert first == {"id": 1, "name": "alpha"}
    assert second == {"id": 1, "name": "alpha"}
    assert len(session.calls) == 1


def test_stale_cached_get_is_refetched(tmp_path):
    session = DummySession(
        [
            DummyResponse(
                json_data={"id": 1, "name": "first"},
                headers={"content-type": "application/json"},
            ),
            DummyResponse(
                json_data={"id": 1, "name": "second"},
                headers={"content-type": "application/json"},
            ),
        ]
    )
    wrapper = make_wrapper(tmp_path, session, default_expiry=1)

    key = wrapper._cache_key("GET", "default", "https://api.example.com/items", None, None)
    assert wrapper.request("GET", "/items", expected="json") == {"id": 1, "name": "first"}

    wrapper.cache.storage.records[key]["timestamp"] = time.time() - 10
    wrapper.cache.storage.save(wrapper.cache.storage.records)

    assert wrapper.request("GET", "/items", expected="json") == {"id": 1, "name": "second"}
    assert len(session.calls) == 2


def test_post_bypasses_cache(tmp_path):
    session = DummySession(
        [
            DummyResponse(
                json_data={"ok": True},
                headers={"content-type": "application/json"},
            ),
            DummyResponse(
                json_data={"ok": True},
                headers={"content-type": "application/json"},
            ),
        ]
    )
    wrapper = make_wrapper(tmp_path, session)

    wrapper.request("POST", "/items", expected="json", json_body={"name": "x"})
    wrapper.request("POST", "/items", expected="json", json_body={"name": "x"})

    assert len(session.calls) == 2


def test_cast_model_hydrates_dict_payload(tmp_path):
    session = DummySession(
        [
            DummyResponse(
                json_data={"id": 7, "name": "gear"},
                headers={"content-type": "application/json"},
            )
        ]
    )
    wrapper = make_wrapper(tmp_path, session)

    result = wrapper.request("GET", "/items/7", expected="json", cast=Widget)

    assert isinstance(result, Widget)
    assert result.id == 7
    assert result.name == "gear"


def test_cast_list_model_hydrates_list_payload(tmp_path):
    session = DummySession(
        [
            DummyResponse(
                json_data=[{"id": 1, "name": "a"}, {"id": 2, "name": "b"}],
                headers={"content-type": "application/json"},
            )
        ]
    )
    wrapper = make_wrapper(tmp_path, session)

    result = wrapper.request("GET", "/items", expected="json", cast=list[Widget])

    assert [item.name for item in result] == ["a", "b"]


def test_expected_text_decodes_text_response(tmp_path):
    session = DummySession(
        [DummyResponse(text="hello", headers={"content-type": "text/plain"})]
    )
    wrapper = make_wrapper(tmp_path, session)

    result = wrapper.request("GET", "/hello", expected="text")

    assert result == "hello"


def test_expected_bytes_decodes_bytes_response(tmp_path):
    session = DummySession(
        [DummyResponse(content=b"\x00\x01", headers={"content-type": "application/octet-stream"})]
    )
    wrapper = make_wrapper(tmp_path, session)

    result = wrapper.request("GET", "/blob", expected="bytes")

    assert result == b"\x00\x01"


def test_empty_body_returns_none(tmp_path):
    session = DummySession(
        [DummyResponse(content=b"", headers={"content-type": "application/json"})]
    )
    wrapper = make_wrapper(tmp_path, session)

    result = wrapper.request("GET", "/empty", expected="auto")

    assert result is None


def test_http_error_raises_with_json_body(tmp_path):
    session = DummySession(
        [
            DummyResponse(
                status_code=404,
                url="https://api.example.com/missing",
                json_data={"error": "missing"},
                headers={"content-type": "application/json"},
            )
        ]
    )
    wrapper = make_wrapper(tmp_path, session)

    with pytest.raises(ApiHTTPError) as exc:
        wrapper.request("GET", "/missing", expected="json")

    assert exc.value.status_code == 404
    assert exc.value.url == "https://api.example.com/missing"
    assert exc.value.body == {"error": "missing"}


def test_http_error_raises_with_text_body(tmp_path):
    session = DummySession(
        [
            DummyResponse(
                status_code=500,
                url="https://api.example.com/fail",
                text="boom",
                headers={"content-type": "text/plain"},
            )
        ]
    )
    wrapper = make_wrapper(tmp_path, session)

    with pytest.raises(ApiHTTPError) as exc:
        wrapper.request("GET", "/fail", expected="auto")

    assert exc.value.body == "boom"


def test_download_to_writes_bytes_to_disk(tmp_path):
    session = DummySession(
        [DummyResponse(content=b"abc", headers={"content-type": "application/octet-stream"})]
    )
    wrapper = make_wrapper(tmp_path, session)
    output = tmp_path / "downloads" / "file.bin"

    result = wrapper.download_to("/file", output)

    assert result == output
    assert output.read_bytes() == b"abc"


def test_request_logging_records_url_and_status(tmp_path):
    session = DummySession(
        [
            DummyResponse(
                json_data={"ok": True},
                url="https://api.example.com/items?x=1",
                headers={"content-type": "application/json"},
            )
        ]
    )
    log_path = tmp_path / "requests.log"
    wrapper = make_wrapper(tmp_path, session, request_log_path=str(log_path))

    wrapper.request("GET", "/items", params={"x": 1}, expected="json")

    records = wrapper.request_logger.as_list()
    assert records[0]["uri"] == "https://api.example.com/items?x=1"
    assert records[0]["status"] == 200


def test_cache_key_is_stable_for_reordered_mappings_and_omits_none(tmp_path):
    wrapper = make_wrapper(tmp_path, DummySession([]))

    first = wrapper._cache_key(
        "GET",
        "default",
        "https://api.example.com/items",
        wrapper._drop_none({"b": 2, "a": 1, "skip": None}),
        wrapper._jsonable({"z": 9, "y": None, "a": 1}),
    )
    second = wrapper._cache_key(
        "GET",
        "default",
        "https://api.example.com/items",
        wrapper._drop_none({"a": 1, "b": 2}),
        wrapper._jsonable({"a": 1, "y": None, "z": 9}),
    )

    assert first == second
    assert first.startswith("api:")
    assert first.startswith("api:default:")
    assert len(first) == 76
    assert '"' not in first


def test_cache_key_uses_hashed_payload_format(tmp_path):
    wrapper = make_wrapper(
        tmp_path,
        DummySession([]),
        origins={"geocode": "https://geocoding-api.open-meteo.com/v1"},
        default_origin="geocode",
    )

    key = wrapper._cache_key(
        "GET",
        "geocode",
        "https://geocoding-api.open-meteo.com/v1/search",
        {
            "count": 1,
            "countryCode": "US",
            "format": "json",
            "language": "en",
            "name": "Phoenix",
        },
        None,
    )

    assert key.startswith("api:geocode:")
    assert key == "api:geocode:5907c79da0296e7f31b9c6b9461a67e2b9472bad2b54bddc033684e685364c41"


def test_request_closes_uploaded_file_handles(tmp_path):
    upload = tmp_path / "upload.txt"
    upload.write_text("hello")
    session = DummySession(
        [
            DummyResponse(
                json_data={"ok": True},
                headers={"content-type": "application/json"},
            )
        ]
    )
    wrapper = make_wrapper(tmp_path, session)
    file_tuple = wrapper._file_tuple(upload)

    wrapper.request("POST", "/upload", expected="json", files={"file": file_tuple})

    assert file_tuple[1].closed is True


def test_json_body_supports_dataclass_serialization(tmp_path):
    session = DummySession(
        [
            DummyResponse(
                json_data={"ok": True},
                headers={"content-type": "application/json"},
            )
        ]
    )
    wrapper = make_wrapper(tmp_path, session)

    wrapper.request("POST", "/items", expected="json", json_body=Payload(name="gear", count=2))

    assert session.calls[0]["json"] == {"name": "gear", "count": 2}


def test_close_closes_owned_session(tmp_path):
    session = DummySession([])
    wrapper = make_wrapper(tmp_path, session)

    wrapper.close()

    assert session.closed is False


def test_stream_sse_parses_single_event(tmp_path):
    response = DummyResponse(
        lines=["data: hello", ""],
        headers={"content-type": "text/event-stream"},
    )
    session = DummySession([response])
    wrapper = make_wrapper(tmp_path, session)

    events = list(wrapper.stream_sse("/stream"))

    assert events == [SSEEvent(data="hello")]
    assert session.calls[0]["stream"] is True
    assert session.calls[0]["headers"]["Accept"] == "text/event-stream"
    assert response.closed is True


def test_stream_sse_parses_multiline_data_and_fields(tmp_path):
    response = DummyResponse(
        lines=[
            "event: update",
            "id: 42",
            "retry: 1500",
            "data: first",
            "data: second",
            "",
        ],
        headers={"content-type": "text/event-stream"},
    )
    wrapper = make_wrapper(tmp_path, DummySession([response]))

    events = list(wrapper.stream_sse("/stream"))

    assert events == [SSEEvent(event="update", data="first\nsecond", id="42", retry=1500)]


def test_stream_sse_ignores_comments_and_emits_final_event_at_eof(tmp_path):
    response = DummyResponse(
        lines=[
            ": keep-alive",
            "data: one",
            "",
            ": trailing comment",
            "event: done",
            "data: final",
        ],
        headers={"content-type": "text/event-stream"},
    )
    wrapper = make_wrapper(tmp_path, DummySession([response]))

    events = list(wrapper.stream_sse("/stream"))

    assert events == [
        SSEEvent(data="one"),
        SSEEvent(event="done", data="final"),
    ]


def test_constructor_rejects_empty_origins(tmp_path):
    with pytest.raises(ValueError, match="origins must be non-empty"):
        ApiWrapper(origins={}, default_origin="default", cache_path=str(tmp_path / "cache.pkl"))


def test_constructor_rejects_missing_default_origin(tmp_path):
    with pytest.raises(ValueError, match="default_origin"):
        ApiWrapper(
            origins={"forecast": "https://api.example.com"},
            default_origin="geocode",
            cache_path=str(tmp_path / "cache.pkl"),
        )


def test_relative_path_uses_default_origin(tmp_path):
    session = DummySession(
        [DummyResponse(json_data={"ok": True}, headers={"content-type": "application/json"})]
    )
    wrapper = make_wrapper(
        tmp_path,
        session,
        origins={
            "forecast": "https://api.example.com/v1/",
            "geocode": "https://geo.example.com/v1/",
        },
        default_origin="forecast",
    )

    wrapper.request("GET", "/items", expected="json")

    assert session.calls[0]["url"] == "https://api.example.com/v1/items"


def test_explicit_origin_uses_selected_origin(tmp_path):
    session = DummySession(
        [DummyResponse(json_data={"ok": True}, headers={"content-type": "application/json"})]
    )
    wrapper = make_wrapper(
        tmp_path,
        session,
        origins={
            "forecast": "https://api.example.com/v1",
            "geocode": "https://geo.example.com/v1",
        },
        default_origin="forecast",
    )

    wrapper.request("GET", "/search", expected="json", origin="geocode")

    assert session.calls[0]["url"] == "https://geo.example.com/v1/search"


def test_absolute_urls_bypass_origin_lookup(tmp_path):
    session = DummySession(
        [DummyResponse(json_data={"ok": True}, headers={"content-type": "application/json"})]
    )
    wrapper = make_wrapper(tmp_path, session)

    wrapper.request("GET", "https://override.example.com/items", expected="json", origin="default")

    assert session.calls[0]["url"] == "https://override.example.com/items"


def test_cache_keys_differ_between_origins(tmp_path):
    wrapper = make_wrapper(
        tmp_path,
        DummySession([]),
        origins={
            "forecast": "https://api.example.com",
            "geocode": "https://geo.example.com",
        },
        default_origin="forecast",
    )

    first = wrapper._cache_key("GET", "forecast", "https://api.example.com/items", None, None)
    second = wrapper._cache_key("GET", "geocode", "https://geo.example.com/items", None, None)

    assert first != second


def test_download_to_honors_explicit_origin(tmp_path):
    session = DummySession(
        [
            DummyResponse(
                content=b"abc",
                url="https://geo.example.com/v1/file",
                headers={"content-type": "application/octet-stream"},
            )
        ]
    )
    wrapper = make_wrapper(
        tmp_path,
        session,
        origins={
            "forecast": "https://api.example.com/v1",
            "geocode": "https://geo.example.com/v1",
        },
        default_origin="forecast",
    )

    wrapper.download_to("/file", tmp_path / "file.bin", origin="geocode")

    assert session.calls[0]["url"] == "https://geo.example.com/v1/file"


def test_stream_sse_honors_explicit_origin(tmp_path):
    response = DummyResponse(
        url="https://geo.example.com/v1/stream",
        lines=["data: hello", ""],
        headers={"content-type": "text/event-stream"},
    )
    wrapper = make_wrapper(
        tmp_path,
        DummySession([response]),
        origins={
            "forecast": "https://api.example.com/v1",
            "geocode": "https://geo.example.com/v1",
        },
        default_origin="forecast",
    )

    events = list(wrapper.stream_sse("/stream", origin="geocode"))

    assert events == [SSEEvent(data="hello")]
    assert wrapper.session.calls[0]["url"] == "https://geo.example.com/v1/stream"
