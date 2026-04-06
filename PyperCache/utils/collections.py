"""Collection utilities."""

from collections import defaultdict
from typing import Any


def convert_defaultdict_to_dict(data: Any) -> Any:
    """Recursively convert nested ``defaultdict`` instances to plain ``dict``.

    Also traverses nested lists so that defaultdicts at any depth are converted.

    Args:
        data: The object to convert. Non-dict/list values are returned as-is.

    Returns:
        The same structure with every ``defaultdict`` replaced by a ``dict``.
    """
    if isinstance(data, defaultdict):
        data = dict(data)

    if isinstance(data, dict):
        for key, value in data.items():
            data[key] = convert_defaultdict_to_dict(value)
    elif isinstance(data, list):
        for i, item in enumerate(data):
            data[i] = convert_defaultdict_to_dict(item)

    return data
