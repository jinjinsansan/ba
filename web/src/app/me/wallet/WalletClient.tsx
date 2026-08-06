'use client'

// app/me/wallet/WalletClient.tsx — ウォレット登録フォーム + 登録後ステータス表示。
// バリデーションはリアルタイム(TRON: T+33文字 Base58 / BSC: 0x+40hex)。
// TODO: wire real data — 送信先 API・wallets テーブル・チェーン監視は未実装。
// 現状は送信するとローカル状態で「登録済み(確認中)」表示に切り替わるのみ。

import { useState } from 'react'
import { useTranslations } from 'next-intl'
import WalletStatus from '@/components/dashboard/WalletStatus'

type Network = 'tron' | 'bsc'

const PATTERNS: Record<Network, RegExp> = {
  tron: /^T[1-9A-HJ-NP-Za-km-z]{33}$/,
  bsc: /^0x[a-fA-F0-9]{40}$/,
}

export default function WalletClient() {
  const t = useTranslations('walletPage')
  const [network, setNetwork] = useState<Network>('tron')
  const [address, setAddress] = useState('')
  const [registered, setRegistered] = useState<{ network: Network; address: string } | null>(null)

  const trimmed = address.trim()
  const valid = trimmed.length > 0 && PATTERNS[network].test(trimmed)
  const showError = trimmed.length >= 10 && !valid

  function handleSubmit() {
    if (!valid) return
    // TODO: wire real data — ここで登録 API を呼ぶ。現状はローカル状態のみ。
    setRegistered({ network, address: trimmed })
  }

  if (registered) {
    return (
      <div className="flex flex-col gap-4">
        <WalletStatus
          status="checking"
          address={registered.address}
          network={registered.network}
        />
        <div className="bg-surface border border-white/[0.07] rounded-2xl p-6 flex flex-col gap-2">
          <div className="text-[13px] text-text-dim">
            {t('registeredAddr')} · {registered.network === 'tron' ? 'TRON' : 'BNB Chain'}
          </div>
          <div className="font-mono tabular-nums text-[15px] break-all leading-relaxed">{registered.address}</div>
        </div>
        <div className="bg-surface border border-white/[0.07] rounded-2xl overflow-hidden">
          <div className="px-6 py-4 text-[15px] font-semibold border-b border-white/[0.06]">{t('recentTitle')}</div>
          <div className="px-6 py-5 text-sm text-text-muted leading-relaxed">{t('recentEmpty')}</div>
        </div>
        <p className="text-sm text-text-dim leading-relaxed m-0">{t('pendingNote')}</p>
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-6">
      {/* Network — ラジオカード2枚 */}
      <div className="flex flex-col gap-2.5">
        <div className="text-[15px] font-semibold">{t('network')}</div>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          {(['tron', 'bsc'] as const).map(n => {
            const active = network === n
            return (
              <button
                key={n}
                type="button"
                onClick={() => setNetwork(n)}
                aria-pressed={active}
                className={[
                  'text-left rounded-xl px-5 py-4 flex items-center gap-3 transition min-h-[44px]',
                  active
                    ? 'bg-cyan/[0.07] border border-cyan/[0.35]'
                    : 'bg-white/[0.02] border border-white/[0.09] hover:border-white/[0.2]',
                ].join(' ')}
              >
                <span
                  aria-hidden
                  className={[
                    'w-[18px] h-[18px] rounded-full flex-none',
                    active ? 'border-[5px] border-cyan' : 'border-[1.5px] border-white/[0.22]',
                  ].join(' ')}
                />
                <span>
                  <span className="block text-base font-semibold">{t(n)}</span>
                  <span className="block text-[13px] text-text-muted mt-0.5">{t(`${n}Sub`)}</span>
                </span>
              </button>
            )
          })}
        </div>
      </div>

      {/* Address */}
      <div className="flex flex-col gap-2.5">
        <label htmlFor="wallet-address" className="text-[15px] font-semibold">{t('addressLabel')}</label>
        <input
          id="wallet-address"
          type="text"
          value={address}
          onChange={e => setAddress(e.target.value)}
          placeholder={t(network === 'tron' ? 'addressPlaceholderTron' : 'addressPlaceholderBsc')}
          spellCheck={false}
          autoComplete="off"
          className={[
            'w-full bg-white/[0.02] rounded-xl px-5 py-4 font-mono text-base outline-none transition border',
            valid ? 'border-cyan/40' : showError ? 'border-lose/40' : 'border-white/[0.09] focus:border-white/[0.25]',
          ].join(' ')}
        />
        {valid && (
          <div className="flex items-center gap-2 text-sm text-win">
            ✓ {t(network === 'tron' ? 'validTron' : 'validBsc')}
          </div>
        )}
        {showError && (
          <div className="flex items-center gap-2 text-sm text-lose">{t('invalid')}</div>
        )}
      </div>

      {/* 警告は入力欄の下(説明書3.5) */}
      <div className="bg-warn/[0.05] border border-warn/[0.2] rounded-xl px-5 py-4 text-sm leading-[1.85] text-text-muted">
        <strong className="text-warn">{t('warnStrong')}</strong>
        {t('warnBody')}
      </div>

      <div className="flex gap-4 items-center flex-wrap">
        <button
          type="button"
          onClick={handleSubmit}
          disabled={!valid}
          className="bg-cyan text-[#001721] font-bold text-base rounded-xl px-7 py-4 hover:brightness-110 transition disabled:opacity-40 disabled:cursor-not-allowed"
        >
          {t('submit')}
        </button>
        <a href="/me" className="text-[15px] text-text-muted hover:text-text transition">{t('later')}</a>
      </div>
    </div>
  )
}
