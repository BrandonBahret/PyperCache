from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated

import pytest

from pypercache.models.apimodel import Alias, Columns, Lazy, Timestamp, apimodel
from pypercache.models.validation import ApiModelValidationError


@apimodel(validate=True)
class HourlyPoint:
    time: Annotated[datetime, Timestamp(unit="seconds")]
    temperature_c: Annotated[float, Alias("temperature_2m")]
    weather_code: int


def test_eager_columns_hydrates_into_row_models():
    @apimodel(validate=True)
    class Forecast:
        hourly: Annotated[list[HourlyPoint], Columns(required=("time", "temperature_2m"))]

    forecast = Forecast(
        {
            "hourly": {
                "time": [1710000000, 1710003600],
                "temperature_2m": [20.5, 21.0],
                "weather_code": [1, 2],
            }
        }
    )

    assert [point.temperature_c for point in forecast.hourly] == [20.5, 21.0]
    assert forecast.hourly[0].time == datetime.fromtimestamp(1710000000, tz=timezone.utc)


def test_lazy_columns_hydrates_on_first_access_and_caches():
    @apimodel(validate=True)
    class Forecast:
        hourly: Lazy[Annotated[list[HourlyPoint], Columns(required=("time", "temperature_2m"))]]

    forecast = Forecast(
        {
            "hourly": {
                "time": [1710000000],
                "temperature_2m": [20.5],
                "weather_code": [1],
            }
        }
    )

    first = forecast.hourly
    second = forecast.hourly

    assert len(first) == 1
    assert first is second


def test_validate_true_accepts_valid_column_payload():
    @apimodel(validate=True)
    class Forecast:
        hourly: Annotated[list[HourlyPoint], Columns(required=("time",))]

    forecast = Forecast(
        {
            "hourly": {
                "time": [1710000000],
                "temperature_2m": [20.5],
                "weather_code": [1],
            }
        }
    )

    assert forecast.hourly[0].weather_code == 1


def test_strict_true_still_enforces_source_field_presence():
    @apimodel(validate=True, strict=True)
    class Forecast:
        hourly: Annotated[list[HourlyPoint], Columns(required=("time",))]

    with pytest.raises(ApiModelValidationError, match="Forecast\\.hourly is UNSET"):
        Forecast({})


def test_missing_required_column_raises():
    @apimodel(validate=True)
    class Forecast:
        hourly: Annotated[list[HourlyPoint], Columns(required=("time", "temperature_2m"))]

    with pytest.raises(ApiModelValidationError, match="missing required column 'temperature_2m'"):
        Forecast({"hourly": {"time": [1710000000], "weather_code": [1]}})


def test_mismatched_column_lengths_raise():
    @apimodel(validate=True)
    class Forecast:
        hourly: Annotated[list[HourlyPoint], Columns()]

    with pytest.raises(ApiModelValidationError, match="column lengths differ"):
        Forecast({"hourly": {"time": [1710000000], "temperature_2m": [20.5, 21.0]}})


def test_non_list_values_inside_columns_payload_raise():
    @apimodel(validate=True)
    class Forecast:
        hourly: Annotated[list[HourlyPoint], Columns()]

    with pytest.raises(ApiModelValidationError, match="expected list values"):
        Forecast({"hourly": {"time": "1710000000", "temperature_2m": [20.5]}})


def test_assignment_of_row_models_reserializes_to_columns():
    @apimodel(validate=True)
    class Forecast:
        hourly: Annotated[list[HourlyPoint], Columns()]

    forecast = Forecast({"hourly": {"time": [1710000000], "temperature_2m": [20.5], "weather_code": [1]}})
    forecast.hourly = [
        HourlyPoint.from_dict({"time": 1710007200, "temperature_2m": 22.5, "weather_code": 3})
    ]

    assert forecast.as_dict()["hourly"] == {
        "time": [1710007200],
        "temperature_2m": [22.5],
        "weather_code": [3],
    }


def test_assignment_of_row_dicts_reserializes_to_columns():
    @apimodel(validate=True)
    class Forecast:
        hourly: Annotated[list[HourlyPoint], Columns()]

    forecast = Forecast({"hourly": {"time": [1710000000], "temperature_2m": [20.5], "weather_code": [1]}})
    forecast.hourly = [{"time": 1710010800, "temperature_2m": 24.0, "weather_code": 5}]

    assert forecast.hourly[0].temperature_c == 24.0
    assert forecast.as_dict()["hourly"] == {
        "time": [1710010800],
        "temperature_2m": [24.0],
        "weather_code": [5],
    }


def test_as_dict_returns_raw_column_payload_after_assignment():
    @apimodel(validate=True)
    class Forecast:
        hourly: Annotated[list[HourlyPoint], Columns()]

    forecast = Forecast({"hourly": {"time": [1710000000], "temperature_2m": [20.5], "weather_code": [1]}})
    forecast.hourly = [{"time": 1710010800, "temperature_2m": 24.0, "weather_code": 5}]

    assert isinstance(forecast.as_dict()["hourly"], dict)
    assert forecast.as_dict()["hourly"]["temperature_2m"] == [24.0]


def test_alias_works_with_columns():
    @apimodel(validate=True)
    class Forecast:
        points: Annotated[list[HourlyPoint], Alias("hourly"), Columns(required=("time",))]

    forecast = Forecast({"hourly": {"time": [1710000000], "temperature_2m": [20.5], "weather_code": [1]}})

    assert forecast.points[0].temperature_c == 20.5


def test_timestamp_applies_element_wise_to_plain_lists():
    @apimodel(validate=True)
    class Model:
        times: Annotated[list[datetime], Timestamp(unit="seconds")]

    model = Model({"times": [1710000000, 1710003600]})

    assert model.times == [
        datetime.fromtimestamp(1710000000, tz=timezone.utc),
        datetime.fromtimestamp(1710003600, tz=timezone.utc),
    ]


def test_lazy_timestamp_applies_element_wise_to_plain_lists():
    @apimodel(validate=True)
    class Model:
        times: Lazy[Annotated[list[datetime], Timestamp(unit="seconds")]]

    model = Model({"times": [1710000000, 1710003600]})

    assert model.times == [
        datetime.fromtimestamp(1710000000, tz=timezone.utc),
        datetime.fromtimestamp(1710003600, tz=timezone.utc),
    ]
