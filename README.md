# 🚀 AI Text-to-SQL Engine

An enterprise-grade Text-to-SQL engine that translates natural language into executable PostgreSQL queries using Large Language Models (LLMs). This system features AST-based security guardrails, automatic tenant isolation, and sub-10ms Redis caching.

## ✨ Key Features

* **Natural Language to SQL:** Translates plain English prompts into valid SQL using Llama 3 (via local Ollama) or the Groq API.
* **AST Security Guardrails:** Uses `sqlglot` to parse Abstract Syntax Trees, automatically blocking destructive queries (`DROP`, `DELETE`, `UPDATE`) before they can reach the database.
* **Automatic Tenant Isolation:** Programmatically injects `WHERE tenant_id = X` into queries to guarantee zero cross-tenant data leakage.
* **Lightning-Fast Caching:** Integrates Redis to cache identical AI requests, reducing response times to < 10ms.
* **Defense-in-Depth Architecture:** Human-in-the-Loop (HITL) execution pipeline with a React frontend and FastAPI backend.

## 🛠️ Tech Stack

* **Backend:** Python, FastAPI, asyncpg
* **Frontend:** React, Vite, Axios, Recharts
* **AI / LLM:** Ollama (Llama 3), Groq API
* **Database & Caching:** PostgreSQL, Redis (Dockerized)
* **Security Guardrails:** sqlglot (AST Parsing)

## 🚀 Quick Start

### 1. Start Infrastructure (Database & Cache)
Ensure Docker is running, then spin up the PostgreSQL and Redis containers:

```bash
docker-compose up -d
```

### 2. Start the FastAPI Backend
Open a terminal in the root directory and start the Uvicorn server:

```bash
python -m uvicorn app.main:app --reload
```

### 3. Start the React Frontend
Open a new terminal, navigate to the frontend folder, and start the Vite development server:

```bash
cd frontend
npm run dev
```

## 👨‍💻 Author

**Mohammad Zeeshan**  
*Full Stack AI Engineer*  
[GitHub Profile](https://github.com/Zeeshan176) | [LinkedIn](https://linkedin.com/in/md-zeeshan-665907171/)

## 📄 License

This project is open-source and available under the [MIT License](LICENSE).