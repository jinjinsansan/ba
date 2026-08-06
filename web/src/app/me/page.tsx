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
  const tSub = await getTranslations('widgets.subscription')

  // 今週(JST・月〜土)の日付レンジ
  const jstNow = new Date(Date.now() + 9 * 3600_000)
  const dow = jstNow.getUTCDay() // JST の曜日 (0=日)
  const monday = new Date(jstNow)
  monday.setUTCDate(jstNow.getUTCDate() + (dow === 0 ? -6 : 1 - dow))
  const saturday = new Date(monday)
  saturday.setUTCDate(monday.getUTCDate() + 5)
  const isoDate = (d: Date) => d.toISOString().slice(0, 10)

  const [
    { data: profile },
    { data: billing },
    { data: lastDeduction },
    { data: unpaidInvoices },
    { data: wallet },
    { data: weekRows },
  ] = await Promise.all([
    supabase.from('profiles').select('*').eq('id', user.id).single(),
    supabase.from('billing').select('*').eq('user_id', user.id).single(),
    supabase.from('deductions').select('*').eq('user_id', user.id).order('date', { ascending: false }).limit(1).maybeSingle(),
    supabase.from('invoices').select('id, amount, memo, created_at').eq('user_id', user.id).eq('status', 'unpaid').order('created_at', { ascending: true }).then(r => r, () => ({ data: [] })),
    supabase.from('wallets').select('network, address, status, recon_status, last_checked_at').eq('user_id', user.id).maybeSingle().then(r => r, () => ({ data: null })),
    supabase.from('daily_pnl_log').select('date, bet_pnl').eq('user_id', user.id).gte('date', isoDate(monday)).lte('date', isoDate(saturday)).then(r => r, () => ({ data: [] as { date: string; bet_pnl: number }[] })),
  ])

  const email = profile?.email || user.email || ''
  const name = email.split('@')[0] || 'member'
  const suspended = !!billing?.suspended

  // GUI 稼働判定(実データ): session_state.last_balance_at が 90 秒以内なら稼働中
  const ss = (billing?.session_state || {}) as Record<string, unknown>
  const lastBalanceAt = typeof ss.last_balance_at === 'string' ? new Date(ss.last_balance_at).getTime() : NaN
  const guiLive = Number.isFinite(lastBalanceAt) && Date.now() - lastBalanceAt < 90_000
  const guiEverConnected = Number.isFinite(lastBalanceAt)

  const lastPnl = lastDeduction?.daily_profit != null ? Number(lastDeduction.daily_profit) : null
  const carryLoss = Math.max(0, Number(billing?.carry_loss ?? 0))

  // サブスク(実データ): billing.expires_at。null = 課金免除 or 経過措置 or 未加入
  const expiresAt = billing?.expires_at ? String(billing.expires_at) : null
  const daysLeft = expiresAt ? Math.ceil((new Date(expiresAt).getTime() - Date.now()) / 86_400_000) : null
  const subActive = !!billing?.is_free || !!billing?.bot_paid

  // 今週の純利益と日別バー(実データ: daily_pnl_log)
  const DAY_KEYS = ['sun', 'mon', 'tue', 'wed', 'thu', 'fri', 'sat'] as const
  const daily = ((weekRows as { date: string; bet_pnl: number }[]) || [])
    .map(r => {
      const d = new Date(`${r.date}T00:00:00Z`).getUTCDay()
      return { day: DAY_KEYS[d], pnl: Number(r.bet_pnl) || 0 }
    })
    .filter((r): r is { day: 'mon' | 'tue' | 'wed' | 'thu' | 'fri' | 'sat'; pnl: number } => r.day !== 'sun')
  const weeklyNetProfit = daily.reduce((s, r) => s + r.pnl, 0)
  const weekEndsAt = `${isoDate(saturday)}T14:59:00Z` // 土曜 23:59 JST

  // ウォレット突合(実データ)
  const walletRow = wallet as { network: 'tron' | 'bsc'; address: string; status: string; recon_status: 'checking' | 'matched' | 'mismatched'; last_checked_at?: string | null } | null

  // オンボーディング(実データ)
  const onboardingSteps = [
    { id: 'subscription' as const, done: subActive, href: '/purchase' },
    { id: 'wallet' as const, done: !!walletRow, href: '/me/wallet' },
    { id: 'gui' as const, done: guiEverConnected, href: '/me/download' },
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
        {expiresAt && daysLeft != null ? (
          <SubscriptionCard expiresAt={expiresAt} daysLeft={daysLeft} totalDays={30} />
        ) : (
          <div className="bg-surface border border-white/[0.07] rounded-2xl p-6 flex flex-col gap-3.5">
            <span className="text-[15px] text-text-muted">{tSub('title')}</span>
            <div className="text-[24px] font-bold leading-tight">
              {billing?.is_free ? tSub('freePlan') : subActive ? tSub('legacy') : tSub('none')}
            </div>
            <p className="text-sm text-text-muted leading-relaxed m-0">
              {billing?.is_free ? tSub('freePlanBody') : subActive ? tSub('legacyBody') : tSub('noneBody')}
            </p>
            {!subActive && (
              <Link
                href="/purchase"
                className="self-start bg-cyan text-[#001721] font-bold text-[15px] rounded-xl px-6 py-3.5 hover:brightness-110 transition"
              >
                {tSub('subscribeCta')}
              </Link>
            )}
          </div>
        )}
      </div>

      {/* 今週のチャージ見込み(実データ: daily_pnl_log + billing.carry_loss) */}
      <ChargeMeter
        weeklyNetProfit={weeklyNetProfit}
        shareRate={Number(billing?.profit_share_rate ?? 0.30) || 0.30}
        carryLoss={carryLoss}
        weekEndsAt={weekEndsAt}
        daily={daily}
      />

      {/* ウォレット突合(実データ) */}
      {walletRow ? (
        <WalletStatus
          status={walletRow.recon_status}
          address={walletRow.address}
          network={walletRow.network}
          lastCheckedAt={walletRow.last_checked_at || undefined}
        />
      ) : (
        <WalletStatus status="unregistered" />
      )}

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
