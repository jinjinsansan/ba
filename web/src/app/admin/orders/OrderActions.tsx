'use client'

import { useState, useRef } from 'react'
import { useRouter } from 'next/navigation'

export default function OrderActions({ type, id, userId, status, amount }: {
  type: 'order' | 'charge'; id: string; userId: string; status: string; amount?: number
}) {
  const [loading, setLoading] = useState(false)
  const [showUpload, setShowUpload] = useState(false)
  const fileRef = useRef<HTMLInputElement>(null)
  const router = useRouter()

  async function handleConfirm() {
    setLoading(true)
    const res = await fetch('/api/admin/confirm', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ type, id, userId, amount }),
    })
    if (res.ok) {
      if (type === 'order') setShowUpload(true)
      else router.refresh()
    } else alert('Error: ' + (await res.text()))
    setLoading(false)
  }

  async function handleUpload() {
    const file = fileRef.current?.files?.[0]
    if (!file) return
    setLoading(true)
    const formData = new FormData()
    formData.append('file', file)
    formData.append('userId', userId)
    formData.append('version', '1.0')
    const res = await fetch('/api/admin/upload', { method: 'POST', body: formData })
    if (res.ok) {
      await fetch('/api/admin/confirm', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ type: 'deliver', id, userId }),
      })
      router.refresh()
    } else alert('Upload failed')
    setLoading(false)
  }

  if (status === 'delivered') return <span className="text-xs text-green-400">配送済み</span>
  if (status === 'confirmed' && type === 'order') {
    return (
      <div className="flex gap-2 items-center">
        <input ref={fileRef} type="file" accept=".zip" className="text-xs text-slate-400 w-32" />
        <button onClick={handleUpload} disabled={loading}
          className="px-3 py-1 rounded-lg bg-player/20 text-player text-xs font-semibold disabled:opacity-50">
          {loading ? '...' : 'ZIP送付'}
        </button>
      </div>
    )
  }
  if (status === 'confirmed') return null

  return (
    <>
      {showUpload ? (
        <div className="flex gap-2 items-center">
          <input ref={fileRef} type="file" accept=".zip" className="text-xs text-slate-400 w-32" />
          <button onClick={handleUpload} disabled={loading}
            className="px-3 py-1 rounded-lg bg-player/20 text-player text-xs font-semibold disabled:opacity-50">
            {loading ? '...' : 'ZIP送付'}
          </button>
        </div>
      ) : (
        <button onClick={handleConfirm} disabled={loading}
          className="px-3 py-1 rounded-lg bg-green-500/20 text-green-400 text-xs font-semibold hover:bg-green-500/30 transition disabled:opacity-50">
          {loading ? '...' : '確認する'}
        </button>
      )}
    </>
  )
}
