from cachetools import TTLCache

webhook_event_cache = TTLCache(maxsize=2000, ttl=600)
