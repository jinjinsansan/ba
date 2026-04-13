import { createClient } from '@/lib/supabase-server'
import { createAdminClient } from '@/lib/supabase-admin'
import { redirect } from 'next/navigation'
import Link from 'next/link'
import DashboardClient from './DashboardClient'
import SupportForm from './SupportForm'
import ReferralSection from './ReferralSection'

export default async function DashboardPage() {
  const supabase = await createClient()
  const { data: { user } } = await supabase.auth.getUser()
  if (!user) redirect('/login')

  const admin = createAdminClient()

  // 全クエリを並列実行
  const [
    { data: profile },
    { data: billing },
    { data: orders },
    { data: charges },
    { data: deductions },
    { data: deliverables },
    { data: commissions },
    { data: withdrawals },
  ] = await Promise.all([
    supabase.from('profiles').select('*').eq('id', user.id).single(),
    supabase.from('billing').select('*').eq('user_id', user.id).single(),
    supabase.from('orders').select('*').eq('user_id', user.id).order('created_at', { ascending: false }),
    supabase.from('charges').select('*').eq('user_id', user.id).order('created_at', { ascending: false }),
    supabase.from('deductions').select('*').eq('user_id', user.id).order('date', { ascending: false }).limit(30),
    supabase.from('deliverables').select('*').eq('user_id', user.id).order('created_at', { ascending: false }).limit(1),
    supabase.from('referral_commissions').select('*').eq('referrer_id', user.id),
    supabase.from('referral_withdrawals').select('*').eq('user_id', user.id).order('created_at', { ascending: false }),
  ])

  const referralCode = profile?.referral_code || ''
  const siteUrl = process.env.NEXT_PUBLIC_SITE_URL || 'https://bafather.uk'
  const referralUrl = `${siteUrl}/signup?ref=${referralCode}`

  // 紹介ユーザーと全チャージを一括取得 (N+1解消)
  const { data: referredProfiles } = await admin
    .from('profiles')
    .select('id, email, created_at')
    .eq('referred_by', referralCode)

  const referredIds = (referredProfiles || []).map(p => p.id)
  const { data: allReferredCharges } = referredIds.length > 0
    ? await admin.from('charges').select('user_id, amount').in('user_id', referredIds).eq('status', 'confirmed')
    : { data: [] }

  const referredWithCharges = (referredProfiles || []).map(p => {
    const totalCharged = (allReferredCharges || [])
      .filter(c => c.user_id === p.id)
      .reduce((s, c) => s + Number(c.amount), 0)
    return { ...p, total_charged: totalCharged, commission: totalCharged * 0.05 }
  })

  const totalEarned = commissions?.reduce((s, c) => s + Number(c.commission_amount), 0) ?? 0
  const totalWithdrawn = withdrawals?.filter(w => ['pending', 'approved'].includes(w.status))
    .reduce((s, w) => s + Number(w.amount), 0) ?? 0

  const latestOrder = orders?.[0]
  const hasPackage = latestOrder?.status === 'delivered' || latestOrder?.status === 'confirmed'
  const hasActiveCharge = billing && billing.balance > 0 && !billing.suspended
  const canDownload = !!deliverables?.length
  const latestDeliverable = deliverables?.[0]
  const deliverableDate = latestDeliverable?.created_at
    ? new Date(latestDeliverable.created_at).toISOString().split('T')[0]
    : ''

  let status: 'no_purchase' | 'pending' | 'dry_run' | 'active' | 'suspended'
  if (!latestOrder) status = 'no_purchase'
  else if (latestOrder.status === 'pending' || latestOrder.status === 'sent') status = 'pending'
  else if (billing?.suspended) status = 'suspended'
  else if (!hasActiveCharge) status = 'dry_run'
  else status = 'active'

  return (
    <div className="min-h-screen">
      {/* Header */}
      <nav className="border-b border-white/5 bg-bg-primary/80 backdrop-blur-xl">
        <div className="max-w-6xl mx-auto px-6 h-16 flex items-center justify-between">
          <Link href="/" className="text-xl font-black bg-gradient-to-r from-player to-banker bg-clip-text text-transparent">LAPLACE</Link>
          <div className="flex items-center gap-4">
            {profile?.is_admin && <Link href="/admin" className="text-sm text-slate-400 hover:text-white">Admin</Link>}
            <DashboardClient />
          </div>
        </div>
      </nav>

      <div className="max-w-6xl mx-auto px-6 py-10">
        <h1 className="text-3xl font-black mb-8">My Dashboard</h1>

        {/* Status Banner */}
        <div className={`p-6 rounded-2xl border mb-8 ${
          status === 'active' ? 'bg-green-500/10 border-green-500/30' :
          status === 'dry_run' ? 'bg-player/10 border-player/30' :
          status === 'pending' ? 'bg-yellow-500/10 border-yellow-500/30' :
          status === 'suspended' ? 'bg-banker/10 border-banker/30' :
          'bg-bg-card border-white/10'
        }`}>
          <div className="flex items-center justify-between flex-wrap gap-4">
            <div>
              <div className="text-sm text-slate-400 mb-1">Account Status</div>
              <div className={`text-2xl font-bold ${
                status === 'active' ? 'text-green-400' :
                status === 'dry_run' ? 'text-player' :
                status === 'pending' ? 'text-yellow-400' :
                status === 'suspended' ? 'text-banker' :
                'text-slate-400'
              }`}>
                {status === 'active' && 'ACTIVE — Live Betting Enabled'}
                {status === 'dry_run' && 'DRY RUN — Charge to enable live bets'}
                {status === 'pending' && 'PENDING — Awaiting payment confirmation'}
                {status === 'suspended' && 'SUSPENDED — Contact support'}
                {status === 'no_purchase' && 'No License — Purchase to get started'}
              </div>
            </div>
            {status === 'no_purchase' && (
              <Link href="/purchase" className="px-6 py-3 rounded-xl bg-gradient-to-r from-player to-accent text-white font-bold">
                Purchase License
              </Link>
            )}
            {status === 'dry_run' && (
              <Link href="/dashboard/charge" className="px-6 py-3 rounded-xl bg-gradient-to-r from-player to-accent text-white font-bold">
                Charge Balance
              </Link>
            )}
          </div>
        </div>

        {/* Stats Grid */}
        <div className="grid md:grid-cols-4 gap-4 mb-8">
          <div className="p-5 rounded-xl bg-bg-card border border-white/5">
            <div className="text-sm text-slate-400">Balance</div>
            {billing?.is_free ? (
              <div className="flex items-center gap-2 mt-1">
                <div className="text-2xl font-bold text-white">—</div>
                <span className="px-2 py-0.5 rounded text-xs font-black bg-accent/20 text-accent tracking-widest">FREE</span>
              </div>
            ) : (
              <div className="text-2xl font-bold text-white">${billing?.balance?.toFixed(2) || '0.00'}</div>
            )}
          </div>
          <div className="p-5 rounded-xl bg-bg-card border border-white/5">
            <div className="text-sm text-slate-400">Profit Share Rate</div>
            <div className="text-2xl font-bold text-white">{billing ? `${(billing.profit_share_rate * 100).toFixed(0)}%` : '—'}</div>
          </div>
          <div className="p-5 rounded-xl bg-bg-card border border-white/5">
            <div className="text-sm text-slate-400">Total Charged</div>
            <div className="text-2xl font-bold text-white">${billing?.total_charged?.toFixed(2) || '0.00'}</div>
          </div>
          <div className="p-5 rounded-xl bg-bg-card border border-white/5">
            <div className="text-sm text-slate-400">Carry Loss</div>
            <div className="text-2xl font-bold text-banker">${billing?.carry_loss?.toFixed(2) || '0.00'}</div>
          </div>
        </div>

        {/* Download + Referral */}
        <div className="grid md:grid-cols-2 gap-6 mb-8">
          {/* Download Section */}
          <div className="p-6 rounded-2xl bg-bg-card border border-white/5">
            <h2 className="text-lg font-bold mb-4">Software Download</h2>
            {canDownload ? (
              <div className="space-y-3">
                <a
                  href={`/api/download?file=${deliverables![0].file_path}`}
                  className="inline-block px-6 py-3 rounded-xl bg-gradient-to-r from-player to-accent text-white font-bold hover:opacity-90 transition"
                >
                  Download LAPLACE v{deliverables![0].version}
                </a>
                {deliverableDate && (
                  <div className="text-xs text-slate-500">Updated: {deliverableDate}</div>
                )}
              </div>
            ) : hasPackage ? (
              <p className="text-slate-400">Your download is being prepared...</p>
            ) : (
              <p className="text-slate-400">Purchase a license to download.</p>
            )}
          </div>

        </div>

        {/* Referral Section */}
        <ReferralSection
          referralUrl={referralUrl}
          referred={referredWithCharges}
          totalEarned={totalEarned}
          totalWithdrawn={totalWithdrawn}
          withdrawals={withdrawals || []}
        />

        {/* Charge History */}
        <div className="p-6 rounded-2xl bg-bg-card border border-white/5 mb-8">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-bold">Charge History</h2>
            <Link href="/dashboard/charge" className="text-sm text-player hover:underline">Add Charge</Link>
          </div>
          {charges?.length ? (
            <table className="w-full text-sm">
              <thead><tr className="text-slate-500 text-left"><th className="pb-2">Date</th><th className="pb-2">Amount</th><th className="pb-2">Status</th></tr></thead>
              <tbody>
                {charges.map(c => (
                  <tr key={c.id} className="border-t border-white/5">
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
          ) : <p className="text-slate-500 text-sm">No charges yet.</p>}
        </div>

        {/* Daily Settlements */}
        <div className="p-6 rounded-2xl bg-bg-card border border-white/5">
          <h2 className="text-lg font-bold mb-4">Daily Settlements</h2>
          {deductions?.length ? (
            <table className="w-full text-sm">
              <thead><tr className="text-slate-500 text-left"><th className="pb-2">Date</th><th className="pb-2">Profit</th><th className="pb-2">Fee</th><th className="pb-2">Note</th></tr></thead>
              <tbody>
                {deductions.map(d => (
                  <tr key={d.id} className="border-t border-white/5">
                    <td className="py-2">{d.date}</td>
                    <td className={`py-2 font-bold ${Number(d.daily_profit) >= 0 ? 'text-green-400' : 'text-banker'}`}>
                      {Number(d.daily_profit) >= 0 ? '+' : ''}${Number(d.daily_profit).toFixed(2)}
                    </td>
                    <td className="py-2 text-banker">${Number(d.fee_amount).toFixed(2)}</td>
                    <td className="py-2 text-slate-500">{d.note || '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : <p className="text-slate-500 text-sm">No settlements yet.</p>}
        </div>

        {/* Support */}
        <SupportForm />
      </div>
    </div>
  )
}
