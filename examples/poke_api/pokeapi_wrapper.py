"""
pokeapi_wrapper.py
==================
An instructional PokeAPI wrapper that demonstrates four key patterns:

  1. Caching with PyperCache  – persistent file-backed cache with TTL.
  2. Hydrated data models     – raw JSON dicts are inflated into typed Python
                                objects using PyperCache's @Cache.cached
                                decorator and the cast= parameter on store().
  3. Soft rate-limiting       – a token-bucket helper that sleeps just long
                                enough to stay inside a configurable request
                                budget (requests / second).
  4. Automated data refresh   – a background thread wakes up periodically,
                                checks every cached key's freshness, and
                                re-fetches anything that has gone stale.

Usage
-----
    from pokeapi_wrapper import PokeAPIClient

    client = PokeAPIClient(cache_path="my_cache.pkl")
    client.start_auto_refresh()          # optional background refresher

    pikachu = client.get_pokemon("pikachu")
    print(pikachu.name, pikachu.base_experience)

    for move_ref in pikachu.moves[:3]:
        move = client.get_move(move_ref["move"]["name"])
        print(f"  {move.name}: power={move.power}, type={move.type_name}")

    client.stop_auto_refresh()
"""

from __future__ import annotations

import math
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Optional

import requests
from pypercache import Cache

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

BASE_URL = "https://pokeapi.co/api/v2"

# Default TTL values (in seconds).  PokeAPI data is essentially static, so
# these are generous; lower them to see the refresh mechanism in action.
TTL_POKEMON  = math.inf   # Never Expires  — core pokémon data (stats, types, moves)
TTL_MOVE     = math.inf   # Never Expires  — move metadata changes even less often
TTL_ABILITY  = math.inf   # Never Expires  — ability data is relatively static
TTL_TYPE     = math.inf   # Never Expires  — type chart is essentially immutable

# Soft rate-limit: we won't send more than this many requests per second.
# PokeAPI has no official hard limit but asks for fair use.
MAX_RPS = 5  # requests per second

# How often (seconds) the background thread scans for stale cache entries.
REFRESH_INTERVAL = 60  # check every minute


# ---------------------------------------------------------------------------
# Data models (hydrated from raw JSON via PyperCache's cast= mechanism)
# ---------------------------------------------------------------------------

@Cache.cached   # registers the class in PyperCache's ClassRepository so the                
@dataclass      # cache can reconstruct instances from stored dicts
class Pokemon:
    """Represents a single Pokémon resource returned by /api/v2/pokemon/{id}."""

    id: int
    name: str
    base_experience: int
    height: int          # in decimetres
    weight: int          # in hectograms
    types: list[dict]    # [{"slot": 1, "type": {"name": "fire", ...}}, ...]
    stats: list[dict]    # [{"base_stat": 45, "stat": {"name": "hp"}, ...}, ...]
    moves: list[dict]    # [{"move": {"name": "cut", ...}, "version_group_details": [...]}]
    sprite_url: Optional[str] = None

    # ---- convenience helpers -----------------------------------------------

    @property
    def type_names(self) -> list[str]:
        """Return a plain list of type names, e.g. ['fire', 'flying']."""
        return [t["type"]["name"] for t in self.types]

    @property
    def stats_dict(self) -> dict[str, int]:
        """Return base stats as {stat_name: value}."""
        return {s["stat"]["name"]: s["base_stat"] for s in self.stats}

    @classmethod
    def from_dict(cls, data: dict) -> "Pokemon":
        """Inflate a raw PokeAPI JSON dict into a Pokemon instance."""
        return cls(
            id              = data["id"],
            name            = data["name"],
            base_experience = data.get("base_experience") or 0,
            height          = data["height"],
            weight          = data["weight"],
            types           = data["types"],
            stats           = data["stats"],
            moves           = data["moves"],
            sprite_url      = (data.get("sprites") or {}).get("front_default"),
        )

    def __str__(self) -> str:
        types_str = "/".join(self.type_names)
        hp = self.stats_dict.get("hp", "?")
        return (
            f"#{self.id:03d} {self.name.title()} "
            f"[{types_str}] HP={hp} "
            f"({self.height/10:.1f}m, {self.weight/10:.1f}kg)"
        )


