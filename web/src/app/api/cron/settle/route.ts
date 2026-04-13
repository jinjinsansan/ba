import { createAdminClient } from '@/lib/supabase-admin'
import { NextRequest, NextResponse } from 'next/server'

function getJstDateString() {
  return new Date().toLocaleDateString('en-CA', { timeZone: 'Asia/Tokyo' })
}

async function settleUser(admin: ReturnType<typeof createAdminClient>, userId: string, dailyProfit: number, dateStr: string) {
  const { data: billing } = await admin
    .from('billing')
    .select('balance, profit_share_rate, carry_loss, is_free, suspended')
    .eq('user_id', userId)
    .single()

  if (!billing) return { ok: false, error: 'Billing not found' }

  const { data: existing } = await admin
    .from('deductions')
    .select('id')
    .eq('user_id', userId)
    .eq('date', dateStr)
    .maybeSingle()

  if (existing) return { ok: false, error: 'Already settled for this date' }

  const carryLoss = Number(billing.carry_loss) || 0
  const netProfit = dailyProfit + carryLoss
  let feeAmount = 0
  let newCarryLoss = 0

  if (!billing.is_free && netProfit > 0) {
    feeAmount = netProfit * Number(billing.profit_share_rate)
    newCarryLoss = 0
  } else if (netProfit <= 0) {
    feeAmount = 0
    newCarryLoss = netProfit
  }

  const newBalance = Number(billing.balance) - feeAmount
  const nextBalance = Math.max(0, newBalance)
  const shouldSuspend = !billing.is_free && nextBalance <= 0

  await admin.from('deductions').insert({
    user_id: userId,
    date: dateStr,
    daily_profit: dailyProfit,
    fee_amount: feeAmount,
    carry_loss: newCarryLoss,
    note: netProfit > 0
      ? `${(Number(billing.profit_share_rate) * 100).toFixed(0)}% of net $${netProfit.toFixed(2)}`
      : 'Loss carried forward',
  })

  await admin.from('billing').update({
    balance: nextBalance,
    carry_loss: newCarryLoss,
    suspended: shouldSuspend,
    updated_at: new Date().toISOString(),
  }).eq('user_id', userId)

  return { ok: true, feeAmount, newBalance: nextBalance, suspended: shouldSuspend }
}

export async function GET(req: NextRequest) {
  const authHeader = req.headers.get('authorization')
  if (authHeader !== `Bearer ${process.env.CRON_SECRET}`) {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })
  }

  const admin = createAdminClient()
  const dateStr = getJstDateString()

  const { data: billings } = await admin
    .from('billing')
    .select('user_id, balance, profit_share_rate, carry_loss, is_free, suspended')
    .eq('suspended', false)
    .gt('balance', 0)

  if (!billings?.length) return NextResponse.json({ message: 'No active users', settled: 0 })

  let settled = 0

  for (const b of billings) {
    if (b.is_free) continue

    // NOTE: GET is legacy; daily profit should be posted via POST
    const dailyProfit = 0
    if (dailyProfit === 0) continue
    const result = await settleUser(admin, b.user_id, dailyProfit, dateStr)
    if (result.ok) settled++
  }

  return NextResponse.json({ message: `Settled ${settled} users`, date: dateStr, settled })
}

export async function POST(req: NextRequest) {
  const { api_key, email, date, net_profit } = await req.json()
  if (api_key !== process.env.LAPLACE_API_KEY) {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })
  }
  if (!email) return NextResponse.json({ error: 'Missing email' }, { status: 400 })
  if (typeof net_profit !== 'number') {
    return NextResponse.json({ error: 'Missing net_profit' }, { status: 400 })
  }

  const admin = createAdminClient()
  const { data: profile } = await admin.from('profiles').select('id').eq('email', email).single()
  if (!profile) return NextResponse.json({ error: 'User not found' }, { status: 404 })

  const dateStr = date || getJstDateString()
  const result = await settleUser(admin, profile.id, net_profit, dateStr)
  if (!result.ok) {
    return NextResponse.json({ error: result.error }, { status: 409 })
  }

  return NextResponse.json({
    ok: true,
    date: dateStr,
    fee_amount: result.feeAmount,
    balance: result.newBalance,
    suspended: result.suspended,
  })
}
