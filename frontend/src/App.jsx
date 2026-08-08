import React, { useState } from 'react';
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
  try {
    const res = await axios.post(`${API}/execute`, { 
      sql_query: data.sql, // 👈 Changed from data.generated_sql to data.sql
      tenant_id: parseInt(tenantId) 
    });
    setResults(res.data.data);
  } catch (err) {
    console.error("Execution failed:", err);
  }
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
