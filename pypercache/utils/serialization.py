"""Pickle-based persistence and zlib-backed dict compression."""

import concurrent.futures
import json
import pickle
import zlib
from pathlib import Path
from typing import Any, Dict

from .fs import ensure_dirs_exist


class PickleStore:
    """Static helpers for persisting arbitrary Python objects via ``pickle``."""

    @staticmethod
    def touch_file(default_obj: Any, filename: str) -> None:
        """Ensure *filename* exists, creating it with *default_obj* if absent.

        Args:
            default_obj: The object to pickle if the file does not yet exist.
            filename:    Path to the target pickle file.
        """
        if not Path(filename).exists():
            PickleStore.save_object(default_obj, filename)

    @staticmethod
    def save_object(obj: Any, filename: str) -> None:
        """Serialise *obj* to *filename* using pickle.

        Intermediate directories are created automatically.

        Args:
            obj:      The Python object to serialise.
            filename: Destination file path.
        """
        try:
            ensure_dirs_exist(filename)
            with open(filename, "wb") as fh:
                pickle.dump(obj, fh)
        except Exception as exc:
            print(f"Failed to save object to {filename}: {exc}")

    @staticmethod
    def load_object(filename: str) -> Any | None:
        """Deserialise and return the object stored in *filename*.

        Args:
            filename: Path to a pickle file created by :meth:`save_object`.

        Returns:
            The deserialised object, or ``None`` if the file is missing or
            an error occurs.
        """
        try:
            with open(filename, "rb") as fh:
                return pickle.load(fh)
        except FileNotFoundError:
            print(f"No such file: {filename}")
        except Exception as exc:
            print(f"Failed to load object from {filename}: {exc}")
        return None


class DataSerializer:
    """Compress, encode, and JSON-serialise dictionaries whose values are
    strings or nested dicts.

    Compression uses zlib; the compressed bytes are hex-encoded so they can
    be safely embedded in JSON. Serialisation and deserialisation of
    individual keys are parallelised with a ``ThreadPoolExecutor`` —
    ``zlib.compress`` releases the GIL, so threads achieve true parallelism
    here without the IPC overhead of a process pool.

    Supported value types: ``str``, ``dict``.
    """

    @staticmethod
    def compress_text(text: str, level: int = 6) -> str:
        """Compress *text* with zlib and return the result as a hex string.

        Args:
            text:  UTF-8 text to compress.
            level: zlib compression level (0–9). Default is 6.

        Returns:
            Hex-encoded compressed bytes.
        """
        compressed = zlib.compress(text.encode("utf-8"), level)
        return compressed.hex()

    @staticmethod
    def decompress_text(hex_encoded: str) -> str:
        """Decompress a hex string produced by :meth:`compress_text`.

        Args:
            hex_encoded: Hex-encoded compressed bytes.

        Returns:
            The original UTF-8 text.
        """
        compressed = bytes.fromhex(hex_encoded)
        return zlib.decompress(compressed).decode("utf-8")

    @staticmethod
    def serialize_dict(data: Dict[str, Any], level: int = 6) -> str:
        """Compress each value in *data* and serialise the result to a JSON string.

        Each value is replaced by a ``(type_tag, compressed_hex)`` tuple so
        that the correct deserialisation path can be chosen later.

        Args:
            data:  A flat dictionary whose values are ``str`` or ``dict``.
            level: zlib compression level passed to :meth:`compress_text`.

        Returns:
            A JSON string representing the compressed dictionary.

        Raises:
            ValueError: If a value's type is not ``str`` or ``dict``.
        """
        def compress_entry(key: str, value: Any) -> tuple[str, Any]:
            if isinstance(value, str):
                return key, ("str", DataSerializer.compress_text(value, level))
            elif isinstance(value, dict):
                return key, ("dict", DataSerializer.compress_text(json.dumps(value), level))
            else:
                raise ValueError(f"Serialisation not supported for type {type(value)}.")

        compressed: Dict[str, Any] = {}
        with concurrent.futures.ThreadPoolExecutor() as executor:
            futures = {
                executor.submit(compress_entry, key, value): key
                for key, value in data.items()
            }
            for future in concurrent.futures.as_completed(futures):
                key, result = future.result()
                compressed[key] = result

        return json.dumps(compressed)

    @staticmethod
    def deserialize_dict(json_str: str) -> Dict[str, Any]:
        """Deserialise a JSON string produced by :meth:`serialize_dict`.

        Each ``(type_tag, compressed_hex)`` pair is decompressed and
        converted back to its original type.

        Args:
            json_str: A JSON string as returned by :meth:`serialize_dict`.

        Returns:
            The reconstructed dictionary with original value types restored.
        """
        data: Dict[str, Any] = json.loads(json_str)

        def decompress_entry(key: str, value: Any) -> tuple[str, Any]:
            type_tag, compressed_hex = value
            if type_tag == "str":
                return key, DataSerializer.decompress_text(compressed_hex)
            elif type_tag == "dict":
                return key, json.loads(DataSerializer.decompress_text(compressed_hex))
            raise ValueError(f"Unknown type tag: {type_tag!r}")

        result: Dict[str, Any] = {}
        with concurrent.futures.ThreadPoolExecutor() as executor:
            futures = {
                executor.submit(decompress_entry, key, value): key
                for key, value in data.items()
            }
            for future in concurrent.futures.as_completed(futures):
                key, decompressed = future.result()
                result[key] = decompressed

        return result
