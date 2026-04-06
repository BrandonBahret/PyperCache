"""Tests for PyperCache.query.json_injester: JsonInjester."""

import json
import pytest
from PyperCache.query.json_injester import JsonInjester, UNSET


SAMPLE = {
    "users": [
        {"id": "1", "name": "Alice", "role": "admin", "address": {"city": "NYC"}},
        {"id": "2", "name": "Bob",   "role": "user",  "address": {"city": "LA"}},
        {"id": "3", "name": "Carol", "role": "admin", "address": {"city": "NYC"}},
    ],
    "meta": {
        "total": 3,
        "page": 1,
    },
}


# ---------------------------------------------------------------------------
# Basic navigation
# ---------------------------------------------------------------------------

class TestBasicNavigation:

    def test_top_level_key(self):
        ji = JsonInjester(SAMPLE)
        assert ji.get("meta").get("total") == 3

    def test_nested_dotted_path(self):
        ji = JsonInjester(SAMPLE)
        assert ji.get("meta.total") == 3

    def test_missing_key_returns_unset(self):
        ji = JsonInjester(SAMPLE)
        assert ji.get("meta.nonexistent") is UNSET

    def test_missing_key_with_default(self):
        ji = JsonInjester(SAMPLE)
        assert ji.get("meta.nonexistent", default_value=0) == 0

    def test_missing_intermediate_key_returns_unset(self):
        # A missing key partway through a path should not raise, just return UNSET.
        ji = JsonInjester(SAMPLE)
        assert ji.get("meta.ghost.nested") is UNSET

    def test_has_existing_key(self):
        ji = JsonInjester(SAMPLE)
        assert ji.has("meta.total")

    def test_has_missing_key(self):
        ji = JsonInjester(SAMPLE)
        assert not ji.has("meta.ghost")

    def test_root_parameter_shifts_cursor(self):
        ji = JsonInjester(SAMPLE, root="meta")
        assert ji.get("total") == 3
        assert ji.get("page") == 1

    def test_json_string_input(self):
        ji = JsonInjester(json.dumps(SAMPLE))
        assert ji.get("meta.total") == 3

    def test_get_returns_list(self):
        ji = JsonInjester(SAMPLE)
        result = ji.get("users")
        assert isinstance(result, list)
        assert len(result) == 3

    def test_get_returns_nested_dict(self):
        # Navigate to a filtered result (list of matched dicts), then navigate
        # into the "address" key of each via a tail.
        ji = JsonInjester(SAMPLE)
        result = ji.get("users?id=1.address")
        assert result == [{"city": "NYC"}]

    def test_integer_index_navigation_not_supported(self):
        # _move_cursor only handles dict navigation; integer list indexing via dotted path
        # (e.g. "users.0.name") is NOT supported and raises AttributeError.
        # Use ?key* pluck or ?key=value filter to access list elements instead.
        ji = JsonInjester(SAMPLE)
        with pytest.raises(AttributeError, match="got 'list'"):
            ji.get("users.0.name")

    def test_default_value_zero_is_returned(self):
        # Ensure falsy default values like 0 and "" are returned correctly.
        ji = JsonInjester(SAMPLE)
        assert ji.get("meta.missing", default_value=0) == 0
        assert ji.get("meta.missing", default_value="") == ""
        assert ji.get("meta.missing", default_value=False) is False


# ---------------------------------------------------------------------------
# Filtering  (?key=value  →  JIMatch)
# ---------------------------------------------------------------------------