@Cache.cached
@dataclass
class Move:
    """Represents a single Move from /api/v2/move/{id}."""

    id: int
    name: str
    type_name: str        # "fire", "water", ...
    damage_class: str     # "physical", "special", "status"
    power: Optional[int]  # None for status moves
    accuracy: Optional[int]
    pp: int               # power points
    effect_chance: Optional[int]
    short_effect: str     # human-readable description

    @classmethod
    def from_dict(cls, data: dict) -> "Move":
        effect_entries = data.get("effect_entries") or []
        en_effect = next(
            (e for e in effect_entries if e.get("language", {}).get("name") == "en"),
            {}
        )
        return cls(
            id            = data["id"],
            name          = data["name"],
            type_name     = data["type"]["name"],
            damage_class  = data["damage_class"]["name"],
            power         = data.get("power"),
            accuracy      = data.get("accuracy"),
            pp            = data.get("pp") or 0,
            effect_chance = data.get("effect_chance"),
            short_effect  = en_effect.get("short_effect", ""),
        )

    def __str__(self) -> str:
        pwr = self.power if self.power is not None else "—"
        acc = f"{self.accuracy}%" if self.accuracy is not None else "—"
        return (
            f"{self.name.replace('-', ' ').title()} "
            f"[{self.type_name}/{self.damage_class}] "
            f"PWR={pwr} ACC={acc} PP={self.pp}"
        )


@Cache.cached
@dataclass
class Ability:
    """Represents an Ability from /api/v2/ability/{id}."""

    id: int
    name: str
    is_main_series: bool
    short_effect: str
    pokemon_names: list[str]   # Pokémon that can have this ability

    @classmethod
    def from_dict(cls, data: dict) -> "Ability":
        effect_entries = data.get("effect_entries") or []
        en_effect = next(
            (e for e in effect_entries if e.get("language", {}).get("name") == "en"),
            {}
        )
        pokemon = [p["pokemon"]["name"] for p in (data.get("pokemon") or [])]
        return cls(
            id             = data["id"],
            name           = data["name"],
            is_main_series = data.get("is_main_series", True),
            short_effect   = en_effect.get("short_effect", ""),
            pokemon_names  = pokemon,
        )

    def __str__(self) -> str:
        return f"{self.name.replace('-', ' ').title()}: {self.short_effect}"


# ---------------------------------------------------------------------------
# Rate limiter (token-bucket style, soft / sleep-based)
# ---------------------------------------------------------------------------

class SoftRateLimiter:
    """
    A simple token-bucket rate limiter that *sleeps* to stay under the limit
    rather than raising an exception.  This is the "soft" approach — it never
    drops a request, it just slows the caller down.

    Usage
    -----
        limiter = SoftRateLimiter(max_rps=5)
        limiter.acquire()   # blocks until a token is available
        # ... make the request ...

    Thread-safety
    -------------
    ``acquire()`` is protected by a ``threading.Lock`` so it can be called
    from multiple threads safely.
    """

    def __init__(self, max_rps: float = MAX_RPS) -> None:
        self._max_rps    = max_rps
        self._min_gap    = 1.0 / max_rps   # minimum seconds between requests
        self._last_call  = 0.0
        self._lock       = threading.Lock()

    def acquire(self) -> None:
        """Block until it is safe to fire another request."""
        with self._lock:
            now     = time.monotonic()
            elapsed = now - self._last_call
            wait    = self._min_gap - elapsed
            if wait > 0:
                time.sleep(wait)
            self._last_call = time.monotonic()


# ---------------------------------------------------------------------------
# Main client
# ---------------------------------------------------------------------------

