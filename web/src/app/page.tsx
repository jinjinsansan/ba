import Link from 'next/link'

function Card({ suit, value, color }: { suit: string; value: string; color: string }) {
  return (
    <div className={`w-16 h-24 rounded-lg border ${color === 'red' ? 'border-banker/40 bg-banker/10' : 'border-player/40 bg-player/10'} flex flex-col items-center justify-center text-2xl font-bold ${color === 'red' ? 'text-banker' : 'text-player'} shadow-lg`}>
      <span className="text-xs opacity-60">{suit}</span>
      <span>{value}</span>
    </div>
  )
}

export default function Home() {
  return (
    <main className="min-h-screen">
      {/* Navbar */}
      <nav className="fixed top-0 inset-x-0 z-50 border-b border-white/5 bg-bg-primary/80 backdrop-blur-xl">
        <div className="max-w-6xl mx-auto px-6 h-16 flex items-center justify-between">
          <span className="text-xl font-black tracking-wider bg-gradient-to-r from-player to-banker bg-clip-text text-transparent">LAPLACE</span>
          <div className="hidden md:flex items-center gap-8 text-sm text-slate-400">
            <a href="#features" className="hover:text-white transition">Features</a>
            <a href="#pricing" className="hover:text-white transition">Pricing</a>
            <a href="#faq" className="hover:text-white transition">FAQ</a>
            <Link href="/login" className="hover:text-white transition">Login</Link>
            <Link href="/signup" className="px-4 py-2 rounded-lg bg-gradient-to-r from-player to-accent text-white font-semibold text-sm hover:opacity-90 transition">Get Started</Link>
          </div>
          <div className="flex md:hidden items-center gap-3">
            <Link href="/login" className="text-sm text-slate-400 hover:text-white">Login</Link>
            <Link href="/signup" className="px-3 py-1.5 rounded-lg bg-gradient-to-r from-player to-accent text-white font-semibold text-xs">Start</Link>
          </div>
        </div>
      </nav>

      {/* Hero */}
      <section className="relative min-h-screen flex flex-col items-center justify-center text-center px-6 pt-20">
        <div className="absolute inset-0 overflow-hidden pointer-events-none">
          <div className="absolute top-1/4 left-1/4 w-96 h-96 bg-player/5 rounded-full blur-3xl" />
          <div className="absolute bottom-1/4 right-1/4 w-96 h-96 bg-banker/5 rounded-full blur-3xl" />
        </div>
        <div className="relative z-10">
          <div className="flex gap-3 justify-center mb-8">
            <Card suit="♠" value="A" color="blue" />
            <Card suit="♥" value="K" color="red" />
            <Card suit="♦" value="9" color="red" />
            <Card suit="♣" value="7" color="blue" />
          </div>
          <h1 className="text-5xl md:text-7xl font-black mb-6 leading-tight">
            <span className="text-player">Predict.</span>{' '}
            <span className="text-white">Execute.</span>{' '}
            <span className="text-banker">Profit.</span>
          </h1>
          <p className="text-lg text-slate-400 max-w-2xl mx-auto mb-10">
            AI-powered baccarat prediction engine with fully automated bet execution.
            Advanced pattern recognition running 24/7 on your desktop.
          </p>
          <div className="flex gap-4 justify-center flex-wrap">
            <Link href="/signup" className="px-8 py-4 rounded-xl bg-gradient-to-r from-player to-accent text-white font-bold text-lg hover:shadow-lg hover:shadow-player/20 transition-all hover:-translate-y-0.5">
              Start Now
            </Link>
            <a href="#features" className="px-8 py-4 rounded-xl border border-white/10 text-white font-semibold text-lg hover:border-white/30 transition">
              Learn More
            </a>
          </div>
        </div>
      </section>

      {/* Features */}
      <section id="features" className="py-24 px-6">
        <div className="max-w-6xl mx-auto">
          <h2 className="text-4xl font-bold text-center mb-4">Why <span className="text-player">LAPLACE</span></h2>
          <p className="text-center text-slate-400 mb-16 max-w-xl mx-auto">A complete automated system built for serious players</p>
          <div className="grid md:grid-cols-3 gap-6">
            {[
              { icon: '🧠', title: 'AI Pattern Recognition', desc: 'Proprietary Maru-Batsu strategy with multi-layer sequence analysis across shoe patterns.' },
              { icon: '⚡', title: 'Fully Automated', desc: 'From table selection to bet placement to result tracking. Zero manual intervention.' },
              { icon: '🛡️', title: 'Risk Management', desc: 'Built-in profit targets and loss limits. Automatic session reset and bankroll protection.' },
              { icon: '📊', title: 'Real-Time Analytics', desc: 'Live dashboard showing win rate, P&L tracking, and set-by-set breakdown.' },
              { icon: '🌐', title: 'Cloud Logic Engine', desc: 'Prediction runs on our secure servers. Your client handles execution only.' },
              { icon: '🔒', title: 'Fingerprinted Security', desc: 'Each client is uniquely bound to your API key. Redistribution is blocked.' },
            ].map((f, i) => (
              <div key={i} className="p-6 rounded-2xl bg-bg-card border border-white/5 hover:border-player/30 transition-all hover:-translate-y-1">
                <div className="text-3xl mb-4">{f.icon}</div>
                <h3 className="text-lg font-bold mb-2">{f.title}</h3>
                <p className="text-slate-400 text-sm">{f.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Stats */}
      <section className="py-16 border-y border-white/5">
        <div className="max-w-4xl mx-auto flex justify-around flex-wrap gap-8 px-6">
          {[
            { num: '52%+', label: 'Win Rate' },
            { num: '24/7', label: 'Automated' },
            { num: '<2s', label: 'Decision Speed' },
            { num: '100%', label: 'Hands Tracked' },
          ].map((s, i) => (
            <div key={i} className="text-center">
              <div className="text-4xl font-black bg-gradient-to-r from-player to-banker bg-clip-text text-transparent">{s.num}</div>
              <div className="text-sm text-slate-500 mt-1">{s.label}</div>
            </div>
          ))}
        </div>
      </section>

      {/* Pricing */}
      <section id="pricing" className="py-24 px-6">
        <div className="max-w-4xl mx-auto">
          <h2 className="text-4xl font-bold text-center mb-4">Pricing</h2>
          <p className="text-center text-slate-400 mb-16">One-time license + charge-based profit sharing</p>
          <div className="grid md:grid-cols-2 gap-6">
            <div className="p-8 rounded-2xl bg-bg-card border border-white/5">
              <h3 className="text-xl font-bold mb-1">Starter</h3>
              <div className="text-4xl font-black my-4">$1,000 <span className="text-sm text-slate-500 font-normal">license</span></div>
              <ul className="space-y-3 text-sm text-slate-400 mb-8">
                <li className="flex gap-2"><span className="text-player">✓</span> Full AI prediction engine</li>
                <li className="flex gap-2"><span className="text-player">✓</span> Automated bet execution</li>
                <li className="flex gap-2"><span className="text-player">✓</span> Real-time dashboard</li>
                <li className="flex gap-2"><span className="text-player">✓</span> 20% daily profit share</li>
              </ul>
              <Link href="/signup?plan=starter" className="block text-center py-3 rounded-xl border border-player/30 text-player font-semibold hover:bg-player/10 transition">Get Starter</Link>
            </div>
            <div className="p-8 rounded-2xl bg-bg-card border border-player/40 relative">
              <div className="absolute -top-3 left-1/2 -translate-x-1/2 px-4 py-1 rounded-full bg-gradient-to-r from-player to-accent text-xs font-bold text-white">POPULAR</div>
              <h3 className="text-xl font-bold mb-1">Professional</h3>
              <div className="text-4xl font-black my-4">$3,000 <span className="text-sm text-slate-500 font-normal">license</span></div>
              <ul className="space-y-3 text-sm text-slate-400 mb-8">
                <li className="flex gap-2"><span className="text-player">✓</span> Everything in Starter</li>
                <li className="flex gap-2"><span className="text-player">✓</span> Priority cloud processing</li>
                <li className="flex gap-2"><span className="text-player">✓</span> Advanced analytics</li>
                <li className="flex gap-2"><span className="text-player">✓</span> Priority support</li>
              </ul>
              <Link href="/signup?plan=pro" className="block text-center py-3 rounded-xl bg-gradient-to-r from-player to-accent text-white font-semibold hover:opacity-90 transition">Get Professional</Link>
            </div>
          </div>
          <p className="text-center text-slate-500 text-sm mt-6">License fee is deducted from your first charge. Daily profit share: losses carry forward.</p>
        </div>
      </section>

      {/* How It Works */}
      <section className="py-24 px-6 bg-bg-secondary/50">
        <div className="max-w-4xl mx-auto">
          <h2 className="text-4xl font-bold text-center mb-16">How It Works</h2>
          <div className="grid md:grid-cols-4 gap-8">
            {[
              { step: '1', title: 'Sign Up & Pay', desc: 'Select plan, pay with USDT' },
              { step: '2', title: 'Download', desc: 'Get your personalized LAPLACE.exe' },
              { step: '3', title: 'Login Once', desc: 'Sign into Stake in the built-in browser' },
              { step: '4', title: 'Press START', desc: 'Bot handles everything automatically' },
            ].map((s, i) => (
              <div key={i} className="text-center">
                <div className="w-14 h-14 rounded-full bg-gradient-to-r from-player to-accent flex items-center justify-center text-xl font-black mx-auto mb-4">{s.step}</div>
                <h4 className="font-bold mb-2">{s.title}</h4>
                <p className="text-sm text-slate-400">{s.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* FAQ */}
      <section id="faq" className="py-24 px-6">
        <div className="max-w-2xl mx-auto">
          <h2 className="text-4xl font-bold text-center mb-16">FAQ</h2>
          {[
            { q: 'What is the daily profit share?', a: 'At midnight JST, we calculate net profit. Profitable days have a percentage deducted from your charge balance. Losses carry forward to offset future profits.' },
            { q: 'What happens when my balance runs out?', a: '24-hour grace period, then the bot pauses. Recharge to resume. No penalties.' },
            { q: 'How is the license fee charged?', a: 'Deducted from your first charge. $1,000 plan + $3,000 charge = $2,000 starting balance.' },
            { q: 'What payment methods?', a: 'USDT via TRC-20 (TRON) or ERC-20 (Ethereum). Confirmed manually, usually within 30 minutes.' },
            { q: 'Can I run on a cloud desktop?', a: 'Yes. Any Windows 10/11 machine including AWS WorkSpaces, Paperspace, or Shadow PC.' },
          ].map((f, i) => (
            <details key={i} className="group border-b border-white/5 py-5">
              <summary className="cursor-pointer font-semibold flex justify-between items-center">
                {f.q}
                <span className="text-slate-500 group-open:rotate-45 transition-transform text-xl">+</span>
              </summary>
              <p className="mt-3 text-slate-400 text-sm">{f.a}</p>
            </details>
          ))}
        </div>
      </section>

      {/* CTA */}
      <section className="py-24 px-6 text-center">
        <h2 className="text-4xl font-bold mb-6">Ready to start?</h2>
        <Link href="/signup" className="inline-block px-10 py-4 rounded-xl bg-gradient-to-r from-player to-banker text-white font-bold text-lg hover:shadow-xl hover:shadow-player/20 transition-all hover:-translate-y-1">
          Create Account
        </Link>
      </section>

      {/* Footer */}
      <footer className="border-t border-white/5 py-8 text-center text-sm text-slate-500">
        <p>&copy; 2026 LAPLACE. All rights reserved.</p>
      </footer>
    </main>
  )
}
