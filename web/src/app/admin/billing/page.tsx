import Link from 'next/link'
import { createAdminClient } from '@/lib/supabase-admin'
import { Card, CardHead } from '@/components/ui/Card'
import { PageHeader, Label } from '@/components/ui/PageHeader'
import { Pill } from '@/components/ui/Pill'
import { Money } from '@/components/ui/Money'

export const dynamic = 'force-dynamic'

type Row = Record<string, unknown>

// 全ユーザー横断の「請求 / 入金」一覧。誰にいくら請求中・誰が入金済みかを一目で。
export default async function AdminBillingPage() {
  const admin = createAdminClient()
  const [{ data: invoices }, { data: payments }, { data: weekly }] = await Promise.all([
    admin.from('invoices').select('*').order('created_at', { ascending: false }).limit(300)
      .then(r => r, () => ({ data: [] as Row[] })),
    admin.from('crypto_payments').select('*').order('created_at', { ascending: false }).limit(100)
      .then(r => r, () => ({ data: [] as Row[] })),
    admin.from('weekly_pnl').select('*').order('week_start', { ascending: false }).limit(120)
      .then(r => r, () => ({ data: [] as Row[] })),
  ])
  const invs = ((invoices as Row[]) || [])
  const pays = ((payments as Row[]) || [])
  const weeks = ((weekly as Row[]) || [])
  const latestWeek = weeks.length ? String(weeks[0].week_start) : ''
  const latestWeekRows = weeks.filter(w => String(w.week_start) === latestWeek)

  const ids = Array.from(new Set([
    ...invs.map(i => String(i.user_id)),
    ...pays.map(p => String(p.user_id)),
    ...weeks.map(w => String(w.user_id)),
  ].filter(Boolean)))
  const emailMap: Record<string, string> = {}
  if (ids.length) {
    const { data: profs } = await admin.from('profiles').select('id, email').in('id', ids)
    for (const p of (profs || [])) emailMap[String(p.id)] = String(p.email || '')
  }
  const emailOf = (uid: unknown) => emailMap[String(uid)] || String(uid).slice(0, 8)

  const unpaid = invs.filter(i => String(i.status) === 'unpaid')
  const outstandingTotal = unpaid.reduce((s, i) => s + Number(i.amount || 0), 0)
  const paidTotal = invs.filter(i => String(i.status) === 'paid').reduce((s, i) => s + Number(i.amount || 0), 0)
  const creditedTotal = pays.filter(p => String(p.status) === 'credited').reduce((s, p) => s + Number(p.paid_amount ?? p.expected_amount ?? 0), 0)
  const nowMs = Date.now()

  return (
    <div>
      <PageHeader kicker="Admin · Billing" title="請求 / 入金 一覧" sub="全ユーザー横断" />

      <Card padded={false} className="mb-4">
        <CardHead>サマリー</CardHead>
        <div className="grid grid-cols-2 sm:grid-cols-4 px-5 py-5">
          <div>
            <Label>未払い合計</Label>
            <div className="mt-1.5"><Money value={outstandingTotal} size="2xl" weight="bold" tone={outstandingTotal > 0 ? 'warn' : 'win'} /></div>
          </div>
          <div className="sm:pl-4 sm:border-l border-white/[0.07]">
            <Label>未払い件数</Label>
            <div className="mt-1.5 text-2xl font-semibold text-text">{unpaid.length}</div>
          </div>
          <div className="sm:pl-4 sm:border-l border-white/[0.07]">
            <Label>請求 支払済 合計</Label>
            <div className="mt-1.5"><Money value={paidTotal} size="2xl" weight="semibold" /></div>
          </div>
          <div className="sm:pl-4 sm:border-l border-white/[0.07]">
            <Label>USDT入金 確認済 合計</Label>
            <div className="mt-1.5"><Money value={creditedTotal} size="2xl" weight="semibold" tone="win" /></div>
          </div>
        </div>
      </Card>

      {/* 直近週の週次精算(全ユーザー) */}
      {latestWeekRows.length > 0 && (
        <Card padded={false} className="mb-4">
          <CardHead right={<span className="text-text-dim text-xs font-mono">{latestWeek}〜</span>}>直近週の週次精算 ({latestWeekRows.length})</CardHead>
          <div className="overflow-x-auto">
            <table className="min-w-[760px] w-full text-sm">
              <thead>
                <tr className="border-b border-white/[0.07]">
                  {[['ユーザー','left'],['純PnL','right'],['繰越in','right'],['課金対象','right'],['率','right'],['手数料','right'],['繰越out','right'],['状態','left']].map(([h,a],i) => (
                    <th key={i} className={['px-4 py-3 font-mono text-[10px] text-text-dim tracking-[0.12em] uppercase font-normal', a === 'right' ? 'text-right' : 'text-left'].join(' ')}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {latestWeekRows.map((w, idx) => {
                  const gross = Number(w.gross_pnl) || 0, carryIn = Number(w.carry_in) || 0, net = Number(w.net_pnl) || 0
                  const fee = Number(w.fee_amount) || 0, carryOut = Number(w.carry_out) || 0, rate = Number(w.fee_rate) || 0
                  const st = String(w.status)
                  return (
                    <tr key={String(w.id)} className={idx ? 'border-t border-white/[0.07]' : ''}>
                      <td className="px-4 py-3"><Link href={`/admin/users/${String(w.user_id)}?tab=history`} className="text-cyan hover:underline text-xs">{emailOf(w.user_id)}</Link></td>
                      <td className="px-4 py-3 text-right"><Money value={gross} sign tone={gross >= 0 ? 'win' : 'lose'} /></td>
                      <td className="px-4 py-3 text-right"><Money value={carryIn} sign tone={carryIn < 0 ? 'lose' : 'muted'} /></td>
                      <td className="px-4 py-3 text-right"><Money value={net} sign tone={net >= 0 ? 'win' : 'lose'} /></td>
                      <td className="px-4 py-3 text-right text-xs text-text-muted">{(rate * 100).toFixed(0)}%</td>
                      <td className="px-4 py-3 text-right"><Money value={fee} weight="bold" tone={fee > 0 ? 'amber' : 'muted'} /></td>
                      <td className="px-4 py-3 text-right"><Money value={carryOut} sign tone={carryOut < 0 ? 'lose' : 'muted'} /></td>
                      <td className="px-4 py-3"><Pill tone={st === 'billed' ? 'live' : st === 'review' ? 'danger' : 'info'}>{st === 'billed' ? '課金' : st === 'review' ? '要確認' : '課金無'}</Pill></td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </Card>
      )}

      {/* 未払い請求書(全ユーザー) */}
      <Card padded={false} className="mb-4 border-warn/25">
        <CardHead right={<span className="text-warn font-semibold text-sm">未払い ${outstandingTotal.toFixed(2)}</span>}>未払い請求書 ({unpaid.length})</CardHead>
        {unpaid.length ? (
          <div className="overflow-x-auto">
            <table className="min-w-[680px] w-full text-sm">
              <thead>
                <tr className="border-b border-white/[0.07]">
                  {[['ユーザー','left'],['金額','right'],['メモ','left'],['発行日時','left'],['',''] ].map(([h,a],i) => (
                    <th key={i} className={['px-5 py-3 font-mono text-[10px] text-text-dim tracking-[0.15em] uppercase font-normal', a === 'right' ? 'text-right' : 'text-left'].join(' ')}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {unpaid.map((iv, idx) => (
                  <tr key={String(iv.id)} className={idx ? 'border-t border-white/[0.07]' : ''}>
                    <td className="px-5 py-3"><Link href={`/admin/users/${String(iv.user_id)}`} className="text-cyan hover:underline text-xs">{emailOf(iv.user_id)}</Link></td>
                    <td className="px-5 py-3 text-right"><Money value={Number(iv.amount)} size="md" weight="bold" /></td>
                    <td className="px-5 py-3 text-xs text-text-muted break-words max-w-[240px]">{String(iv.memo || '—')}</td>
                    <td className="px-5 py-3 font-mono text-xs text-text-muted">{new Date(String(iv.created_at)).toLocaleString('ja-JP')}</td>
                    <td className="px-5 py-3 text-right"><Link href={`/admin/users/${String(iv.user_id)}?tab=history`} className="text-text-dim hover:text-cyan text-xs">管理 →</Link></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : <div className="px-5 py-6 text-text-muted text-sm">未払いの請求書はありません。</div>}
      </Card>

      {/* USDT入金履歴(全ユーザー) */}
      <Card padded={false}>
        <CardHead>入金履歴 USDT ({pays.length})</CardHead>
        {pays.length ? (
          <div className="overflow-x-auto">
            <table className="min-w-[720px] w-full text-sm">
              <thead>
                <tr className="border-b border-white/[0.07]">
                  {[['日時','left'],['ユーザー','left'],['種別','left'],['金額','right'],['状態','left'],['tx','left']].map(([h,a],i) => (
                    <th key={i} className={['px-5 py-3 font-mono text-[10px] text-text-dim tracking-[0.15em] uppercase font-normal', a === 'right' ? 'text-right' : 'text-left'].join(' ')}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {pays.map((p, idx) => {
                  const st = String(p.status)
                  const expired = st === 'pending' && p.expires_at && new Date(String(p.expires_at)).getTime() <= nowMs
                  const effSt = expired ? 'expired' : st
                  const tone = effSt === 'credited' ? 'live' : effSt === 'expired' ? 'danger' : 'warn'
                  const label = effSt === 'credited' ? '入金確認済' : effSt === 'expired' ? '失効' : '保留'
                  const amt = Number(p.paid_amount ?? p.expected_amount ?? 0)
                  const tx = String(p.tx_hash || '')
                  return (
                    <tr key={String(p.id)} className={idx ? 'border-t border-white/[0.07]' : ''}>
                      <td className="px-5 py-3 font-mono text-xs text-text-muted">{new Date(String(p.created_at)).toLocaleString('ja-JP')}</td>
                      <td className="px-5 py-3"><Link href={`/admin/users/${String(p.user_id)}`} className="text-cyan hover:underline text-xs">{emailOf(p.user_id)}</Link></td>
                      <td className="px-5 py-3 text-xs text-text">{p.kind === 'license' ? 'ライセンス' : 'チャージ'}</td>
                      <td className="px-5 py-3 text-right"><Money value={amt} size="md" weight="semibold" /></td>
                      <td className="px-5 py-3"><Pill tone={tone}>{label}</Pill></td>
                      <td className="px-5 py-3 font-mono text-[10px] text-text-dim break-all max-w-[200px]">{tx ? tx.slice(0, 12) + '…' : '—'}</td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        ) : <div className="px-5 py-6 text-text-muted text-sm">USDT入金履歴はありません。</div>}
      </Card>
    </div>
  )
}
