import { createClient } from '@/lib/supabase-server'
import { Card, CardHead } from '@/components/ui/Card'
import { PageHeader } from '@/components/ui/PageHeader'
import { Pill } from '@/components/ui/Pill'
import { Money } from '@/components/ui/Money'
import AutoCryptoCharge from './AutoCryptoCharge'

export default async function BalancePage() {
  const supabase = await createClient()
  const { data: { user } } = await supabase.auth.getUser()
  if (!user) return null

  const [{ data: billing }, { data: payments }] = await Promise.all([
    supabase.from('billing').select('*').eq('user_id', user.id).single(),
    supabase.from('crypto_payments').select('*').eq('user_id', user.id).order('created_at', { ascending: false }),
  ])

  const pays = payments || []
  const nowMs = Date.now()
  // 期限切れの pending は実質「失効」(statusはpendingのまま残るため expires_at で判定)
  const isLivePending = (c: { status?: string; expires_at?: string }) =>
    String(c.status) === 'pending' && new Date(String(c.expires_at)).getTime() > nowMs
  const pendingCount = pays.filter(isLivePending).length
  const lastConfirmed = pays.find(c => String(c.status) === 'credited')

  return (
    <div>
      <PageHeader
        kicker="Member · Balance"
        title="残高・チャージ"
        sub="bafather.uk に預けている残高と、USDT でのチャージ (入金) の手続き・履歴です。"
      />

      {billing?.is_free && (
        <Card className="mb-4 border-cyan/30 bg-cyan/[0.03]">
          <div className="flex items-start gap-3">
            <Pill tone="free">FREE</Pill>
            <div>
              <div className="text-base font-semibold text-cyan mb-1">課金免除プラン適用中</div>
              <div className="text-sm text-text-muted leading-relaxed">
                管理者から課金免除を受けているため、ライセンス料・日次手数料は不要です。チャージ(資金追加)は任意で行えます。
              </div>
            </div>
          </div>
        </Card>
      )}

      <Card padded={false} className="mb-4">
        <CardHead>残高</CardHead>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-5 sm:gap-0 px-5 py-6">
          <div>
            <div className="text-[15px] font-semibold">今の残高</div>
            <div className="text-[13px] text-text-dim">手数料の支払いに使われます</div>
            <div className="mt-1.5">
              {billing?.is_free
                ? <span className="text-xl font-semibold text-cyan">課金免除</span>
                : <Money value={Number(billing?.balance ?? 0)} size="2xl" weight="bold" />}
            </div>
          </div>
          <div className="sm:pl-4 sm:border-l border-white/[0.07]">
            <div className="text-[15px] font-semibold">これまでのチャージ合計</div>
            <div className="text-[13px] text-text-dim">入金した金額の累計</div>
            <div className="mt-1.5"><Money value={Number(billing?.total_charged ?? 0)} size="2xl" weight="semibold" /></div>
          </div>
          <div className="sm:pl-4 sm:border-l border-white/[0.07]">
            <div className="text-[15px] font-semibold">繰越損失</div>
            <div className="text-[13px] text-text-dim">負けた週の損失。次の利益から先に差し引かれます</div>
            <div className="mt-1.5"><Money value={Number(billing?.carry_loss ?? 0)} size="2xl" weight="semibold" tone={Number(billing?.carry_loss ?? 0) > 0 ? 'lose' : 'muted'} /></div>
          </div>
        </div>
      </Card>

      <div className="mb-4">
        <AutoCryptoCharge mode="charge" />
      </div>

      <Card padded={false} className="mb-4">
        <CardHead>チャージの状況</CardHead>
        <div className="px-5 py-5">
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 text-sm">
            <div className="p-4 rounded-xl border border-white/[0.07] bg-white/[0.02]">
              <div className="text-[14px] text-text-muted">確認待ちのチャージ</div>
              <div className={`text-xl font-semibold mt-1 ${pendingCount > 0 ? 'text-warn' : 'text-win'}`}>{pendingCount} 件</div>
            </div>
            <div className="p-4 rounded-xl border border-white/[0.07] bg-white/[0.02]">
              <div className="text-[14px] text-text-muted">最後に反映された日</div>
              <div className="text-xl font-semibold text-text mt-1">{lastConfirmed ? new Date(lastConfirmed.created_at).toLocaleDateString('ja-JP') : '未反映'}</div>
            </div>
            <div className="p-4 rounded-xl border border-white/[0.07] bg-white/[0.02]">
              <div className="text-[14px] text-text-muted">プラン</div>
              <div className="text-xl font-semibold text-text mt-1">
                {billing?.is_free ? 'FREE' : `${billing ? (Number(billing.profit_share_rate) * 100).toFixed(0) : '?'}% Share`}
              </div>
            </div>
          </div>
          <div className="mt-4 text-[14px] text-text-muted leading-relaxed">
            チャージは上の「暗号資産で自動チャージ」から行えます。表示された<strong>正確な金額</strong>を USDT(TRC-20)で送金すると、約1〜2分で<strong>自動反映</strong>されます(手動承認は不要)。
          </div>
        </div>
      </Card>

      <Card padded={false}>
        <CardHead>チャージ履歴 ({pays.length})</CardHead>
        {pays.length ? (
          <div className="overflow-x-auto">
            <table className="min-w-[560px] w-full text-sm">
              <thead>
                <tr className="border-b border-white/[0.07]">
                  <th className="px-5 py-3 text-[13px] text-text-muted font-normal text-left">日時</th>
                  <th className="px-5 py-3 text-[13px] text-text-muted font-normal text-left">種別</th>
                  <th className="px-5 py-3 text-[13px] text-text-muted font-normal text-right">金額</th>
                  <th className="px-5 py-3 text-[13px] text-text-muted font-normal text-left">ステータス</th>
                </tr>
              </thead>
              <tbody>
                {pays.map((c, i) => {
                  let st = String(c.status)
                  if (st === 'pending' && new Date(String(c.expires_at)).getTime() <= nowMs) st = 'expired'
                  const tone = st === 'credited' ? 'live' : st === 'expired' ? 'danger' : 'warn'
                  const label = st === 'credited' ? '反映済' : st === 'expired' ? '失効' : '保留'
                  const amt = Number(c.paid_amount ?? c.expected_amount ?? 0)
                  return (
                    <tr key={c.id} className={i ? 'border-t border-white/[0.07]' : ''}>
                      <td className="px-5 py-3 text-text-muted font-mono text-sm">{new Date(c.created_at).toLocaleString('ja-JP')}</td>
                      <td className="px-5 py-3 text-sm text-text">{c.kind === 'license' ? 'ライセンス' : 'チャージ'}</td>
                      <td className="px-5 py-3 text-right"><Money value={amt} size="md" weight="semibold" /></td>
                      <td className="px-5 py-3"><Pill tone={tone}>{label}</Pill></td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="px-5 py-6 text-text-muted text-sm">まだチャージ履歴がありません。</div>
        )}
      </Card>
    </div>
  )
}
