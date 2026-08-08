import asyncio, asyncpg, random
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
