import os
import asyncpg
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from app.llm_provider import generate_sql
from app.guardrails import SQLGuardrail
from app.cache import get_cached_sql, set_cached_sql

app = FastAPI(title="AI Text-to-SQL Engine")

# CORS Middleware for React Frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

MOCK_SCHEMA = "TABLE users(id, tenant_id, full_name); TABLE products(id, tenant_id, product_name, category, price); TABLE sales(id, tenant_id, user_id, product_id, quantity, total_amount, transaction_date);"

# Database Connection String
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:password@localhost:5432/enterprise_db")

# Request Schemas
class QueryReq(BaseModel):
    user_prompt: str
    tenant_id: int = 1

class ExecReq(BaseModel):
    sql_query: str
    tenant_id: int = 1  # 👈 Optional tenant_id so extra fields don't throw unexpected errors

@app.get("/health")
async def health():
    return {"status": "ok"}

@app.post("/generate")
async def generate(req: QueryReq):
    # 1. Check Redis Cache
    cached_result = await get_cached_sql(req.tenant_id, req.user_prompt)
    if cached_result:
        cached_result["cached"] = True
        return cached_result

    # 2. Generate SQL via LLM if cache miss
    raw_sql = await generate_sql(req.user_prompt, MOCK_SCHEMA)

    # 3. Security: AST-based Tenant Isolation Injection
    secure_sql = SQLGuardrail.enforce_tenant_isolation(raw_sql, req.tenant_id)

    # 4. Security: Guardrail Check
    is_safe, msg = SQLGuardrail.is_safe_query(secure_sql)

    response_payload = {
        "sql": secure_sql,
        "is_safe": is_safe,
        "guardrail_msg": msg,
        "requires_approval": not is_safe or "users" in secure_sql.lower(),
        "cached": False
    }

    # 5. Store in Redis
    if is_safe:
        await set_cached_sql(req.tenant_id, req.user_prompt, response_payload)

    return response_payload


@app.post("/execute")
async def execute(req: ExecReq):
    # 1. Double-check Guardrail Safety before touching DB
    is_safe, msg = SQLGuardrail.is_safe_query(req.sql_query)
    if not is_safe:
        raise HTTPException(status_code=400, detail=f"Guardrail Rejection: {msg}")

    # 2. Execute SQL against PostgreSQL
    try:
        conn = await asyncpg.connect(DATABASE_URL)
        rows = await conn.fetch(req.sql_query)
        await conn.close()
        
        # Format database records as JSON
        result = [dict(row) for row in rows]
        return {"status": "success", "data": result}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Database Execution Error: {str(e)}")