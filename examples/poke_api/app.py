"""
app.py
======
A demonstration application built on top of ``pokeapi_wrapper.py``.

What this app shows
-------------------
* How to instantiate and configure the ``PokeAPIClient``.
* How cached fetches behave: first call hits the network, subsequent calls
  are served from the cache with no HTTP round-trip.
* How TTL expiry and the auto-refresh daemon interact — we deliberately shorten
  the TTL in the demo client so you can *watch* entries go stale and refresh.
* How hydrated data models (``Pokemon``, ``Move``, ``Ability``) let you write
  clean, attribute-based code instead of wrestling with raw JSON dicts.
* How the ``CacheRecord.query`` dotted-path accessor works for ad-hoc reads.

Run it
------
    python app.py

Expected output (abbreviated):
    ══════════════════════════════════════════
     PokéAPI Wrapper Demo  (PyperCache + TTL)
    ══════════════════════════════════════════
    ...
"""

import time
from datetime import datetime

from pokeapi_wrapper import PokeAPIClient, Pokemon, Move, Ability
from pypercache import Cache  # for the raw-record query demo

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

LINE  = "─" * 54
DLINE = "═" * 54


def banner(text: str) -> None:
    print(f"\n{DLINE}\n  {text}\n{DLINE}")


def section(text: str) -> None:
    print(f"\n{LINE}\n  {text}\n{LINE}")


def ts() -> str:
    """Return a short HH:MM:SS timestamp for log messages."""
    return datetime.now().strftime("%H:%M:%S")


# ---------------------------------------------------------------------------
# 1 — Basic usage: get a Pokémon, print its data model
# ---------------------------------------------------------------------------

def demo_basic_fetch(client: PokeAPIClient) -> Pokemon:
    section("1 · Basic fetch  →  Pokémon data model")

    print(f"[{ts()}] Fetching pikachu (cache miss expected) …")
    t0 = time.perf_counter()
    pika = client.get_pokemon("pikachu")
    elapsed = time.perf_counter() - t0

    print(f"[{ts()}] Network fetch took {elapsed*1000:.0f} ms")
    print(f"\n  {pika}")
    print(f"  sprite : {pika.sprite_url}")
    print(f"  types  : {pika.type_names}")
    print(f"  stats  : {pika.stats_dict}")

    # Second call — should come from cache instantly
    print(f"\n[{ts()}] Fetching pikachu again (cache hit expected) …")
    t0 = time.perf_counter()
    pika2 = client.get_pokemon("pikachu")
    elapsed = time.perf_counter() - t0
    print(f"[{ts()}] Cache hit took {elapsed*1000:.2f} ms  ← near-zero latency")
    assert pika.id == pika2.id, "Cache returned wrong record!"

    return pika


# ---------------------------------------------------------------------------
# 2 — Follow references: pull each of Pikachu's first N moves
# ---------------------------------------------------------------------------

def demo_follow_references(client: PokeAPIClient, pika: Pokemon, n: int = 4) -> None:
    section(f"2 · Follow references  →  first {n} moves")

    # The Pokemon.moves list holds lightweight stubs like:
    #   {"move": {"name": "mega-punch", "url": "..."}, "version_group_details": [...]}
    # We resolve each stub into a full Move object via get_move().
    for entry in pika.moves[:n]:
        move_name = entry["move"]["name"]
        move: Move = client.get_move(move_name)
        print(f"  {move}")


# ---------------------------------------------------------------------------
# 3 — Abilities
# ---------------------------------------------------------------------------

def demo_abilities(client: PokeAPIClient) -> None:
    section("3 · Ability hydration")

    for name in ("static", "lightning-rod"):
        ability: Ability = client.get_ability(name)
        print(f"  {ability}")
        if ability.pokemon_names:
            sample = ", ".join(ability.pokemon_names[:5])
            print(f"    Pokémon that can have it: {sample} …")


# ---------------------------------------------------------------------------
# 4 — Paginated list
# ---------------------------------------------------------------------------

def demo_list(client: PokeAPIClient) -> None:
    section("4 · Paginated Pokémon list  (stubs only)")

    stubs = client.get_pokemon_list(limit=10, offset=0)
    print(f"  First 10 Pokémon:")
    for stub in stubs:
        print(f"    • {stub['name']}")

    # Second call to the same page should be cached
    print(f"\n  Requesting the same page again …")
    t0    = time.perf_counter()
    _     = client.get_pokemon_list(limit=10, offset=0)
    print(f"  Served from cache in {(time.perf_counter()-t0)*1000:.2f} ms")