class TestFiltering:

    def test_filter_list_by_field(self):
        ji = JsonInjester(SAMPLE)
        admins = ji.get("users?role=admin")
        assert len(admins) == 2
        assert all(u["role"] == "admin" for u in admins)

    def test_filter_returns_empty_list_when_no_match(self):
        ji = JsonInjester(SAMPLE)
        result = ji.get("users?role=superuser")
        assert result == []

    def test_filter_on_nested_field(self):
        ji = JsonInjester(SAMPLE)
        nyc_users = ji.get("users?address.city=NYC")
        assert len(nyc_users) == 2

    def test_filter_preserves_full_record(self):
        ji = JsonInjester(SAMPLE)
        admins = ji.get("users?role=admin")
        names = {u["name"] for u in admins}
        assert names == {"Alice", "Carol"}

    def test_filter_single_match(self):
        ji = JsonInjester(SAMPLE)
        result = ji.get("users?role=user")
        assert len(result) == 1
        assert result[0]["name"] == "Bob"

    def test_filter_result_is_list_even_for_one_match(self):
        ji = JsonInjester(SAMPLE)
        result = ji.get("users?role=user")
        assert isinstance(result, list)

    def test_filter_on_dict_of_dicts(self):
        # _apply_filter on a dict-of-dicts returns (key, value) tuples for matches.
        data = {
            "services": {
                "auth":    {"type": "internal", "port": 8080},
                "gateway": {"type": "external", "port": 443},
                "jobs":    {"type": "internal", "port": 8081},
            }
        }
        ji = JsonInjester(data)
        result = ji.get("services?type=internal")
        assert len(result) == 2
        keys = {item[0] for item in result}
        assert keys == {"auth", "jobs"}

    def test_filter_followed_by_tail_plucks_field(self):
        # A tail path after a filter plucks from each matched dict.
        ji = JsonInjester(SAMPLE)
        names = ji.get("users?role=admin.name")
        assert set(names) == {"Alice", "Carol"}

    def test_filter_numeric_match_value(self):
        # match_value supports #number literals for numeric equality.
        data = {"items": [{"id": 1, "val": 10}, {"id": 2, "val": 20}, {"id": 3, "val": 10}]}
        ji = JsonInjester(data)
        result = ji.get("items?val=#10")
        assert len(result) == 2
        assert all(item["val"] == 10 for item in result)

    def test_filter_numeric_float_match_value(self):
        data = {"readings": [{"sensor": "A", "temp": 98.6}, {"sensor": "B", "temp": 37.0}]}
        ji = JsonInjester(data)
        result = ji.get("readings?temp=#98.6")
        assert len(result) == 1
        assert result[0]["sensor"] == "A"


# ---------------------------------------------------------------------------
# Exists filter  (?key  →  JIExistsFilter)
# ---------------------------------------------------------------------------

class TestExistsFilter:
    """?key checks for presence; it does NOT extract values.

    On a dict cursor: returns the cursor unchanged if the key exists, UNSET otherwise.
    On a list cursor: returns only the *elements* that contain the key.
    """

    def test_exists_on_dict_returns_cursor_when_key_present(self):
        ji = JsonInjester(SAMPLE)
        # "meta?total" — meta is a dict and "total" exists, so the cursor (meta dict) is returned.
        result = ji.get("meta?total")
        assert result == {"total": 3, "page": 1}

    def test_exists_on_dict_returns_default_when_key_absent(self):
        ji = JsonInjester(SAMPLE)
        result = ji.get("meta?ghost", default_value="nope")
        assert result == "nope"

    def test_exists_on_dict_returns_unset_when_key_absent_no_default(self):
        ji = JsonInjester(SAMPLE)
        assert ji.get("meta?ghost") is UNSET

    def test_exists_on_list_filters_elements_containing_key(self):
        # Elements that have "role" are returned; the list itself is returned, not the values.
        data = {"items": [{"a": 1}, {"b": 2}, {"a": 3}]}
        ji = JsonInjester(data)
        result = ji.get("items?a")
        assert result == [{"a": 1}, {"a": 3}]

    def test_exists_on_list_all_elements_match(self):
        ji = JsonInjester(SAMPLE)
        result = ji.get("users?role")
        assert len(result) == 3
        assert all(isinstance(u, dict) for u in result)

    def test_exists_on_list_no_elements_match(self):
        ji = JsonInjester(SAMPLE)
        result = ji.get("users?nonexistent_key")
        assert result == []

    def test_exists_on_scalar_returns_unset(self):
        data = {"count": 42}
        ji = JsonInjester(data)
        assert ji.get("count?anything") is UNSET


# ---------------------------------------------------------------------------
# Pluck  (?key*  →  JIPluck)
# ---------------------------------------------------------------------------

