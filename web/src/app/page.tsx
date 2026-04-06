import Link from 'next/link'
import Image from 'next/image'

export default function Home() {
  return (
    <main className="min-h-screen bg-bg-primary">

      {/* Navbar */}
      <nav className="fixed top-0 inset-x-0 z-50 border-b border-white/[0.04]" style={{background:'rgba(5,7,12,0.85)',backdropFilter:'blur(20px)'}}>
        <div className="max-w-6xl mx-auto px-6 h-16 flex items-center justify-between">
          <span className="text-sm font-black tracking-[0.25em] text-white uppercase">LAPLACE</span>
          <div className="hidden md:flex items-center gap-10 text-xs tracking-widest text-slate-500 uppercase">
            <a href="#features" className="hover:text-white transition-colors">System</a>
            <a href="#pricing" className="hover:text-white transition-colors">Access</a>
            <a href="#faq" className="hover:text-white transition-colors">FAQ</a>
            <Link href="/login" className="hover:text-white transition-colors">Login</Link>
            <Link href="/signup" className="px-5 py-2 border border-white/20 text-white text-xs tracking-widest hover:border-white/60 hover:bg-white/5 transition-all">
              GET ACCESS
            </Link>
          </div>
          <div className="flex md:hidden items-center gap-4">
            <Link href="/login" className="text-xs text-slate-500 hover:text-white tracking-widest uppercase">Login</Link>
            <Link href="/signup" className="px-3 py-1.5 border border-white/20 text-white text-xs tracking-widest uppercase hover:border-white/60 transition-all">Access</Link>
          </div>
        </div>
      </nav>

      {/* Hero */}
      <section className="relative min-h-screen flex items-center px-6 pt-16 overflow-hidden">
        <div className="absolute inset-0 pointer-events-none">
          <div className="absolute top-0 left-1/2 -translate-x-1/2 w-px h-full bg-gradient-to-b from-transparent via-white/[0.03] to-transparent" />
        </div>

        <div className="max-w-6xl mx-auto w-full grid md:grid-cols-2 gap-16 items-center py-24">
          {/* Left — text */}
          <div>
            <p className="text-xs tracking-[0.3em] text-player/60 uppercase mb-8">Automated Baccarat Intelligence</p>
            <h1 className="text-6xl md:text-8xl font-black leading-[0.9] tracking-tight mb-8">
              <span className="block text-white">THE</span>
              <span className="block text-white/20">EDGE</span>
              <span className="block text-white">IS</span>
              <span className="block text-banker">REAL.</span>
            </h1>
            <p className="text-slate-500 text-sm leading-relaxed max-w-sm mb-12">
              Pattern recognition. Automated execution. Surgical risk control.
              LAPLACE operates where discipline meets probability.
            </p>
            <div className="flex items-center gap-6">
              <Link href="/signup" className="px-8 py-3.5 bg-white text-black text-xs font-black tracking-widest uppercase hover:bg-white/90 transition-colors">
                GET ACCESS
              </Link>
              <a href="#features" className="text-xs tracking-widest text-slate-500 uppercase hover:text-white transition-colors border-b border-transparent hover:border-slate-500 pb-0.5">
                How it works
              </a>
            </div>

            {/* Stats inline */}
            <div className="mt-16 grid grid-cols-3 gap-6 border-t border-white/5 pt-10">
              {[
                { num: '52%+', label: 'Win Rate', color: 'text-player' },
                { num: '<2s', label: 'Per Decision', color: 'text-banker' },
                { num: '24/7', label: 'Operation', color: 'text-player' },
              ].map((s, i) => (
                <div key={i}>
                  <div className={`text-2xl font-black tabular-nums ${s.color}`}>{s.num}</div>
                  <div className="text-[10px] tracking-widest text-slate-600 uppercase mt-1">{s.label}</div>
                </div>
              ))}
            </div>
          </div>

          {/* Right — image */}
          <div className="relative flex justify-center md:justify-end">
            <div className="relative w-72 md:w-96">
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
      <section id="features" className="py-32 px-6 border-t border-white/[0.04]">
        <div className="max-w-6xl mx-auto">
          <div className="grid md:grid-cols-2 gap-4 mb-4">
            <p className="text-[10px] tracking-[0.3em] text-player/60 uppercase">System Architecture</p>
          </div>
          <h2 className="text-4xl md:text-5xl font-black text-white mb-20 leading-tight">
            Built for<br /><span className="text-white/20">precision.</span>
          </h2>
          <div className="grid md:grid-cols-3 gap-px bg-white/[0.04]">
            {[
              { num: '01', title: 'Pattern Recognition', desc: 'Proprietary Maru-Batsu strategy. Multi-layer sequence analysis across full shoe history.', c: 'text-player' },
              { num: '02', title: 'Zero Touch Execution', desc: 'Table selection, bet sizing, result logging. Fully automated from entry to exit.', c: 'text-banker' },
              { num: '03', title: 'Risk Architecture', desc: 'Hard profit targets. Hard loss limits. Automatic session termination. No overrides.', c: 'text-player' },
              { num: '04', title: 'Live Intelligence', desc: 'Win rate, P&L curve, set-by-set breakdown. Every hand accounted for.', c: 'text-banker' },
              { num: '05', title: 'Cloud Logic Engine', desc: 'Prediction computed server-side. Your machine handles execution only. Low latency.', c: 'text-player' },
              { num: '06', title: 'Bound Distribution', desc: 'Each binary is cryptographically tied to your license. Redistribution is structurally impossible.', c: 'text-banker' },
            ].map((f, i) => (
              <div key={i} className="bg-bg-primary p-8 hover:bg-white/[0.02] transition-colors group">
                <div className={`text-[10px] tracking-widest mb-6 font-mono ${f.c}`}>{f.num}</div>
                <h3 className="text-sm font-bold text-white mb-3 tracking-wide">{f.title}</h3>
                <p className="text-xs text-slate-500 leading-relaxed">{f.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Pricing */}
      <section id="pricing" className="py-32 px-6 border-t border-white/[0.04]">
        <div className="max-w-6xl mx-auto">
          <p className="text-[10px] tracking-[0.3em] text-player/60 uppercase mb-4">Access</p>
          <h2 className="text-4xl md:text-5xl font-black text-white mb-20">One license.<br /><span className="text-white/20">No subscription.</span></h2>
          <div className="max-w-lg">
            <div className="border border-white/10 p-10 relative">
              <div className="absolute top-0 left-0 w-8 h-px bg-player" />
              <div className="absolute top-0 left-0 w-px h-8 bg-player" />
              <div className="absolute bottom-0 right-0 w-8 h-px bg-banker" />
              <div className="absolute bottom-0 right-0 w-px h-8 bg-banker" />

              <p className="text-[10px] tracking-widest text-slate-600 uppercase mb-4">LAPLACE License</p>
              <div className="text-5xl font-black text-white mb-1">$2,000</div>
              <p className="text-xs text-slate-600 mb-10">USDT · One-time · Deducted from first charge</p>

              <div className="space-y-4 mb-10">
                {[
                  'Full prediction engine access',
                  'Automated bet execution',
                  'Live dashboard',
                  'Cloud logic processing',
                  'Lifetime updates',
                ].map((item, i) => (
                  <div key={i} className="flex items-center gap-3 text-xs text-slate-400">
                    <div className="w-3 h-px bg-player flex-shrink-0" />
                    {item}
                  </div>
                ))}
              </div>

              <Link href="/signup" className="block text-center py-4 bg-white text-black text-xs font-black tracking-widest uppercase hover:bg-white/90 transition-colors">
                GET ACCESS
              </Link>
            </div>
            <p className="text-xs text-slate-700 mt-6 leading-relaxed">
              Daily profit share applied at midnight JST. Losses carry forward and offset future fees before any deduction is made.
            </p>
          </div>
        </div>
      </section>

      {/* How It Works */}
      <section className="py-32 px-6 border-t border-white/[0.04]">
        <div className="max-w-6xl mx-auto">
          <p className="text-[10px] tracking-[0.3em] text-banker/60 uppercase mb-4">Deployment</p>
          <h2 className="text-4xl md:text-5xl font-black text-white mb-20">Four steps.<br /><span className="text-white/20">Then nothing.</span></h2>
          <div className="grid md:grid-cols-4 gap-px bg-white/[0.04]">
            {[
              { step: '01', title: 'Pay', desc: 'Purchase license with USDT. TRC-20 or ERC-20. Confirmed within 30 minutes.', c: 'text-player' },
              { step: '02', title: 'Download', desc: 'Receive your personalized LAPLACE.exe. Bound to your license key.', c: 'text-banker' },
              { step: '03', title: 'Connect', desc: 'Sign into Stake once inside the built-in browser. Credentials stay local.', c: 'text-player' },
              { step: '04', title: 'Run', desc: 'Press START. The system operates autonomously. No further input required.', c: 'text-banker' },
            ].map((s, i) => (
              <div key={i} className="bg-bg-primary p-8">
                <div className={`text-[10px] tracking-widest font-mono mb-6 ${s.c}`}>{s.step}</div>
                <h4 className="text-sm font-bold text-white mb-3">{s.title}</h4>
                <p className="text-xs text-slate-500 leading-relaxed">{s.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* FAQ */}
      <section id="faq" className="py-32 px-6 border-t border-white/[0.04]">
        <div className="max-w-6xl mx-auto grid md:grid-cols-2 gap-20">
          <div>
            <p className="text-[10px] tracking-[0.3em] text-player/60 uppercase mb-4">FAQ</p>
            <h2 className="text-4xl md:text-5xl font-black text-white leading-tight">Questions<br /><span className="text-white/20">answered.</span></h2>
          </div>
          <div className="space-y-0">
            {[
              { q: 'How does the profit share work?', a: 'At midnight JST, net session profit is calculated. A percentage is deducted from your balance. Losing days carry forward — no fees until prior losses are recovered.' },
              { q: 'What happens when the balance hits zero?', a: 'A 24-hour grace period activates. Bot pauses. Recharge at any time to resume. No penalties, no account loss.' },
              { q: 'How is the license fee charged?', a: 'Deducted automatically from your first charge. Pay $2,000 license + $3,000 charge = $3,000 operational balance.' },
              { q: 'What payment methods are accepted?', a: 'USDT only. TRC-20 (TRON) or ERC-20 (Ethereum). Manual confirmation, typically under 30 minutes.' },
              { q: 'Can this run on a cloud machine?', a: 'Yes. Any Windows 10/11 environment — local or cloud. AWS WorkSpaces, Paperspace, Shadow PC all confirmed.' },
            ].map((f, i) => (
              <details key={i} className="group border-b border-white/[0.04] py-6">
                <summary className="cursor-pointer text-sm font-semibold text-white flex justify-between items-center gap-4 list-none">
                  {f.q}
                  <span className="text-slate-700 group-open:text-player transition-colors flex-shrink-0 font-light text-lg leading-none">+</span>
                </summary>
                <p className="mt-4 text-xs text-slate-500 leading-relaxed">{f.a}</p>
              </details>
            ))}
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="py-32 px-6 border-t border-white/[0.04]">
        <div className="max-w-6xl mx-auto flex flex-col md:flex-row items-start md:items-end justify-between gap-12">
          <div>
            <p className="text-[10px] tracking-[0.3em] text-banker/60 uppercase mb-6">Start Operating</p>
            <h2 className="text-5xl md:text-7xl font-black text-white leading-none">
              Ready<br />when<br /><span className="text-white/20">you are.</span>
            </h2>
          </div>
          <Link href="/signup" className="px-10 py-4 bg-white text-black text-xs font-black tracking-widest uppercase hover:bg-white/90 transition-colors flex-shrink-0">
            CREATE ACCOUNT
          </Link>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-white/[0.04] py-8 px-6">
        <div className="max-w-6xl mx-auto flex justify-between items-center text-[10px] tracking-widest text-slate-700 uppercase">
          <span>LAPLACE</span>
          <span>&copy; 2026</span>
        </div>
      </footer>
    </main>
  )
}
