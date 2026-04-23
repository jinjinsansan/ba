import Link from 'next/link'
import Image from 'next/image'
import { useMessages, useTranslations } from 'next-intl'
import { LanguageSwitcher } from './_components/LanguageSwitcher'

export default function Home() {
  const t = useTranslations()
  const messages = useMessages() as {
    features: { items: Array<{ title: string; desc: string }> }
    pricing: { features: string[] }
    howItWorks: { steps: Array<{ title: string; desc: string }> }
    faq: { items: Array<{ q: string; a: string }> }
  }
  const featureItems = messages.features.items
  const pricingFeatures = messages.pricing.features
  const steps = messages.howItWorks.steps
  const faqItems = messages.faq.items

  const featureColors = ['text-player', 'text-banker', 'text-player', 'text-banker', 'text-player', 'text-banker']
  const stepColors = ['text-player', 'text-banker', 'text-player', 'text-banker']

  return (
    <main className="min-h-screen bg-bg-primary text-text">

      {/* Navbar */}
      <nav className="fixed top-0 inset-x-0 z-50 glass-panel border-b border-accent/20">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 h-16 flex items-center justify-between">
          <span className="text-xs font-hud tracking-[0.4em] text-accent uppercase">LAPLACE</span>
          <div className="hidden md:flex items-center gap-10 text-xs tracking-widest text-text-muted uppercase">
            <a href="#features" className="hover:text-text transition-colors">{t('nav.system')}</a>
            <a href="#pricing" className="hover:text-text transition-colors">{t('nav.access')}</a>
            <a href="#faq" className="hover:text-text transition-colors">{t('nav.faq')}</a>
            <Link href="/login" className="hover:text-text transition-colors">{t('nav.login')}</Link>
            <Link href="/signup" className="btn-outline px-5 py-2">
              {t('nav.cta')}
            </Link>
            <LanguageSwitcher />
          </div>
          <div className="flex md:hidden items-center gap-3">
            <LanguageSwitcher />
            <Link href="/login" className="text-xs text-text-muted hover:text-text tracking-widest uppercase">{t('nav.login')}</Link>
            <Link href="/signup" className="btn-outline px-3 py-1.5 text-xs">{t('nav.ctaShort')}</Link>
          </div>
        </div>
      </nav>

      {/* Hero */}
      <section className="relative min-h-screen flex items-center px-4 sm:px-6 pt-16 overflow-hidden">
        <div className="absolute inset-0 pointer-events-none">
          <div className="absolute top-0 left-1/2 -translate-x-1/2 w-px h-full bg-gradient-to-b from-transparent via-white/[0.03] to-transparent" />
        </div>

        <div className="max-w-6xl mx-auto w-full grid lg:grid-cols-2 gap-10 lg:gap-16 items-center py-16 sm:py-20">
          {/* Left — text */}
          <div className="text-center lg:text-left">
            <p className="hud-label mb-8">{t('hero.hudLabel')}</p>
            <h1 className="text-4xl sm:text-5xl md:text-7xl lg:text-8xl font-black leading-[0.9] tracking-tight mb-8 font-hud">
              <span className="block text-text">{t('hero.titleLine1')}</span>
              <span className="block text-text-dim">{t('hero.titleLine2')}</span>
              <span className="block text-text">{t('hero.titleLine3')}</span>
              <span className="block text-banker">{t('hero.titleLine4')}</span>
            </h1>
            <p className="text-text-muted text-sm sm:text-base leading-relaxed max-w-md mx-auto lg:mx-0 mb-10 sm:mb-12">
              {t('hero.tagline')}
            </p>
            <div className="flex flex-col sm:flex-row items-center gap-4 sm:gap-6 justify-center lg:justify-start">
              <Link href="/signup" className="btn-primary px-8 py-3.5 w-full sm:w-auto">
                {t('hero.cta')}
              </Link>
              <a href="#features" className="text-xs tracking-widest text-text-muted uppercase hover:text-text transition-colors border-b border-transparent hover:border-accent/40 pb-0.5">
                {t('hero.how')}
              </a>
            </div>

            {/* Stats inline */}
            <div className="mt-12 sm:mt-16 grid grid-cols-1 sm:grid-cols-3 gap-6 border-t border-white/5 pt-8 sm:pt-10">
                {[
                { num: '52%+', label: t('hero.stats.winRate'), color: 'text-player' },
                { num: '<2s', label: t('hero.stats.perDecision'), color: 'text-banker' },
                { num: '24/7', label: t('hero.stats.operation'), color: 'text-player' },
              ].map((s, i) => (
                <div key={i} className="text-center sm:text-left">
                  <div className={`text-2xl font-black tabular-nums ${s.color}`}>{s.num}</div>
                    <div className="text-[10px] tracking-widest text-text-dim uppercase mt-1">{s.label}</div>
                </div>
              ))}
            </div>
          </div>

          {/* Right — image */}
          <div className="relative flex justify-center lg:justify-end">
            <div className="relative w-64 sm:w-72 lg:w-96">
              <Image
                src="/foodblack.jpg"
                alt="LAPLACE"
                width={480}
                height={600}
                className="w-full object-cover"
                style={{filter:'contrast(1.05) brightness(0.95)'}}
                priority
              />
              <div className="absolute inset-x-0 bottom-0 h-32 bg-gradient-to-t from-bg-primary to-transparent" />
              <div className="absolute inset-y-0 right-0 w-16 bg-gradient-to-l from-bg-primary to-transparent hidden md:block" />
            </div>
          </div>
        </div>
      </section>

      {/* Features */}
      <section id="features" className="py-20 sm:py-28 lg:py-32 px-4 sm:px-6 border-t border-accent/10">
        <div className="max-w-6xl mx-auto">
          <div className="grid lg:grid-cols-2 gap-4 mb-4">
            <p className="hud-label">{t('features.hudLabel')}</p>
          </div>
          <h2 className="text-3xl sm:text-4xl lg:text-5xl font-black text-text mb-12 sm:mb-20 leading-tight font-hud">
            {t('features.titleLine1')}<br className="hidden sm:block" /><span className="text-text-dim">{t('features.titleLine2')}</span>
          </h2>
          <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {featureItems.map((f, i) => (
              <div key={i} className="glass-card p-6 sm:p-8 group">
                <div className={`text-[10px] tracking-widest mb-6 font-mono ${featureColors[i]}`}>{String(i + 1).padStart(2, '0')}</div>
                <h3 className="text-sm font-bold text-text mb-3 tracking-wide">{f.title}</h3>
                <p className="text-xs text-text-muted leading-relaxed">{f.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Pricing */}
      <section id="pricing" className="py-20 sm:py-28 lg:py-32 px-4 sm:px-6 border-t border-accent/10">
        <div className="max-w-6xl mx-auto">
          <p className="hud-label mb-4">{t('pricing.hudLabel')}</p>
          <h2 className="text-3xl sm:text-4xl lg:text-5xl font-black text-text mb-12 sm:mb-20 font-hud">{t('pricing.titleLine1')}<br className="hidden sm:block" /><span className="text-text-dim">{t('pricing.titleLine2')}</span></h2>
          <div className="max-w-lg">
            <div className="glass-card p-6 sm:p-10 relative">
              <div className="absolute top-0 left-0 w-8 h-px bg-player" />
              <div className="absolute top-0 left-0 w-px h-8 bg-player" />
              <div className="absolute bottom-0 right-0 w-8 h-px bg-banker" />
              <div className="absolute bottom-0 right-0 w-px h-8 bg-banker" />

              <p className="text-[10px] tracking-widest text-text-dim uppercase mb-4">{t('pricing.licenseLabel')}</p>
              <div className="text-5xl font-black text-text mb-1">$2,000</div>
              <p className="text-xs text-text-dim mb-10">{t('pricing.priceNote')}</p>

              <div className="space-y-4 mb-10">
                {pricingFeatures.map((item, i) => (
                  <div key={i} className="flex items-center gap-3 text-xs text-text-muted">
                    <div className="w-3 h-px bg-player flex-shrink-0" />
                    {item}
                  </div>
                ))}
              </div>

              <Link href="/signup" className="btn-primary block text-center py-4">
                {t('pricing.cta')}
              </Link>
            </div>
            <p className="text-xs text-text-dim mt-6 leading-relaxed">
              {t('pricing.footnote')}
            </p>
          </div>
        </div>
      </section>

      {/* How It Works */}
      <section className="py-20 sm:py-28 lg:py-32 px-4 sm:px-6 border-t border-accent/10">
        <div className="max-w-6xl mx-auto">
          <p className="hud-label mb-4">{t('howItWorks.hudLabel')}</p>
          <h2 className="text-3xl sm:text-4xl lg:text-5xl font-black text-text mb-12 sm:mb-20 font-hud">{t('howItWorks.titleLine1')}<br className="hidden sm:block" /><span className="text-text-dim">{t('howItWorks.titleLine2')}</span></h2>
          <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4">
            {steps.map((s, i) => (
              <div key={i} className="glass-card p-6 sm:p-8">
                <div className={`text-[10px] tracking-widest font-mono mb-6 ${stepColors[i]}`}>{String(i + 1).padStart(2, '0')}</div>
                <h4 className="text-sm font-bold text-text mb-3">{s.title}</h4>
                <p className="text-xs text-text-muted leading-relaxed">{s.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* FAQ */}
      <section id="faq" className="py-20 sm:py-28 lg:py-32 px-4 sm:px-6 border-t border-accent/10">
        <div className="max-w-6xl mx-auto grid lg:grid-cols-2 gap-12 lg:gap-20">
          <div>
            <p className="hud-label mb-4">{t('faq.hudLabel')}</p>
            <h2 className="text-3xl sm:text-4xl lg:text-5xl font-black text-text leading-tight font-hud">{t('faq.titleLine1')}<br className="hidden sm:block" /><span className="text-text-dim">{t('faq.titleLine2')}</span></h2>
          </div>
          <div className="space-y-0">
            {faqItems.map((f, i) => (
              <details key={i} className="group border-b border-accent/10 py-6">
                <summary className="cursor-pointer text-sm font-semibold text-text flex justify-between items-center gap-4 list-none">
                  {f.q}
                  <span className="text-text-dim group-open:text-player transition-colors flex-shrink-0 font-light text-lg leading-none">+</span>
                </summary>
                <p className="mt-4 text-xs text-text-muted leading-relaxed">{f.a}</p>
              </details>
            ))}
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="py-20 sm:py-28 lg:py-32 px-4 sm:px-6 border-t border-accent/10">
        <div className="max-w-6xl mx-auto flex flex-col lg:flex-row items-start lg:items-end justify-between gap-10 lg:gap-12">
          <div>
            <p className="hud-label mb-4 sm:mb-6">{t('finalCta.hudLabel')}</p>
            <h2 className="text-4xl sm:text-5xl lg:text-7xl font-black text-text leading-tight font-hud">
              <span className="block sm:inline">{t('finalCta.titleWord1')}</span>{' '}
              <span className="block sm:inline">{t('finalCta.titleWord2')}</span>{' '}
              <span className="block sm:inline text-text-dim">{t('finalCta.titleWord3')}</span>
            </h2>
          </div>
          <Link href="/signup" className="btn-primary px-10 py-4 w-full sm:w-auto flex-shrink-0">
            {t('finalCta.button')}
          </Link>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-accent/10 py-8 px-4 sm:px-6">
        <div className="max-w-6xl mx-auto flex flex-col sm:flex-row justify-between items-center text-[10px] tracking-widest text-text-dim uppercase gap-2">
          <span className="text-accent">LAPLACE</span>
          <span>&copy; 2026</span>
        </div>
      </footer>
    </main>
  )
}
