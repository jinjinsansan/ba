// app/me/settlements/page.tsx — 精算履歴(リデザイン 2026-08)
// 週次カード型(ハンドオフ説明書3.4): 1枚のカードに 週の純利益 / 請求額(30%) / 繰越額 を横並び。
// マイナス週は請求 $0 + 繰越を warn 色で表示。日次の内訳は折りたたみに退避。
// データ取得は既存のまま(weekly_pnl / daily_profit_invoices / deductions)。

import { getTranslations } from 'next-intl/server'
import { createClient } from '@/lib/supabase-server'
import { Card, CardHead } from '@/components/ui/Card'
import { Pill } from '@/components/ui/Pill'
import { Money } from '@/components/ui/Money'

type InvoiceRow = {
  id?: string
  settle_date?: string
  daily_profit?: number
  net_profit?: number
  operator_fee_amount?: number
  outstanding_amount?: number
  status?: string
}
type DeductionRow = {
  id?: string
  date?: string
  daily_profit?: number
  fee_amount?: number
  note?: string
}

function fmtUsd(n: number) {
  const sign = n < 0 ? '−' : n > 0 ? '+' : ''
  return `${sign}$${Math.abs(n).toLocaleString('en-US', { maximumFractionDigits: 2 })}`
}

function fmtRange(start: string, end: string) {
  const s = new Date(start)
  const e = new Date(end)
  const f = (d: Date) => d.toLocaleDateString('ja-JP', { month: 'numeric', day: 'numeric' })
  return `${f(s)} 〜 ${f(e)}`
}

function sundayAfter(weekEnd: string) {
  const d = new Date(weekEnd)
  d.setDate(d.getDate() + 1)
  return d.toLocaleDateString('ja-JP', { month: 'numeric', day: 'numeric' })
}

