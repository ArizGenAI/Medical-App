"""
LangChain LLM caching.

The assignment requires BOTH cache types plus a clear explanation of the difference.

  InMemoryCache  — stored in RAM. Fastest. Lost when the process restarts.
  SQLiteCache    — stored in a .db file on disk. Slightly slower. Survives restart.

Usage:
    from langchain.globals import set_llm_cache
    set_llm_cache(...)   # register ONCE; LangChain checks the cache before each call

Submitting the same form twice with caching on should be faster the second time
because the identical prompt hits the cache instead of OpenAI.
"""

from __future__ import annotations

from langchain_community.cache import InMemoryCache, SQLiteCache

# LangChain 1.x: langchain_core.globals — older 0.x: langchain.globals
try:
    from langchain_core.globals import set_llm_cache
except ImportError:  # pragma: no cover
    from langchain.globals import set_llm_cache

from src.config import SQLITE_CACHE_PATH

CACHE_HELP = {
    "off": (
        "Caching is off. Every submit calls the OpenAI API (useful when you want "
        "a fresh answer every time)."
    ),
    "memory": (
        "InMemoryCache: results live in RAM only. Same prompt in this session is "
        "instant; restarting Streamlit clears the cache."
    ),
    "sqlite": (
        "SQLiteCache: results are saved to a local database file, so identical "
        "prompts stay fast even after you restart the app."
    ),
}


def configure_cache(mode: str) -> str:
    """
    Register the selected LangChain cache globally.

    Call this before creating ChatOpenAI / running a chain.
    Returns a short human-readable status string for the UI.
    """
    mode = (mode or "off").lower()

    if mode == "memory":
        set_llm_cache(InMemoryCache())
        return CACHE_HELP["memory"]

    if mode == "sqlite":
        SQLITE_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        set_llm_cache(SQLiteCache(database_path=str(SQLITE_CACHE_PATH)))
        return CACHE_HELP["sqlite"]

    # langchain allows None to disable caching
    set_llm_cache(None)
    return CACHE_HELP["off"]
