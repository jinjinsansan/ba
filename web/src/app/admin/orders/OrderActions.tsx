'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'

export default function OrderActions({ type, id, userId, status, amount }: {
  type: 'order' | 'charge'; id: string; userId: string; status: string; amount?: number
}) {
  const [loading, setLoading] = useState(false)
  const router = useRouter()

  async function handleConfirm() {
    setLoading(true)
    const res = await fetch('/api/admin/confirm', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ type, id, userId, amount }),
    })
    if (res.ok) router.refresh()
    else alert('Error: ' + (await res.text()))
    setLoading(false)
  }

  if (status === 'confirmed' || status === 'delivered') return null

  return (
    <button
      onClick={handleConfirm}
      disabled={loading}
      className="px-3 py-1 rounded-lg bg-green-500/20 text-green-400 text-xs font-semibold hover:bg-green-500/30 transition disabled:opacity-50"
    >
      {loading ? '...' : 'Confirm'}
    </button>
  )
}