# ---------------------------------------------------------------------------
# 5 — Raw CacheRecord query (dotted-path accessor)
# ---------------------------------------------------------------------------

def demo_cache_query(client: PokeAPIClient) -> None:
    section("5 · CacheRecord.query  →  dotted-path access")

    # Retrieve the raw record (not the hydrated model) to show the query API.
    record = client._cache.get("pokemon:pikachu")

    # Dotted-path lookup — walks nested dicts
    base_exp = record.query.get("base_experience")
    height   = record.query.get("height")
    name     = record.query.get("name")

    print(f"  record.query.get('name')             → {name}")
    print(f"  record.query.get('base_experience')  → {base_exp}")
    print(f"  record.query.get('height')           → {height} dm")
    print(f"  record.query.has('sprites')          → {record.query.has('sprites')}")
    print(f"  record.is_data_stale                 → {record.is_data_stale}")


# ---------------------------------------------------------------------------
# 6 — TTL & auto-refresh demo
# ---------------------------------------------------------------------------

def demo_ttl_and_autorefresh(client: PokeAPIClient) -> None:
    section("6 · TTL expiry + auto-refresh")

    # Use a very short TTL so we can watch entries go stale in seconds.
    SHORT_TTL = 5  # seconds

    # Manually store a pikachu record with a tiny TTL to simulate staleness.
    # In production the TTL constants in pokeapi_wrapper.py (hours) are used.
    key  = "pokemon:demo-ttl"
    data = {"id": 9999, "name": "demo-ttl-pokemon", "types": [], "stats": [],
            "moves": [], "height": 0, "weight": 0, "base_experience": 0,
            "sprites": {"front_default": None}}

    client._cache.store(key, data, expiry=SHORT_TTL, cast=Pokemon)
    print(f"  Stored '{key}' with TTL={SHORT_TTL}s")
    print(f"  is_data_fresh → {client._cache.is_data_fresh(key)}  (should be True)")

    print(f"\n  Sleeping {SHORT_TTL + 1}s to let TTL expire …")
    time.sleep(SHORT_TTL + 1)

    print(f"  is_data_fresh → {client._cache.is_data_fresh(key)}  (should be False)")
    record = client._cache.get(key)
    print(f"  is_data_stale → {record.is_data_stale}  (should be True)")

    # The auto-refresh thread in the real client would now silently re-fetch.
    # Here we call the refresh method directly to show the mechanics.
    print(f"\n  Manually triggering stale-entry refresh …")
    client._refresh_stale()   # in production this runs in the background thread


# ---------------------------------------------------------------------------
# 7 — Cache stats dashboard
# ---------------------------------------------------------------------------

def demo_stats(client: PokeAPIClient) -> None:
    section("7 · Cache stats")

    stats = client.cache_stats()
    print(f"  Tracked keys  : {stats['total_tracked']}")
    print(f"  Fresh entries : {stats['fresh']}")
    print(f"  Stale entries : {stats['stale']}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    banner("PokéAPI Wrapper Demo  (PyperCache + TTL + Auto-refresh)")

    # -----------------------------------------------------------------------
    # Instantiate the client.
    #
    # cache_path  – persistent file; delete it to start fresh
    # max_rps     – soft rate-limit, requests/second
    # -----------------------------------------------------------------------
    client = PokeAPIClient(
        cache_path="pokeapi_demo_cache.json",
        max_rps=5,
    )

    # Start the background refresh daemon.
    # In this demo the refresh interval is 60 s (see REFRESH_INTERVAL in the
    # wrapper), so you won't see it fire during the short demo run — but it
    # *is* running.  Lower REFRESH_INTERVAL in the wrapper to see live output.
    client.start_auto_refresh()

    try:
        pika = demo_basic_fetch(client)
        demo_follow_references(client, pika, n=4)
        demo_abilities(client)
        demo_list(client)
        demo_cache_query(client)
        demo_ttl_and_autorefresh(client)
        demo_stats(client)

    finally:
        # Always stop the background thread cleanly.
        client.stop_auto_refresh()

    
    banner("Demo complete  ✓")
    print(f"  The cache file '{client._cache.storage.filepath}' persists on disk.")
    print("  Re-run app.py immediately — every fetch will be a cache hit.\n")


if __name__ == "__main__":
    main()