class PokeAPIClient:
    """
    A caching PokeAPI v2 client backed by PyperCache.

    Key behaviours
    --------------
    * **Cache-first fetching** — ``get_pokemon()``, ``get_move()``, and
      ``get_ability()`` check the cache before hitting the network.
      On a cache hit that is still fresh (within TTL) the network is never
      touched.

    * **Hydrated returns** — every public getter returns a typed dataclass
      (``Pokemon``, ``Move``, or ``Ability``) rather than a raw ``dict``.
      PyperCache's ``cast=`` parameter stores the type alongside the data so
      ``get_object()`` can reconstruct the instance on subsequent calls.

    * **Soft rate-limiting** — all HTTP calls go through ``_fetch()``, which
      first asks the ``SoftRateLimiter`` for permission, so parallel or rapid
      calls are automatically throttled.

    * **Auto-refresh** — ``start_auto_refresh()`` spins up a daemon thread
      that calls ``_refresh_stale()`` every ``REFRESH_INTERVAL`` seconds.
      Stale entries are silently re-fetched in the background; callers always
      get the freshest data available.
    """

    def __init__(
        self,
        cache_path: str   = "pokeapi_cache.pkl",
        max_rps: float    = MAX_RPS,
        session: Optional[requests.Session] = None,
    ) -> None:
        # PyperCache persists data across process restarts.  Use a .pkl file
        # (msgpack-backed) for speed, or swap to .json for human readability.
        self._cache    = Cache(filepath=cache_path)
        self._limiter  = SoftRateLimiter(max_rps=max_rps)
        self._session  = session or requests.Session()

        # Background refresh bookkeeping
        self._refresh_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

        # Map cache-key prefixes → (fetcher_callable, TTL)
        # Used by the auto-refresh loop to know how to re-fetch any stale key.
        self._key_registry: dict[str, tuple] = {}  # key → (fetch_fn, args, ttl)

    # -----------------------------------------------------------------------
    # Internal helpers
    # -----------------------------------------------------------------------

    def _make_key(self, resource: str, identifier: str | int) -> str:
        """Build a deterministic, unique cache key."""
        return f"{resource}:{str(identifier).lower()}"

    def _fetch(self, url: str) -> dict:
        """
        Execute a rate-limited GET request and return the parsed JSON.

        This is the single choke-point for all network I/O.  Every public
        method routes its HTTP calls through here so the rate-limiter and
        error handling are applied consistently.
        """
        self._limiter.acquire()          # <- soft rate-limit happens here
        response = self._session.get(url, timeout=10)
        response.raise_for_status()
        return response.json()

    def _store_and_return(
        self,
        key: str,
        data: dict,
        model_cls: type,
        ttl: float,
    ) -> Any:
        """
        Store ``data`` in the cache under ``key`` with the given TTL, then
        inflate it into ``model_cls`` and return the hydrated instance.

        The ``cast=model_cls`` argument tells PyperCache which class to use
        when reconstructing the object from stored data via ``get_object()``.
        """
        self._cache.store(key, data, expiry=ttl, cast=model_cls)
        return model_cls.from_dict(data)

    # -----------------------------------------------------------------------
    # Public getters (cache-first)
    # -----------------------------------------------------------------------

    def get_pokemon(self, identifier: str | int) -> Pokemon:
        """
        Fetch a Pokémon by name or Pokédex number.

        Returns a cached ``Pokemon`` instance if the entry is fresh; otherwise
        fetches from the network, updates the cache, and returns the new object.

        Args:
            identifier: Pokémon name (e.g. "pikachu") or national dex id (25).

        Returns:
            A hydrated ``Pokemon`` dataclass instance.
        """
        key = self._make_key("pokemon", identifier)

        # Cache hit — still within TTL?
        if self._cache.is_data_fresh(key):
            # get_object() reconstructs the Pokemon from cached data using
            # the type that was registered via cast= at store time.
            return self._cache.get_object(key)

        # Cache miss (or stale) — go to the network
        url  = f"{BASE_URL}/pokemon/{identifier}"
        data = self._fetch(url)

        # Register for auto-refresh
        self._key_registry[key] = (self.get_pokemon, (identifier,), TTL_POKEMON)

        return self._store_and_return(key, data, Pokemon, TTL_POKEMON)

    def get_move(self, identifier: str | int) -> Move:
        """
        Fetch a move by name or id.

        Args:
            identifier: Move name (e.g. "thunderbolt") or id.

        Returns:
            A hydrated ``Move`` dataclass instance.
        """
        key = self._make_key("move", identifier)

        if self._cache.is_data_fresh(key):
            return self._cache.get_object(key)

        url  = f"{BASE_URL}/move/{identifier}"
        data = self._fetch(url)

        self._key_registry[key] = (self.get_move, (identifier,), TTL_MOVE)

        return self._store_and_return(key, data, Move, TTL_MOVE)

    def get_ability(self, identifier: str | int) -> Ability:
        """
        Fetch an ability by name or id.

        Args:
            identifier: Ability name (e.g. "intimidate") or id.

        Returns:
            A hydrated ``Ability`` dataclass instance.
        """
        key = self._make_key("ability", identifier)

        if self._cache.is_data_fresh(key):
            return self._cache.get_object(key)

        url  = f"{BASE_URL}/ability/{identifier}"
        data = self._fetch(url)

        self._key_registry[key] = (self.get_ability, (identifier,), TTL_ABILITY)

        return self._store_and_return(key, data, Ability, TTL_ABILITY)

    def get_pokemon_list(self, limit: int = 20, offset: int = 0) -> list[dict]:
        """
        Return a paginated list of Pokémon name/url stubs.

        This endpoint is cached under a composite key so different page
        requests don't collide.  The list response is lightweight (names +
        URLs only) so it's returned as plain dicts rather than hydrated models.

        Args:
            limit:  Number of results (max 100 per request).
            offset: Starting position in the full list.

        Returns:
            List of {"name": str, "url": str} dicts.
        """
        key = f"pokemon_list:{offset}:{limit}"

        if self._cache.is_data_fresh(key):
            record = self._cache.get(key)
            return record.data.get("results", [])

        url  = f"{BASE_URL}/pokemon?limit={limit}&offset={offset}"
        data = self._fetch(url)
        self._cache.store(key, data, expiry=TTL_POKEMON)

        return data.get("results", [])

    # -----------------------------------------------------------------------
    # Auto-refresh
    # -----------------------------------------------------------------------

    def _refresh_stale(self) -> None:
        """
        Scan the key registry and re-fetch any entry that has gone stale.

        Called by the background thread on a fixed interval.  Each stale entry
        is refreshed by invoking the same public getter that originally fetched
        it, which applies the rate-limiter so the refresh burst stays polite.
        """
        for key, (fetch_fn, args, _ttl) in list(self._key_registry.items()):
            if self._stop_event.is_set():
                return
            if not self._cache.is_data_fresh(key):
                print(f"[AutoRefresh] Refreshing stale key: {key}")
                try:
                    fetch_fn(*args)
                except Exception as exc:
                    # Don't crash the background thread on transient errors;
                    # the stale (but still present) entry remains usable.
                    print(f"[AutoRefresh] Failed to refresh {key}: {exc}")

    def _refresh_loop(self) -> None:
        """Entry point for the background daemon thread."""
        while not self._stop_event.wait(timeout=REFRESH_INTERVAL):
            self._refresh_stale()

    def start_auto_refresh(self) -> None:
        """
        Start the background refresh daemon thread.

        The thread is a *daemon*, meaning it will not prevent the process from
        exiting.  Call ``stop_auto_refresh()`` for an orderly shutdown.
        """
        if self._refresh_thread and self._refresh_thread.is_alive():
            return   # already running

        self._stop_event.clear()
        self._refresh_thread = threading.Thread(
            target=self._refresh_loop,
            name="PokeAPIAutoRefresh",
            daemon=True,   # won't block process exit
        )
        self._refresh_thread.start()
        print(f"[AutoRefresh] Started (interval={REFRESH_INTERVAL}s)")

    def stop_auto_refresh(self) -> None:
        """Signal the background thread to stop and wait for it to exit."""
        self._stop_event.set()
        if self._refresh_thread:
            self._refresh_thread.join(timeout=5)
        print("[AutoRefresh] Stopped")

    def cache_stats(self) -> dict:
        """
        Return a summary of how many keys are in the registry and how many
        are currently fresh.  Useful for debugging or monitoring dashboards.
        """
        total  = len(self._key_registry)
        fresh  = sum(
            1 for k in self._key_registry if self._cache.is_data_fresh(k)
        )
        return {"total_tracked": total, "fresh": fresh, "stale": total - fresh}
