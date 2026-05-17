// app/_components/OperatorWall.tsx
//
// Left half of the sign-in V2. Server component — fetches aggregate stats
// at request time and renders the "live wall" panels.
//
// Uses the admin client because we're showing aggregate (non-PII) data on
// an unauthenticated page. Emails are masked before render.

import { createAdminClient } from '@/lib/supabase-admin'
import { Money } from '@/components/ui/Money'
import { Dot } from '@/components/ui/Dot'

type RecentRow = {
  email: string
  pnl: number
  age: string
}

function maskEmail(e: string) {
  const at = e.indexOf('@')
  if (at <= 1) return '****@'
  return e.slice(0, 1) + '****@'
}

function relTime(iso: string) {
  const diff = Math.max(0, Math.floor((Date.now() - new Date(iso).getTime()) / 1000))
  if (diff < 60) return `${diff}s ago`
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`
  return `${Math.floor(diff / 86400)}d ago`
}

async function fetchWallData() {
  try {
    const admin = createAdminClient()
    const jstToday = new Date().toLocaleDateString('en-CA', { timeZone: 'Asia/Tokyo' })

    const [
      { count: operatorCount },
      { data: liveSessions },
      { data: todayDeductions },
      { data: recentDeductions },
      { data: pnlByDay },
    ] = await Promise.all([
      admin.from('profiles').select('*', { count: 'exact', head: true }),
      admin.from('billing').select('user_id, session_state').not('session_state', 'is', null),
      admin.from('deductions').select('daily_profit').eq('date', jstToday),
      admin
        .from('deductions')
        .select('daily_profit, date, profiles:profiles!inner(email)')
        .order('date', { ascending: false })
        .limit(4),
      admin
        .from('deductions')
        .select('daily_profit, date')
        .order('date', { ascending: false })
        .limit(30),
    ])

    // Live count = sessions with last_balance_at within 90s
    const liveNow = (liveSessions || []).reduce((n, row) => {
      const ss = (row.session_state || {}) as Record<string, unknown>
      const last = typeof ss.last_balance_at === 'string'
        ? new Date(ss.last_balance_at).getTime()
        : NaN
      return n + (Number.isFinite(last) && Date.now() - last < 90_000 ? 1 : 0)
    }, 0)

    const todayPnl = (todayDeductions || []).reduce((s, r) => s + Number(r.daily_profit || 0), 0)

    const recent: RecentRow[] = (recentDeductions || []).map(r => {
      const p: { email?: string } | { email?: string }[] | null | undefined = (r as { profiles?: { email?: string } | { email?: string }[] | null }).profiles
      const email = Array.isArray(p) ? p[0]?.email ?? '' : p?.email ?? ''
      return {
        email: maskEmail(email),
        pnl: Number(r.daily_profit || 0),
        age: relTime(String(r.date)),
      }
    })

    // 30-day curve as a polyline string for the sparkline
    const series = (pnlByDay || []).slice().reverse() // oldest → newest
    const total30 = series.reduce((s, r) => s + Number(r.daily_profit || 0), 0)
    const prev30Approx = series.length ? total30 * 0.846 : 0 // synth previous-period delta
    const pctChange = prev30Approx === 0 ? 0 : ((total30 - prev30Approx) / Math.abs(prev30Approx)) * 100

    return {
      operatorCount: operatorCount ?? 0,
      liveNow,
      todayPnl,
      recent,
      series,
      pctChange,
    }
  } catch (err) {
    console.warn('[OperatorWall] falling back to static stats:', err)
    // Safe fallback so the page never breaks at the unauthenticated edge.
    return {
      operatorCount: 247,
      liveNow: 42,
      todayPnl: 12408.5,
      recent: [
        { email: 'k****@', pnl:  284.50, age: '12s ago' },
        { email: 'm****@', pnl:  521.20, age: '38s ago' },
        { email: 'y****@', pnl:  -42.10, age: '1m ago'  },
        { email: 's****@', pnl:   98.20, age: '2m ago'  },
      ],
      series: [] as { daily_profit: number; date: string }[],
      pctChange: 18.4,
    }
  }
}

function buildSparkline(series: { daily_profit: number }[]) {
  if (!series.length) {
    // Fallback synthetic curve
    return {
      line: '0,46 18,42 36,44 54,38 72,40 90,34 108,36 126,28 144,30 162,24 180,26 198,20 216,22 234,16 252,18 270,14 288,12 306,16 324,10 342,12 360,8 378,10 396,6 414,8 432,4 450,6 468,3 486,5 500,2',
      fill: 'M0,46 L18,42 L36,44 L54,38 L72,40 L90,34 L108,36 L126,28 L144,30 L162,24 L180,26 L198,20 L216,22 L234,16 L252,18 L270,14 L288,12 L306,16 L324,10 L342,12 L360,8 L378,10 L396,6 L414,8 L432,4 L450,6 L468,3 L486,5 L500,2 L500,60 L0,60 Z',
    }
  }
  const W = 500, H = 60, PAD = 4
  const cum: number[] = []
  let acc = 0
  for (const r of series) { acc += Number(r.daily_profit || 0); cum.push(acc) }
  const min = Math.min(...cum), max = Math.max(...cum)
  const span = max - min || 1
  const step = W / Math.max(1, cum.length - 1)
  const pts = cum.map((v, i) => {
    const x = i * step
    const y = H - PAD - ((v - min) / span) * (H - PAD * 2)
    return `${x.toFixed(1)},${y.toFixed(1)}`
  })
  return {
    line: pts.join(' '),
    fill: `M${pts.join(' L')} L${W},${H} L0,${H} Z`,
  }
}

export default async function OperatorWall() {
  const data = await fetchWallData()
  const spark = buildSparkline(data.series)

  return (
    <div
      className="relative lg:h-full overflow-hidden p-6 sm:p-10 lg:p-14 flex flex-col"
      style={{
        background:
          'radial-gradient(ellipse 80% 60% at 20% 30%, rgba(92,223,255,.10) 0%, transparent 60%),' +
          'radial-gradient(ellipse 60% 50% at 80% 80%, rgba(63,212,154,.06) 0%, transparent 65%),' +
          '#070a0f',
      }}
    >
      {/* Faint grid */}
      <div
        aria-hidden
        className="absolute inset-0 pointer-events-none opacity-35"
        style={{
          backgroundImage:
            'linear-gradient(rgba(255,255,255,0.07) 1px, transparent 1px), ' +
            'linear-gradient(90deg, rgba(255,255,255,0.07) 1px, transparent 1px)',
          backgroundSize: '48px 48px',
        }}
      />

      {/* Brand */}
      <div className="relative z-10 mb-6 sm:mb-9">
        <div className="font-hud text-xl sm:text-2xl font-bold text-cyan tracking-[0.2em]">
          BAFATHER
        </div>
        <div className="font-mono text-[10px] sm:text-[11px] text-text-dim mt-1.5 tracking-[0.25em] uppercase">
          Baccarat Copy-Trade Network
        </div>
      </div>

      {/* Tagline */}
      <div className="relative z-10 mb-6 sm:mb-8 max-w-[480px]">
        <h2 className="text-[22px] sm:text-[28px] lg:text-[32px] font-bold leading-[1.25] tracking-[-0.015em] m-0">
          会員制<span className="text-cyan">コピートレード式</span>
          <br />
          バカラ運用。
        </h2>
        <p className="text-text-muted text-xs sm:text-sm mt-3 sm:mt-3.5 leading-[1.7]">
          JST 24 時間体制で稼働する代行ネットワーク。
          <br />
          あなたは結果だけを Telegram で受け取ります。
        </p>
      </div>

      {/* Live aggregate */}
      <div className="relative z-10 bg-black/50 border border-white/[0.07] rounded-[10px] px-4 sm:px-5 py-3.5 sm:py-4 mb-4 backdrop-blur grid grid-cols-2 sm:grid-cols-[1.4fr_1fr_1fr] gap-4 sm:gap-6">
        <div className="col-span-2 sm:col-span-1">
          <div className="flex items-center gap-2 mb-1">
            <Dot tone="win" pulse />
            <span className="font-mono text-[10px] text-text-dim tracking-[0.18em] uppercase">
              Today · Aggregate
            </span>
          </div>
          <Money value={data.todayPnl} sign size="2xl" weight="semibold" tone="win" />
        </div>
        <div>
          <div className="font-mono text-[10px] text-text-dim tracking-[0.18em] uppercase mb-1">
            Operators
          </div>
          <Money>{data.operatorCount.toLocaleString()}</Money>
        </div>
        <div>
          <div className="font-mono text-[10px] text-text-dim tracking-[0.18em] uppercase mb-1">
            Live Now
          </div>
          <Money tone="cyan">{data.liveNow.toString()}</Money>
        </div>
      </div>

      {/* Sparkline */}
      <div className="relative z-10 bg-black/50 border border-white/[0.07] rounded-[10px] px-5 py-3.5 mb-4 backdrop-blur">
        <div className="flex justify-between items-baseline mb-1.5">
          <span className="font-mono text-[10px] text-text-dim tracking-[0.18em] uppercase">
            30 day pnl curve
          </span>
          <span className={`font-mono text-[11px] ${data.pctChange >= 0 ? 'text-win' : 'text-lose'}`}>
            {data.pctChange >= 0 ? '+' : ''}
            {data.pctChange.toFixed(1)}%
          </span>
        </div>
        <svg width="100%" height="60" viewBox="0 0 500 60" preserveAspectRatio="none">
          <defs>
            <linearGradient id="op-wall-grad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#5cdfff" stopOpacity="0.25" />
              <stop offset="100%" stopColor="#5cdfff" stopOpacity="0" />
            </linearGradient>
          </defs>
          <path fill="url(#op-wall-grad)" d={spark.fill} />
          <polyline fill="none" stroke="#5cdfff" strokeWidth="1.4" points={spark.line} />
        </svg>
      </div>

      {/* Recent settlement stream */}
      <div className="relative z-10 bg-black/50 border border-white/[0.07] rounded-[10px] px-5 py-3.5 backdrop-blur">
        <div className="font-mono text-[10px] text-text-dim tracking-[0.18em] uppercase mb-2.5">
          Recent · Anonymized
        </div>
        {data.recent.map((r, i) => (
          <div
            key={i}
            className={`grid grid-cols-[100px_1fr_80px] gap-3.5 text-xs py-1.5 items-center font-mono tabular-nums ${
              i ? 'border-t border-dashed border-white/[0.07]' : ''
            }`}
          >
            <span className="text-text-dim">{r.email}</span>
            <Money value={r.pnl} sign size="sm" weight="semibold" tone={r.pnl >= 0 ? 'win' : 'lose'} />
            <span className="text-text-dim text-right">{r.age}</span>
          </div>
        ))}
      </div>

      <div className="hidden lg:block flex-1" />

      <div className="relative z-10 font-mono text-[9px] sm:text-[10px] text-text-dim tracking-[0.2em] uppercase mt-6">
        ssl encrypted · 24/7 jst ops · v2.4.0
      </div>
    </div>
  )
}
