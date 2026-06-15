import { createClient } from '@/lib/supabase-server'
import { Card, CardHead } from '@/components/ui/Card'
import { PageHeader, Label } from '@/components/ui/PageHeader'
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

export default async function SettlementsPage() {
  const supabase = await createClient()
  const { data: { user } } = await supabase.auth.getUser()
  if (!user) return null

  const [{ data: invoices }, { data: deductions }, { data: weekly }] = await Promise.all([
    supabase.from('daily_profit_invoices').select('*').eq('user_id', user.id).order('settle_date', { ascending: false }).limit(60),
    supabase.from('deductions').select('*').eq('user_id', user.id).order('date', { ascending: false }).limit(60),
    supabase.from('weekly_pnl').select('*').eq('user_id', user.id).order('week_start', { ascending: false }).limit(52).then(r => r, () => ({ data: [] as Record<string, unknown>[] })),
  ])
  const weeklyRows = (weekly as Record<string, unknown>[]) || []

  const outstandingTotal = (invoices || []).filter((i: InvoiceRow) => String(i.status) === 'unpaid').reduce((s: number, i: InvoiceRow) => s + Number(i.outstanding_amount || 0), 0)
  const last30Profit = (invoices || []).slice(0, 30).reduce((s: number, i: InvoiceRow) => s + Number(i.daily_profit || 0), 0)
  const last30Fee = (invoices || []).slice(0, 30).reduce((s: number, i: InvoiceRow) => s + Number(i.operator_fee_amount || 0), 0)

  const rows: Array<InvoiceRow & DeductionRow> = (invoices?.length ? invoices : (deductions || [])) as Array<InvoiceRow & DeductionRow>

  return (
    <div>
      <PageHeader
        kicker="Member · Settlements"
        title="日次精算履歴"
        sub="毎日 JST 00:05 に前日分の損益・手数料が確定します"
        right={outstandingTotal > 0 ? <Pill tone="warn">未払い ${outstandingTotal.toFixed(2)}</Pill> : <Pill tone="paid">未払いなし</Pill>}
      />

      {weeklyRows.length > 0 && (
        <Card padded={false} className="mb-4">
          <CardHead>週次精算履歴 (土曜締切・繰越計算)</CardHead>
          <div className="overflow-x-auto">
            <table className="min-w-[640px] w-full text-sm">
              <thead>
                <tr className="border-b border-white/[0.07]">
                  {[['週(月〜土)','left'],['純PnL','right'],['繰越','right'],['課金対象','right'],['手数料','right'],['状態','left']].map(([h,a],i) => (
                    <th key={i} className={['px-5 py-3 font-mono text-[10px] text-text-dim tracking-[0.15em] uppercase font-normal', a === 'right' ? 'text-right' : 'text-left'].join(' ')}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {weeklyRows.map((w, idx) => {
                  const gross = Number(w.gross_pnl) || 0
                  const carryIn = Number(w.carry_in) || 0
                  const net = Number(w.net_pnl) || 0
                  const fee = Number(w.fee_amount) || 0
                  const st = String(w.status)
                  return (
                    <tr key={String(w.id)} className={idx ? 'border-t border-white/[0.07]' : ''}>
                      <td className="px-5 py-3 font-mono text-xs text-text-muted">{String(w.week_start)}〜{String(w.week_end).slice(5)}</td>
                      <td className="px-5 py-3 text-right"><Money value={gross} sign weight="bold" tone={gross >= 0 ? 'win' : 'lose'} /></td>
                      <td className="px-5 py-3 text-right"><Money value={carryIn} sign tone={carryIn < 0 ? 'lose' : 'muted'} /></td>
                      <td className="px-5 py-3 text-right"><Money value={net} sign tone={net >= 0 ? 'win' : 'lose'} /></td>
                      <td className="px-5 py-3 text-right"><Money value={fee} weight="bold" tone={fee > 0 ? 'amber' : 'muted'} /></td>
                      <td className="px-5 py-3"><Pill tone={st === 'billed' ? 'live' : 'info'}>{st === 'billed' ? '請求' : '請求なし'}</Pill></td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </Card>
      )}

      <Card padded={false} className="mb-4">
        <CardHead>30 Days Summary</CardHead>
        <div className="grid grid-cols-1 sm:grid-cols-3 px-5 py-5">
          <div>
            <Label>Outstanding (未払い)</Label>
            <div className="mt-1.5"><Money value={outstandingTotal} size="2xl" weight="bold" tone={outstandingTotal > 0 ? 'warn' : 'win'} /></div>
          </div>
          <div className="sm:pl-4 sm:border-l border-white/[0.07]">
            <Label>30日 損益合計</Label>
            <div className="mt-1.5"><Money value={last30Profit} sign size="2xl" weight="bold" tone={last30Profit >= 0 ? 'win' : 'lose'} /></div>
          </div>
          <div className="sm:pl-4 sm:border-l border-white/[0.07]">
            <Label>30日 手数料合計</Label>
            <div className="mt-1.5"><Money value={last30Fee} size="2xl" weight="bold" tone="cyan" /></div>
          </div>
        </div>
      </Card>

      <Card padded={false}>
        <CardHead right={<span className="font-mono text-[11px] text-text-dim">JST 日次確定ベース</span>}>履歴 (最大 60 件)</CardHead>
        {rows.length ? (
          <div className="overflow-x-auto">
            <table className="min-w-[760px] w-full text-sm">
              <thead>
                <tr className="border-b border-white/[0.07]">
                  {[['日付','left'],['日次 PnL','right'],['Net','right'],['手数料','right'],['未払い','right'],['ステータス','left']].map(([h,a],i) => (
                    <th key={i} className={['px-5 py-3 font-mono text-[10px] text-text-dim tracking-[0.15em] uppercase font-normal', a === 'right' ? 'text-right' : 'text-left'].join(' ')}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {rows.map((row, idx) => {
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
        ) : (
          <div className="px-5 py-6 text-text-muted text-sm">まだ精算履歴がありません。受け子で BET セッションが完了し、JST 00:05 の cron が走ると 1 行追加されます。</div>
        )}
      </Card>
    </div>
  )
}
