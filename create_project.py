import os

files = {
    "docker-compose.yml": """version: '3.8'
services:
  postgres:
    image: pgvector/pgvector:pg16
    container_name: local_postgres
    environment:
      POSTGRES_USER: user
      POSTGRES_PASSWORD: password
      POSTGRES_DB: enterprise_db
    ports:
      - "5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data

  redis:
    image: redis:alpine
    container_name: local_redis
    ports:
      - "6379:6379"

volumes:
  pgdata:
""",
    "schema.sql": """CREATE EXTENSION IF NOT EXISTS vector;

DROP TABLE IF EXISTS sales CASCADE;
DROP TABLE IF EXISTS products CASCADE;
DROP TABLE IF EXISTS users CASCADE;
DROP TABLE IF EXISTS tenants CASCADE;

CREATE TABLE tenants (
    id SERIAL PRIMARY KEY,
    company_name VARCHAR(100) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    tenant_id INT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    full_name VARCHAR(100) NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    role VARCHAR(50) DEFAULT 'member',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE products (
    id SERIAL PRIMARY KEY,
    tenant_id INT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    product_name VARCHAR(150) NOT NULL,
    category VARCHAR(50) NOT NULL,
    price DECIMAL(10, 2) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE sales (
    id SERIAL PRIMARY KEY,
    tenant_id INT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    user_id INT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    product_id INT NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    quantity INT NOT NULL CHECK (quantity > 0),
    total_amount DECIMAL(12, 2) NOT NULL,
    status VARCHAR(20) DEFAULT 'completed',
    transaction_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_users_tenant ON users(tenant_id);
CREATE INDEX idx_products_tenant ON products(tenant_id);
CREATE INDEX idx_sales_tenant ON sales(tenant_id);
""",
    "requirements.txt": """fastapi
uvicorn
asyncpg
sqlglot
httpx
pydantic-settings
groq
faker
python-dotenv
""",
    ".env": """ENVIRONMENT=local
POSTGRES_URI=postgresql://user:password@localhost:5432/enterprise_db
REDIS_URL=redis://localhost:6379
OLLAMA_BASE_URL=http://localhost:11434
GROQ_API_KEY=
""",
    "app/__init__.py": "",
    "app/config.py": """import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "local")
    POSTGRES_URI: str = os.getenv("POSTGRES_URI", "postgresql://user:password@localhost:5432/enterprise_db")
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379")
    OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")

    class Config:
        env_file = ".env"

settings = Settings()
""",
    "app/guardrails.py": """import sqlglot
from sqlglot import exp

class SQLGuardrail:
    @staticmethod
    def is_safe_query(sql_query: str) -> tuple[bool, str]:
        try:
            parsed = sqlglot.parse(sql_query)
            for stmt in parsed:
                if stmt is None: continue
                if not isinstance(stmt, exp.Select):
                    return False, f"Forbidden query type: {stmt.key.upper()}. Only SELECT queries allowed."
            return True, "Query passed security checks."
        except Exception as e:
            return False, f"SQL Parsing Error: {str(e)}"
""",
    "app/llm_provider.py": """import httpx
from app.config import settings

async def generate_sql(prompt: str, schema_context: str) -> str:
    system_prompt = f"You are an expert PostgreSQL DBA. Translate to valid SQL based on schema:\\n{schema_context}\\nRespond ONLY with raw SQL."
    if settings.ENVIRONMENT == "local":
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{settings.OLLAMA_BASE_URL}/api/generate",
                json={"model": "llama3", "prompt": f"{system_prompt}\\nPrompt: {prompt}", "stream": False},
                timeout=60.0
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
""",
    "app/main.py": """from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import asyncpg
from app.config import settings
from app.guardrails import SQLGuardrail
from app.llm_provider import generate_sql

app = FastAPI(title="Text-to-SQL Engine")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

MOCK_SCHEMA = "TABLE users(id, tenant_id, full_name); TABLE products(id, tenant_id, product_name, price); TABLE sales(id, tenant_id, user_id, product_id, quantity, total_amount, transaction_date);"

class QueryReq(BaseModel):
    user_prompt: str
    tenant_id: int

class ExecReq(BaseModel):
    sql_query: str
    tenant_id: int

@app.get("/health")
def health(): return {"status": "online", "environment": settings.ENVIRONMENT}

@app.post("/generate")
async def generate(req: QueryReq):
    raw_sql = await generate_sql(req.user_prompt, MOCK_SCHEMA)
    clean_sql = raw_sql.replace("```sql", "").replace("```", "").strip()
    is_safe, msg = SQLGuardrail.is_safe_query(clean_sql)
    return {
        "generated_sql": clean_sql,
        "is_safe": is_safe,
        "guardrail_message": msg,
        "requires_human_approval": not is_safe or "users" in clean_sql.lower()
    }

@app.post("/execute")
async def execute(req: ExecReq):
    is_safe, msg = SQLGuardrail.is_safe_query(req.sql_query)
    if not is_safe: raise HTTPException(400, detail=msg)
    conn = await asyncpg.connect(settings.POSTGRES_URI)
    records = await conn.fetch(req.sql_query)
    await conn.close()
    return {"data": [dict(r) for r in records]}
""",
    "seed_data.py": """import asyncio, asyncpg, random
from datetime import datetime, timedelta
from faker import Faker

fake = Faker()
URI = "postgresql://user:password@localhost:5432/enterprise_db"

async def seed():
    conn = await asyncpg.connect(URI)
    with open("schema.sql") as f: await conn.execute(f.read())
    
    t1 = await conn.fetchval("INSERT INTO tenants (company_name) VALUES ('Acme Corp') RETURNING id")
    t2 = await conn.fetchval("INSERT INTO tenants (company_name) VALUES ('Global Tech') RETURNING id")
    
    for t_id in [t1, t2]:
        prods = [(await conn.fetchval("INSERT INTO products (tenant_id, product_name, category, price) VALUES ($1,$2,$3,$4) RETURNING id", t_id, fake.word().capitalize(), "Software", round(random.uniform(50,500), 2)), round(random.uniform(50,500), 2)) for _ in range(5)]
        users = [await conn.fetchval("INSERT INTO users (tenant_id, full_name, email) VALUES ($1,$2,$3) RETURNING id", t_id, fake.name(), fake.unique.email()) for _ in range(10)]
        
        sales = []
        for _ in range(300):
            p_id, price = random.choice(prods)
            sales.append((t_id, random.choice(users), p_id, 2, price*2, "completed", datetime.now() - timedelta(days=random.randint(0,180))))
        
        await conn.executemany("INSERT INTO sales (tenant_id, user_id, product_id, quantity, total_amount, status, transaction_date) VALUES ($1,$2,$3,$4,$5,$6,$7)", sales)
    
    print("Database Seeded Successfully!")
    await conn.close()

if __name__ == "__main__": asyncio.run(seed())
""",
    "frontend/package.json": """{
  "name": "frontend",
  "private": true,
  "version": "0.0.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "vite build"
  },
  "dependencies": {
    "axios": "^1.6.0",
    "react": "^18.2.0",
    "react-dom": "^18.2.0",
    "recharts": "^2.10.0"
  },
  "devDependencies": {
    "@vitejs/plugin-react": "^4.2.0",
    "vite": "^5.0.0"
  }
}
""",
    "frontend/vite.config.js": """import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: { port: 5173 }
})
""",
    "frontend/index.html": """<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <title>AI Data Analyst</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.jsx"></script>
  </body>
</html>
""",
    "frontend/src/main.jsx": """import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App.jsx'

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
)
""",
    "frontend/src/App.jsx": """import React, { useState } from 'react';
import axios from 'axios';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts';

const API = 'http://localhost:8000';

export default function App() {
  const [tenantId, setTenantId] = useState(1);
  const [prompt, setPrompt] = useState('SELECT * FROM sales WHERE tenant_id = 1 LIMIT 10;');
  const [data, setData] = useState(null);
  const [results, setResults] = useState(null);

  const handleGen = async () => {
    const res = await axios.post(`${API}/generate`, { user_prompt: prompt, tenant_id: parseInt(tenantId) });
    setData(res.data);
  };

  const handleExec = async () => {
    const res = await axios.post(`${API}/execute`, { sql_query: data.generated_sql, tenant_id: parseInt(tenantId) });
    setResults(res.data.data);
  };

  return (
    <div style={{ padding: 30, fontFamily: 'sans-serif', maxWidth: 800, margin: '0 auto' }}>
      <h2>🤖 Multi-Tenant AI Data Analyst</h2>
      <div>
        <label>Tenant Scope: </label>
        <select value={tenantId} onChange={e => setTenantId(e.target.value)}>
          <option value={1}>Tenant 1 (Acme)</option>
          <option value={2}>Tenant 2 (Global Tech)</option>
        </select>
      </div>
      <br />
      <textarea value={prompt} onChange={e => setPrompt(e.target.value)} rows={3} style={{ width: '100%' }} />
      <br />
      <button onClick={handleGen} style={{ marginTop: 10, padding: '8px 16px' }}>Generate SQL</button>

      {data && (
        <div style={{ marginTop: 20, background: '#f4f4f4', padding: 15, borderRadius: 5 }}>
          <h4>Generated SQL:</h4>
          <code>{data.generated_sql}</code>
          <p>Safe: {data.is_safe ? '✅' : '❌'} | HITL Approval: {data.requires_human_approval ? '⚠️ Required' : '⚡ Auto'}</p>
          <button onClick={handleExec} style={{ background: '#28a745', color: '#fff', border: 'none', padding: '8px 16px' }}>Approve & Execute</button>
        </div>
      )}

      {results && (
        <div style={{ marginTop: 20 }}>
          <h4>Execution Results ({results.length} rows):</h4>
          {results.length > 0 && (
            <div style={{ height: 250, width: '100%' }}>
              <ResponsiveContainer>
                <BarChart data={results}>
                  <XAxis dataKey={Object.keys(results[0])[0]} />
                  <YAxis />
                  <Tooltip />
                  <Bar dataKey={Object.keys(results[0])[1] || Object.keys(results[0])[0]} fill="#0070f3" />
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}
          <pre style={{ background: '#eee', padding: 10 }}>{JSON.stringify(results, null, 2)}</pre>
        </div>
      )}
    </div>
  );
}
"""
}

for path, content in files.items():
    folder = os.path.dirname(path)
    if folder:
        os.makedirs(folder, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)

print("✅ All Project Files Generated Successfully!")