'use client'
import { useEffect, useRef, useState } from 'react'
import { useTranslations } from 'next-intl'

type SessionState = {
  daily_bet_pnl?: number
  daily_bet_pnl_date?: string
  prev_daily_bet_pnl?: number
  prev_daily_bet_pnl_date?: string
  current_balance?: number
  daily_open_balance?: number
  daily_open_date?: string
  last_balance_at?: string
  total_bets?: number
  total_wins?: number
  total_losses?: number
  ties?: number
  daily_pnl?: number
} & Record<string, unknown>

function jstDateStr() {
  return new Date().toLocaleDateString('en-CA', { timeZone: 'Asia/Tokyo' })
}

export default function RealtimePnlCard({ initial }: { initial: SessionState | null }) {
  const t = useTranslations('realtimePnl')
  const [ss, setSs] = useState<SessionState | null>(initial)
  const [now, setNow] = useState(Date.now())
  const inflightRef = useRef(false)

  useEffect(() => {
    async function poll() {
      if (inflightRef.current) return
      inflightRef.current = true
      try {
        const res = await fetch('/api/user/session-state', { cache: 'no-store' })
        if (!res.ok) return
        const data = await res.json()
        setSs(data.session_state ?? null)
      } catch {
        // ignore transient errors
      } finally {
        inflightRef.current = false
      }
    }
    const pollTimer = setInterval(poll, 30_000)
    const tickTimer = setInterval(() => setNow(Date.now()), 1_000)
    return () => {
      clearInterval(pollTimer)
      clearInterval(tickTimer)
    }
  }, [])

  if (!ss) {
    return (
      <div className="p-6 rounded-2xl glass-card mb-8">
        <h2 className="text-lg font-bold mb-2">{t('title')}</h2>
        <p className="text-text-muted text-sm">{t('noData')}</p>
      </div>
    )
  }

  const today = jstDateStr()
  const dbpToday = typeof ss.daily_bet_pnl === 'number' && ss.daily_bet_pnl_date === today ? ss.daily_bet_pnl : null
  const dbpPrev = typeof ss.prev_daily_bet_pnl === 'number' && ss.prev_daily_bet_pnl_date === today ? ss.prev_daily_bet_pnl : null
  const dbp = dbpToday ?? dbpPrev
  const dpFallback = typeof ss.daily_pnl === 'number' ? ss.daily_pnl : null
  const pnl = dbp ?? dpFallback
  const isFromBetPnl = dbp !== null

  const balance = typeof ss.current_balance === 'number' ? ss.current_balance : null
  const openBal = typeof ss.daily_open_balance === 'number' ? ss.daily_open_balance : null

  const lastAt = typeof ss.last_balance_at === 'string' ? new Date(ss.last_balance_at).getTime() : NaN
  const ageSec = Number.isFinite(lastAt) ? Math.max(0, Math.floor((now - lastAt) / 1000)) : Infinity
  const isLive = ageSec < 90

  function ageLabel(s: number) {
    if (!Number.isFinite(s)) return '—'
    if (s < 60) return `${s}${t('agoSec')}`
    if (s < 3600) return `${Math.floor(s / 60)}${t('agoMin')}`
    if (s < 86400) return `${Math.floor(s / 3600)}${t('agoHour')}`
    return `${Math.floor(s / 86400)}${t('agoDay')}`
  }

  const wins = ss.total_wins ?? null
  const losses = ss.total_losses ?? null
  const ties = ss.ties ?? null
  const bets = ss.total_bets ?? null

  return (
    <div className="p-6 rounded-2xl glass-card mb-8">
      <div className="flex items-center justify-between mb-4 flex-wrap gap-2">
        <h2 className="text-lg font-bold">{t('title')}</h2>
        <span className={`px-3 py-1 rounded text-xs font-bold ${isLive ? 'bg-green-500/20 text-green-400' : 'bg-yellow-500/20 text-yellow-400'}`}>
          {isLive ? `🟢 ${t('live')}` : `🟡 ${t('paused')}`}
        </span>
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div className="p-4 rounded-xl bg-surface border border-accent/10">
          <div className="text-xs text-text-muted mb-1">{t('dailyPnl')}</div>
          <div className={`text-3xl font-black ${pnl == null ? 'text-text' : pnl >= 0 ? 'text-green-400' : 'text-banker'}`}>
            {pnl == null ? '—' : `${pnl >= 0 ? '+' : ''}$${pnl.toFixed(2)}`}
          </div>
          {!isFromBetPnl && pnl != null && (
            <div className="text-[10px] text-text-muted mt-1">{t('fallbackBalance')}</div>
          )}
        </div>
        <div className="p-4 rounded-xl bg-surface border border-accent/10">
          <div className="text-xs text-text-muted mb-1">{t('stakeBalance')}</div>
          <div className="text-xl font-bold text-text">{balance != null ? `$${balance.toFixed(2)}` : '—'}</div>
          {openBal != null && (
            <div className="text-[10px] text-text-muted mt-1">{t('openBalance')}: ${openBal.toFixed(2)}</div>
          )}
        </div>
        <div className="p-4 rounded-xl bg-surface border border-accent/10">
          <div className="text-xs text-text-muted mb-1">{t('bets')}</div>
          <div className="text-xl font-bold text-text">{bets ?? '—'}</div>
          {(wins != null || losses != null || ties != null) && (
            <div className="text-[10px] text-text-muted mt-1">
              {t('wins')}: {wins ?? '?'} / {t('losses')}: {losses ?? '?'} / {t('ties')}: {ties ?? '?'}
            </div>
          )}
        </div>
      </div>
      <div className="mt-3 text-xs text-text-muted">
        {t('lastUpdate')}: {ageLabel(ageSec)}
      </div>
    </div>
  )
}
