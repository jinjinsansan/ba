import { createClient } from '@/lib/supabase-server'

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

  const [{ data: invoices }, { data: deductions }] = await Promise.all([
    supabase.from('daily_profit_invoices').select('*').eq('user_id', user.id).order('settle_date', { ascending: false }).limit(60),
    supabase.from('deductions').select('*').eq('user_id', user.id).order('date', { ascending: false }).limit(60),
  ])

  const outstandingTotal = (invoices || []).filter((i: InvoiceRow) => String(i.status) === 'unpaid').reduce((s: number, i: InvoiceRow) => s + Number(i.outstanding_amount || 0), 0)
  const last30Profit = (invoices || []).slice(0, 30).reduce((s: number, i: InvoiceRow) => s + Number(i.daily_profit || 0), 0)
  const last30Fee = (invoices || []).slice(0, 30).reduce((s: number, i: InvoiceRow) => s + Number(i.operator_fee_amount || 0), 0)

  const rows: Array<InvoiceRow & DeductionRow> = (invoices?.length ? invoices : (deductions || [])) as Array<InvoiceRow & DeductionRow>

  return (
    <div className="space-y-6">
      <div>
        <div className="hud-label mb-2">Settlements</div>
        <h1 className="text-2xl sm:text-3xl font-hud">日次精算履歴</h1>
        <p className="text-text-muted text-sm mt-2">毎日 JST 00:05 に前日分の損益・手数料が確定します。</p>
      </div>

      {/* Summary */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
        <div className="p-4 rounded-xl glass-card">
          <div className="text-[10px] tracking-widest text-text-dim uppercase">Outstanding (未払い)</div>
          <div className={`text-2xl font-bold mt-1 ${outstandingTotal > 0 ? 'text-yellow-400' : 'text-green-400'}`}>${outstandingTotal.toFixed(2)}</div>
        </div>
        <div className="p-4 rounded-xl glass-card">
          <div className="text-[10px] tracking-widest text-text-dim uppercase">30日 損益合計</div>
          <div className={`text-2xl font-bold mt-1 ${last30Profit >= 0 ? 'text-green-400' : 'text-banker'}`}>{last30Profit >= 0 ? '+' : ''}${last30Profit.toFixed(2)}</div>
        </div>
        <div className="p-4 rounded-xl glass-card">
          <div className="text-[10px] tracking-widest text-text-dim uppercase">30日 手数料合計</div>
          <div className="text-2xl font-bold text-accent mt-1">${last30Fee.toFixed(2)}</div>
        </div>
      </div>

      {/* History table */}
      <div className="p-5 rounded-2xl glass-card">
        <div className="flex items-center justify-between mb-4 gap-3 flex-wrap">
          <h2 className="text-lg font-bold">履歴 (最大 60 件)</h2>
          <span className="text-xs text-text-dim">JST 日次確定ベース</span>
        </div>
        {rows.length ? (
          <div className="overflow-x-auto">
            <table className="min-w-[760px] w-full text-sm">
              <thead>
                <tr className="text-text-muted text-left">
                  <th className="pb-2">日付</th>
                  <th className="pb-2">日次 PnL</th>
                  <th className="pb-2">Net</th>
                  <th className="pb-2">手数料</th>
                  <th className="pb-2">Outstanding</th>
                  <th className="pb-2">ステータス</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row, idx) => {
                  const date = String(row.settle_date || row.date || '')
                  const dailyProfit = Number(row.daily_profit || 0)
                  const netProfit = Number(row.net_profit ?? row.daily_profit ?? 0)
                  const fee = Number(row.operator_fee_amount ?? row.fee_amount ?? 0)
                  const outstanding = Number(row.outstanding_amount ?? 0)
                  const statusLabel = String(row.status || (outstanding > 0 ? 'unpaid' : 'paid'))
                  return (
                    <tr key={`${row.id || idx}-${date}`} className="border-t border-accent/10">
                      <td className="py-2">{date || '—'}</td>
                      <td className={`py-2 font-bold ${dailyProfit >= 0 ? 'text-green-400' : 'text-banker'}`}>{dailyProfit >= 0 ? '+' : ''}${dailyProfit.toFixed(2)}</td>
                      <td className={`py-2 ${netProfit >= 0 ? 'text-text' : 'text-banker'}`}>{netProfit >= 0 ? '+' : ''}${netProfit.toFixed(2)}</td>
                      <td className="py-2 text-accent">${fee.toFixed(2)}</td>
                      <td className={`py-2 ${outstanding > 0 ? 'text-yellow-400' : 'text-text-muted'}`}>${outstanding.toFixed(2)}</td>
                      <td className="py-2">
                        <span className={`px-2 py-0.5 rounded text-xs ${
                          statusLabel === 'unpaid' ? 'bg-yellow-500/20 text-yellow-400' :
                          statusLabel === 'paid' ? 'bg-green-500/20 text-green-400' :
                          'bg-slate-500/20 text-slate-300'
                        }`}>{statusLabel}</span>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="text-text-muted text-sm">まだ精算履歴がありません。受け子で BET セッションが完了し、JST 00:05 の cron が走ると 1 行追加されます。</p>
        )}
      </div>
    </div>
  )
}
