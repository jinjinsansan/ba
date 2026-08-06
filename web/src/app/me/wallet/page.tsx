// app/me/wallet/page.tsx — ウォレット登録(リデザイン 2026-08 新規ページ)
// 入出金を1アドレスに限定し、オンチェーンとベット成績を突合するための登録画面。
// 現段階は UI のみ(ハンドオフ方針: モックデータ + TODO)。永続化・チェーン監視は後工程。

import { getTranslations } from 'next-intl/server'
import { createClient } from '@/lib/supabase-server'
import WalletClient from './WalletClient'

export default async function WalletPage() {
  const supabase = await createClient()
  const { data: { user } } = await supabase.auth.getUser()
  if (!user) return null

  const t = await getTranslations('walletPage')

  return (
    <div className="max-w-[720px]">
      <div className="mb-7">
        <div className="font-mono text-[10px] text-text-dim tracking-[0.15em] uppercase">{t('kicker')}</div>
        <h1 className="text-[26px] sm:text-[30px] font-bold tracking-tight mt-1">{t('title')}</h1>
        {/* 「なぜ必要か」は入力欄の上(登録前に読ませる — 説明書3.5) */}
        <p className="text-base leading-[1.9] text-text-muted mt-2.5 m-0">{t('intro')}</p>
      </div>
      <WalletClient />
    </div>
  )
}