export default async function SettlementsPage() {
  const supabase = await createClient()
  const { data: { user } } = await supabase.auth.getUser()
  if (!user) return null

  const t = await getTranslations('settlementsV2')

  const [{ data: invoices }, { data: deductions }, { data: weekly }] = await Promise.all([
    supabase.from('daily_profit_invoices').select('*').eq('user_id', user.id).order('settle_date', { ascending: false }).limit(60),
    supabase.from('deductions').select('*').eq('user_id', user.id).order('date', { ascending: false }).limit(60),
    supabase.from('weekly_pnl').select('*').eq('user_id', user.id).order('week_start', { ascending: false }).limit(52).then(r => r, () => ({ data: [] as Record<string, unknown>[] })),
  ])
  const weeklyRows = (weekly as Record<string, unknown>[]) || []

  const outstandingTotal = (invoices || []).filter((i: InvoiceRow) => String(i.status) === 'unpaid').reduce((s: number, i: InvoiceRow) => s + Number(i.outstanding_amount || 0), 0)
  const dailyRows: Array<InvoiceRow & DeductionRow> = (invoices?.length ? invoices : (deductions || [])) as Array<InvoiceRow & DeductionRow>

  return (
    <div>
      {/* Header */}
      <div className="flex justify-between items-end flex-wrap gap-3 mb-6">
        <div>
          <div className="font-mono text-[10px] text-text-dim tracking-[0.15em] uppercase">{t('kicker')}</div>
          <h1 className="text-[26px] sm:text-[28px] font-bold tracking-tight mt-1">{t('title')}</h1>
          <p className="text-sm text-text-muted mt-1 m-0">{t('sub')}</p>
        </div>
        {outstandingTotal > 0
          ? <Pill tone="warn">未払い ${outstandingTotal.toFixed(2)}</Pill>
          : <Pill tone="paid">未払いなし</Pill>}
      </div>

      {/* 週次カード */}
      {weeklyRows.length ? (
        <div className="flex flex-col gap-3 mb-6">
          {weeklyRows.map(w => {
            const gross = Number(w.gross_pnl) || 0
            const fee = Number(w.fee_amount) || 0
            const carryOut = Math.abs(Number(w.carry_out) || 0)
            const billed = String(w.status) === 'billed' && fee > 0
            const negative = gross < 0

            return (
              <div key={String(w.id)} className="bg-surface border border-white/[0.07] rounded-2xl p-6 flex flex-col gap-4">
                <div className="flex justify-between items-center flex-wrap gap-2">
                  <div>
                    <div className="text-[17px] font-semibold">{fmtRange(String(w.week_start), String(w.week_end))}</div>
                    <div className="text-sm text-text-dim mt-0.5">
                      {billed ? t('billedOn', { date: sundayAfter(String(w.week_end)) }) : t('zeroSub')}
                    </div>
                  </div>
                  {billed
                    ? <span className="bg-cyan/10 text-cyan rounded-full px-3.5 py-1.5 text-[13px] font-semibold">{t('statusBilled')}</span>
                    : <span className="bg-white/[0.05] text-text-muted rounded-full px-3.5 py-1.5 text-[13px] font-semibold">{t('statusZero')}</span>}
                </div>

                <div className="grid grid-cols-3 gap-px bg-white/[0.07] rounded-xl overflow-hidden">
                  <div className="bg-surface px-3 sm:px-4 py-4">
                    <div className="text-[12px] sm:text-[13px] text-text-dim">{t('cellNet')}</div>
                    <div className={['font-mono tabular-nums text-lg sm:text-2xl font-bold mt-1', gross >= 0 ? 'text-win' : 'text-lose'].join(' ')}>
                      {fmtUsd(gross)}
                    </div>
                  </div>
                  <div className="bg-surface px-3 sm:px-4 py-4">
                    <div className="text-[12px] sm:text-[13px] text-text-dim">{t('cellFee')}</div>
                    <div className="font-mono tabular-nums text-lg sm:text-2xl font-bold mt-1">
                      ${fee.toLocaleString('en-US', { maximumFractionDigits: 2 })}
                    </div>
                  </div>
                  <div className="bg-surface px-3 sm:px-4 py-4">
                    <div className="text-[12px] sm:text-[13px] text-text-dim">{t('cellCarry')}</div>
                    <div className={['font-mono tabular-nums text-lg sm:text-2xl font-bold mt-1', carryOut > 0 ? 'text-warn' : 'text-text-dim'].join(' ')}>
                      ${carryOut.toLocaleString('en-US', { maximumFractionDigits: 2 })}
                    </div>
                  </div>
                </div>

                {negative && carryOut > 0 && (
                  <div className="text-sm leading-[1.8] text-text-muted">
                    {t.rich('carryNote', {
                      c: (chunk) => <span className="font-mono tabular-nums text-warn">{chunk}</span>,
                      amount: `$${carryOut.toLocaleString('en-US', { maximumFractionDigits: 2 })}`,
                    })}
                  </div>
                )}
              </div>
            )
          })}
        </div>
      ) : (
        <div className="bg-surface border border-white/[0.07] rounded-2xl px-6 py-8 text-text-muted text-sm mb-6">
          {t('empty')}
        </div>
      )}

      {/* 日次の内訳(折りたたみ) */}
      {dailyRows.length > 0 && (
        <details className="group">
          <summary className="list-none cursor-pointer select-none bg-surface border border-white/[0.07] rounded-2xl px-6 py-5 flex justify-between items-center">
            <span className="text-base text-text-muted">{t('dailyDetails')}</span>
            <span className="text-text-dim group-open:rotate-180 transition-transform">▾</span>
          </summary>
          <Card padded={false} className="mt-2">
            <CardHead right={<span className="font-mono text-[11px] text-text-dim">JST</span>}>
              履歴 (最大 60 件)
            </CardHead>
            <div className="overflow-x-auto">
              <table className="min-w-[760px] w-full text-sm">
                <thead>
                  <tr className="border-b border-white/[0.07]">
                    {[['日付', 'left'], ['日次 PnL', 'right'], ['Net', 'right'], ['手数料', 'right'], ['未払い', 'right'], ['ステータス', 'left']].map(([h, a], i) => (
                      <th key={i} className={['px-5 py-3 font-mono text-[10px] text-text-dim tracking-[0.15em] uppercase font-normal', a === 'right' ? 'text-right' : 'text-left'].join(' ')}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {dailyRows.map((row, idx) => {
                    const date = String(row.settle_date || row.date || '')
                    const dp = Number(row.daily_profit || 0)
                    const np = Number(row.net_profit ?? row.daily_profit ?? 0)
                    const fee = Number(row.operator_fee_amount ?? row.fee_amount ?? 0)
                    const out = Number(row.outstanding_amount || 0)
                    const st = String(row.status || (out > 0 ? 'unpaid' : 'paid'))
                    return (
                      <tr key={`${row.id || idx}-${date}`} className={idx ? 'border-t border-white/[0.07]' : ''}>
                        <td className="px-5 py-3 font-mono text-xs text-text-muted">{date}</td>
                        <td className="px-5 py-3 text-right"><Money value={dp} sign size="md" weight="semibold" tone={dp >= 0 ? 'win' : 'lose'} /></td>
                        <td className="px-5 py-3 text-right"><Money value={np} sign size="md" weight="medium" tone={np >= 0 ? undefined : 'lose'} /></td>
                        <td className="px-5 py-3 text-right"><Money value={fee} size="md" weight="medium" tone="cyan" /></td>
                        <td className="px-5 py-3 text-right"><Money value={out} size="md" weight="medium" tone={out > 0 ? 'warn' : 'muted'} /></td>
                        <td className="px-5 py-3">
                          <Pill tone={st === 'unpaid' ? 'warn' : st === 'paid' ? 'live' : 'paid'}>{st}</Pill>
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          </Card>
        </details>
      )}
    </div>
  )
}