class TestPluck:
    """?key* extracts values: navigates on a dict, collects from a list."""

    def test_pluck_from_dict_returns_value(self):
        ji = JsonInjester(SAMPLE)
        assert ji.get("meta?total*") == 3

    def test_pluck_from_dict_missing_key_returns_unset(self):
        ji = JsonInjester(SAMPLE)
        assert ji.get("meta?ghost*") is UNSET

    def test_pluck_from_dict_missing_key_with_default(self):
        ji = JsonInjester(SAMPLE)
        assert ji.get("meta?ghost*", default_value="nope") == "nope"

    def test_pluck_from_list_collects_values(self):
        ji = JsonInjester(SAMPLE)
        names = ji.get("users?name*")
        assert names == ["Alice", "Bob", "Carol"]

    def test_pluck_from_list_skips_missing(self):
        data = {"items": [{"a": 1}, {"b": 2}, {"a": 3}]}
        ji = JsonInjester(data)
        result = ji.get("items?a*")
        assert result == [1, 3]

    def test_pluck_nested_key_from_list(self):
        ji = JsonInjester(SAMPLE)
        cities = ji.get("users?address.city*")
        assert cities == ["NYC", "LA", "NYC"]

    def test_chained_pluck(self):
        # ?role* plucks roles (dicts), then ?label* plucks "label" from each.
        data = {
            "users": [
                {"name": "Alice", "role": {"label": "Admin", "level": 3}},
                {"name": "Bob",   "role": {"label": "User",  "level": 1}},
                {"name": "Carol"},  # no role — skipped by first pluck
            ]
        }
        ji = JsonInjester(data)
        labels = ji.get("users?role*?label*")
        assert labels == ["Admin", "User"]

    def test_pluck_on_scalar_returns_unset(self):
        data = {"count": 42}
        ji = JsonInjester(data)
        assert ji.get("count?anything*") is UNSET


# ---------------------------------------------------------------------------
# Tail selector (path after a match/exists/pluck expression)
# ---------------------------------------------------------------------------

class TestTailSelector:

    def test_tail_after_filter_plucks_field(self):
        ji = JsonInjester(SAMPLE)
        ids = ji.get("users?role=admin.id")
        assert set(ids) == {"1", "3"}

    def test_tail_navigates_nested_field_after_filter(self):
        ji = JsonInjester(SAMPLE)
        cities = ji.get("users?role=admin.address.city")
        assert cities == ["NYC", "NYC"]


# ---------------------------------------------------------------------------
# select_first parameter
# ---------------------------------------------------------------------------

class TestSelectFirst:

    def test_select_first_returns_first_element_of_list(self):
        ji = JsonInjester(SAMPLE)
        result = ji.get("users?role=admin", select_first=True)
        assert result["name"] == "Alice"

    def test_select_first_on_empty_list_returns_unset(self):
        ji = JsonInjester(SAMPLE)
        result = ji.get("users?role=superuser", select_first=True)
        assert result is UNSET

    def test_select_first_false_returns_full_list(self):
        ji = JsonInjester(SAMPLE)
        result = ji.get("users?role=admin", select_first=False)
        assert isinstance(result, list)
        assert len(result) == 2

    def test_select_first_on_scalar_is_noop(self):
        # select_first only acts on lists; scalars pass through unchanged.
        ji = JsonInjester(SAMPLE)
        result = ji.get("meta.total", select_first=True)
        assert result == 3


# ---------------------------------------------------------------------------
# Type casting
# ---------------------------------------------------------------------------

class TestTypeCasting:

    def test_cast_dict_to_dataclass_style(self):
        class Meta:
            def __init__(self, data: dict):
                self.__dict__.update(data)

        ji = JsonInjester(SAMPLE)
        meta = ji.get("meta", cast=Meta)
        assert isinstance(meta, Meta)
        assert meta.total == 3

    def test_cast_only_applied_to_dict(self):
        # cast is a no-op when the result is a list or scalar.
        class Dummy:
            def __init__(self, data):
                self.data = data

        ji = JsonInjester(SAMPLE)
        result = ji.get("users", cast=Dummy)
        assert isinstance(result, list)

    def test_no_cast_returns_raw(self):
        ji = JsonInjester(SAMPLE)
        result = ji.get("meta")
        assert isinstance(result, dict)

    def test_cast_with_named_tuple(self):
        from typing import NamedTuple

        class Meta(NamedTuple):
            total: int
            page: int

        ji = JsonInjester(SAMPLE)
        meta = ji.get("meta", cast=lambda d: Meta(**d))
        assert meta.total == 3
        assert meta.page == 1


