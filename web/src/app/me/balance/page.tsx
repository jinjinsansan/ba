import { createClient } from '@/lib/supabase-server'
import { Card, CardHead } from '@/components/ui/Card'
import { PageHeader, Label } from '@/components/ui/PageHeader'
import { Pill } from '@/components/ui/Pill'
import { Money } from '@/components/ui/Money'
import { Button } from '@/components/ui/Button'
import AutoCryptoCharge from './AutoCryptoCharge'

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

  return (
    <div>
      <PageHeader
        kicker="Member · Balance"
        title="残高・チャージ"
        right={
          billing?.is_free
            ? <Button tone="ghost" size="sm" disabled>資金追加 (免除済)</Button>
            : undefined
        }
      />

      {billing?.is_free && (
        <Card className="mb-4 border-cyan/30 bg-cyan/[0.03]">
          <div className="flex items-start gap-3">
            <Pill tone="free">FREE</Pill>
            <div>
              <div className="text-sm font-semibold text-cyan mb-1">課金免除プラン適用中</div>
              <div className="text-xs text-text-muted leading-relaxed">
                管理者から課金免除を受けているため、ライセンス料・日次手数料・チャージはすべて不要です。残高数値は内部表示で、実際の課金には使用されません。
              </div>
            </div>
          </div>
        </Card>
      )}

      <Card padded={false} className="mb-4">
        <CardHead>Current Balances</CardHead>
        <div className="grid grid-cols-1 sm:grid-cols-3 px-5 py-5">
          <div>
            <Label>Current Balance</Label>
            <div className="mt-1.5">
              {billing?.is_free
                ? <span className="text-xl font-semibold text-cyan">課金免除</span>
                : <Money value={Number(billing?.balance ?? 0)} size="2xl" weight="bold" />}
            </div>
          </div>
          <div className="sm:pl-4 sm:border-l border-white/[0.07]">
            <Label>Total Charged</Label>
            <div className="mt-1.5"><Money value={Number(billing?.total_charged ?? 0)} size="2xl" weight="semibold" /></div>
          </div>
          <div className="sm:pl-4 sm:border-l border-white/[0.07]">
            <Label>Carry Loss</Label>
            <div className="mt-1.5"><Money value={Number(billing?.carry_loss ?? 0)} size="2xl" weight="semibold" tone={Number(billing?.carry_loss ?? 0) > 0 ? 'lose' : 'muted'} /></div>
          </div>
        </div>
      </Card>

      {!billing?.is_free && (
        <div className="mb-4">
          <AutoCryptoCharge mode="charge" />
        </div>
      )}

      <Card padded={false} className="mb-4">
        <CardHead>課金ステータス</CardHead>
        <div className="px-5 py-5">
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 text-xs">
            <div className="p-3 rounded border border-white/[0.07] bg-white/[0.02]">
              <Label>未確認チャージ</Label>
              <div className={`text-base font-semibold mt-1 ${pendingCount > 0 ? 'text-warn' : 'text-win'}`}>{pendingCount} 件</div>
            </div>
            <div className="p-3 rounded border border-white/[0.07] bg-white/[0.02]">
              <Label>最終反映</Label>
              <div className="text-base font-semibold text-text mt-1">{lastConfirmed ? new Date(lastConfirmed.created_at).toLocaleDateString('ja-JP') : '未反映'}</div>
            </div>
            <div className="p-3 rounded border border-white/[0.07] bg-white/[0.02]">
              <Label>プラン</Label>
              <div className="text-base font-semibold text-text mt-1">
                {billing?.is_free ? 'FREE' : `${billing ? (Number(billing.profit_share_rate) * 100).toFixed(0) : '?'}% Share`}
              </div>
            </div>
          </div>
          {!billing?.is_free && (
            <div className="mt-3 text-[11px] text-text-muted leading-relaxed">
              チャージは上の「暗号資産で自動チャージ」から行えます。表示された<strong>正確な金額</strong>を USDT(TRC-20)で送金すると、約1〜2分で<strong>自動反映</strong>されます(手動承認は不要)。
            </div>
          )}
        </div>
      </Card>

      <Card padded={false}>
        <CardHead>チャージ履歴 ({(charges || []).length})</CardHead>
        {charges?.length ? (
          <div className="overflow-x-auto">
            <table className="min-w-[520px] w-full text-sm">
              <thead>
                <tr className="border-b border-white/[0.07]">
                  <th className="px-5 py-3 font-mono text-[10px] text-text-dim tracking-[0.15em] uppercase font-normal text-left">日付</th>
                  <th className="px-5 py-3 font-mono text-[10px] text-text-dim tracking-[0.15em] uppercase font-normal text-right">金額</th>
                  <th className="px-5 py-3 font-mono text-[10px] text-text-dim tracking-[0.15em] uppercase font-normal text-left">ステータス</th>
                </tr>
              </thead>
              <tbody>
                {charges.map((c, i) => (
                  <tr key={c.id} className={i ? 'border-t border-white/[0.07]' : ''}>
                    <td className="px-5 py-3 text-text-muted font-mono text-xs">{new Date(c.created_at).toLocaleDateString('ja-JP')}</td>
                    <td className="px-5 py-3 text-right"><Money value={Number(c.amount)} size="md" weight="semibold" /></td>
                    <td className="px-5 py-3">
                      <Pill tone={c.status === 'confirmed' ? 'live' : c.status === 'rejected' ? 'danger' : 'warn'}>{c.status}</Pill>
                    </td>
                  </tr>
                ))}
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
