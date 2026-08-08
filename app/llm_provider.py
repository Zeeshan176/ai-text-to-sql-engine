import httpx
from app.config import settings

async def generate_sql(prompt: str, schema_context: str) -> str:
    system_prompt = f"""You are an expert PostgreSQL DBA. 
Translate the user prompt into valid SQL based on this schema:
{schema_context}

CRITICAL RULES:
1. Respond ONLY with raw, executable SQL. 
2. Do NOT say 'Here is the SQL' or add any conversational text.
3. Do NOT use markdown formatting or backticks.
4. Start your response directly with SELECT."""

    if settings.ENVIRONMENT == "local":
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{settings.OLLAMA_BASE_URL}/api/generate",
                json={"model": "llama3", "prompt": f"{system_prompt}\nPrompt: {prompt}", "stream": False},
                timeout=300.0
            )
            return resp.json().get("response", "").strip()
    else:
        from groq import AsyncGroq
        client = AsyncGroq(api_key=settings.GROQ_API_KEY)
        res = await client.chat.completions.create(
            messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": prompt}],
            model="llama-3.1-8b-instant"
        )
        return res.choices[0].message.content.strip()