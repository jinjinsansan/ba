import { createAdminClient } from '@/lib/supabase-admin'
import { revalidatePath } from 'next/cache'
import Link from 'next/link'
import { notFound } from 'next/navigation'
import RealtimePnlCard from '../../../dashboard/RealtimePnlCard'

export const dynamic = 'force-dynamic'

type Params = { id: string }

export default async function AdminUserDetailPage({ params }: { params: Promise<Params> }) {
  const { id } = await params
  const admin = createAdminClient()

  const [
    { data: profile },
    { data: billing },
    { data: orders },
    { data: charges },
    { data: deductions },
    { data: invoices },
    { data: deliverables },
    { data: commissionsAsReferrer },
    { data: commissionsAsReferred },
  ] = await Promise.all([
    admin.from('profiles').select('*').eq('id', id).single(),
    admin.from('billing').select('*').eq('user_id', id).single(),
    admin.from('orders').select('*').eq('user_id', id).order('created_at', { ascending: false }),
    admin.from('charges').select('*').eq('user_id', id).order('created_at', { ascending: false }),
    admin.from('deductions').select('*').eq('user_id', id).order('date', { ascending: false }).limit(30),
    admin.from('daily_profit_invoices').select('*').eq('user_id', id).order('settle_date', { ascending: false }).limit(30),
    admin.from('deliverables').select('*').eq('user_id', id).order('created_at', { ascending: false }),
    admin.from('referral_commissions').select('*').eq('referrer_id', id),
    admin.from('referral_commissions').select('*').eq('referred_id', id),
  ])

  if (!profile) notFound()

  const botConfig = (billing?.bot_config && typeof billing.bot_config === 'object')
    ? (billing.bot_config as Record<string, unknown>)
    : {}
  const sessionState = (billing?.session_state && typeof billing.session_state === 'object')
    ? (billing.session_state as Record<string, unknown>)
    : null

  const totalCommissionEarned = (commissionsAsReferrer || []).reduce((s, c) => s + Number(c.commission_amount || 0), 0)

  // ===== Server Actions =====
  async function updateBalance(formData: FormData) {
    'use server'
    const newBalance = parseFloat(String(formData.get('balance') || '0'))
    if (!Number.isFinite(newBalance) || newBalance < 0) return
    const a = createAdminClient()
    await a.from('billing').update({ balance: newBalance, updated_at: new Date().toISOString() }).eq('user_id', id)
    revalidatePath(`/admin/users/${id}`)
  }
  async function updateProfitShareRate(formData: FormData) {
    'use server'
    const pct = parseFloat(String(formData.get('rate') || '0'))
    if (!Number.isFinite(pct) || pct < 0 || pct > 100) return
    const a = createAdminClient()
    await a.from('billing').update({ profit_share_rate: pct / 100, updated_at: new Date().toISOString() }).eq('user_id', id)
    revalidatePath(`/admin/users/${id}`)
  }
  async function toggleSuspended() {
    'use server'
    const a = createAdminClient()
    const { data: cur } = await a.from('billing').select('suspended').eq('user_id', id).single()
    await a.from('billing').update({ suspended: !cur?.suspended, grace_deadline: !cur?.suspended ? new Date().toISOString() : null, updated_at: new Date().toISOString() }).eq('user_id', id)
    revalidatePath(`/admin/users/${id}`)
  }
  async function toggleFree() {
    'use server'
    const a = createAdminClient()
    const { data: cur } = await a.from('billing').select('is_free').eq('user_id', id).single()
    await a.from('billing').update({ is_free: !cur?.is_free, updated_at: new Date().toISOString() }).eq('user_id', id)
    revalidatePath(`/admin/users/${id}`)
  }
  async function approveCharge(formData: FormData) {
    'use server'
    const chargeId = String(formData.get('chargeId') || '')
    if (!chargeId) return
    const a = createAdminClient()
    const { data: charge } = await a.from('charges').select('*').eq('id', chargeId).single()
    if (!charge) return
    const { data: b } = await a.from('billing').select('balance, total_charged').eq('user_id', id).single()
    const newBalance = Number(b?.balance || 0) + Number(charge.amount || 0)
    const newTotal = Number(b?.total_charged || 0) + Number(charge.amount || 0)
    await a.from('charges').update({ status: 'confirmed', confirmed_at: new Date().toISOString() }).eq('id', chargeId)
    await a.from('billing').update({ balance: newBalance, total_charged: newTotal, suspended: false, updated_at: new Date().toISOString() }).eq('user_id', id)
    revalidatePath(`/admin/users/${id}`)
  }
  async function rejectCharge(formData: FormData) {
    'use server'
    const chargeId = String(formData.get('chargeId') || '')
    if (!chargeId) return
    const a = createAdminClient()
    await a.from('charges').update({ status: 'rejected', confirmed_at: new Date().toISOString() }).eq('id', chargeId)
    revalidatePath(`/admin/users/${id}`)
  }
  async function unlinkTelegram() {
    'use server'
    const a = createAdminClient()
    const { data: row } = await a.from('billing').select('bot_config').eq('user_id', id).maybeSingle()
    const cur = row?.bot_config && typeof row.bot_config === 'object' ? ({ ...(row.bot_config as Record<string, unknown>) }) : {}
    delete cur.customer_telegram_chat_id
    delete cur.customer_telegram_username
    delete cur.customer_telegram_linked_at
    cur.customer_telegram_enabled = false
    await a.from('billing').upsert({ user_id: id, bot_config: cur, updated_at: new Date().toISOString() }, { onConflict: 'user_id' })
    revalidatePath(`/admin/users/${id}`)
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between flex-wrap gap-3">
        <div>
          <Link href="/admin/users" className="text-xs text-text-muted hover:text-text">← ユーザー一覧</Link>
          <h1 className="text-2xl sm:text-3xl font-hud mt-2 break-all">{profile.email}</h1>
          <div className="flex gap-2 mt-3 flex-wrap">
            {profile.is_admin && <span className="text-[10px] bg-yellow-500/20 text-yellow-400 px-2 py-0.5 rounded uppercase tracking-widest">Admin</span>}
            {billing?.is_free && <span className="text-[10px] bg-accent/20 text-accent px-2 py-0.5 rounded uppercase tracking-widest">Free</span>}
            {billing?.suspended && <span className="text-[10px] bg-banker/20 text-banker px-2 py-0.5 rounded uppercase tracking-widest">Locked</span>}
            {!billing?.suspended && !billing?.is_free && <span className="text-[10px] bg-green-500/20 text-green-400 px-2 py-0.5 rounded uppercase tracking-widest">Active</span>}
          </div>
        </div>
        <div className="text-right text-xs text-text-dim">
          <div>登録: {new Date(profile.created_at).toLocaleString('ja-JP')}</div>
          <div>ID: {profile.id.slice(0, 8)}...</div>
          {profile.referral_code && <div>紹介コード: {profile.referral_code}</div>}
        </div>
      </div>

      {/* 概要 (Stats) */}
      <section className="p-5 rounded-2xl glass-card">
        <h2 className="text-lg font-bold mb-3">概要</h2>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <div className="p-3 rounded-lg bg-bg-glass border border-accent/10">
            <div className="text-[10px] tracking-widest text-text-dim uppercase">Balance</div>
            <div className="text-xl font-bold text-text mt-1">${Number(billing?.balance || 0).toFixed(2)}</div>
          </div>
          <div className="p-3 rounded-lg bg-bg-glass border border-accent/10">
            <div className="text-[10px] tracking-widest text-text-dim uppercase">Profit Share</div>
            <div className="text-xl font-bold text-text mt-1">{billing ? `${(Number(billing.profit_share_rate) * 100).toFixed(0)}%` : '—'}</div>
          </div>
          <div className="p-3 rounded-lg bg-bg-glass border border-accent/10">
            <div className="text-[10px] tracking-widest text-text-dim uppercase">Total Charged</div>
            <div className="text-xl font-bold text-text mt-1">${Number(billing?.total_charged || 0).toFixed(2)}</div>
          </div>
          <div className="p-3 rounded-lg bg-bg-glass border border-accent/10">
            <div className="text-[10px] tracking-widest text-text-dim uppercase">Carry Loss</div>
            <div className="text-xl font-bold text-banker mt-1">${Number(billing?.carry_loss || 0).toFixed(2)}</div>
          </div>
        </div>
      </section>

      {/* Billing 操作 */}
      <section className="p-5 rounded-2xl glass-card">
        <h2 className="text-lg font-bold mb-3">Billing 操作</h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <form action={updateBalance} className="space-y-2">
            <label className="block text-xs text-text-muted">残高を手動設定 ($)</label>
            <div className="flex gap-2">
              <input name="balance" type="number" step="0.01" defaultValue={Number(billing?.balance || 0).toFixed(2)} className="flex-1 px-3 py-2 rounded bg-bg-glass border border-accent/15 text-text text-sm" />
              <button type="submit" className="btn-outline px-4 py-2 text-xs">更新</button>
            </div>
          </form>

          <form action={updateProfitShareRate} className="space-y-2">
            <label className="block text-xs text-text-muted">分配率 (%)</label>
            <div className="flex gap-2">
              <input name="rate" type="number" min="0" max="100" defaultValue={billing ? (Number(billing.profit_share_rate) * 100).toFixed(0) : '20'} className="flex-1 px-3 py-2 rounded bg-bg-glass border border-accent/15 text-text text-sm" />
              <button type="submit" className="btn-outline px-4 py-2 text-xs">更新</button>
            </div>
          </form>

          <form action={toggleSuspended}>
            <button type="submit" className={`w-full py-2 rounded text-sm ${billing?.suspended ? 'bg-green-500/15 text-green-400 border border-green-500/30 hover:border-green-500/60' : 'bg-banker/15 text-banker border border-banker/30 hover:border-banker/60'} transition`}>
              {billing?.suspended ? 'サスペンド解除' : 'サスペンドする'}
            </button>
          </form>

          <form action={toggleFree}>
            <button type="submit" className={`w-full py-2 rounded text-sm ${billing?.is_free ? 'bg-text-muted/15 text-text-muted border border-text-muted/30' : 'bg-accent/15 text-accent border border-accent/30 hover:border-accent/60'} transition`}>
              {billing?.is_free ? 'FREE モードを解除' : 'FREE モードにする'}
            </button>
          </form>
        </div>
      </section>

      {/* Realtime session_state */}
      <section className="p-5 rounded-2xl glass-card">
        <h2 className="text-lg font-bold mb-3">ライブ運用状況 (session_state)</h2>
        <RealtimePnlCard initial={sessionState} />
      </section>

      {/* Bot Config */}
      <section className="p-5 rounded-2xl glass-card">
        <div className="flex items-center justify-between mb-3 flex-wrap gap-2">
          <h2 className="text-lg font-bold">Bot Config / Telegram</h2>
          {!!botConfig.customer_telegram_chat_id && (
            <form action={unlinkTelegram}>
              <button type="submit" className="btn-outline text-xs px-3 py-1">Telegram 連携を解除</button>
            </form>
          )}
        </div>
        <div className="text-xs space-y-2">
          <div>
            <span className="text-text-dim">Telegram 連携: </span>
            <span className={botConfig.customer_telegram_chat_id ? 'text-green-400' : 'text-text-muted'}>
              {botConfig.customer_telegram_chat_id ? `✓ ${botConfig.customer_telegram_username ? '@' + String(botConfig.customer_telegram_username) : 'linked'}` : '未連携'}
            </span>
          </div>
          {!!botConfig.customer_telegram_linked_at && String(botConfig.customer_telegram_linked_at).length > 0 && (
            <div><span className="text-text-dim">連携日時: </span>{new Date(String(botConfig.customer_telegram_linked_at)).toLocaleString('ja-JP')}</div>
          )}
          <details className="mt-3">
            <summary className="text-text-muted cursor-pointer">bot_config JSON 全体 (debug)</summary>
            <pre className="mt-2 p-3 rounded bg-bg-glass border border-accent/10 text-[10px] overflow-x-auto">{JSON.stringify(botConfig, null, 2)}</pre>
          </details>
        </div>
      </section>

      {/* チャージ履歴 + 承認 */}
      <section className="p-5 rounded-2xl glass-card">
        <h2 className="text-lg font-bold mb-3">チャージ履歴 ({(charges || []).length})</h2>
        {charges?.length ? (
          <div className="overflow-x-auto">
            <table className="min-w-[640px] w-full text-sm">
              <thead>
                <tr className="text-text-muted text-left border-b border-accent/10">
                  <th className="pb-2">日付</th><th className="pb-2">金額</th><th className="pb-2">ステータス</th><th className="pb-2">操作</th>
                </tr>
              </thead>
              <tbody>
                {charges.map(c => (
                  <tr key={c.id} className="border-b border-white/5">
                    <td className="py-2">{new Date(c.created_at).toLocaleDateString('ja-JP')}</td>
                    <td className="py-2 font-bold">${Number(c.amount).toLocaleString()}</td>
                    <td className="py-2">
                      <span className={`px-2 py-0.5 rounded text-xs ${c.status === 'confirmed' ? 'bg-green-500/20 text-green-400' : c.status === 'rejected' ? 'bg-banker/20 text-banker' : 'bg-yellow-500/20 text-yellow-400'}`}>{c.status}</span>
                    </td>
                    <td className="py-2">
                      {c.status === 'pending' && (
                        <div className="flex gap-1">
                          <form action={approveCharge}>
                            <input type="hidden" name="chargeId" value={c.id} />
                            <button className="text-xs bg-green-500/15 text-green-400 hover:bg-green-500/25 px-2 py-1 rounded">承認</button>
                          </form>
                          <form action={rejectCharge}>
                            <input type="hidden" name="chargeId" value={c.id} />
                            <button className="text-xs bg-banker/15 text-banker hover:bg-banker/25 px-2 py-1 rounded">却下</button>
                          </form>
                        </div>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : <p className="text-text-muted text-sm">なし</p>}
      </section>

      {/* 日次精算 (invoices) */}
      <section className="p-5 rounded-2xl glass-card">
        <h2 className="text-lg font-bold mb-3">日次精算履歴 (直近 30 件)</h2>
        {(invoices?.length || deductions?.length) ? (
          <div className="overflow-x-auto">
            <table className="min-w-[760px] w-full text-sm">
              <thead>
                <tr className="text-text-muted text-left border-b border-accent/10">
                  <th className="pb-2">日付</th><th className="pb-2">PnL</th><th className="pb-2">Net</th><th className="pb-2">手数料</th><th className="pb-2">未払い</th><th className="pb-2">Status</th>
                </tr>
              </thead>
              <tbody>
                {(invoices?.length ? invoices : (deductions || [])).map((row: { id?: string; settle_date?: string; date?: string; daily_profit?: number; net_profit?: number; operator_fee_amount?: number; fee_amount?: number; outstanding_amount?: number; status?: string }, idx: number) => {
                  const date = String(row.settle_date || row.date || '')
                  const dp = Number(row.daily_profit || 0)
                  const np = Number(row.net_profit ?? row.daily_profit ?? 0)
                  const fee = Number(row.operator_fee_amount ?? row.fee_amount ?? 0)
                  const out = Number(row.outstanding_amount || 0)
                  const st = String(row.status || (out > 0 ? 'unpaid' : 'paid'))
                  return (
                    <tr key={`${row.id || idx}-${date}`} className="border-b border-white/5">
                      <td className="py-2">{date}</td>
                      <td className={`py-2 font-bold ${dp >= 0 ? 'text-green-400' : 'text-banker'}`}>{dp >= 0 ? '+' : ''}${dp.toFixed(2)}</td>
                      <td className={`py-2 ${np >= 0 ? 'text-text' : 'text-banker'}`}>{np >= 0 ? '+' : ''}${np.toFixed(2)}</td>
                      <td className="py-2 text-accent">${fee.toFixed(2)}</td>
                      <td className={`py-2 ${out > 0 ? 'text-yellow-400' : 'text-text-muted'}`}>${out.toFixed(2)}</td>
                      <td className="py-2"><span className={`px-2 py-0.5 rounded text-xs ${st === 'unpaid' ? 'bg-yellow-500/20 text-yellow-400' : st === 'paid' ? 'bg-green-500/20 text-green-400' : 'bg-slate-500/20 text-slate-300'}`}>{st}</span></td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        ) : <p className="text-text-muted text-sm">なし</p>}
      </section>

      {/* 注文履歴 */}
      <section className="p-5 rounded-2xl glass-card">
        <h2 className="text-lg font-bold mb-3">注文履歴 ({(orders || []).length})</h2>
        {orders?.length ? (
          <div className="overflow-x-auto">
            <table className="min-w-[520px] w-full text-sm">
              <thead><tr className="text-text-muted text-left border-b border-accent/10"><th className="pb-2">日付</th><th className="pb-2">タイプ</th><th className="pb-2">金額</th><th className="pb-2">ステータス</th></tr></thead>
              <tbody>
                {orders.map(o => (
                  <tr key={o.id} className="border-b border-white/5">
                    <td className="py-2">{new Date(o.created_at).toLocaleDateString('ja-JP')}</td>
                    <td className="py-2">{o.type || '—'}</td>
                    <td className="py-2 font-bold">${Number(o.amount || 0).toFixed(2)}</td>
                    <td className="py-2"><span className={`px-2 py-0.5 rounded text-xs ${o.status === 'confirmed' || o.status === 'delivered' ? 'bg-green-500/20 text-green-400' : 'bg-yellow-500/20 text-yellow-400'}`}>{o.status}</span></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : <p className="text-text-muted text-sm">なし</p>}
      </section>

      {/* 紹介情報 */}
      <section className="p-5 rounded-2xl glass-card">
        <h2 className="text-lg font-bold mb-3">紹介情報</h2>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 mb-4">
          <div className="p-3 rounded-lg bg-bg-glass border border-accent/10">
            <div className="text-[10px] text-text-dim tracking-widest uppercase">紹介コード</div>
            <div className="text-sm font-bold mt-1">{profile.referral_code || '—'}</div>
          </div>
          <div className="p-3 rounded-lg bg-bg-glass border border-accent/10">
            <div className="text-[10px] text-text-dim tracking-widest uppercase">紹介者として獲得</div>
            <div className="text-sm font-bold mt-1">${totalCommissionEarned.toFixed(2)}</div>
          </div>
          <div className="p-3 rounded-lg bg-bg-glass border border-accent/10">
            <div className="text-[10px] text-text-dim tracking-widest uppercase">被紹介として支払い</div>
            <div className="text-sm font-bold mt-1">{(commissionsAsReferred || []).length} 件</div>
          </div>
        </div>
        {profile.referred_by && <div className="text-xs text-text-muted">この人を紹介したコード: {profile.referred_by}</div>}
      </section>

      {/* ライセンス / 配布物 */}
      <section className="p-5 rounded-2xl glass-card">
        <h2 className="text-lg font-bold mb-3">配布物 ({(deliverables || []).length})</h2>
        {deliverables?.length ? (
          <div className="space-y-2 text-sm">
            {deliverables.map(d => (
              <div key={d.id} className="flex items-center justify-between border-t border-accent/10 pt-2">
                <div>
                  <span className="text-text font-semibold">v{d.version}</span>
                  <span className="text-text-dim text-xs ml-2">{d.created_at ? new Date(d.created_at).toLocaleDateString('ja-JP') : ''}</span>
                </div>
                <code className="text-[10px] text-text-dim break-all max-w-[60%] text-right">{d.file_path}</code>
              </div>
            ))}
          </div>
        ) : <p className="text-text-muted text-sm">なし</p>}
      </section>
    </div>
  )
}
