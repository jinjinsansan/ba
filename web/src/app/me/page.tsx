// app/me/page.tsx — 会員ホーム(リデザイン 2026-08 / ダッシュボード案1a: 縦一列・数字主役)
//
// 並び(ハンドオフ説明書3.2 案1a):
//   オンボーディング → 今日の純損益 / サブスク残り(2列) → チャージ見込み → 突合ステータス → 詳細リンク
// 旧「チャージしないと使えない」系の文言・状態は廃止(新料金モデル)。
// データ取得は既存のまま。新ウィジェットのうち未配線のものはモックデータ + TODO。

import Link from 'next/link'
import { getTranslations } from 'next-intl/server'
import { createClient } from '@/lib/supabase-server'
import { createAdminClient } from '@/lib/supabase-admin'
import { type ReceiverStatus, receiverState, secondsSince, PRODUCT_LABEL, PRODUCT_CLASS } from '@/lib/receiver-status'
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
  const tBets = await getTranslations('betHistory')
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
  // ★2026-09-22: 今の受け子は session_state を送らないので、受け子 GUI の生存報告 (receiver_status) も見る。
  //   receiver_status はブラウザから直接読めない (RLS) ので、サーバーで本人の行だけを取る。
  // ★2026-09-23: 受け子の状態と今日の BET は同時に取る (順番に待つと往復が2回分かかる)
  const jstMidnightUtc = new Date(Math.floor((Date.now() + 9 * 3600_000) / 86_400_000) * 86_400_000 - 9 * 3600_000).toISOString()
  const adminDb = createAdminClient()
  const [{ data: rsData }, { data: todayBetRows }] = await Promise.all([
    adminDb.from('receiver_status').select('*').eq('user_id', user.id).order('last_seen_at', { ascending: false }),
    adminDb.from('receiver_bets').select('outcome, pnl').eq('user_id', user.id).gte('occurred_at', jstMidnightUtc).limit(5000),
  ])
  const myReceivers = (rsData || []) as ReceiverStatus[]
  const guiLive = (Number.isFinite(lastBalanceAt) && Date.now() - lastBalanceAt < 90_000)
    || myReceivers.some(r => receiverState(r) === 'running')
  const guiEverConnected = Number.isFinite(lastBalanceAt) || myReceivers.length > 0

  // ★2026-09-23: 「今日の成績」= 受け子アプリが送った今日 (日本時間) の BET。
  //   以前の「今日の純損益」は前日までに精算された1日分 (deductions) で、今日の数字ではなかった。
  const todayBets = (todayBetRows || []) as { outcome: string; pnl: number | null }[]
  const todayW = todayBets.filter(b => b.outcome === 'win').length
  const todayL = todayBets.filter(b => b.outcome === 'lose').length
  const todayP = todayBets.filter(b => b.outcome === 'push').length
  const todayPnl = todayBets.reduce((a, b) => a + Number(b.pnl || 0), 0)

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
    { href: '/me/bets', key: 'bets' },
    { href: '/me/download', key: 'download' },
    { href: '/me/referral', key: 'referral' },
    { href: '/me/support', key: 'support' },
  ] as const

  return (
    <div className="flex flex-col gap-5">
      {/* Header: greeting + GUI status */}
      <div className="flex justify-between items-end flex-wrap gap-3">
        <div>
          <div className="text-[13px] text-cyan font-semibold tracking-wide">{t('pageTitle')}</div>
          <div className="text-[24px] sm:text-[30px] font-bold tracking-tight mt-0.5">{t('greeting', { name })}</div>
          <div className="text-[15px] text-text-muted mt-1.5">{t('pageSub')}</div>
          <div className="text-[13px] text-text-dim mt-1">{today} · JST</div>
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

      {/* あなたの受け子 (受け子 GUI の生存報告・2026-09-22 / 2026-09-23 見やすく) */}
      <div className="bg-surface border border-white/[0.07] rounded-2xl p-5 sm:p-6">
        <div className="flex justify-between items-start mb-4 gap-3">
          <div>
            <div className="text-[17px] font-semibold">{t('receivers.title')}</div>
            <div className="text-[13px] text-text-dim mt-0.5">{t('receiversSub')}</div>
          </div>
          <Link href="/me/bets" className="text-[14px] text-cyan hover:underline whitespace-nowrap">{tBets('link')} →</Link>
        </div>
        {myReceivers.length === 0 ? (
          <div className="text-[15px] text-text-muted">{t('receivers.none')}</div>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            {myReceivers.map(r => {
              const st = receiverState(r)
              const ago = secondsSince(r.last_seen_at)
              const agoTxt = ago === null ? '-' : ago < 60 ? `${ago}s` : ago < 3600 ? `${Math.floor(ago / 60)}m` : ago < 86400 ? `${Math.floor(ago / 3600)}h` : `${Math.floor(ago / 86400)}d`
              const tone = st === 'running' ? 'border-win/40 bg-win/[0.07]' : st === 'idle' ? 'border-cyan/30 bg-cyan/[0.05]' : 'border-white/[0.1] bg-surface-2'
              return (
                <div key={`${r.product}-${r.executor_id}`} className={`rounded-xl border p-4 ${tone}`}>
                  <div className="flex items-center justify-between gap-2">
                    <div className="flex items-center gap-2">
                      <span className={`w-2.5 h-2.5 rounded-full ${st === 'running' ? 'bg-win animate-pulse' : st === 'idle' ? 'bg-cyan' : 'bg-text-dim'}`} />
                      <span className={`text-[16px] font-semibold ${st === 'running' ? 'text-win' : st === 'idle' ? 'text-cyan' : 'text-text-muted'}`}>
                        {st === 'running' ? t('receivers.running') : st === 'idle' ? t('receivers.idle') : t('receivers.offline')}
                      </span>
                    </div>
                    <span className={`px-2 py-0.5 rounded text-[11px] font-mono ${PRODUCT_CLASS[r.product] || ''}`}>{PRODUCT_LABEL[r.product] || r.product}</span>
                  </div>
                  <div className="mt-2 text-[14px] text-text-muted flex flex-col gap-0.5">
                    {r.table_name && <span>{t('receivers.table')}: <span className="text-text">{r.table_name}</span></span>}
                    {r.bets_today !== null && <span>{t('receivers.betsToday')}: <span className="text-text">{r.bets_today}</span> ({r.wins_today ?? 0}-{r.losses_today ?? 0}-{r.ties_today ?? 0})</span>}
                    <span className="text-[12px] text-text-dim">{t('receivers.lastSeen')}: {agoTxt}</span>
                  </div>
                </div>
              )
            })}
          </div>
        )}
      </div>

      {/* 今日の成績 (受け子アプリの BET・日本時間) */}
      <div className="bg-surface border border-white/[0.07] rounded-2xl p-5 sm:p-6">
        <div className="text-[17px] font-semibold mb-4">{t('todayResultTitle')}</div>
        {todayBets.length === 0 ? (
          <div className="text-[15px] text-text-muted">{t('todayNoBets')}</div>
        ) : (
          <div className="grid grid-cols-3 gap-4">
            <div>
              <div className="text-[13px] text-text-muted">{t('todayPnl')}</div>
              <div className="mt-1"><Money value={todayPnl} sign size="2xl" weight="bold" tone={todayPnl >= 0 ? 'win' : 'lose'} /></div>
            </div>
            <div>
              <div className="text-[13px] text-text-muted">{t('todayBets')}</div>
              <div className="text-[28px] font-bold font-mono mt-1">{todayBets.length}</div>
            </div>
            <div>
              <div className="text-[13px] text-text-muted">{t('todayRecord')}</div>
              <div className="text-[28px] font-bold font-mono mt-1">{todayW}-{todayL}-{todayP}</div>
            </div>
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
