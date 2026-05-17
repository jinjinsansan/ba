import { createClient } from '@/lib/supabase-server'
import Link from 'next/link'

export default async function BalancePage() {
  const supabase = await createClient()
  const { data: { user } } = await supabase.auth.getUser()
  if (!user) return null

  const [{ data: billing }, { data: charges }] = await Promise.all([
    supabase.from('billing').select('*').eq('user_id', user.id).single(),
    supabase.from('charges').select('*').eq('user_id', user.id).order('created_at', { ascending: false }),
  ])

  const pendingCount = (charges || []).filter(c => String(c.status) !== 'confirmed').length
  const lastConfirmed = (charges || []).find(c => String(c.status) === 'confirmed')
  const walletAddress = String(process.env.NEXT_PUBLIC_USDT_TRC20 || '').trim()

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between gap-3 flex-wrap">
        <div>
          <div className="hud-label mb-2">Balance</div>
          <h1 className="text-2xl sm:text-3xl font-hud">残高・チャージ</h1>
        </div>
        <Link href="/dashboard/charge" className="btn-primary px-5 py-2.5 text-sm">今すぐ資金追加</Link>
      </div>

      {/* Current balances */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
        <div className="p-4 rounded-xl glass-card">
          <div className="text-[10px] tracking-widest text-text-dim uppercase">Current Balance</div>
          <div className="text-2xl font-bold text-text mt-1">
            {billing?.is_free ? '— FREE' : `$${Number(billing?.balance || 0).toFixed(2)}`}
          </div>
        </div>
        <div className="p-4 rounded-xl glass-card">
          <div className="text-[10px] tracking-widest text-text-dim uppercase">Total Charged</div>
          <div className="text-2xl font-bold text-text mt-1">${Number(billing?.total_charged || 0).toFixed(2)}</div>
        </div>
        <div className="p-4 rounded-xl glass-card">
          <div className="text-[10px] tracking-widest text-text-dim uppercase">Carry Loss</div>
          <div className="text-2xl font-bold text-banker mt-1">${Number(billing?.carry_loss || 0).toFixed(2)}</div>
        </div>
      </div>

      {/* Charge guide */}
      <div className="p-5 rounded-2xl glass-card">
        <h2 className="text-lg font-bold mb-3">チャージ手順</h2>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 text-xs mb-4">
          <div className="p-3 rounded-lg bg-bg-glass border border-accent/10">
            <div className="text-text-dim">未確認チャージ</div>
            <div className={`text-base font-semibold mt-1 ${pendingCount > 0 ? 'text-yellow-400' : 'text-green-400'}`}>{pendingCount} 件</div>
          </div>
          <div className="p-3 rounded-lg bg-bg-glass border border-accent/10">
            <div className="text-text-dim">最終反映</div>
            <div className="text-base font-semibold text-text mt-1">
              {lastConfirmed ? new Date(lastConfirmed.created_at).toLocaleDateString('ja-JP') : '未反映'}
            </div>
          </div>
          <div className="p-3 rounded-lg bg-bg-glass border border-accent/10">
            <div className="text-text-dim">プラン</div>
            <div className="text-base font-semibold text-text mt-1">
              {billing?.is_free ? 'FREE' : `${billing ? (Number(billing.profit_share_rate) * 100).toFixed(0) : '?'}% Share`}
            </div>
          </div>
        </div>
        <div className="space-y-2 text-xs text-text-muted">
          <div className="flex items-start gap-2"><span className="text-accent">1.</span><span>「今すぐ資金追加」から金額を入力して申請</span></div>
          <div className="flex items-start gap-2"><span className="text-accent">2.</span><span>USDT (TRC-20) を送金</span></div>
          <div className="flex items-start gap-2"><span className="text-accent">3.</span><span>管理承認後に残高へ反映 (未払いがあれば自動充当)</span></div>
        </div>
        {walletAddress && (
          <div className="mt-3 text-[11px] text-text-dim break-all">送金先(TRC-20): {walletAddress}</div>
        )}
      </div>

      {/* Charge history */}
      <div className="p-5 rounded-2xl glass-card">
        <h2 className="text-lg font-bold mb-4">チャージ履歴</h2>
        {charges?.length ? (
          <div className="overflow-x-auto">
            <table className="min-w-[520px] w-full text-sm">
              <thead>
                <tr className="text-text-muted text-left">
                  <th className="pb-2">日付</th>
                  <th className="pb-2">金額</th>
                  <th className="pb-2">ステータス</th>
                </tr>
              </thead>
              <tbody>
                {charges.map(c => (
                  <tr key={c.id} className="border-t border-accent/10">
                    <td className="py-2">{new Date(c.created_at).toLocaleDateString()}</td>
                    <td className="py-2 font-bold">${Number(c.amount).toLocaleString()}</td>
                    <td className="py-2">
                      <span className={`px-2 py-0.5 rounded text-xs ${c.status === 'confirmed' ? 'bg-green-500/20 text-green-400' : 'bg-yellow-500/20 text-yellow-400'}`}>
                        {c.status}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="text-text-muted text-sm">まだチャージ履歴がありません。</p>
        )}
      </div>
    </div>
  )
}
