// app/me/bets/page.tsx — BET 履歴 (2026-09-22・ダッシュボード段階2)
// 受け子アプリが送った「Stake が受理して決済された BET」(receiver_bets) を、本人の分だけ出す。

import { getTranslations } from 'next-intl/server'
import { redirect } from 'next/navigation'
import { createClient } from '@/lib/supabase-server'
import BetHistory, { type BetHistoryLabels } from '@/components/receivers/BetHistory'

export const dynamic = 'force-dynamic'

export default async function MyBetsPage() {
  const supabase = await createClient()
  const { data: { user } } = await supabase.auth.getUser()
  if (!user) redirect('/login')
  const t = await getTranslations('betHistory')
  const labels: BetHistoryLabels = {
    monthly: t('monthly'), daily: t('daily'), recent: t('recent'), month: t('month'), date: t('date'),
    time: t('time'), bets: t('bets'), record: t('record'), pnl: t('pnl'), table: t('table'),
    side: t('side'), amount: t('amount'), result: t('result'), none: t('none'),
    sides: { player: t('sides.player'), banker: t('sides.banker'), tie: t('sides.tie') },
    outcomes: { win: t('outcomes.win'), lose: t('outcomes.lose'), push: t('outcomes.push') },
  }
  return (
    <div className="flex flex-col gap-4">
      <div>
        <div className="text-[22px] sm:text-[28px] font-bold tracking-tight">{t('title')}</div>
        <div className="text-[14px] text-text-muted mt-1.5">{t('sub')}</div>
      </div>
      <BetHistory userId={user.id} labels={labels} />
    </div>
  )
}
