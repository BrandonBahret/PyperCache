"""Design-pattern utilities: singleton decorator and class registry."""

from functools import wraps
from typing import Any, Callable, Dict, List, Type, TypeVar


T = TypeVar("T")


def singleton(cls: Type[T]) -> Callable[..., T]:
    """Class decorator that enforces the singleton pattern.

    The first call constructs and caches the instance. If the class defines
    ``__post_init__``, it is invoked immediately after construction. Subsequent
    calls return the cached instance regardless of the arguments passed.

    Args:
        cls: The class to wrap as a singleton.

    Returns:
        A wrapper function that always returns the single shared instance.
    """
    instances: Dict[type, Any] = {}

    @wraps(cls)
    def get_instance(*args: Any, **kwargs: Any) -> T:
        if cls not in instances:
            instances[cls] = cls(*args, **kwargs)
            if hasattr(instances[cls], "__post_init__"):
                instances[cls].__post_init__()
        return instances[cls]

    return get_instance


@singleton
class ClassRepository:
    """A singleton registry that maps class names to their types.

    Useful for dynamic instantiation by name — e.g. deserialising objects
    whose concrete type is stored as a string.
    """

    def __init__(self) -> None:
        self.classes: Dict[str, type] = {}
        # map fully-qualified name -> type
        self.fqclasses: Dict[str, type] = {}

    def add_module_classes(self, globals_dict: Dict[str, Any]) -> None:
        """Discover and register every class defined in *globals_dict*.

        Typically called with ``globals()`` from the module you want to index.
        ``ClassRepository`` itself is excluded to avoid self-registration.

        Args:
            globals_dict: The global namespace to scan (pass ``globals()``).
        """
        for name, obj in globals_dict.items():
            if name != "ClassRepository" and isinstance(obj, type):
                self.classes[name] = obj

    def add_class(self, cls: type) -> None:
        """Register a single class.

        Args:
            cls: The class to register.

        Raises:
            TypeError: If *cls* is not a type.
        """
        if not isinstance(cls, type):
            raise TypeError("'cls' must be a type.")
        self.classes[cls.__name__] = cls
        fq = f"{cls.__module__}.{cls.__name__}"
        self.fqclasses[fq] = cls

    def get_class(self, class_name: str) -> type | None:
        """Return the class registered under *class_name*, or ``None``.

        Args:
            class_name: The ``__name__`` of the desired class.

        Returns:
            The registered class, or ``None`` if not found.
        """
        # Try short name first, then fully-qualified name.
        if class_name in self.classes:
            return self.classes[class_name]
        return self.fqclasses.get(class_name)

    def list_classes(self) -> List[str]:
        """Return the names of all registered classes.

        Returns:
            A list of class name strings.
        """
        return list(self.classes.keys())
