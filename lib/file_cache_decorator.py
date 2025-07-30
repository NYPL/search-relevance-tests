import json
import pickle
from functools import wraps


def cache_path(func):
    return f"/tmp/.cache-{func.__name__}"


def init_cache(func):
    try:
        with open(cache_path(func), "rb") as f:
            func.cache = pickle.load(f)
    except FileNotFoundError:
        func.cache = {}


def persist_cache(func):
    with open(cache_path(func), "wb") as f:
        pickle.dump(func.cache, f)


def file_cached(func):
    init_cache(func)

    @wraps(func)
    def wrapper(*args, **kwargs):
        key = args

        # Allow caching override when no_cache=True passed to wrapped function:
        if kwargs.get("no_cache", False):
            return func(*args)

        try:
            val = func.cache[key]
            return val
        except KeyError:
            func.cache[key] = result = func(*args)
            persist_cache(func)
            return result

    return wrapper
