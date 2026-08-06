// app/me/page.tsx — 会員ホーム(リデザイン 2026-08 / ダッシュボード案1a: 縦一列・数字主役)
//
// 並び(ハンドオフ説明書3.2 案1a):
//   オンボーディング → 今日の純損益 / サブスク残り(2列) → チャージ見込み → 突合ステータス → 詳細リンク
// 旧「チャージしないと使えない」系の文言・状態は廃止(新料金モデル)。
// データ取得は既存のまま。新ウィジェットのうち未配線のものはモックデータ + TODO。

import Link from 'next/link'
import { getTranslations } from 'next-intl/server'
import { createClient } from '@/lib/supabase-server'
import { Money } from '@/components/ui/Money'
import InvoicesCard from './InvoicesCard'
import OnboardingChecklist from '@/components/dashboard/OnboardingChecklist'
import SubscriptionCard from '@/components/dashboard/SubscriptionCard'
import ChargeMeter from '@/components/dashboard/ChargeMeter'
import WalletStatus from '@/components/dashboard/WalletStatus'

export default async function MePage() {
  const supabase = await createClient()
  const { data: { user } } = await supabase.auth.getUser()
  if (!user) return null

  const t = await getTranslations('dashboardV2')

  const [
    { data: profile },
    { data: billing },
    { data: lastDeduction },
    { data: unpaidInvoices },
  ] = await Promise.all([
    supabase.from('profiles').select('*').eq('id', user.id).single(),
    supabase.from('billing').select('*').eq('user_id', user.id).single(),
    supabase.from('deductions').select('*').eq('user_id', user.id).order('date', { ascending: false }).limit(1).maybeSingle(),
    supabase.from('invoices').select('id, amount, memo, created_at').eq('user_id', user.id).eq('status', 'unpaid').order('created_at', { ascending: true }).then(r => r, () => ({ data: [] })),
  ])

  const email = profile?.email || user.email || ''
  const name = email.split('@')[0] || 'member'
  const suspended = !!billing?.suspended

  // GUI 稼働判定(実データ): session_state.last_balance_at が 90 秒以内なら稼働中
  const ss = (billing?.session_state || {}) as Record<string, unknown>
  const lastBalanceAt = typeof ss.last_balance_at === 'string' ? new Date(ss.last_balance_at).getTime() : NaN
  const guiLive = Number.isFinite(lastBalanceAt) && Date.now() - lastBalanceAt < 90_000

  const lastPnl = lastDeduction?.daily_profit != null ? Number(lastDeduction.daily_profit) : null
  const carryLoss = Math.max(0, Number(billing?.carry_loss ?? 0))

  // TODO: wire real data — サブスク期限(subscriptions テーブル未実装)。
  // 現状はモック値。バックエンド実装後に expiresAt / daysLeft を実値へ差し替える。
  const mockSubscription = { expiresAt: '2026-08-28T14:59:00Z', daysLeft: 22, totalDays: 30 }

  // TODO: wire real data — 今週の純利益と日別バー(weekly_pnl の当該週 + daily_pnl_log)。
  const mockWeek = {
    weeklyNetProfit: 1240,
    daily: [
      { day: 'mon' as const, pnl: 420 },
      { day: 'tue' as const, pnl: -180 },
      { day: 'wed' as const, pnl: 640 },
      { day: 'thu' as const, pnl: 360 },
    ],
  }

  // TODO: wire real data — ウォレット登録・オンチェーン突合(wallets / chain_transfers 未実装)。
  const mockWallet = { status: 'unregistered' as const }

  // TODO: wire real data — オンボーディング実状態(サブスク支払い / ウォレット登録)。
  // GUI 接続のみ実データ(guiLive)を使用。
  const onboardingSteps = [
    { id: 'subscription' as const, done: true, href: '/purchase' },
    { id: 'wallet' as const, done: false, href: '/me/wallet' },
    { id: 'gui' as const, done: guiLive, href: '/me/download' },
  ]

  const today = new Date().toLocaleDateString('ja-JP', {
    timeZone: 'Asia/Tokyo', year: 'numeric', month: 'long', day: 'numeric', weekday: 'short',
  })

  const detailLinks = [
    { href: '/me/settlements', key: 'weekly' },
    { href: '/me/realtime', key: 'realtime' },
    { href: '/me/download', key: 'download' },
    { href: '/me/referral', key: 'referral' },
    { href: '/me/support', key: 'support' },
  ] as const

  return (
    <div className="flex flex-col gap-5">
      {/* Header: greeting + GUI status */}
      <div className="flex justify-between items-end flex-wrap gap-3">
        <div>
          <div className="text-[22px] sm:text-[28px] font-bold tracking-tight">{t('greeting', { name })}</div>
          <div className="text-[15px] text-text-muted mt-1.5">{today} · JST</div>
        </div>
        {suspended ? (
          <div className="flex items-center gap-2 bg-lose/[0.08] border border-lose/[0.22] text-lose rounded-full px-4 py-2 text-sm font-semibold">
            <span className="w-2 h-2 rounded-full bg-lose" />
            {t('statusSuspended')}
          </div>
        ) : guiLive ? (
          <div className="flex items-center gap-2 bg-win/[0.08] border border-win/[0.22] text-win rounded-full px-4 py-2 text-sm font-semibold">
            <span className="w-2 h-2 rounded-full bg-win animate-pulse" />
            {t('statusRunning')}
          </div>
        ) : (
          <div className="flex items-center gap-2 bg-white/[0.03] border border-white/[0.1] text-text-muted rounded-full px-4 py-2 text-sm font-semibold">
            <span className="w-2 h-2 rounded-full bg-text-dim" />
            {t('statusIdle')}
          </div>
        )}
      </div>

      {/* 未払い請求書(管理者発行) — 実データ */}
      <InvoicesCard invoices={(unpaidInvoices as { id: string; amount: number; memo?: string | null; created_at?: string }[]) || []} />

      {/* オンボーディング(全完了なら自動非表示) */}
      <OnboardingChecklist steps={onboardingSteps} />

      {/* 今日の純損益 / サブスク残り */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
        <div className="bg-surface border border-white/[0.07] rounded-2xl p-6 flex flex-col gap-3">
          <div className="text-[15px] text-text-muted">{t('todayTitle')}</div>
          {lastPnl != null ? (
            <>
              <div className="leading-none">
                <Money value={lastPnl} sign size="3xl" weight="bold" tone={lastPnl >= 0 ? 'win' : 'lose'} />
              </div>
              <div className="text-sm text-text-dim">{t('todayMeta', { date: String(lastDeduction?.date || '') })}</div>
            </>
          ) : (
            <div className="text-lg text-text-dim py-4">{t('todayEmpty')}</div>
          )}
        </div>
        <SubscriptionCard {...mockSubscription} />
      </div>

      {/* 今週のチャージ見込み(carryLoss のみ実データ) */}
      <ChargeMeter
        weeklyNetProfit={mockWeek.weeklyNetProfit}
        shareRate={0.30}
        carryLoss={carryLoss}
        weekEndsAt="2026-08-08T14:59:00Z"
        daily={mockWeek.daily}
      />

      {/* ウォレット突合 */}
      <WalletStatus {...mockWallet} />

      {/* 詳細への折りたたみリンク */}
      <div className="flex flex-col gap-0.5 bg-white/[0.06] rounded-[14px] overflow-hidden">
        {detailLinks.map(l => (
          <Link
            key={l.href}
            href={l.href}
            className="bg-surface hover:bg-white/[0.03] px-6 py-5 flex justify-between items-center transition group"
          >
            <span className="text-base text-text-muted group-hover:text-text transition">{t(`details.${l.key}`)}</span>
            <span className="text-text-dim group-hover:text-cyan transition">→</span>
          </Link>
        ))}
      </div>
    </div>
  )
}
