import { createAdminClient } from '@/lib/supabase-admin'
import { NextRequest, NextResponse } from 'next/server'

// チェーン監視 (2026-08-06 新料金モデル / 突合 案A Phase 1)。
// 登録ウォレットの USDT 転送を観測して chain_transfers に蓄積し、
// wallets.status(pending→verified)と recon_status を更新する。
//
// 実行方法: Vercel cron ではなく VPS の cron から叩く(Vercel cron 枠温存)。
// 認証は CRON_SECRET(Bearer)または PAYMENTS_WEBHOOK_SECRET(x-payments-secret)の
// どちらでも通る — VPS 決済ポーラーが既に後者を持っているため、秘密の追加配布が不要:
//   */10 * * * * curl -s -H "x-payments-secret: $PAYMENTS_WEBHOOK_SECRET" https://www.bafather.uk/api/cron/wallet-watch
//
// Phase 1 の突合ルール(単純化・TODO 参照):
//   転送の観測なし → recon_status='checking' / 観測あり → 'matched'
//   TODO: wire real data — Phase 2 でベットPnL(weekly_pnl)と
//   「残高差分 + 出金 − 入金」を比較し、乖離時に 'mismatched' へ遷移させる。
//
// 対応チェーン: TRON(TronGrid・キー無しでも動くが TRONGRID_API_KEY 推奨)。
// BSC は TODO(BSCSCAN_API_KEY + Etherscan V2 API で追加予定)— 現状 checking のまま。

const USDT_TRC20 = 'TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t'

// Stake のホットウォレット(カンマ区切り env)。一致した相手先を stake_deposit /
// stake_withdrawal に分類する。未設定でも動く(全部 other になるだけ)。
function stakeAddresses(): Set<string> {
  return new Set(
    (process.env.STAKE_TRON_ADDRESSES || '')
      .split(',')
      .map(a => a.trim())
      .filter(Boolean),
  )
}

type TronTransfer = {
  transaction_id: string
  from: string
  to: string
  value: string
  block_timestamp: number
  token_info?: { symbol?: string; decimals?: number }
}

async function fetchTronTransfers(address: string): Promise<TronTransfer[]> {
  const url = `https://api.trongrid.io/v1/accounts/${address}/transactions/trc20`
    + `?limit=50&contract_address=${USDT_TRC20}`
  const headers: Record<string, string> = { Accept: 'application/json' }
  if (process.env.TRONGRID_API_KEY) headers['TRON-PRO-API-KEY'] = process.env.TRONGRID_API_KEY
  const res = await fetch(url, { headers, cache: 'no-store' })
  if (!res.ok) throw new Error(`trongrid ${res.status}`)
  const json = await res.json() as { data?: TronTransfer[] }
  return json.data || []
}

export async function GET(req: NextRequest) {
  const authHeader = req.headers.get('authorization')
  const paySecret = req.headers.get('x-payments-secret') || ''
  const cronOk = !!process.env.CRON_SECRET && authHeader === `Bearer ${process.env.CRON_SECRET}`
  const payOk = !!process.env.PAYMENTS_WEBHOOK_SECRET && paySecret === process.env.PAYMENTS_WEBHOOK_SECRET
  if (!cronOk && !payOk) {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })
  }

  const admin = createAdminClient()
  const { data: wallets, error } = await admin
    .from('wallets')
    .select('id, user_id, network, address, status, recon_status')
  if (error) return NextResponse.json({ error: error.message }, { status: 500 })

  const stake = stakeAddresses()
  const results: Array<{ address: string; network: string; fetched?: number; inserted?: number; skipped?: string; error?: string }> = []

  for (const w of wallets || []) {
    if (w.network !== 'tron') {
      // TODO: wire real data — BSC 監視は未実装(BSCSCAN_API_KEY + Etherscan V2)
      results.push({ address: w.address, network: w.network, skipped: 'bsc not implemented yet' })
      continue
    }
    try {
      const transfers = await fetchTronTransfers(w.address)
      const rows = transfers
        .filter(t => (t.token_info?.symbol || 'USDT') === 'USDT')
        .map(t => {
          const isIn = t.to === w.address
          const counterparty = isIn ? t.from : t.to
          const decimals = t.token_info?.decimals ?? 6
          const amount = Number(t.value) / 10 ** decimals
          const classified = stake.has(counterparty)
            ? (isIn ? 'stake_withdrawal' : 'stake_deposit')
            : 'other'
          return {
            user_id: w.user_id,
            wallet_id: w.id,
            network: 'tron',
            tx_hash: t.transaction_id,
            direction: isIn ? 'in' : 'out',
            counterparty,
            amount_usdt: amount,
            occurred_at: new Date(t.block_timestamp).toISOString(),
            classified,
          }
        })
        .filter(r => Number.isFinite(r.amount_usdt) && r.amount_usdt > 0)

      let inserted = 0
      if (rows.length) {
        const { error: insErr, count } = await admin
          .from('chain_transfers')
          .upsert(rows, { onConflict: 'network,tx_hash,direction,counterparty', ignoreDuplicates: true, count: 'exact' })
        if (insErr) throw new Error(insErr.message)
        inserted = count || 0
      }

      // 観測に応じてステータス更新(Phase 1: 観測あり=verified+matched)
      const { count: totalCount } = await admin
        .from('chain_transfers')
        .select('id', { count: 'exact', head: true })
        .eq('wallet_id', w.id)
      const hasAny = (totalCount || 0) > 0
      await admin.from('wallets').update({
        status: hasAny ? 'verified' : w.status,
        recon_status: w.recon_status === 'mismatched' ? 'mismatched' : hasAny ? 'matched' : 'checking',
        last_checked_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      }).eq('id', w.id)

      results.push({ address: w.address, network: 'tron', fetched: transfers.length, inserted })
    } catch (e) {
      results.push({ address: w.address, network: w.network, error: e instanceof Error ? e.message : String(e) })
    }
  }

  return NextResponse.json({ ok: true, wallets: (wallets || []).length, results })
}