# ---------------------------------------------------------------------------
# default_tail
# ---------------------------------------------------------------------------

class TestDefaultTail:

    def test_default_tail_applied_to_dict_result(self):
        ji = JsonInjester(SAMPLE, default_tail="total")
        result = ji.get("meta")
        assert result == 3

    def test_default_tail_not_applied_to_list(self):
        ji = JsonInjester(SAMPLE, default_tail="name")
        result = ji.get("users")
        assert isinstance(result, list)

    def test_default_tail_not_applied_to_scalar(self):
        ji = JsonInjester(SAMPLE, default_tail="anything")
        result = ji.get("meta.total")
        assert result == 3  # scalar passes through unchanged

    def test_default_tail_missing_key_returns_unset(self):
        ji = JsonInjester(SAMPLE, default_tail="nonexistent")
        result = ji.get("meta")
        assert result is UNSET


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:

    def test_invalid_input_type_raises(self):
        with pytest.raises(ValueError):
            JsonInjester(12345)

    def test_navigate_intermediate_non_dict_raises(self):
        ji = JsonInjester({"a": [1, 2, 3]})
        with pytest.raises(AttributeError):
            ji.get("a.b")

    def test_deeply_nested_path(self):
        data = {"a": {"b": {"c": {"d": "deep"}}}}
        ji = JsonInjester(data)
        assert ji.get("a.b.c.d") == "deep"

    def test_none_value_with_default(self):
        ji = JsonInjester({"key": None})
        assert ji.get("key", default_value="fallback") == "fallback"

    def test_none_value_without_default_returns_none(self):
        # When there is no default_value, a None result should pass through as None.
        ji = JsonInjester({"key": None})
        assert ji.get("key") is None

    def test_false_value_is_not_treated_as_missing(self):
        # Falsy values other than None (False, 0, "") should NOT trigger the default.
        ji = JsonInjester({"flag": False, "count": 0, "label": ""})
        assert ji.get("flag", default_value=True) is False
        assert ji.get("count", default_value=99) == 0
        assert ji.get("label", default_value="missing") == ""

    def test_empty_list_value(self):
        ji = JsonInjester({"items": []})
        assert ji.get("items") == []

    def test_empty_dict_value(self):
        ji = JsonInjester({"cfg": {}})
        assert ji.get("cfg") == {}

    def test_root_dict_nested_path(self):
        ji = JsonInjester(SAMPLE, root="meta")
        assert ji.get("total") == 3
        assert ji.get("page") == 1

    def test_root_integer_index_not_supported(self):
        # root= splits on "." and calls _move_cursor, which doesn't handle list indexing.
        with pytest.raises(AttributeError, match="got 'list'"):
            JsonInjester(SAMPLE, root="users.0")

    def test_has_returns_true_for_none_value(self):
        # has() delegates to get(); get() returns None (not UNSET) for a key holding None.
        # So has() returns True — the key IS present.
        ji = JsonInjester({"key": None})
        assert ji.has("key") is True

    def test_list_root_bare_path_raises_type_error(self):
        # A JSON-encoded top-level list is accepted by the constructor.
        # Navigating it with a bare string key raises TypeError (not AttributeError)
        # because the list-root guard fires before _move_cursor.
        ji = JsonInjester('[{"id": 1}, {"id": 2}]')
        with pytest.raises(TypeError, match="bare path selector"):
            ji.get("id")

    def test_unicode_key_not_supported_by_grammar(self):
        # The Lark grammar uses CNAME (ASCII identifier) for key tokens.
        # Non-ASCII characters raise a parse error.
        from lark.exceptions import UnexpectedCharacters
        data = {"résumé": {"café": "latte"}}
        ji = JsonInjester(data)
        with pytest.raises(UnexpectedCharacters):
            ji.get('résumé.café')

    def test_key_with_hyphen_quoted(self):
        # Keys containing hyphens must be quoted in the selector syntax.
        data = {"my-key": {"sub-key": 42}}
        ji = JsonInjester(data)
        assert ji.get('"my-key"."sub-key"') == 42