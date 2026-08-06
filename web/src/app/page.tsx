// app/page.tsx — マーケティングランディング(リデザイン 2026-08)
//
// 旧: OperatorWall + LoginForm の「ログインの壁」 → 新: 初心者向けLP。
// ログイン導線は既存 /login へ(認証フローは不変)。ログイン済みは従来どおり /me へ。
// 構成順はハンドオフ説明書3.1: ヒーロー → 3ステップ → 料金 → 仕組み → FAQ → リスク開示。

import Link from 'next/link'
import { redirect } from 'next/navigation'
import { getTranslations } from 'next-intl/server'
import { createClient } from '@/lib/supabase-server'

export const dynamic = 'force-dynamic'

export default async function HomePage() {
  const supabase = await createClient()
  const { data: { user } } = await supabase.auth.getUser()
  if (user) redirect('/me')

  const t = await getTranslations('landingV2')

  const steps = ['s1', 's2', 's3'] as const
  const faqs = [1, 2, 3, 4, 5] as const

  return (
    <div className="min-h-screen bg-bg text-text">
      {/* ── Header ─────────────────────────────────────────────── */}
      <header className="px-5 sm:px-12 py-5 flex items-center justify-between border-b border-white/[0.05]">
        <div className="text-[19px] font-bold tracking-tight">bafather</div>
        <nav className="flex items-center gap-4 sm:gap-7 text-[15px] text-text-muted">
          <a href="#how" className="hidden sm:inline hover:text-text transition">{t('nav.how')}</a>
          <a href="#pricing" className="hidden sm:inline hover:text-text transition">{t('nav.pricing')}</a>
          <a href="#faq" className="hidden md:inline hover:text-text transition">{t('nav.faq')}</a>
          <Link href="/login" className="text-text hover:text-cyan transition">{t('nav.login')}</Link>
          <Link
            href="/signup"
            className="bg-cyan text-[#001721] font-bold rounded-[10px] px-4 sm:px-5 py-2.5 hover:brightness-110 transition"
          >
            {t('nav.signup')}
          </Link>
        </nav>
      </header>

      {/* ── Hero ───────────────────────────────────────────────── */}
      <section className="px-5 sm:px-12 pt-14 sm:pt-[88px] pb-14 sm:pb-[72px] grid grid-cols-1 lg:grid-cols-[1.15fr_.85fr] gap-10 lg:gap-14 items-center max-w-[1240px] mx-auto">
        <div className="flex flex-col gap-6">
          <div className="inline-flex self-start items-center gap-2 bg-cyan/[0.07] border border-cyan/[0.22] text-cyan rounded-full px-4 py-2 text-sm font-semibold">
            {t('hero.badge')}
          </div>
          <h1 className="m-0 text-[33px] sm:text-[48px] lg:text-[56px] leading-[1.3] font-bold tracking-tight">
            {t('hero.title')}
          </h1>
          <p className="m-0 text-base sm:text-[19px] leading-[1.85] text-text-muted max-w-[560px]">
            {t('hero.body')}
          </p>
          <div className="flex gap-3.5 items-center flex-wrap">
            <Link
              href="/signup"
              className="bg-cyan text-[#001721] font-bold text-[17px] rounded-xl px-8 py-4 hover:brightness-110 transition"
            >
              {t('hero.ctaPrimary')}
            </Link>
            <a
              href="#how"
              className="border border-white/[0.14] text-text text-[17px] rounded-xl px-7 py-4 hover:border-white/30 transition"
            >
              {t('hero.ctaSecondary')}
            </a>
          </div>
          <div className="text-sm text-text-dim">{t('hero.paymentNote')}</div>
        </div>

        {/* Example card — 必ず「表示例」ラベルを付ける(煽り防止) */}
        <div className="bg-surface border border-white/[0.07] rounded-[18px] p-7 flex flex-col gap-5">
          <div className="flex justify-between items-center">
            <span className="font-mono text-[11px] tracking-[0.18em] uppercase text-text-dim">{t('example.kicker')}</span>
            <span className="text-xs text-text-dim border border-white/10 rounded-md px-2 py-1">{t('example.label')}</span>
          </div>
          <div>
            <div className="text-[15px] text-text-muted mb-2">{t('example.weeklyProfit')}</div>
            <div className="font-mono tabular-nums text-[42px] sm:text-[52px] font-bold text-win tracking-tight">+$1,240</div>
          </div>
          <div className="h-px bg-white/[0.07]" />
          <div className="flex justify-between items-baseline">
            <span className="text-[15px] text-text-muted">{t('example.sundayBill')}</span>
            <span className="font-mono tabular-nums text-[26px] font-bold">$372</span>
          </div>
          <div className="bg-white/[0.03] rounded-xl p-4 text-sm leading-[1.8] text-text-muted">
            {t('example.zeroNote')}
          </div>
        </div>
      </section>

      {/* ── 3 Steps ────────────────────────────────────────────── */}
      <section className="px-5 sm:px-12 py-14 sm:py-[72px] border-t border-white/[0.05]">
        <div className="max-w-[1240px] mx-auto">
          <h2 className="m-0 mb-2 text-[26px] sm:text-[34px] font-bold tracking-tight">{t('steps.title')}</h2>
          <p className="m-0 mb-10 text-base text-text-muted">{t('steps.sub')}</p>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
            {steps.map((s, i) => (
              <div key={s} className="bg-surface border border-white/[0.07] rounded-2xl p-7 flex flex-col gap-3.5">
                <div className="font-mono tabular-nums w-11 h-11 rounded-xl bg-cyan/10 text-cyan flex items-center justify-center text-[19px] font-bold">
                  {i + 1}
                </div>
                <div className="text-xl font-bold">{t(`steps.${s}.title`)}</div>
                <div className="text-[15px] leading-[1.85] text-text-muted">{t(`steps.${s}.body`)}</div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── Pricing ────────────────────────────────────────────── */}
      <section id="pricing" className="px-5 sm:px-12 py-14 sm:py-[72px] border-t border-white/[0.05] bg-bg-rail">
        <div className="max-w-[1240px] mx-auto">
          <h2 className="m-0 mb-10 text-[26px] sm:text-[34px] font-bold tracking-tight">{t('pricing.title')}</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
            <div className="bg-surface border border-white/[0.07] rounded-[18px] p-8 flex flex-col gap-4">
              <div className="font-mono text-[11px] tracking-[0.18em] uppercase text-text-dim">{t('pricing.subscription.kicker')}</div>
              <div className="flex items-baseline gap-2.5">
                <span className="font-mono tabular-nums text-[40px] sm:text-[52px] font-bold tracking-tight">{t('pricing.subscription.price')}</span>
                <span className="text-base sm:text-[19px] text-text-muted">{t('pricing.subscription.unit')}</span>
              </div>
              <div className="text-base leading-[1.85] text-text-muted">{t('pricing.subscription.body')}</div>
            </div>
            <div className="bg-surface border border-win/[0.28] rounded-[18px] p-8 flex flex-col gap-4">
              <div className="font-mono text-[11px] tracking-[0.18em] uppercase text-win">{t('pricing.profitShare.kicker')}</div>
              <div className="flex items-baseline gap-2.5">
                <span className="font-mono tabular-nums text-[40px] sm:text-[52px] font-bold tracking-tight">{t('pricing.profitShare.price')}</span>
                <span className="text-base sm:text-[19px] text-text-muted">{t('pricing.profitShare.unit')}</span>
              </div>
              <div className="text-base leading-[1.85] text-text-muted">{t('pricing.profitShare.body')}</div>
              <div className="bg-win/[0.07] rounded-xl p-4 text-[15px] leading-[1.8]">
                <strong className="text-win">{t('pricing.profitShare.highlightStrong')}</strong>
                {t('pricing.profitShare.highlightBody')}
              </div>
            </div>
          </div>
          <div className="mt-5 text-[15px] text-text-dim leading-[1.8]">{t('pricing.note')}</div>
        </div>
      </section>

      {/* ── How it works ───────────────────────────────────────── */}
      <section id="how" className="px-5 sm:px-12 py-14 sm:py-[72px] border-t border-white/[0.05]">
        <div className="max-w-[1240px] mx-auto">
          <h2 className="m-0 mb-10 text-[26px] sm:text-[34px] font-bold tracking-tight">{t('how.title')}</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
            {(['copyTrade', 'weekly'] as const).map(k => (
              <div key={k} className="bg-surface border border-white/[0.07] rounded-2xl p-7 flex flex-col gap-3.5">
                <div className="text-[21px] font-bold">{t(`how.${k}.title`)}</div>
                <div className="text-base leading-[1.9] text-text-muted">{t(`how.${k}.body`)}</div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── FAQ ────────────────────────────────────────────────── */}
      <section id="faq" className="px-5 sm:px-12 py-14 sm:py-[72px] border-t border-white/[0.05] bg-bg-rail">
        <div className="max-w-[1240px] mx-auto">
          <h2 className="m-0 mb-8 text-[26px] sm:text-[34px] font-bold tracking-tight">{t('faq.title')}</h2>
          <div className="flex flex-col gap-0.5 bg-white/[0.06] rounded-[14px] overflow-hidden">
            {faqs.map(n => (
              <details key={n} className="bg-surface group">
                <summary className="list-none cursor-pointer px-6 py-6 flex justify-between items-center gap-4 select-none">
                  <span className="text-[16px] sm:text-[17px] font-semibold">{t(`faq.q${n}`)}</span>
                  <span className="text-text-dim text-lg group-open:hidden">+</span>
                  <span className="text-cyan text-lg hidden group-open:inline">−</span>
                </summary>
                <div className="px-6 pb-6 text-base leading-[1.9] text-text-muted">{t(`faq.a${n}`)}</div>
              </details>
            ))}
          </div>
        </div>
      </section>

      {/* ── Risk disclosure + footer ───────────────────────────── */}
      <footer className="px-5 sm:px-12 py-12 sm:py-14 border-t border-white/[0.05]">
        <div className="max-w-[1240px] mx-auto flex flex-col md:flex-row gap-8 md:gap-10">
          <div className="flex-1 flex flex-col gap-3">
            <div className="font-mono text-[11px] tracking-[0.18em] uppercase text-warn">{t('risk.label')}</div>
            <div className="text-[13px] sm:text-[15px] leading-[1.95] text-text-muted max-w-[760px]">{t('risk.body')}</div>
          </div>
          {/* TODO: wire real data — 規約/プライバシー/特商法ページは未作成。作成後に Link 化する */}
          <div className="md:w-[220px] flex md:flex-col flex-wrap gap-x-6 gap-y-2.5 text-sm text-text-dim">
            <span>{t('footer.terms')}</span>
            <span>{t('footer.privacy')}</span>
            <span>{t('footer.tokushoho')}</span>
            <span>{t('footer.support')}</span>
          </div>
        </div>
      </footer>
    </div>
  )
}
