// 受け子の BET 履歴 (receiver_bets) — 2026-09-22 (ダッシュボード段階2)
// 会員ページ (/me/bets) と管理画面 (ユーザー詳細の BET タブ) で共用するサーバーコンポーネント。
// 月ごと・日ごと (日本時間) の合計と、直近の BET を出す。

import { createAdminClient } from '@/lib/supabase-admin'
import { PRODUCT_LABEL, PRODUCT_CLASS } from '@/lib/receiver-status'

export type BetHistoryLabels = {
  monthly: string
  daily: string
  recent: string
  month: string
  date: string
  time: string
  bets: string
  record: string
  pnl: string
  table: string
  side: string
  amount: string
  result: string
  none: string
  sides: { player: string; banker: string; tie: string }
  outcomes: { win: string; lose: string; push: string }
}

type BetRow = {
  occurred_at: string
  product: string
  executor_id: string
  table_name: string | null
  side: string | null
  amount: number | null
  result: string | null
  outcome: 'win' | 'lose' | 'push'
  pnl: number | null
}

type Agg = { key: string; bets: number; w: number; l: number; p: number; pnl: number }

function jst(iso: string): Date {
  return new Date(new Date(iso).getTime() + 9 * 3600 * 1000)
}
function ymd(iso: string): string { return jst(iso).toISOString().slice(0, 10) }
function ym(iso: string): string { return jst(iso).toISOString().slice(0, 7) }
function hm(iso: string): string { return jst(iso).toISOString().slice(5, 16).replace('T', ' ') }

function aggregate(rows: BetRow[], keyOf: (r: BetRow) => string): Agg[] {
  const m = new Map<string, Agg>()
  for (const r of rows) {
    const k = keyOf(r)
    const a = m.get(k) || { key: k, bets: 0, w: 0, l: 0, p: 0, pnl: 0 }
    a.bets += 1
    if (r.outcome === 'win') a.w += 1
    else if (r.outcome === 'lose') a.l += 1
    else a.p += 1
    a.pnl += Number(r.pnl || 0)
    m.set(k, a)
  }
  return [...m.values()].sort((a, b) => (a.key < b.key ? 1 : -1))
}

function Pnl({ v }: { v: number }) {
  const cls = v > 0 ? 'text-win' : v < 0 ? 'text-lose' : 'text-text-muted'
  return <span className={`font-mono ${cls}`}>{v >= 0 ? '+' : '-'}${Math.abs(v).toFixed(2)}</span>
}

const th = 'px-3 py-2 font-mono text-[10px] text-text-dim tracking-[0.12em] uppercase font-normal text-left'
const td = 'px-3 py-2 text-xs'

export default async function BetHistory({ userId, labels, days = 90, recent = 200 }: {
  userId: string
  labels: BetHistoryLabels
  days?: number
  recent?: number
}) {
  const since = new Date(Date.now() - days * 86400 * 1000).toISOString()
  const { data } = await createAdminClient()
    .from('receiver_bets')
    .select('occurred_at, product, executor_id, table_name, side, amount, result, outcome, pnl')
    .eq('user_id', userId)
    .gte('occurred_at', since)
    .order('occurred_at', { ascending: false })
    .limit(10000)
  const rows = (data || []) as BetRow[]

  if (!rows.length) {
    return <div className="text-sm text-text-muted px-1 py-4">{labels.none}</div>
  }

  const monthly = aggregate(rows, r => ym(r.occurred_at))
  const daily = aggregate(rows, r => ymd(r.occurred_at)).slice(0, 31)
  const aggTable = (title: string, keyLabel: string, list: Agg[]) => (
    <div className="rounded-xl border border-white/[0.08] overflow-x-auto">
      <div className="px-3 pt-3 pb-1 text-[13px] text-text-muted">{title}</div>
      <table className="w-full min-w-[420px]">
        <thead><tr><th className={th}>{keyLabel}</th><th className={th}>{labels.bets}</th><th className={th}>{labels.record}</th><th className={th}>{labels.pnl}</th></tr></thead>
        <tbody>
          {list.map(a => (
            <tr key={a.key} className="border-t border-white/[0.06]">
              <td className={td + ' font-mono'}>{a.key}</td>
              <td className={td + ' font-mono'}>{a.bets}</td>
              <td className={td + ' font-mono'}>{a.w}-{a.l}-{a.p}</td>
              <td className={td}><Pnl v={a.pnl} /></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )

  return (
    <div className="flex flex-col gap-4">
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {aggTable(labels.monthly, labels.month, monthly)}
        {aggTable(labels.daily, labels.date, daily)}
      </div>
      <div className="rounded-xl border border-white/[0.08] overflow-x-auto">
        <div className="px-3 pt-3 pb-1 text-[13px] text-text-muted">{labels.recent}</div>
        <table className="w-full min-w-[640px]">
          <thead><tr>
            <th className={th}>{labels.time}</th><th className={th}></th><th className={th}>{labels.table}</th>
            <th className={th}>{labels.side}</th><th className={th}>{labels.amount}</th>
            <th className={th}>{labels.result}</th><th className={th}>{labels.pnl}</th>
          </tr></thead>
          <tbody>
            {rows.slice(0, recent).map((r, i) => (
              <tr key={i} className="border-t border-white/[0.06]">
                <td className={td + ' font-mono whitespace-nowrap'}>{hm(r.occurred_at)}</td>
                <td className={td}><span className={`px-1.5 py-0.5 rounded text-[10px] font-mono ${PRODUCT_CLASS[r.product] || ''}`}>{PRODUCT_LABEL[r.product] || r.product}</span></td>
                <td className={td}>{r.table_name || '-'}</td>
                <td className={td}>{r.side ? (labels.sides as Record<string, string>)[r.side] || r.side : '-'}</td>
                <td className={td + ' font-mono'}>{r.amount !== null ? `$${Number(r.amount).toFixed(2)}` : '-'}</td>
                <td className={td + (r.outcome === 'win' ? ' text-win' : r.outcome === 'lose' ? ' text-lose' : ' text-text-muted')}>{labels.outcomes[r.outcome]}</td>
                <td className={td}><Pnl v={Number(r.pnl || 0)} /></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
