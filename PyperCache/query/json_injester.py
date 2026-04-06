from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Tuple, Type, TypeVar, Union

from lark import Lark, Transformer

from ..utils.sentinel import UNSET
from ..utils.typing_cast import instantiate_type


T = TypeVar("T")

# ---------------------------------------------------------------------------
# Query AST nodes
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class JIPath:
    """A dot-separated key path used to navigate a JSON structure.

    Example: ``"a.b.c"`` → ``JIPath(keys=('a', 'b', 'c'))``
    """

    keys: Tuple[str, ...]


@dataclass(frozen=True)
class JIMatch:
    """A filter expression that keeps only items where a nested key equals a value.

    Example: ``"?type=admin"`` → ``JIMatch(key_path=JIPath(('type',)), value='admin')``
    """

    key_path: JIPath
    value: Any


@dataclass(frozen=True)
class JIExistsFilter:
    """Filter: keeps only items where a key exists (no value check).

    On a **dict** cursor: returns ``UNSET`` if absent, cursor unchanged if present.
    On a **list** cursor: returns only elements that contain ``key_path``.

    Example: ``"?name"`` -> ``JIExistsFilter(key_path=JIPath(('name',)))``
    """

    key_path: JIPath


@dataclass(frozen=True)
class JIPluck:
    """Pluck: extracts a key value from each element.

    On a **dict** cursor: navigates to ``key_path``, returns ``UNSET`` if absent.
    On a **list** cursor: extracts ``key_path`` from every element, collecting hits.

    Example: ``"?name*"`` -> ``JIPluck(key_path=JIPath(('name',)))``
    """

    key_path: JIPath


# ---------------------------------------------------------------------------
# Grammar & transformer
# ---------------------------------------------------------------------------

#: Lark grammar for the selector mini-language.
#:
#: Syntax examples:
#:   ``"users"``                     – navigate to the ``users`` key
#:   ``"users.0.name"``              – navigate nested keys / indices
#:   ``"users?role=admin"``          – filter list items where role == "admin"
#:   ``"?name"``                     – safe-get ``name`` from the current cursor
#:   ``"users?role"``                – pluck ``role`` from every item in ``users``
#:   ``"users?role?label"``          – chain safe-gets: pluck ``role``, then ``label``
_GRAMMAR = r"""
    start:       path_expr? (selector tail?)*
    tail:        "." ITEM ("." ITEM)*
    selector:    exists_expr | pluck_expr | match_expr
    exists_expr: "?" path_expr
    pluck_expr:  "?" path_expr "*"
    match_expr:  "?" path_expr "=" match_value
    path_expr:   ITEM ("." ITEM)*

    match_value: NUM_LITERAL | ESCAPED_STRING | ITEM
    NUM_LITERAL: "#" /-?[0-9]+(\.[0-9]+)?/

    ITEM: CNAME | ESCAPED_STRING | INT
    INT:  /-?[0-9]+/

    _STRING_INNER: /[a-zA-Z0-9-]+/
    STRING:        _STRING_INNER /(?<!\\)(\\\\)*?/

    %ignore WS

    %import common.CNAME
    %import common.ESCAPED_STRING
    %import common.WS
"""

QueryParser = Lark(_GRAMMAR, parser="lalr")


def _dequote(s: str) -> str:
    """Strip matching single or double quotes from a string token, if present."""
    if len(s) >= 2 and s[0] == s[-1] and s[0] in ('"', "'"):
        return s[1:-1]
    return s


class JIQuery(Transformer):
    """Lark transformer that converts a parse tree into a list of AST nodes."""

    def start(self, children: List[Any]) -> List[Any]:
        return children

    def tail(self, children: List[str]) -> JIPath:
        return JIPath(tuple(children))

    def path_expr(self, children: List[str]) -> JIPath:
        return JIPath(tuple(children))

    def match_value(self, children: List[Any]) -> Any:  # noqa: N802
        value = children[0]
        # ESCAPED_STRING tokens arrive still quoted (e.g. '"foo"'); dequote them
        # so the returned value is a plain str, not the raw token with quotes.
        if isinstance(value, str) and len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
            return _dequote(value)
        return value

    def NUM_LITERAL(self, token: Any) -> Union[int, float]:  # noqa: N802
        raw = str(token)[1:]  # strip leading '#'
        return float(raw) if "." in raw else int(raw)

    def exists_expr(self, children: List[Any]) -> JIExistsFilter:
        return JIExistsFilter(key_path=children[0])

    def pluck_expr(self, children: List[Any]) -> JIPluck:
        return JIPluck(key_path=children[0])

    def match_expr(self, children: List[Any]) -> JIMatch:
        key_path, value = children
        return JIMatch(key_path, value)

    def selector(self, children: List[Any]) -> Any:
        return children[0]

    def ESCAPED_STRING(self, token: Any) -> str:  # noqa: N802 – must match Lark terminal name
        return _dequote(str(token))

    def ITEM(self, token: Any) -> str:  # noqa: N802
        return _dequote(str(token))


