import json
import redis.asyncio as redis

# Connects to your running Docker Redis container (local_redis)
redis_client = redis.Redis(
    host="localhost",
    port=6379,
    db=0,
    decode_responses=True
)

async def get_cached_sql(tenant_id: int, prompt: str):
    """Retrieve cached SQL response from Redis if available."""
    try:
        key = f"cache:{tenant_id}:{prompt.strip().lower()}"
        cached = await redis_client.get(key)
        if cached:
            return json.loads(cached)
    except Exception as e:
        print(f"Redis Get Warning: {e}")
    return None

async def set_cached_sql(tenant_id: int, prompt: str, payload: dict, ttl: int = 3600):
    """Save generated SQL response into Redis with a 1-hour expiration."""
    try:
        key = f"cache:{tenant_id}:{prompt.strip().lower()}"
        await redis_client.setex(key, ttl, json.dumps(payload))
    except Exception as e:
        print(f"Redis Set Warning: {e}")