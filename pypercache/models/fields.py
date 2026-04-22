"""Field metadata helpers for ``@apimodel`` annotations."""
from __future__ import annotations

from datetime import datetime, timezone, tzinfo
from typing import Any

from ..utils.sentinel import UNSET


class Alias:
    """Read a model field from a different key in the raw input dict.

    Use inside ``typing.Annotated`` for eager or lazy fields::

        display_name: Annotated[str, Alias("name")]
        profile: Lazy[Annotated[Profile, Alias("user.profile")]]
    """

    def __init__(self, key: str) -> None:
        self.key = key

    def __repr__(self) -> str:  # pragma: no cover
        return f"Alias({self.key!r})"


class Columns:
    """Project a dict-of-arrays payload into ``list[RowModel]`` fields.

    Use inside ``typing.Annotated`` for eager or lazy fields::

        hourly: Annotated[list[HourlyPoint], Columns()]
        daily: Lazy[Annotated[list[DailyPoint], Columns(required=("time",))]]
    """

    def __init__(self, required: tuple[str, ...] = ()) -> None:
        self.required = required

    def __repr__(self) -> str:  # pragma: no cover
        return f"Columns(required={self.required!r})"


class Timestamp:
    """Parse raw API timestamps into ``datetime`` fields.

    Use inside ``typing.Annotated`` for eager or lazy fields::

        created_at: Annotated[datetime, Timestamp()]
        updated_at: Annotated[datetime, Timestamp("%Y-%m-%d %H:%M:%S")]
        seen_at: Lazy[Annotated[datetime, Alias("seen"), Timestamp(unit="ms")]]

    Without a format string, ISO 8601 strings and numeric Unix timestamps are
    supported.  Numeric timestamps default to seconds; use ``unit="ms"`` or
    ``unit="milliseconds"`` for millisecond payloads.
    """

    _UNIT_FACTORS = {
        "s": 1,
        "sec": 1,
        "second": 1,
        "seconds": 1,
        "ms": 1000,
        "millisecond": 1000,
        "milliseconds": 1000,
    }

    def __init__(
        self,
        fmt: str | None = None,
        *,
        unit: str = "seconds",
        tz: tzinfo | None = timezone.utc,
    ) -> None:
        unit = unit.lower()
        if unit not in self._UNIT_FACTORS:
            allowed = ", ".join(sorted(self._UNIT_FACTORS))
            raise ValueError(f"unsupported timestamp unit {unit!r}; expected one of {allowed}")

        self.fmt = fmt
        self.unit = unit
        self.tz = tz

    def parse(self, value: Any) -> Any:
        """Return ``value`` as a ``datetime`` when it can be parsed."""
        if value is UNSET or value is None or isinstance(value, datetime):
            return value

        if isinstance(value, (int, float)):
            return datetime.fromtimestamp(value / self._UNIT_FACTORS[self.unit], tz=self.tz)

        if isinstance(value, str):
            text = value.strip()

            if self.fmt is not None:
                parsed = datetime.strptime(text, self.fmt)
                if parsed.tzinfo is None and self.tz is not None:
                    return parsed.replace(tzinfo=self.tz)
                return parsed

            try:
                numeric = float(text)
            except ValueError:
                numeric = None

            if numeric is not None:
                return datetime.fromtimestamp(numeric / self._UNIT_FACTORS[self.unit], tz=self.tz)

            if text.endswith("Z"):
                text = text[:-1] + "+00:00"
            return datetime.fromisoformat(text)

        raise TypeError(f"cannot parse {type(value).__name__} as a timestamp")

    def serialize(self, value: Any) -> Any:
        """Return a raw API value for an assigned ``datetime``."""
        if value is UNSET or value is None or isinstance(value, str):
            return value

        if isinstance(value, datetime):
            if self.fmt is not None:
                return value.strftime(self.fmt)
            return value.isoformat()

        return value

    def __repr__(self) -> str:  # pragma: no cover
        args = []
        if self.fmt is not None:
            args.append(repr(self.fmt))
        if self.unit != "seconds":
            args.append(f"unit={self.unit!r}")
        if self.tz is not timezone.utc:
            args.append(f"tz={self.tz!r}")
        return f"Timestamp({', '.join(args)})"
