import time

class SimpleTTLCache:
    def __init__(self, ttl_seconds: int = 60):
        self.ttl = ttl_seconds
        self.cache = {}

    def get(self, key):
        if key in self.cache:
            val, expiry = self.cache[key]
            if time.time() < expiry:
                return val
            else:
                del self.cache[key]
        return None

    def set(self, key, value):
        self.cache[key] = (value, time.time() + self.ttl)

    def clear(self):
        self.cache.clear()


# Global cache instances
specialties_cache = SimpleTTLCache(ttl_seconds=300)
slots_cache = SimpleTTLCache(ttl_seconds=120)


def invalidate_availabilities_cache():
    """Clear all cached specialties and doctor slots."""
    specialties_cache.clear()
    slots_cache.clear()
