import { createClient } from '@/lib/supabase-server'
import { createAdminClient } from '@/lib/supabase-admin'
import ReferralSection from '../../dashboard/ReferralSection'

export default async function ReferralPage() {
  const supabase = await createClient()
  const { data: { user } } = await supabase.auth.getUser()
  if (!user) return null

  const admin = createAdminClient()

  const [{ data: profile }, { data: commissions }, { data: withdrawals }] = await Promise.all([
    supabase.from('profiles').select('referral_code').eq('id', user.id).single(),
    supabase.from('referral_commissions').select('*').eq('referrer_id', user.id),
    supabase.from('referral_withdrawals').select('*').eq('user_id', user.id).order('created_at', { ascending: false }),
  ])

  const referralCode = profile?.referral_code || ''
  const siteUrl = process.env.NEXT_PUBLIC_SITE_URL || 'https://bafather.uk'
  const referralUrl = `${siteUrl}/signup?ref=${referralCode}`

  const { data: referredProfiles } = await admin
    .from('profiles')
    .select('id, email, created_at')
    .eq('referred_by', referralCode)

  const referredIds = (referredProfiles || []).map(p => p.id)
  const { data: allReferredCharges } = referredIds.length > 0
    ? await admin.from('charges').select('user_id, amount').in('user_id', referredIds).eq('status', 'confirmed')
    : { data: [] }

  const commissionByReferred = new Map<string, number>()
  for (const c of (commissions || [])) {
    const rid = String((c as { referred_id?: string }).referred_id || '')
    if (!rid) continue
    commissionByReferred.set(rid, (commissionByReferred.get(rid) || 0) + Number((c as { commission_amount?: number }).commission_amount || 0))
  }

  const referredWithCharges = (referredProfiles || []).map(p => {
    const totalCharged = (allReferredCharges || [])
      .filter(c => c.user_id === p.id)
      .reduce((s, c) => s + Number(c.amount), 0)
    return {
      ...p,
      total_charged: totalCharged,
      commission: commissionByReferred.get(p.id) || 0,
    }
  })

  const totalEarned = commissions?.reduce((s, c) => s + Number(c.commission_amount), 0) ?? 0
  const totalWithdrawn = withdrawals?.filter(w => ['pending', 'approved'].includes(w.status))
    .reduce((s, w) => s + Number(w.amount), 0) ?? 0

  return (
    <div className="space-y-6">
      <div>
        <div className="hud-label mb-2">Referral</div>
        <h1 className="text-2xl sm:text-3xl font-hud">紹介プログラム</h1>
        <p className="text-text-muted text-sm mt-2">あなたの紹介から成立したチャージに対して報酬が発生します。</p>
      </div>
      <ReferralSection
        referralUrl={referralUrl}
        referred={referredWithCharges}
        totalEarned={totalEarned}
        totalWithdrawn={totalWithdrawn}
        withdrawals={withdrawals || []}
      />
    </div>
  )
}
