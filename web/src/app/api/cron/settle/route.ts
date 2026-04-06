import { createAdminClient } from '@/lib/supabase-admin'
import { NextRequest, NextResponse } from 'next/server'

export async function GET(req: NextRequest) {
  const authHeader = req.headers.get('authorization')
  if (authHeader !== `Bearer ${process.env.CRON_SECRET}`) {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })
  }

  const admin = createAdminClient()
  const today = new Date()
  const dateStr = today.toISOString().split('T')[0]

  const { data: billings } = await admin
    .from('billing')
    .select('user_id, balance, profit_share_rate, carry_loss, is_free, suspended')
    .eq('suspended', false)
    .gt('balance', 0)

  if (!billings?.length) return NextResponse.json({ message: 'No active users', settled: 0 })

  let settled = 0

  for (const b of billings) {
    if (b.is_free) continue

    // TODO: Fetch actual daily profit from VPS API for this user
    // For now, skip users without external profit data
    // This is a placeholder - integrate with VPS laplace_api.py
    const dailyProfit = 0

    if (dailyProfit === 0) continue

    const carryLoss = Number(b.carry_loss) || 0
    let netProfit = dailyProfit + carryLoss
    let feeAmount = 0
    let newCarryLoss = 0

    if (netProfit > 0) {
      feeAmount = netProfit * Number(b.profit_share_rate)
      newCarryLoss = 0
    } else {
      feeAmount = 0
      newCarryLoss = netProfit
    }

    const newBalance = Number(b.balance) - feeAmount

    await admin.from('deductions').insert({
      user_id: b.user_id,
      date: dateStr,
      daily_profit: dailyProfit,
      fee_amount: feeAmount,
      carry_loss: newCarryLoss,
      note: netProfit > 0 ? `${(Number(b.profit_share_rate) * 100).toFixed(0)}% of net $${netProfit.toFixed(2)}` : 'Loss carried forward',
    })

    await admin.from('billing').update({
      balance: Math.max(0, newBalance),
      carry_loss: newCarryLoss,
      suspended: newBalance <= 0,
      updated_at: new Date().toISOString(),
    }).eq('user_id', b.user_id)

    settled++
  }

  return NextResponse.json({ message: `Settled ${settled} users`, date: dateStr, settled })
}
