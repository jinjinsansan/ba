'use client'

import { useState } from 'react'

export default function ReportPage() {
  const [password, setPassword] = useState('')
  const [authenticated, setAuthenticated] = useState(false)
  const [files, setFiles] = useState<string[]>([])
  const [error, setError] = useState('')
  const [viewingFile, setViewingFile] = useState('')
  const [htmlContent, setHtmlContent] = useState('')

  async function handleLogin() {
    setError('')
    const res = await fetch('/api/report', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ password }),
    })
    if (!res.ok) {
      setError('Invalid password')
      return
    }
    const data = await res.json()
    setFiles(data.files || [])
    setAuthenticated(true)
  }

  async function openFile(file: string) {
    const res = await fetch('/api/report', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ password, file }),
    })
    if (!res.ok) {
      setError('Failed to load file')
      return
    }
    const html = await res.text()
    setHtmlContent(html)
    setViewingFile(file)
  }

  if (viewingFile) {
    return (
      <div style={{ background: '#0f1419', minHeight: '100vh' }}>
        <div style={{
          padding: '8px 16px',
          background: '#1a2332',
          borderBottom: '1px solid #2a3441',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
        }}>
          <span style={{ color: '#6dd5ed', fontSize: '13px', fontWeight: 700 }}>{viewingFile}</span>
          <button
            onClick={() => { setViewingFile(''); setHtmlContent(''); }}
            style={{
              background: '#2a3441', border: '1px solid #3a4a5a', color: '#8a96a8',
              padding: '4px 14px', borderRadius: '4px', cursor: 'pointer', fontSize: '12px',
            }}
          >
            ← BACK
          </button>
        </div>
        <iframe
          srcDoc={htmlContent}
          style={{ width: '100%', height: 'calc(100vh - 44px)', border: 'none' }}
          sandbox="allow-same-origin"
        />
      </div>
    )
  }

  if (!authenticated) {
    return (
      <div style={{
        background: '#0f1419', minHeight: '100vh',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
      }}>
        <div style={{
          background: '#1a2332', border: '1px solid #2a3441', borderRadius: '12px',
          padding: '40px', width: '340px', textAlign: 'center',
        }}>
          <div style={{ color: '#6dd5ed', fontSize: '24px', fontWeight: 900, letterSpacing: '4px', marginBottom: '8px' }}>
            LAPLACE
          </div>
          <div style={{ color: '#4a5568', fontSize: '11px', letterSpacing: '2px', marginBottom: '28px' }}>
            REPORT ACCESS
          </div>
          {error && (
            <div style={{ color: '#ff3366', fontSize: '12px', marginBottom: '12px' }}>{error}</div>
          )}
          <input
            type="password"
            value={password}
            onChange={e => setPassword(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && handleLogin()}
            placeholder="Password"
            style={{
              width: '100%', padding: '10px 14px', background: '#0f1419',
              border: '1px solid #2a3441', borderRadius: '6px', color: '#e0e8f0',
              fontSize: '14px', outline: 'none', marginBottom: '14px', boxSizing: 'border-box',
            }}
          />
          <button
            onClick={handleLogin}
            style={{
              width: '100%', padding: '10px', background: 'linear-gradient(135deg, #005f7a, #00b8d4)',
              border: 'none', borderRadius: '6px', color: '#fff', fontSize: '13px',
              fontWeight: 700, letterSpacing: '2px', cursor: 'pointer',
            }}
          >
            ENTER
          </button>
        </div>
      </div>
    )
  }

  return (
    <div style={{ background: '#0f1419', minHeight: '100vh', padding: '24px' }}>
      <div style={{ maxWidth: '900px', margin: '0 auto' }}>
        <h1 style={{ color: '#ffd700', fontSize: '24px', borderBottom: '2px solid #ffd700', paddingBottom: '8px', marginBottom: '24px' }}>
          LAPLACE Report
        </h1>
        <div style={{
          display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))',
          gap: '12px',
        }}>
          {files.map(f => (
            <button
              key={f}
              onClick={() => openFile(f)}
              style={{
                background: '#1a2332', border: '1px solid #2a3441', borderRadius: '8px',
                padding: '14px 16px', textAlign: 'left', cursor: 'pointer',
                color: '#6dd5ed', fontSize: '13px', fontWeight: 600,
                transition: 'border-color 0.2s',
              }}
              onMouseEnter={e => (e.currentTarget.style.borderColor = '#6dd5ed')}
              onMouseLeave={e => (e.currentTarget.style.borderColor = '#2a3441')}
            >
              {f.replace('.html', '').replace(/_/g, ' ')}
            </button>
          ))}
        </div>
      </div>
    </div>
  )
}
