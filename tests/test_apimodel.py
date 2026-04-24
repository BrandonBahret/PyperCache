"""Adversarial pytest suite for @apimodel, Alias, Lazy[T], and LazyDescriptor.

Strategy
--------
* Normal package imports - pytest resolves pypercache just like any other test.
* The three internal dependencies (ClassRepository, JsonInjester,
  instantiate_type) are patched at their *use-site* inside the modules under
  test, not at import time, so no other test files are disturbed.
* A module-scoped autouse fixture applies the three patches for the entire
  file; individual tests only need extra patching for spy work.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated, Any
from unittest.mock import patch

import pytest

from pypercache.models.lazy_descriptor import LazyDescriptor
from pypercache.models.apimodel import (
    Alias,
    ApiModelValidationError,
    Lazy,
    Shallow,
    Timestamp,
    apimodel,
    _model_eq,
    _model_repr,
)
from pypercache.utils import UNSET
from pypercache.utils.typing_cast import instantiate_type as _real_instantiate_type


# ---------------------------------------------------------------------------
# Lightweight stubs for the three internal collaborators
# ---------------------------------------------------------------------------

class _FakeRepo:
    """Minimal ClassRepository stand-in that records registrations."""
    _registry: dict[str, Any] = {}

    def add_class(self, cls: type) -> None:
        _FakeRepo._registry[cls.__name__] = cls

    @classmethod
    def reset(cls) -> None:
        cls._registry.clear()


def test_apimodel_reexports_field_helpers() -> None:
    from pypercache.models.apimodel import Alias, Columns, Lazy, Shallow, Timestamp, apimodel
    from pypercache.models.fields import Alias as FieldsAlias
    from pypercache.models.fields import Columns as FieldsColumns
    from pypercache.models.fields import Shallow as FieldsShallow
    from pypercache.models.fields import Timestamp as FieldsTimestamp
    from pypercache.models.lazy import Lazy as LazyMarker

    assert Alias is FieldsAlias
    assert Columns is FieldsColumns
    assert Lazy is LazyMarker
    assert Shallow is FieldsShallow
    assert Timestamp is FieldsTimestamp
    assert callable(apimodel)


class _FakeJsonInjester:
    """Identity injester - just wraps a dict with a .get()."""
    def __init__(self, data: dict) -> None:
        self._data = data

    def get(self, key: str, *, default_value=None):
        return self._data.get(key, default_value)


def _identity_instantiate(annotation, raw):
    """Pass raw through unchanged so tests decide what values look like."""
    return raw


# ---------------------------------------------------------------------------
# Autouse fixture - patches collaborators for every test.
# Patches the *use-site* (inside the modules under test) so the real
# pypercache package is left completely intact for other test files.
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _patch_collaborators(monkeypatch):
    monkeypatch.setattr("pypercache.models.apimodel.ClassRepository", _FakeRepo)
    monkeypatch.setattr("pypercache.models.apimodel.JsonInjester", _FakeJsonInjester)
    monkeypatch.setattr("pypercache.models.apimodel.instantiate_type", _identity_instantiate)
    monkeypatch.setattr("pypercache.models.lazy_descriptor.JsonInjester", _FakeJsonInjester)
    monkeypatch.setattr("pypercache.models.lazy_descriptor.instantiate_type", _identity_instantiate)
    _FakeRepo.reset()


# ===========================================================================
# Section 1 - @apimodel basic construction
# ===========================================================================

class TestApimodelConstruction:

    def test_class_registered_in_repo(self):
        """ClassRepository.add_class must be called at decoration time."""
        @apimodel
        class Widget:
            name: str

        assert "Widget" in _FakeRepo._registry
        assert _FakeRepo._registry["Widget"] is Widget

    def test_empty_class_constructs_without_error(self):
        @apimodel
        class Empty:
            pass

        obj = Empty({})
        assert obj.as_dict() == {}

    def test_eager_field_hydrated(self):
        @apimodel
        class Model:
            x: int

        assert Model({"x": 42}).x == 42

    def test_missing_key_becomes_unset(self):
        """Absent key must yield UNSET, not KeyError or None."""
        @apimodel
        class Model:
            x: int

        assert Model({}).x is UNSET

    def test_strict_true_raises_for_missing_eager_field(self):
        @apimodel(strict=True)
        class Model:
            x: int

        with pytest.raises(ApiModelValidationError, match="Model\\.x is UNSET"):
            Model({})

    def test_strict_false_keeps_missing_eager_field_unset(self):
        @apimodel(strict=False)
        class Model:
            x: int

        assert Model({}).x is UNSET

    def test_strict_true_allows_falsy_eager_values(self):
        @apimodel(strict=True)
        class Model:
            flag: bool
            n: int
            s: str

        obj = Model({"flag": False, "n": 0, "s": ""})
        assert obj.flag is False
        assert obj.n == 0
        assert obj.s == ""

    def test_validate_true_allows_castable_eager_value(self, monkeypatch):
        monkeypatch.setattr("pypercache.models.apimodel.instantiate_type", _real_instantiate_type)

        @apimodel(validate=True)
        class Model:
            x: int

        assert Model({"x": "7"}).x == 7

    def test_validate_true_raises_for_uncastable_eager_value(self):
        @apimodel(validate=True)
        class Model:
            x: int

        with pytest.raises(ApiModelValidationError, match="Model\\.x expected"):
            Model({"x": "not an int"})

    def test_validate_true_allows_tiny_user_after_casting(self, monkeypatch):
        monkeypatch.setattr("pypercache.models.apimodel.instantiate_type", _real_instantiate_type)

        @apimodel(validate=True)
        class TinyUser:
            id: int
            name: str
            missing_ok: str

        tiny = TinyUser({
            "id": "7",
            "name": "Mina",
            "extra": "kept raw",
            "missing_ok": "foobar",
        })

        assert tiny.id == 7
        assert tiny.name == "Mina"
        assert tiny.missing_ok == "foobar"
        assert tiny.as_dict()["extra"] == "kept raw"

    def test_validate_true_allows_matching_eager_type(self):
        @apimodel(validate=True)
        class Model:
            x: int

        assert Model({"x": 1}).x == 1

    def test_validate_true_does_not_require_missing_eager_field(self):
        @apimodel(validate=True)
        class Model:
            x: int

        assert Model({}).x is UNSET

    def test_validate_and_strict_can_be_combined_for_missing_eager_field(self):
        @apimodel(validate=True, strict=True)
        class Model:
            x: int

        with pytest.raises(ApiModelValidationError, match="Model\\.x is UNSET"):
            Model({})

    def test_validate_true_rejects_non_list_for_list_annotation(self):
        @apimodel(validate=True)
        class Model:
            values: list[int]

        with pytest.raises(ApiModelValidationError, match="Model\\.values expected"):
            Model({"values": "123"})

    def test_validate_true_rejects_list_item_type_mismatch(self):
        @apimodel(validate=True)
        class Model:
            values: list[int]

        with pytest.raises(ApiModelValidationError, match="Model\\.values expected"):
            Model({"values": [1, "two"]})

    def test_validate_true_allows_nested_apimodel_dict(self):
        @apimodel
        class Child:
            name: str

        @apimodel(validate=True)
        class Parent:
            child: Child

        assert Parent({"child": {"name": "Ada"}}).child == {"name": "Ada"}

    def test_extra_keys_ignored(self):
        @apimodel
        class Model:
            x: int

        assert Model({"x": 1, "boom": "nope"}).x == 1

    def test_multiple_eager_fields(self):
        @apimodel
        class Model:
            a: int
            b: str
            c: float

        obj = Model({"a": 1, "b": "hi", "c": 3.14})
        assert (obj.a, obj.b, obj.c) == (1, "hi", 3.14)

    def test_as_dict_returns_same_object(self):
        """as_dict must return the *identical* dict, not a copy."""
        raw = {"x": 7}

        @apimodel
        class Model:
            x: int

        assert Model(raw).as_dict() is raw

    def test_from_dict_produces_correct_instance(self):
        @apimodel
        class Model:
            v: str

        assert Model.from_dict({"v": "hello"}).v == "hello"

    def test_from_dict_equivalent_to_direct_construction(self):
        @apimodel
        class Model:
            v: str

        raw = {"v": "hello"}
        assert Model(raw).v == Model.from_dict(raw).v

    def test_raw_data_stored_under_mangled_key(self):
        raw = {"x": 1}

        @apimodel
        class Model:
            x: int

        assert getattr(Model(raw), "_Initial__Data") is raw

    def test_two_instances_are_independent(self):
        @apimodel
        class Model:
            x: int

        a, b = Model({"x": 1}), Model({"x": 2})
        assert a.x == 1 and b.x == 2

    def test_decorator_returns_same_class_object(self):
        """@apimodel must return the exact same class, not a wrapper."""
        class Before:
            val: int

        assert apimodel(Before) is Before

    def test_from_dict_is_classmethod(self):
        import inspect

        @apimodel
        class Model:
            x: int

        assert isinstance(inspect.getattr_static(Model, "from_dict"), classmethod)

    def test_as_dict_callable_on_instance(self):
        @apimodel
        class Model:
            x: int

        assert isinstance(Model({"x": 1}).as_dict(), dict)

    def test_repr_uses_annotated_fields(self):
        @apimodel
        class Model:
            x: int
            name: str

        assert repr(Model({"x": 1, "name": "Ada"})) == "Model(x=1, name='Ada')"

    def test_repr_missing_field_uses_unset(self):
        @apimodel
        class Model:
            x: int

        assert repr(Model({})) == "Model(x=UNSET)"

    def test_same_class_same_raw_data_is_equal(self):
        @apimodel
        class Model:
            x: int

        assert Model({"x": 1}) == Model({"x": 1})

    def test_same_class_different_raw_data_is_not_equal(self):
        @apimodel
        class Model:
            x: int

        assert Model({"x": 1}) != Model({"x": 2})

    def test_different_classes_are_not_equal(self):
        @apimodel
        class A:
            x: int

        @apimodel
        class B:
            x: int

        assert A({"x": 1}) != B({"x": 1})

    def test_generated_repr_and_eq_use_shared_helpers(self):
        @apimodel
        class Model:
            x: int

        assert Model.__repr__ is _model_repr
        assert Model.__eq__ is _model_eq

    def test_existing_init_is_replaced(self):
        """A pre-existing __init__ must be overwritten by the decorator."""
        @apimodel
        class Model:
            x: int

            def __init__(self, _):
                raise AssertionError("old __init__ must not run")

        obj = Model({"x": 1})
        assert obj.x == 1

    def test_post_init_called_after_hydration(self):
        @apimodel(validate=True)
        class TinyProfile:
            handle: str
            reputation: int

            def __post_init__(self):
                self.summary = f"{self.handle}:{self.reputation}"

        obj = TinyProfile({"handle": "mina", "reputation": 12})

        assert obj.summary == "mina:12"

    def test_post_init_called_once_per_instance(self):
        calls = []

        @apimodel
        class Model:
            x: int

            def __post_init__(self):
                calls.append(self.x)

        first = Model({"x": 1})
        second = Model.from_dict({"x": 2})

        assert calls == [1, 2]
        assert first.x == 1
        assert second.x == 2

    def test_post_init_not_called_when_construction_fails(self):
        calls = []

        @apimodel(strict=True)
        class Model:
            x: int

            def __post_init__(self):
                calls.append("called")

        with pytest.raises(ApiModelValidationError, match="Model\\.x is UNSET"):
            Model({})

        assert calls == []

    def test_applied_twice_does_not_raise(self):
        @apimodel
        class Model:
            x: int

        apimodel(Model)  # must not raise

    def test_raw_dict_mutation_visible_via_as_dict(self):
        """as_dict returns the same dict, so mutations are visible - lock that down."""
        raw = {"x": 1}

        @apimodel
        class Model:
            x: int

        obj = Model(raw)
        raw["x"] = 999
        assert obj.as_dict()["x"] == 999

    def test_eager_assignment_updates_raw_dict(self):
        raw = {"x": 1}

        @apimodel
        class Model:
            x: int

        obj = Model(raw)
        obj.x = 2

        assert obj.x == 2
        assert raw["x"] == 2

    def test_eager_assignment_is_type_checked(self):
        @apimodel
        class Model:
            x: int

        obj = Model({"x": 1})

        with pytest.raises(ApiModelValidationError, match="Model\\.x expected"):
            obj.x = "not an int"

    def test_eager_assignment_casts_before_type_checking(self, monkeypatch):
        monkeypatch.setattr("pypercache.models.apimodel.instantiate_type", _real_instantiate_type)

        raw = {"x": 1}

        @apimodel
        class Model:
            x: int

        obj = Model(raw)
        obj.x = "7"

        assert obj.x == 7
        assert raw["x"] == 7

    def test_eager_assignment_accepts_existing_apimodel_instance(self, monkeypatch):
        monkeypatch.setattr("pypercache.models.apimodel.instantiate_type", _real_instantiate_type)

        @apimodel
        class TinyProfile:
            handle: str
            reputation: int

        @apimodel
        class TinyAccount:
            id: int
            profile: TinyProfile

        account = TinyAccount({"id": 3, "profile": {"handle": "mina", "reputation": "42"}})
        profile = TinyProfile({"handle": "george", "reputation": 5})

        account.profile = profile

        assert account.profile is profile
        assert account.as_dict()["profile"] == {"handle": "george", "reputation": 5}

    def test_eager_alias_assignment_updates_aliased_raw_key(self):
        raw = {"name": "Alice"}

        @apimodel
        class Model:
            display_name: Annotated[str, Alias("name")]

        obj = Model(raw)
        obj.display_name = "Mina"

        assert obj.display_name == "Mina"
        assert raw["name"] == "Mina"
        assert "display_name" not in raw

    def test_nested_alias_assignment_updates_raw_path_without_field_key(self):
        raw = {"profile": {"name": "Alice"}}

        @apimodel
        class Model:
            display_name: Annotated[str, Alias("profile.name")]

        obj = Model(raw)
        obj.display_name = "Mina"

        assert raw == {"profile": {"name": "Mina"}}
        assert "display_name" not in raw

    def test_timestamp_assignment_stores_raw_string(self):
        raw = {"created_at": "2026-04-19T12:34:56+00:00"}

        @apimodel
        class Model:
            created_at: Annotated[datetime, Timestamp()]

        obj = Model(raw)
        obj.created_at = datetime(2026, 4, 20, 1, 2, 3, tzinfo=timezone.utc)

        assert obj.created_at == datetime(2026, 4, 20, 1, 2, 3, tzinfo=timezone.utc)
        assert raw["created_at"] == "2026-04-20T01:02:03+00:00"

    def test_timestamp_assignment_uses_explicit_format_for_raw_string(self):
        raw = {"created_at": "2026/04/19 12:34:56"}

        @apimodel
        class Model:
            created_at: Annotated[datetime, Timestamp("%Y/%m/%d %H:%M:%S")]

        obj = Model(raw)
        obj.created_at = datetime(2026, 4, 20, 1, 2, 3, tzinfo=timezone.utc)

        assert obj.created_at == datetime(2026, 4, 20, 1, 2, 3, tzinfo=timezone.utc)
        assert raw["created_at"] == "2026/04/20 01:02:03"

    def test_inherited_annotations_not_hydrated(self):
        """The decorator must only inspect cls.__annotations__, not walk the MRO."""
        class Base:
            inherited: int = 0

        @apimodel
        class Child(Base):
            own: int

        obj = Child({"own": 5, "inherited": 999})
        assert obj.own == 5
        # Base-class default must be untouched.
        assert Base.inherited == 0

    def test_annotated_non_lazy_field_is_eager(self):
        """Annotated[T, metadata] without Lazy must hydrate normally."""
        @apimodel
        class Model:
            x: Annotated[int, "metadata"]

        obj = Model({"x": 5})
        assert obj.x == 5
        assert not isinstance(Model.__dict__.get("x"), LazyDescriptor)


# ===========================================================================
# Section 2 - Lazy field basic behaviour
# ===========================================================================

class TestLazyBasics:

    def test_lazy_field_skipped_during_init(self, monkeypatch):
        """instantiate_type must NOT be called for Lazy fields in __init__."""
        calls = []

        def spying_instantiate(annotation, raw):
            calls.append(annotation)
            return raw

        monkeypatch.setattr("pypercache.models.apimodel.instantiate_type", spying_instantiate)

        @apimodel
        class Model:
            eager: int
            lazy_val: Lazy[str]

        Model({"eager": 1, "lazy_val": "surprise"})
        assert int in calls, "eager field must be instantiated"
        assert str not in calls, "lazy field must NOT be instantiated in __init__"

    def test_lazy_field_hydrated_on_first_access(self):
        @apimodel
        class Model:
            data: Lazy[str]

        assert Model({"data": "loaded"}).data == "loaded"

    def test_lazy_missing_key_returns_unset(self):
        @apimodel
        class Model:
            x: Lazy[str]

        assert Model({}).x is UNSET

    def test_strict_true_raises_for_missing_lazy_field_at_init(self):
        @apimodel(strict=True)
        class Model:
            x: Lazy[str]

        with pytest.raises(ApiModelValidationError, match="Model\\.x is UNSET"):
            Model({})

    def test_strict_true_raises_for_missing_lazy_field_at_access_after_mutation(self):
        raw = {"x": "ok"}

        @apimodel(strict=True)
        class Model:
            x: Lazy[str]

        obj = Model(raw)
        raw.pop("x")

        with pytest.raises(ApiModelValidationError, match="Model\\.x is UNSET"):
            obj.x

    def test_validate_true_allows_castable_lazy_value_at_init(self, monkeypatch):
        monkeypatch.setattr("pypercache.models.apimodel.instantiate_type", _real_instantiate_type)
        monkeypatch.setattr("pypercache.models.lazy_descriptor.instantiate_type", _real_instantiate_type)

        @apimodel(validate=True)
        class Model:
            x: Lazy[int]

        obj = Model({"x": "7"})
        assert hasattr(obj, "_lazycache_x")
        assert obj.x == 7

    def test_validate_true_raises_for_uncastable_lazy_value_at_init(self):
        @apimodel(validate=True)
        class Model:
            x: Lazy[int]

        with pytest.raises(ApiModelValidationError, match="Model\\.x expected"):
            Model({"x": "not an int"})

    def test_validate_true_lazy_field_is_snapshot_after_init_mutation(self):
        raw = {"x": 1}

        @apimodel(validate=True)
        class Model:
            x: Lazy[int]

        obj = Model(raw)
        raw["x"] = "not an int"

        assert obj.x == 1

    def test_validate_true_lazy_field_does_not_hydrate_again_on_first_access(self, monkeypatch):
        monkeypatch.setattr("pypercache.models.apimodel.instantiate_type", _real_instantiate_type)
        monkeypatch.setattr("pypercache.models.lazy_descriptor.instantiate_type", _real_instantiate_type)

        calls = []
        original = LazyDescriptor._hydrate

        def counting(self_d, obj):
            calls.append(1)
            return original(self_d, obj)

        monkeypatch.setattr(LazyDescriptor, "_hydrate", counting)

        @apimodel(validate=True)
        class Profile:
            handle: str
            reputation: int

        @apimodel(validate=True)
        class Account:
            profile: Lazy[Profile]

        obj = Account({"profile": {"handle": "mina", "reputation": "42"}})

        assert hasattr(obj, "_lazycache_profile")
        assert obj.profile.reputation == 42
        assert calls == []

    def test_validate_true_shallow_lazy_field_waits_until_access(self, monkeypatch):
        monkeypatch.setattr("pypercache.models.apimodel.instantiate_type", _real_instantiate_type)
        monkeypatch.setattr("pypercache.models.lazy_descriptor.instantiate_type", _real_instantiate_type)

        @apimodel(validate=True)
        class Model:
            eager: int
            x: Lazy[Annotated[int, Shallow()]]

        obj = Model({"eager": "7", "x": "not an int"})

        assert obj.eager == 7
        assert not hasattr(obj, "_lazycache_x")
        with pytest.raises(ApiModelValidationError, match="Model\\.x expected"):
            obj.x

    def test_validate_true_shallow_lazy_field_does_not_snapshot_value_at_init(self, monkeypatch):
        monkeypatch.setattr("pypercache.models.apimodel.instantiate_type", _real_instantiate_type)
        monkeypatch.setattr("pypercache.models.lazy_descriptor.instantiate_type", _real_instantiate_type)

        raw = {"x": "7"}

        @apimodel(validate=True)
        class Model:
            x: Lazy[Annotated[int, Shallow()]]

        obj = Model(raw)
        raw["x"] = "9"

        assert obj.x == 9

    def test_strict_true_shallow_lazy_field_waits_until_access(self):
        @apimodel(strict=True)
        class Model:
            x: Lazy[Annotated[int, Shallow()]]

        obj = Model({})

        with pytest.raises(ApiModelValidationError, match="Model\\.x is UNSET"):
            obj.x

    def test_validate_and_strict_shallow_lazy_field_still_checks_on_access(self, monkeypatch):
        monkeypatch.setattr("pypercache.models.apimodel.instantiate_type", _real_instantiate_type)
        monkeypatch.setattr("pypercache.models.lazy_descriptor.instantiate_type", _real_instantiate_type)

        @apimodel(validate=True, strict=True)
        class Model:
            eager: int
            x: Lazy[Annotated[int, Shallow()]]

        obj = Model({"eager": "5", "x": "11"})

        assert obj.eager == 5
        assert obj.x == 11

    def test_lazy_hydrated_exactly_once(self, monkeypatch):
        """_hydrate must be called once; subsequent reads must hit the cache."""
        calls = []
        original = LazyDescriptor._hydrate

        def counting(self_d, obj):
            calls.append(1)
            return original(self_d, obj)

        monkeypatch.setattr(LazyDescriptor, "_hydrate", counting)

        @apimodel
        class Model:
            val: Lazy[int]

        obj = Model({"val": 42})
        for _ in range(5):
            _ = obj.val

        assert len(calls) == 1, f"expected 1 hydration, got {len(calls)}"

    def test_eager_and_lazy_coexist(self):
        @apimodel
        class Model:
            eager: int
            lazy_val: Lazy[str]

        obj = Model({"eager": 10, "lazy_val": "deferred"})
        assert obj.eager == 10
        assert obj.lazy_val == "deferred"

    def test_multiple_lazy_fields_independent(self):
        @apimodel
        class Model:
            a: Lazy[int]
            b: Lazy[str]

        obj = Model({"a": 1, "b": "two"})
        assert obj.a == 1
        assert obj.b == "two"

    def test_lazy_descriptor_installed_on_class(self):
        @apimodel
        class Model:
            x: Lazy[int]

        assert isinstance(Model.__dict__["x"], LazyDescriptor)

    def test_class_level_access_returns_descriptor(self):
        """Accessing a lazy field on the class (obj=None) must return the descriptor."""
        @apimodel
        class Model:
            x: Lazy[int]

        assert isinstance(Model.x, LazyDescriptor)

    def test_cache_isolated_between_instances(self):
        """Hydrating one instance must not pollute another."""
        @apimodel
        class Model:
            val: Lazy[int]

        a, b = Model({"val": 1}), Model({"val": 2})
        _ = a.val
        assert b.val == 2


# ===========================================================================
# Section 3 - Alias
# ===========================================================================

class TestAlias:

    def test_eager_alias_reads_aliased_key(self):
        @apimodel
        class Model:
            display_name: Annotated[str, Alias("name")]

        assert Model({"name": "Alice"}).display_name == "Alice"

    def test_eager_alias_ignores_field_name_key(self):
        @apimodel
        class Model:
            display_name: Annotated[str, Alias("name")]

        obj = Model({"display_name": "WRONG", "name": "RIGHT"})
        assert obj.display_name == "RIGHT"

    def test_eager_alias_missing_returns_unset(self):
        @apimodel
        class Model:
            x: Annotated[str, Alias("y")]

        assert Model({"x": "ignored"}).x is UNSET

    def test_strict_true_uses_eager_alias_when_checking_missing_field(self):
        @apimodel(strict=True)
        class Model:
            x: Annotated[str, Alias("y")]

        with pytest.raises(ApiModelValidationError, match="Model\\.x is UNSET"):
            Model({"x": "ignored"})

    def test_validate_true_uses_eager_alias_when_casting_before_checking_type(self, monkeypatch):
        monkeypatch.setattr("pypercache.models.apimodel.instantiate_type", _real_instantiate_type)

        @apimodel(validate=True)
        class Model:
            x: Annotated[int, Alias("y")]

        assert Model({"y": "7"}).x == 7

    def test_lazy_alias_reads_aliased_key(self):
        @apimodel
        class Model:
            display_name: Lazy[Annotated[str, Alias("name")]]

        assert Model({"name": "Alice"}).display_name == "Alice"

    def test_lazy_alias_ignores_field_name_key(self):
        """When alias is set, the field-name key in the raw dict must be ignored."""
        @apimodel
        class Model:
            display_name: Lazy[Annotated[str, Alias("name")]]

        obj = Model({"display_name": "WRONG", "name": "RIGHT"})
        assert obj.display_name == "RIGHT"

    def test_lazy_alias_missing_returns_unset(self):
        @apimodel
        class Model:
            x: Lazy[Annotated[str, Alias("y")]]

        assert Model({"x": "ignored"}).x is UNSET

    def test_strict_true_uses_lazy_alias_when_checking_missing_field(self):
        @apimodel(strict=True)
        class Model:
            x: Lazy[Annotated[str, Alias("y")]]

        with pytest.raises(ApiModelValidationError, match="Model\\.x is UNSET"):
            Model({"x": "ignored"})

    def test_validate_true_uses_lazy_alias_when_casting_before_checking_type(self, monkeypatch):
        monkeypatch.setattr("pypercache.models.apimodel.instantiate_type", _real_instantiate_type)
        monkeypatch.setattr("pypercache.models.lazy_descriptor.instantiate_type", _real_instantiate_type)

        @apimodel(validate=True)
        class Model:
            x: Lazy[Annotated[int, Alias("y")]]

        assert Model({"y": "7"}).x == 7

    def test_shallow_marker_on_non_lazy_field_does_not_skip_validation(self):
        @apimodel(validate=True)
        class Model:
            x: Annotated[int, Shallow()]

        with pytest.raises(ApiModelValidationError, match="Model\\.x expected"):
            Model({"x": "not an int"})

    def test_alias_empty_string_is_valid_key(self):
        """An empty-string alias is a valid dict key and must not crash."""
        @apimodel
        class Model:
            val: Annotated[str, Alias("")]

        assert Model({"": "empty"}).val == "empty"


class TestTimestamp:

    def test_eager_timestamp_parses_iso_string(self):
        @apimodel
        class Model:
            created_at: Annotated[datetime, Timestamp()]

        obj = Model({"created_at": "2026-04-19T12:34:56Z"})

        assert obj.created_at == datetime(2026, 4, 19, 12, 34, 56, tzinfo=timezone.utc)

    def test_eager_timestamp_parses_custom_format(self):
        @apimodel
        class Model:
            created_at: Annotated[datetime, Timestamp("%Y/%m/%d %H:%M:%S")]

        obj = Model({"created_at": "2026/04/19 12:34:56"})

        assert obj.created_at == datetime(2026, 4, 19, 12, 34, 56, tzinfo=timezone.utc)

    def test_eager_timestamp_parses_milliseconds(self):
        @apimodel
        class Model:
            created_at: Annotated[datetime, Timestamp(unit="ms")]

        obj = Model({"created_at": 1776602096000})

        assert obj.created_at == datetime(2026, 4, 19, 12, 34, 56, tzinfo=timezone.utc)

    def test_eager_timestamp_composes_with_alias(self):
        @apimodel
        class Model:
            created_at: Annotated[datetime, Alias("created"), Timestamp()]

        obj = Model({"created": "2026-04-19T12:34:56+00:00"})

        assert obj.created_at == datetime(2026, 4, 19, 12, 34, 56, tzinfo=timezone.utc)

    def test_lazy_timestamp_parses_on_access(self):
        @apimodel
        class Model:
            created_at: Lazy[Annotated[datetime, Timestamp()]]

        obj = Model({"created_at": "2026-04-19T12:34:56Z"})

        assert obj.created_at == datetime(2026, 4, 19, 12, 34, 56, tzinfo=timezone.utc)

    def test_validate_true_rejects_invalid_timestamp(self):
        @apimodel(validate=True)
        class Model:
            created_at: Annotated[datetime, Timestamp()]

        with pytest.raises(ApiModelValidationError, match="Model\\.created_at expected"):
            Model({"created_at": "not a timestamp"})

    def test_timestamp_does_not_call_general_instantiator(self, monkeypatch):
        calls = []

        def spying_instantiate(annotation, raw):
            calls.append((annotation, raw))
            return raw

        monkeypatch.setattr("pypercache.models.apimodel.instantiate_type", spying_instantiate)

        @apimodel
        class Model:
            created_at: Annotated[datetime, Timestamp()]

        obj = Model({"created_at": "2026-04-19T12:34:56Z"})

        assert obj.created_at == datetime(2026, 4, 19, 12, 34, 56, tzinfo=timezone.utc)
        assert calls == []


# ===========================================================================
# Section 4 - Explicit assignment and deletion
# ===========================================================================

class TestDescriptorSetDelete:

    def test_explicit_assignment_overrides_value(self):
        @apimodel
        class Model:
            val: Lazy[int]

        obj = Model({"val": 1})
        obj.val = 999
        assert obj.val == 999

    def test_assignment_before_first_access(self):
        @apimodel
        class Model:
            val: Lazy[int]

        obj = Model({"val": 1})
        obj.val = 42
        assert obj.val == 42

    def test_assignment_updates_raw_dict(self):
        raw = {"val": 1}

        @apimodel
        class Model:
            val: Lazy[int]

        obj = Model(raw)
        obj.val = 999
        assert raw["val"] == 999

    def test_lazy_assignment_is_type_checked(self):
        @apimodel
        class Model:
            val: Lazy[int]

        obj = Model({"val": 1})

        with pytest.raises(ApiModelValidationError, match="Model\\.val expected"):
            obj.val = "not an int"

    def test_lazy_assignment_accepts_existing_apimodel_instance(self, monkeypatch):
        monkeypatch.setattr("pypercache.models.apimodel.instantiate_type", _real_instantiate_type)
        monkeypatch.setattr("pypercache.models.lazy_descriptor.instantiate_type", _real_instantiate_type)

        @apimodel
        class TinyProfile:
            handle: str
            reputation: int

        @apimodel
        class TinyAccount:
            profile: Lazy[TinyProfile]

        account = TinyAccount({"profile": {"handle": "mina", "reputation": "42"}})
        profile = TinyProfile({"handle": "george", "reputation": 5})

        account.profile = profile

        assert account.profile is profile
        assert account.as_dict()["profile"] == {"handle": "george", "reputation": 5}

    def test_lazy_timestamp_assignment_stores_raw_string(self):
        raw = {"created_at": "2026-04-19T12:34:56+00:00"}

        @apimodel
        class Model:
            created_at: Lazy[Annotated[datetime, Timestamp()]]

        obj = Model(raw)
        obj.created_at = datetime(2026, 4, 20, 1, 2, 3, tzinfo=timezone.utc)

        assert obj.created_at == datetime(2026, 4, 20, 1, 2, 3, tzinfo=timezone.utc)
        assert raw["created_at"] == "2026-04-20T01:02:03+00:00"

    def test_delete_forces_rehydration(self, monkeypatch):
        calls = []
        original = LazyDescriptor._hydrate

        def counting(self_d, inst):
            calls.append(1)
            return original(self_d, inst)

        monkeypatch.setattr(LazyDescriptor, "_hydrate", counting)

        @apimodel
        class Model:
            val: Lazy[int]

        obj = Model({"val": 5})
        _ = obj.val   # first hydration
        del obj.val   # clear cache
        _ = obj.val   # must hydrate again

        assert len(calls) == 2

    def test_double_delete_does_not_raise(self):
        """Deleting an already-absent cache must be a silent no-op."""
        @apimodel
        class Model:
            val: Lazy[int]

        obj = Model({"val": 1})
        del obj.val
        del obj.val  # must not raise

    def test_assigned_value_not_rehydrated(self, monkeypatch):
        calls = []
        original = LazyDescriptor._hydrate

        def counting(self_d, inst):
            calls.append(1)
            return original(self_d, inst)

        monkeypatch.setattr(LazyDescriptor, "_hydrate", counting)

        @apimodel
        class Model:
            val: Lazy[int]

        obj = Model({"val": 1})
        obj.val = 777
        for _ in range(5):
            assert obj.val == 777

        assert len(calls) == 0, (
            "_hydrate must never be called when value was explicitly set"
        )

    def test_lazy_field_raw_dict_mutation_picked_up_after_delete(self):
        raw = {"val": 1}

        @apimodel
        class Model:
            val: Lazy[int]

        obj = Model(raw)
        _ = obj.val
        raw["val"] = 2
        del obj.val
        assert obj.val == 2


# ===========================================================================
# Section 5 - Descriptor isolation
# ===========================================================================

class TestDescriptorIsolation:

    def test_shared_descriptor_independent_instance_caches(self):
        """Same descriptor object on the class must not bleed state between instances."""
        @apimodel
        class Model:
            val: Lazy[int]

        desc = Model.__dict__["val"]
        a, b = Model({"val": 10}), Model({"val": 20})
        assert a.val == 10
        assert b.val == 20
        assert Model.__dict__["val"] is desc  # same descriptor object

    def test_two_classes_have_independent_descriptors(self):
        @apimodel
        class A:
            x: Lazy[int]

        @apimodel
        class B:
            x: Lazy[int]

        assert A.__dict__["x"] is not B.__dict__["x"]


# ===========================================================================
# Section 6 - Falsy / edge-case values
# ===========================================================================

class TestEdgeCaseValues:

    def test_none_in_dict_stays_none_eager(self):
        @apimodel
        class Model:
            x: int

        assert Model({"x": None}).x is None

    def test_none_in_dict_stays_none_lazy(self):
        @apimodel
        class Model:
            x: Lazy[int]

        assert Model({"x": None}).x is None

    def test_false_not_mistaken_for_missing_eager(self):
        @apimodel
        class Model:
            flag: bool

        assert Model({"flag": False}).flag is False

    def test_zero_not_mistaken_for_missing_eager(self):
        @apimodel
        class Model:
            n: int

        assert Model({"n": 0}).n == 0

    def test_empty_string_not_mistaken_for_missing_eager(self):
        @apimodel
        class Model:
            s: str

        assert Model({"s": ""}).s == ""

    def test_lazy_false_cached_not_rehydrated(self, monkeypatch):
        """Falsy cached value must NOT cause re-hydration on subsequent access.

        This is the classic `if not cache` vs `if cache is not None` bug.
        If the implementation ever checked `if not cached_value` instead of
        `if cache is not None`, False/0/'' would all re-hydrate every time.
        """
        calls = []
        original = LazyDescriptor._hydrate

        def counting(self_d, obj):
            calls.append(1)
            return original(self_d, obj)

        monkeypatch.setattr(LazyDescriptor, "_hydrate", counting)

        @apimodel
        class Model:
            flag: Lazy[bool]

        obj = Model({"flag": False})
        _ = obj.flag
        _ = obj.flag

        assert len(calls) == 1, (
            "Falsy value triggered re-hydration - "
            "cache check must use `is not None`, not truthiness"
        )

    def test_lazy_zero_cached_not_rehydrated(self, monkeypatch):
        calls = []
        original = LazyDescriptor._hydrate

        def counting(self_d, obj):
            calls.append(1)
            return original(self_d, obj)

        monkeypatch.setattr(LazyDescriptor, "_hydrate", counting)

        @apimodel
        class Model:
            n: Lazy[int]

        obj = Model({"n": 0})
        for _ in range(3):
            _ = obj.n

        assert len(calls) == 1

    def test_lazy_empty_string_cached_not_rehydrated(self, monkeypatch):
        calls = []
        original = LazyDescriptor._hydrate

        def counting(self_d, obj):
            calls.append(1)
            return original(self_d, obj)

        monkeypatch.setattr(LazyDescriptor, "_hydrate", counting)

        @apimodel
        class Model:
            s: Lazy[str]

        obj = Model({"s": ""})
        for _ in range(3):
            _ = obj.s

        assert len(calls) == 1


# ===========================================================================
# Section 7 - LazyDescriptor unit tests (direct)
# ===========================================================================

class TestLazyDescriptorDirect:
    """Poke LazyDescriptor in isolation, bypassing @apimodel entirely."""

    def _fake_instance(self, raw: dict):
        class FakeInstance:
            pass
        inst = FakeInstance()
        object.__setattr__(inst, "_Initial__Data", raw)
        return inst

    def test_get_on_class_returns_descriptor(self):
        desc = LazyDescriptor("x", int)
        assert desc.__get__(None, object) is desc

    def test_set_name_updates_field_and_cache_key(self):
        desc = LazyDescriptor("old", int)
        desc.__set_name__(object, "new_name")
        assert desc.field == "new_name"
        assert desc._cache_key == "_lazycache_new_name"

    def test_alias_reads_from_alias_key(self):
        desc = LazyDescriptor("x", int, alias="raw")
        inst = self._fake_instance({"raw": 42, "x": 0})
        assert desc._hydrate(inst) == 42

    def test_hydrate_writes_cache_on_instance(self):
        desc = LazyDescriptor("x", int)
        inst = self._fake_instance({"x": 42})
        result = desc._hydrate(inst)
        assert result == 42
        assert getattr(inst, "_lazycache_x") == 42

    def test_set_writes_cache_directly(self):
        desc = LazyDescriptor("x", int)
        inst = self._fake_instance({})
        desc.__set__(inst, 99)
        assert getattr(inst, "_lazycache_x") == 99

    def test_delete_removes_cache(self):
        desc = LazyDescriptor("x", int)
        inst = self._fake_instance({"x": 1})
        desc._hydrate(inst)
        assert hasattr(inst, "_lazycache_x")
        desc.__delete__(inst)
        assert not hasattr(inst, "_lazycache_x")

    def test_delete_on_uncached_instance_does_not_raise(self):
        desc = LazyDescriptor("x", int)
        inst = self._fake_instance({})
        desc.__delete__(inst)  # must not raise

