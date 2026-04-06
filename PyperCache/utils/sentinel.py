"""Shared sentinel value for distinguishing "no argument supplied" from None.

A single definition lives here so every module in the package uses the same
object identity, making ``is UNSET`` checks reliable across module boundaries.
"""


class _UnsetType:
    """Singleton sentinel type.  Use the ``UNSET`` module-level instance."""

    _instance: "_UnsetType | None" = None

    def __new__(cls) -> "_UnsetType":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __repr__(self) -> str:
        return "UNSET"

    def __bool__(self) -> bool:
        return False


#: The canonical sentinel instance.  Test with ``value is UNSET``.
UNSET = _UnsetType()
