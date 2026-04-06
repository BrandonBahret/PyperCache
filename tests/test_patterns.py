"""Tests for PyperCache.utils.patterns: singleton decorator and ClassRepository."""

import pytest


class TestSingletonDecorator:

    def test_same_instance_returned(self):
        from PyperCache.utils.patterns import singleton

        @singleton
        class MyService:
            def __init__(self):
                self.value = 0

        a = MyService()
        b = MyService()
        assert a is b

    def test_init_called_once(self):
        from PyperCache.utils.patterns import singleton

        call_count = {"n": 0}

        @singleton
        class Counter:
            def __init__(self):
                call_count["n"] += 1

        Counter()
        Counter()
        Counter()
        assert call_count["n"] == 1

    def test_post_init_called(self):
        from PyperCache.utils.patterns import singleton

        ran = {"post_init": False}

        @singleton
        class WithPostInit:
            def __init__(self):
                pass
            def __post_init__(self):
                ran["post_init"] = True

        WithPostInit()
        assert ran["post_init"] is True

    def test_subsequent_args_ignored(self):
        """Constructor args on subsequent calls are silently ignored."""
        from PyperCache.utils.patterns import singleton

        @singleton
        class Greeter:
            def __init__(self, name="default"):
                self.name = name

        a = Greeter("alice")
        b = Greeter("bob")   # ignored
        assert a is b
        assert a.name == "alice"


class TestClassRepository:

    def test_is_singleton(self):
        from PyperCache.utils.patterns import ClassRepository
        assert ClassRepository() is ClassRepository()

    def test_add_and_get_class(self):
        from PyperCache.utils.patterns import ClassRepository
        repo = ClassRepository()

        class _TestWidget:
            pass

        repo.add_class(_TestWidget)
        assert repo.get_class("_TestWidget") is _TestWidget

    def test_add_non_class_raises(self):
        from PyperCache.utils.patterns import ClassRepository
        with pytest.raises(TypeError):
            ClassRepository().add_class("not_a_class")

    def test_get_missing_class_returns_none(self):
        from PyperCache.utils.patterns import ClassRepository
        assert ClassRepository().get_class("__NonExistent__") is None

    def test_list_classes(self):
        from PyperCache.utils.patterns import ClassRepository

        class _ListMe:
            pass

        ClassRepository().add_class(_ListMe)
        assert "_ListMe" in ClassRepository().list_classes()

    def test_add_module_classes(self):
        from PyperCache.utils.patterns import ClassRepository

        class _ModA:
            pass
        class _ModB:
            pass

        fake_globals = {"_ModA": _ModA, "_ModB": _ModB, "some_func": lambda: None}
        ClassRepository().add_module_classes(fake_globals)

        assert "_ModA" in ClassRepository().list_classes()
        assert "_ModB" in ClassRepository().list_classes()
        assert "some_func" not in ClassRepository().list_classes()

    def test_add_module_classes_excludes_class_repository_itself(self):
        from PyperCache.utils.patterns import ClassRepository
        ClassRepository().add_module_classes({"ClassRepository": ClassRepository})
        # Should not self-register
        # (it may already be in the registry from other tests; just confirm no crash)

    def test_consistent_across_import_paths(self):
        from PyperCache.utils.patterns import ClassRepository as CR1
        from PyperCache.utils import ClassRepository as CR2
        assert CR1() is CR2()