# ---------------------------------------------------------------------------
# Main class
# ---------------------------------------------------------------------------

class JsonInjester:
    """Lightweight query interface for navigating and filtering JSON data.

    Parameters
    ----------
    json_data:
        Either a raw JSON string or an already-parsed dictionary.
    root:
        Optional dot-separated path to use as the starting cursor.
        For example, ``root="data.users"`` is equivalent to immediately
        calling ``.get("data.users")`` and using that as the new root.
    default_tail:
        When a ``get()`` call resolves to a ``dict``, automatically
        follow this additional selector before returning.  Useful when
        every value in a collection has the same wrapper key.
    """

    def __init__(
        self,
        json_data: Union[str, Dict[str, Any]],
        root: Optional[str] = None,
        default_tail: Optional[str] = None,
    ) -> None:
        self.default_tail = default_tail

        if isinstance(json_data, str):
            self.data: Any = json.loads(json_data)
        elif isinstance(json_data, (dict, list)):
            self.data = json_data
        else:
            raise ValueError(
                f"json_data must be a str, dict, or list, got {type(json_data).__name__!r}"
            )

        if root is not None:
            self.data = self._move_cursor(self.data, JIPath(tuple(root.split("."))))

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def has(self, selector: str) -> bool:
        """Return ``True`` if the selector resolves to an existing value."""
        return self.get(selector) is not UNSET

    def get(
        self,
        selector: str,
        default_value: Any = UNSET,
        select_first: bool = False,
        cast: Optional[Type[T]] = None,
    ) -> Any:
        """Evaluate *selector* against the current data and return the result.

        Parameters
        ----------
        selector:
            A dot-separated path, optionally followed by a ``?key=value``
            filter expression.  Examples::

                "name"
                "address.city"
                "users?role=admin"

        default_value:
            Returned when the path does not exist or resolves to ``None``.
            Defaults to ``UNSET`` (the sentinel), which means "no default".
        select_first:
            Determines if to return a List of matches or first available item.
            When none are found, returns ``UNSET``.
        cast:
            When provided and the resolved value is a ``dict``, the dict is
            passed as keyword arguments to this type/constructor.

        Returns
        -------
        Any
            The resolved value, ``default_value`` if the path is missing,
            or ``UNSET`` if no default was supplied and the path is missing.
        """
        tree = QueryParser.parse(selector)
        actions: List[Union[JIPath, JIMatch]] = JIQuery().transform(tree)

        cursor: Any = self.data
        result: Any = cursor

        for action in actions:
            if isinstance(action, JIPath):
                if isinstance(cursor, list):
                    # A bare path against a list is ambiguous — require ?key syntax.
                    if cursor is self.data:
                        raise TypeError(
                            f"Cannot use a bare path selector {'.'.join(action.keys)!r} "
                            "directly on a list root. "
                            "Use '?key' to pluck a field from each element, "
                            "or '?key=value' to filter."
                        )
                    # Cursor is already a list produced by a prior filter/pluck.
                    result = self._pluck_from_list(cursor, action)
                    cursor = result
                else:
                    cursor = self._move_cursor(cursor, action)
                    if cursor is UNSET:
                        return default_value
                    result = cursor

            elif isinstance(action, JIExistsFilter):
                result = self._apply_exists_filter(cursor, action)
                if result is UNSET:
                    return default_value
                cursor = result

            elif isinstance(action, JIPluck):
                result = self._apply_pluck(cursor, action)
                if result is UNSET:
                    return default_value
                cursor = result

            elif isinstance(action, JIMatch):
                result = self._apply_filter(cursor, action)
                cursor = result

        # Optionally follow a default tail selector when the result is a dict.
        if isinstance(result, dict) and self.default_tail:
            result = JsonInjester(result).get(self.default_tail)

        # Optionally cast a dict result to the requested type using the
        # shared instantiation helper so generics and models are handled.
        if cast is not None and isinstance(result, dict):
            # Preserve previous behaviour for arbitrary callables (e.g. lambdas)
            if callable(cast) and not isinstance(cast, type):
                result = cast(result)
            else:
                result = instantiate_type(cast, result)

        # Fall back to default_value when the resolved result is None.
        if result is None and default_value is not UNSET:
            return default_value
        
        if select_first is True and isinstance(result, list):
            return [*result, UNSET][0]
        
        return result

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _move_cursor(self, cursor: Any, path: JIPath) -> Any:
        """Walk *cursor* along each key in *path*.

        Returns ``UNSET`` if any key is absent or if an intermediate node
        is not a dict.
        """
        for key in path.keys:
            if not isinstance(cursor, dict):
                raise AttributeError(
                    f"Expected a dict while navigating key {key!r}, "
                    f"got {type(cursor).__name__!r}"
                )
            if key not in cursor:
                return UNSET
            cursor = cursor[key]
        return cursor

    def _pluck_from_list(self, lst: List[Any], path: JIPath) -> List[Any]:
        """Navigate *path* inside every dict element of *lst*, collecting hits."""
        results: List[Any] = []
        for item in lst:
            if isinstance(item, dict):
                value = self._move_cursor(item, path)
                if value is not UNSET:
                    results.append(value)
            elif isinstance(item, tuple) and len(item) == 2:
                # (key, value) pairs produced by _apply_filter on a dict-of-dicts
                _, item_dict = item
                if isinstance(item_dict, dict):
                    value = self._move_cursor(item_dict, path)
                    if value is not UNSET:
                        results.append(value)
        return results

    def _apply_exists_filter(self, cursor: Any, cond: JIExistsFilter) -> Any:
        """Return items/cursor where ``cond.key_path`` exists (no value check).

        * **dict** cursor – returns ``UNSET`` if key absent, else the cursor itself.
        * **list** cursor – returns only elements that contain ``key_path``.
        * Scalar – treat as missing, return ``UNSET``.
        """
        if isinstance(cursor, dict):
            value = self._move_cursor(cursor, cond.key_path)
            return UNSET if value is UNSET else cursor

        if isinstance(cursor, list):
            results = []
            for item in cursor:
                if isinstance(item, dict):
                    if self._move_cursor(item, cond.key_path) is not UNSET:
                        results.append(item)
            return results

        return UNSET

    def _apply_pluck(self, cursor: Any, pluck: JIPluck) -> Any:
        """Extract ``pluck.key_path`` value from each element.

        * **dict** cursor – navigates and returns ``UNSET`` if key absent.
        * **list** cursor – plucks from every element, collecting non-``UNSET`` hits.
        * Scalar – treat as missing, return ``UNSET``.
        """
        if isinstance(cursor, dict):
            return self._move_cursor(cursor, pluck.key_path)

        if isinstance(cursor, list):
            return self._pluck_from_list(cursor, pluck.key_path)

        return UNSET

    def _apply_filter(
        self,
        cursor: Any,
        match: JIMatch,
    ) -> List[Any]:
        """Return the subset of *cursor* items that satisfy *match*.

        Handles two container shapes:

        * **list of dicts** – each element is checked directly.
        * **dict of dicts** – each ``(key, value)`` pair is checked;
          matching pairs are returned as ``(key, value)`` tuples.
        """
        results: List[Any] = []

        for item in cursor:
            try:
                if isinstance(item, dict):
                    # cursor is a list; item is one element.
                    test_value = self._move_cursor(item, match.key_path)
                    if test_value == match.value:
                        results.append(item)
                elif isinstance(item, str):
                    # cursor is a dict; item is a key string.
                    test_value = self._move_cursor(cursor[item], match.key_path)
                    if test_value == match.value:
                        results.append((item, cursor[item]))
            except KeyError:
                # Key absent in this item — skip silently.
                pass

        return results