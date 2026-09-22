import Link from 'next/link'
import { createAdminClient } from '@/lib/supabase-admin'
import { Card } from '@/components/ui/Card'
import { PageHeader } from '@/components/ui/PageHeader'
import { Pill } from '@/components/ui/Pill'
import { Dot } from '@/components/ui/Dot'
import { AutoRefresh } from '@/components/ui/AutoRefresh'
import {
  type ReceiverStatus, receiverState, secondsSince, fmtAgo,
  PRODUCT_LABEL, PRODUCT_TEAM, PRODUCT_CLASS,
} from '@/lib/receiver-status'

// 全受け子の稼働状況 (3版まとめて) — 2026-09-22
// 受け子 GUI の生存報告 (receiver_status) を一覧にする。30 秒ごとに自動更新。

export const dynamic = 'force-dynamic'

const TABS = [
  { key: '', label: 'すべて' },
  { key: 'bacopy', label: '田辺版' },
  { key: 'kbjapan', label: '梶原版' },
  { key: 'kbkorea', label: '韓国版' },
]

function money(v: number | null): string {
  if (v === null || v === undefined) return '-'
  return '$' + Number(v).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

export default async function AdminReceiversPage({ searchParams }: { searchParams: Promise<{ p?: string }> }) {
  const { p = '' } = await searchParams
  const admin = createAdminClient()
  let q = admin.from('receiver_status').select('*').order('last_seen_at', { ascending: false }).limit(500)
  if (p) q = q.eq('product', p)
  const { data, error } = await q
  const rows = (data || []) as ReceiverStatus[]

  // 版ごとに一番多いエンジンを「基準」とし、違うエンジンの受け子に印を付ける (差し替え漏れの発見用)
  const majority: Record<string, string> = {}
  for (const prod of ['bacopy', 'kbjapan', 'kbkorea']) {
    const counts: Record<string, number> = {}
    for (const r of rows) if (r.product === prod && r.engine_sha && receiverState(r) !== 'offline') counts[r.engine_sha] = (counts[r.engine_sha] || 0) + 1
    const top = Object.entries(counts).sort((a, b) => b[1] - a[1])[0]
    if (top) majority[prod] = top[0]
  }

  const nRunning = rows.filter(r => receiverState(r) === 'running').length
  const nIdle = rows.filter(r => receiverState(r) === 'idle').length
  const nOffline = rows.length - nRunning - nIdle

  return (
    <div>
      <AutoRefresh seconds={30} />
      <PageHeader
        kicker="Admin · Receivers"
        title="受け子の稼働状況"
        sub="受け子 GUI が 1 分ごとに送る生存報告。30 秒ごとに自動更新"
        right={<div className="flex gap-2">
          <Pill tone="live">稼働 {nRunning}</Pill>
          <Pill tone="info">待機 {nIdle}</Pill>
          <Pill tone="mute">オフライン {nOffline}</Pill>
        </div>}
      />

      <div className="flex gap-2 mb-4 flex-wrap">
        {TABS.map(t => (
          <Link key={t.key} href={t.key ? `/admin/receivers?p=${t.key}` : '/admin/receivers'}
            className={['px-3 py-1.5 rounded border text-xs font-mono',
              p === t.key ? 'border-cyan/50 text-cyan bg-cyan/10' : 'border-white/10 text-text-muted hover:text-text'].join(' ')}>
            {t.label}
          </Link>
        ))}
      </div>

      {error && <Card className="mb-4"><div className="text-lose text-sm">読み込みに失敗しました: {error.message}</div></Card>}

      <Card padded={false} className="overflow-x-auto">
        <table className="min-w-[1100px] w-full text-sm">
          <thead>
            <tr className="border-b border-white/[0.07]">
              {['状態', '版', '利用者 / 受け子', '卓', '残高', '今日のBET', '勝-負-タイ', 'BET失敗', '最後のBET', '最終報告', 'エンジン'].map((h, i) => (
                <th key={i} className="px-4 py-3 font-mono text-[10px] text-text-dim tracking-[0.15em] uppercase font-normal text-left">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.length === 0 && (
              <tr><td colSpan={11} className="px-4 py-8 text-center text-text-muted">
                まだ報告がありません (生存報告に対応した受け子 GUI から届き始めます)
              </td></tr>
            )}
            {rows.map((r, i) => {
              const st = receiverState(r)
              const ago = secondsSince(r.last_seen_at)
              const betAgo = secondsSince(r.last_bet_at)
              const oddEngine = !!(r.engine_sha && majority[r.product] && r.engine_sha !== majority[r.product])
              const errs = r.bet_errors_today || 0
              return (
                <tr key={`${r.user_id}-${r.product}-${r.executor_id}`} className={[i ? 'border-t border-white/[0.07]' : '', st === 'offline' ? 'opacity-60' : ''].join(' ')}>
                  <td className="px-4 py-3 whitespace-nowrap">
                    <div className="flex items-center gap-2">
                      <Dot tone={st === 'running' ? 'win' : st === 'idle' ? 'cyan' : 'dim'} pulse={st === 'running'} />
                      <span className="text-xs">{st === 'running' ? '稼働中' : st === 'idle' ? 'GUIのみ' : 'オフライン'}</span>
                    </div>
                  </td>
                  <td className="px-4 py-3">
                    <span className={`px-1.5 py-0.5 rounded text-[10px] font-mono ${PRODUCT_CLASS[r.product] || ''}`}>{PRODUCT_LABEL[r.product] || r.product}</span>
                    <div className="text-[10px] text-text-dim mt-1">{PRODUCT_TEAM[r.product] || ''}</div>
                  </td>
                  <td className="px-4 py-3">
                    <Link href={`/admin/users/${r.user_id}`} className="text-cyan hover:underline break-all">{r.email || r.user_id}</Link>
                    <div className="text-[11px] text-text-muted font-mono">{r.executor_id || '-'}{r.os ? ` · ${r.os}` : ''}{r.app_version ? ` · v${r.app_version}` : ''}</div>
                  </td>
                  <td className="px-4 py-3 text-xs">{r.table_name || '-'}</td>
                  <td className="px-4 py-3 font-mono text-xs text-right">{money(r.balance)}</td>
                  <td className="px-4 py-3 font-mono text-xs text-right">{r.bets_today ?? '-'}</td>
                  <td className="px-4 py-3 font-mono text-xs">{r.bets_today !== null ? `${r.wins_today ?? 0}-${r.losses_today ?? 0}-${r.ties_today ?? 0}` : '-'}</td>
                  <td className={['px-4 py-3 font-mono text-xs text-right', errs >= 3 ? 'text-lose' : errs > 0 ? 'text-warn' : ''].join(' ')}>{r.bet_errors_today ?? '-'}</td>
                  <td className="px-4 py-3 text-xs whitespace-nowrap">{fmtAgo(betAgo)}</td>
                  <td className={['px-4 py-3 text-xs whitespace-nowrap', st === 'offline' ? 'text-text-muted' : ''].join(' ')}>{fmtAgo(ago)}</td>
                  <td className="px-4 py-3 font-mono text-[11px] whitespace-nowrap">
                    <span className={oddEngine ? 'text-warn' : 'text-text-muted'}>{r.engine_sha ? r.engine_sha.slice(0, 8) : '-'}</span>
                    {oddEngine && <div className="text-[10px] text-warn">他の{PRODUCT_TEAM[r.product]}と違う</div>}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </Card>
      <p className="text-[11px] text-text-dim mt-3">
        「稼働中」= GUI とエンジンが動いている / 「GUIのみ」= GUI は開いているがエンジン停止 / 最終報告が 2.5 分以上前は「オフライン」。
        エンジン欄の黄色は、同じ版の他の受け子と違うエンジンで動いている (差し替え漏れの可能性)。
      </p>
    </div>
  )
}
