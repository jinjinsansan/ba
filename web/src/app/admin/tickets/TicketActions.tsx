'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'

export default function TicketActions({ ticketId, status }: { ticketId: string; status: string }) {
  const [reply, setReply] = useState('')
  const [loading, setLoading] = useState(false)
  const [showReply, setShowReply] = useState(false)
  const router = useRouter()

  async function handleReply() {
    if (!reply.trim()) return
    setLoading(true)
    const res = await fetch('/api/admin/tickets', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ action: 'reply', ticketId, reply }),
    })
    if (res.ok) {
      setReply('')
      setShowReply(false)
      router.refresh()
    } else alert('Error')
    setLoading(false)
  }

  async function handleClose() {
    await fetch('/api/admin/tickets', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ action: 'close', ticketId }),
    })
    router.refresh()
  }

  return (
    <div className="flex gap-2 items-start">
      {status !== 'closed' && (
        <>
          {showReply ? (
            <div className="flex-1 flex gap-2">
              <input
                value={reply} onChange={e => setReply(e.target.value)}
                className="flex-1 px-3 py-2 rounded-lg bg-bg-primary border border-white/10 text-white text-sm"
                placeholder="Type reply..."
              />
              <button onClick={handleReply} disabled={loading}
                className="px-3 py-2 rounded-lg bg-player/20 text-player text-xs font-semibold">
                Send
              </button>
              <button onClick={() => setShowReply(false)}
                className="px-3 py-2 rounded-lg bg-slate-500/20 text-slate-400 text-xs">
                Cancel
              </button>
            </div>
          ) : (
            <button onClick={() => setShowReply(true)}
              className="px-3 py-1 rounded-lg bg-player/20 text-player text-xs font-semibold">
              Reply
            </button>
          )}
          <button onClick={handleClose}
            className="px-3 py-1 rounded-lg bg-slate-500/20 text-slate-400 text-xs">
            Close
          </button>
        </>
      )}
    </div>
  )
}
