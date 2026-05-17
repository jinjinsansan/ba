import { createAdminClient } from '@/lib/supabase-admin'
import { revalidatePath } from 'next/cache'
import Link from 'next/link'
import { notFound } from 'next/navigation'
import { Card, CardHead } from '@/components/ui/Card'
import { PageHeader, Label } from '@/components/ui/PageHeader'
import { Pill } from '@/components/ui/Pill'
import { Money } from '@/components/ui/Money'
import { Button } from '@/components/ui/Button'
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

  const referredByCode = String(profile.referred_by || '').trim()
  const { data: referrer } = referredByCode
    ? await admin.from('profiles').select('id, email, referral_code').eq('referral_code', referredByCode).maybeSingle()
    : { data: null }

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
  async function updateReferrerShareRate(formData: FormData) {
    'use server'
    const pct = parseFloat(String(formData.get('rate') || '0'))
    if (!Number.isFinite(pct) || pct < 0 || pct > 100) return
    const a = createAdminClient()
    await a.from('billing').update({ referrer_share_rate: pct / 100, updated_at: new Date().toISOString() }).eq('user_id', id)
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
    <div>
      <div className="mb-4">
        <Link href="/admin/users" className="font-mono text-[11px] text-text-dim hover:text-cyan tracking-[0.15em] uppercase">← Users 一覧へ</Link>
      </div>

      <PageHeader
        kicker="Admin · User Detail"
        title={profile.email}
        sub={`ID: ${profile.id.slice(0, 8)}... / 登録: ${new Date(profile.created_at).toLocaleString('ja-JP')}${profile.referral_code ? ` / コード: ${profile.referral_code}` : ''}`}
        right={
          <div className="flex gap-1 flex-wrap">
            {profile.is_admin && <Pill tone="admin">ADMIN</Pill>}
            {billing?.is_free && <Pill tone="free">FREE</Pill>}
            {billing?.suspended && <Pill tone="danger">SUSPENDED</Pill>}
            {!billing?.suspended && !billing?.is_free && <Pill tone="live">ACTIVE</Pill>}
          </div>
        }
      />

      {/* 概要 */}
      <Card padded={false} className="mb-4">
        <CardHead>概要</CardHead>
        <div className="grid grid-cols-2 sm:grid-cols-4 px-5 py-5">
          <div>
            <Label>Balance</Label>
            <div className="mt-1.5">
              {billing?.is_free
                ? <span className="text-xl font-semibold text-cyan">課金免除</span>
                : <Money value={Number(billing?.balance ?? 0)} size="xl" weight="bold" />}
            </div>
          </div>
          <div className="sm:pl-4 sm:border-l border-white/[0.07]">
            <Label>Profit Share</Label>
            <div className="mt-1.5 text-xl font-semibold text-text font-mono">{billing ? `${(Number(billing.profit_share_rate) * 100).toFixed(0)}%` : '—'}</div>
          </div>
          <div className="sm:pl-4 sm:border-l border-white/[0.07]">
            <Label>Total Charged</Label>
            <div className="mt-1.5"><Money value={Number(billing?.total_charged ?? 0)} size="xl" weight="semibold" /></div>
          </div>
          <div className="sm:pl-4 sm:border-l border-white/[0.07]">
            <Label>Carry Loss</Label>
            <div className="mt-1.5"><Money value={Number(billing?.carry_loss ?? 0)} size="xl" weight="semibold" tone={Number(billing?.carry_loss ?? 0) > 0 ? 'lose' : 'muted'} /></div>
          </div>
        </div>
      </Card>

      {/* Billing 操作 */}
      <Card padded={false} className="mb-4">
        <CardHead>Billing 操作</CardHead>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 px-5 py-5">
          <form action={updateBalance} className="space-y-2">
            <Label>残高を手動設定 ($)</Label>
            <div className="flex gap-2">
              <input name="balance" type="number" step="0.01" defaultValue={Number(billing?.balance || 0).toFixed(2)} className="flex-1 px-3 py-2 rounded bg-white/[0.02] border border-white/[0.07] text-text text-sm font-mono" />
              <Button tone="outline" size="md" type="submit">更新</Button>
            </div>
          </form>

          <form action={updateProfitShareRate} className="space-y-2">
            <Label>分配率 (%)</Label>
            <div className="flex gap-2">
              <input name="rate" type="number" min="0" max="100" defaultValue={billing ? (Number(billing.profit_share_rate) * 100).toFixed(0) : '20'} className="flex-1 px-3 py-2 rounded bg-white/[0.02] border border-white/[0.07] text-text text-sm font-mono" />
              <Button tone="outline" size="md" type="submit">更新</Button>
            </div>
          </form>

          <form action={toggleSuspended}>
            <Button tone={billing?.suspended ? 'success' : 'danger'} size="md" type="submit" className="w-full">
              {billing?.suspended ? 'サスペンド解除' : 'サスペンドする'}
            </Button>
          </form>

          <form action={toggleFree}>
            <Button tone={billing?.is_free ? 'secondary' : 'outline'} size="md" type="submit" className="w-full">
              {billing?.is_free ? 'FREE モードを解除' : 'FREE モードにする'}
            </Button>
          </form>
        </div>
      </Card>

      {/* Realtime */}
      <Card padded={false} className="mb-4">
        <CardHead>ライブ運用状況 (session_state)</CardHead>
        <div className="px-5 py-5">
          <RealtimePnlCard initial={sessionState} />
        </div>
      </Card>

      {/* Bot Config / Telegram */}
      <Card padded={false} className="mb-4">
        <CardHead right={!!botConfig.customer_telegram_chat_id ? (
          <form action={unlinkTelegram}><Button tone="danger" size="sm" type="submit">解除</Button></form>
        ) : undefined}>
          Bot Config / Telegram
        </CardHead>
        <div className="px-5 py-5 text-sm space-y-3">
          <div className="flex items-center gap-2">
            <Label>Telegram 連携</Label>
            {botConfig.customer_telegram_chat_id
              ? <Pill tone="live" dot>連携済み{botConfig.customer_telegram_username ? ` (@${String(botConfig.customer_telegram_username)})` : ''}</Pill>
              : <Pill tone="info">未連携</Pill>}
          </div>
          {!!botConfig.customer_telegram_linked_at && (
            <div className="text-xs text-text-muted">連携日時: {new Date(String(botConfig.customer_telegram_linked_at)).toLocaleString('ja-JP')}</div>
          )}
          <details className="mt-3">
            <summary className="text-xs text-text-muted cursor-pointer hover:text-text">bot_config JSON 全体 (debug)</summary>
            <pre className="mt-2 p-3 rounded bg-white/[0.02] border border-white/[0.07] text-[10px] overflow-x-auto font-mono">{JSON.stringify(botConfig, null, 2)}</pre>
          </details>
        </div>
      </Card>

      {/* チャージ履歴 */}
      <Card padded={false} className="mb-4">
        <CardHead>チャージ履歴 ({(charges || []).length})</CardHead>
        {charges?.length ? (
          <div className="overflow-x-auto">
            <table className="min-w-[640px] w-full text-sm">
              <thead>
                <tr className="border-b border-white/[0.07]">
                  {[['日付','left'],['金額','right'],['ステータス','left'],['操作','left']].map(([h,a],i) => (
                    <th key={i} className={['px-5 py-3 font-mono text-[10px] text-text-dim tracking-[0.15em] uppercase font-normal', a === 'right' ? 'text-right' : 'text-left'].join(' ')}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {charges.map((c, idx) => (
                  <tr key={c.id} className={idx ? 'border-t border-white/[0.07]' : ''}>
                    <td className="px-5 py-3 font-mono text-xs text-text-muted">{new Date(c.created_at).toLocaleDateString('ja-JP')}</td>
                    <td className="px-5 py-3 text-right"><Money value={Number(c.amount)} size="md" weight="bold" /></td>
                    <td className="px-5 py-3">
                      <Pill tone={c.status === 'confirmed' ? 'live' : c.status === 'rejected' ? 'danger' : 'warn'}>{c.status}</Pill>
                    </td>
                    <td className="px-5 py-3">
                      {c.status === 'pending' && (
                        <div className="flex gap-1">
                          <form action={approveCharge}>
                            <input type="hidden" name="chargeId" value={c.id} />
                            <Button tone="success" size="sm" type="submit">承認</Button>
                          </form>
                          <form action={rejectCharge}>
                            <input type="hidden" name="chargeId" value={c.id} />
                            <Button tone="danger" size="sm" type="submit">却下</Button>
                          </form>
                        </div>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : <div className="px-5 py-6 text-text-muted text-sm">なし</div>}
      </Card>

      {/* 日次精算 */}
      <Card padded={false} className="mb-4">
        <CardHead>日次精算履歴 (直近 30 件)</CardHead>
        {(invoices?.length || deductions?.length) ? (
          <div className="overflow-x-auto">
            <table className="min-w-[760px] w-full text-sm">
              <thead>
                <tr className="border-b border-white/[0.07]">
                  {[['日付','left'],['PnL','right'],['Net','right'],['手数料','right'],['未払い','right'],['Status','left']].map(([h,a],i) => (
                    <th key={i} className={['px-5 py-3 font-mono text-[10px] text-text-dim tracking-[0.15em] uppercase font-normal', a === 'right' ? 'text-right' : 'text-left'].join(' ')}>{h}</th>
                  ))}
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
                    <tr key={`${row.id || idx}-${date}`} className={idx ? 'border-t border-white/[0.07]' : ''}>
                      <td className="px-5 py-3 font-mono text-xs text-text-muted">{date}</td>
                      <td className="px-5 py-3 text-right"><Money value={dp} sign size="md" weight="semibold" tone={dp >= 0 ? 'win' : 'lose'} /></td>
                      <td className="px-5 py-3 text-right"><Money value={np} sign size="md" weight="medium" tone={np >= 0 ? undefined : 'lose'} /></td>
                      <td className="px-5 py-3 text-right"><Money value={fee} size="md" weight="medium" tone="cyan" /></td>
                      <td className="px-5 py-3 text-right"><Money value={out} size="md" weight="medium" tone={out > 0 ? 'warn' : 'muted'} /></td>
                      <td className="px-5 py-3"><Pill tone={st === 'unpaid' ? 'warn' : st === 'paid' ? 'live' : 'paid'}>{st}</Pill></td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        ) : <div className="px-5 py-6 text-text-muted text-sm">なし</div>}
      </Card>

      {/* 注文履歴 */}
      <Card padded={false} className="mb-4">
        <CardHead>注文履歴 ({(orders || []).length})</CardHead>
        {orders?.length ? (
          <div className="overflow-x-auto">
            <table className="min-w-[520px] w-full text-sm">
              <thead>
                <tr className="border-b border-white/[0.07]">
                  {[['日付','left'],['タイプ','left'],['金額','right'],['ステータス','left']].map(([h,a],i) => (
                    <th key={i} className={['px-5 py-3 font-mono text-[10px] text-text-dim tracking-[0.15em] uppercase font-normal', a === 'right' ? 'text-right' : 'text-left'].join(' ')}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {orders.map((o, i) => (
                  <tr key={o.id} className={i ? 'border-t border-white/[0.07]' : ''}>
                    <td className="px-5 py-3 font-mono text-xs text-text-muted">{new Date(o.created_at).toLocaleDateString('ja-JP')}</td>
                    <td className="px-5 py-3 text-text">{o.type || '—'}</td>
                    <td className="px-5 py-3 text-right"><Money value={Number(o.amount || 0)} size="md" weight="bold" /></td>
                    <td className="px-5 py-3"><Pill tone={o.status === 'confirmed' || o.status === 'delivered' ? 'live' : 'warn'}>{o.status}</Pill></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : <div className="px-5 py-6 text-text-muted text-sm">なし</div>}
      </Card>

      {/* 紹介情報 */}
      <Card padded={false} className="mb-4">
        <CardHead>紹介情報</CardHead>
        <div className="px-5 py-5">
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 mb-4">
            <div className="p-3 rounded border border-white/[0.07] bg-white/[0.02]">
              <Label>このユーザの紹介コード</Label>
              <div className="text-sm font-bold mt-1 font-mono">{profile.referral_code || '—'}</div>
            </div>
            <div className="p-3 rounded border border-white/[0.07] bg-white/[0.02]">
              <Label>紹介者として獲得</Label>
              <div className="mt-1"><Money value={totalCommissionEarned} size="md" weight="bold" tone="win" /></div>
            </div>
            <div className="p-3 rounded border border-white/[0.07] bg-white/[0.02]">
              <Label>被紹介として支払い</Label>
              <div className="text-sm font-bold mt-1 font-mono">{(commissionsAsReferred || []).length} 件</div>
            </div>
          </div>

          {referredByCode ? (
            <div className="mt-4 p-4 rounded border border-cyan/30 bg-cyan/[0.03]">
              <div className="text-sm font-bold mb-2 text-cyan">このユーザを紹介した人 (紹介元)</div>
              {referrer ? (
                <Link href={`/admin/users/${referrer.id}`} className="text-cyan hover:underline text-sm break-all inline-block mb-3">
                  → {referrer.email} (コード: {referredByCode})
                </Link>
              ) : (
                <div className="text-text-muted text-xs mb-3">紹介コード: {referredByCode} (referrer profile が見つかりません)</div>
              )}

              <form action={updateReferrerShareRate} className="space-y-2">
                <Label>紹介者報酬率 (%)</Label>
                <p className="text-[11px] text-text-dim leading-relaxed">
                  このユーザが支払う手数料のうち何 % を上記の紹介者に渡すか (cron settle で適用)。デフォルト 20% / 未設定 0%
                </p>
                <div className="flex gap-2 items-center">
                  <input
                    name="rate" type="number" min="0" max="100" step="1"
                    defaultValue={billing && billing.referrer_share_rate !== null && billing.referrer_share_rate !== undefined ? (Number(billing.referrer_share_rate) * 100).toFixed(0) : '20'}
                    className="w-24 px-3 py-2 rounded bg-white/[0.02] border border-white/[0.07] text-text text-sm font-mono"
                  />
                  <span className="text-text-muted text-sm">%</span>
                  <Button tone="outline" size="sm" type="submit" className="ml-auto">更新</Button>
                </div>
                <div className="text-[10px] text-text-dim mt-2">
                  現在値: {billing?.referrer_share_rate !== null && billing?.referrer_share_rate !== undefined
                    ? `${(Number(billing.referrer_share_rate) * 100).toFixed(0)}%`
                    : '未設定 (default 20%)'}
                </div>
              </form>
              <div className="mt-3 text-[10px] text-text-dim">
                ※ LAPLACE_ENABLE_DYNAMIC_REFERRAL_SPLIT=true (Vercel env) のときのみ有効
              </div>
            </div>
          ) : (
            <div className="text-xs text-text-muted">このユーザを紹介した人は登録されていません (referred_by 無し)。</div>
          )}
        </div>
      </Card>

      {/* 配布物 */}
      <Card padded={false}>
        <CardHead>配布物 ({(deliverables || []).length})</CardHead>
        {deliverables?.length ? (
          <div>
            {deliverables.map((d, i) => (
              <div key={d.id} className={`flex items-center justify-between px-5 py-3 ${i ? 'border-t border-white/[0.07]' : ''}`}>
                <div>
                  <span className="text-text font-semibold font-mono">v{d.version}</span>
                  <span className="text-text-dim text-xs ml-2 font-mono">{d.created_at ? new Date(d.created_at).toLocaleDateString('ja-JP') : ''}</span>
                </div>
                <code className="text-[10px] text-text-dim break-all max-w-[60%] text-right font-mono">{d.file_path}</code>
              </div>
            ))}
          </div>
        ) : <div className="px-5 py-6 text-text-muted text-sm">なし</div>}
      </Card>
    </div>
  )
}
