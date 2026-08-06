// app/me/wallet/page.tsx — ウォレット登録(2026-08 新料金モデル / 突合 案A)
// サーバー側で登録済みウォレット+照合履歴を取得し、未登録ならフォームを出す。
// 登録は /api/wallet POST(1ユーザー1アドレス・変更はサポート経由)。

import { getTranslations } from 'next-intl/server'
import { createClient } from '@/lib/supabase-server'
import WalletClient, { type RegisteredWallet, type TransferRow } from './WalletClient'

export default async function WalletPage() {
  const supabase = await createClient()
  const { data: { user } } = await supabase.auth.getUser()
  if (!user) return null

  const t = await getTranslations('walletPage')

  const { data: wallet } = await supabase.from('wallets')
    .select('network, address, status, recon_status, last_checked_at')
    .eq('user_id', user.id)
    .maybeSingle()

  let transfers: TransferRow[] = []
  if (wallet) {
    const { data } = await supabase.from('chain_transfers')
      .select('tx_hash, direction, counterparty, amount_usdt, occurred_at, classified')
      .eq('user_id', user.id)
      .order('occurred_at', { ascending: false })
      .limit(10)
    transfers = (data as TransferRow[]) || []
  }

  return (
    <div className="max-w-[720px]">
      <div className="mb-7">
        <div className="font-mono text-[10px] text-text-dim tracking-[0.15em] uppercase">{t('kicker')}</div>
        <h1 className="text-[26px] sm:text-[30px] font-bold tracking-tight mt-1">{t('title')}</h1>
        {/* 「なぜ必要か」は入力欄の上(登録前に読ませる — 説明書3.5) */}
        <p className="text-base leading-[1.9] text-text-muted mt-2.5 m-0">{t('intro')}</p>
      </div>
      <WalletClient initialWallet={(wallet as RegisteredWallet) || null} initialTransfers={transfers} />
    </div>
  )
}
