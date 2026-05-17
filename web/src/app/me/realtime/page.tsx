import { createClient } from '@/lib/supabase-server'
import { Card, CardHead } from '@/components/ui/Card'
import { PageHeader } from '@/components/ui/PageHeader'
import RealtimePnlCard from '../../dashboard/RealtimePnlCard'

export default async function RealtimePage() {
  const supabase = await createClient()
  const { data: { user } } = await supabase.auth.getUser()
  if (!user) return null

  const { data: billing } = await supabase
    .from('billing')
    .select('session_state')
    .eq('user_id', user.id)
    .single()

  const initial = (billing as { session_state?: Record<string, unknown> } | null)?.session_state ?? null

  return (
    <div>
      <PageHeader
        kicker="Member · Live"
        title="ライブ運用状況"
        sub="受け子から 60 秒間隔で送信される運用データを 30 秒間隔でこのページに反映します"
      />

      <div className="mb-4">
        <RealtimePnlCard initial={initial} />
      </div>

      <Card>
        <div className="font-mono text-[11px] text-text-muted tracking-[0.2em] uppercase mb-3">表示の見方</div>
        <ul className="space-y-1.5 text-xs text-text-muted list-disc list-inside leading-relaxed">
          <li><strong className="text-text">当日損益</strong>: 受け子の BET 結果累計 (出金の影響を受けないクリーンな PnL)</li>
          <li><strong className="text-text">Stake 残高</strong>: 受け子 PC 上の Stake.com 表示残高 (60 秒間隔で更新)</li>
          <li><strong className="text-text">稼働中 🟢 / 停止中 🟡</strong>: 90 秒以内に POST が来ていれば稼働中</li>
          <li>受け子 GUI を停止すると数分後に「停止中」になり、最終 PnL がそのまま表示されます</li>
        </ul>
      </Card>
    </div>
  )
}
