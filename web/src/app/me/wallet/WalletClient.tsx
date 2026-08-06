'use client'

// app/me/wallet/WalletClient.tsx — ウォレット登録フォーム + 登録後ステータス表示。
// バリデーションはリアルタイム(TRON: T+33文字 Base58 / BSC: 0x+40hex)。
// 登録は /api/wallet POST。登録済みなら突合ステータス+直近の照合を表示する。

import { useState } from 'react'
import { useTranslations } from 'next-intl'
import WalletStatus from '@/components/dashboard/WalletStatus'

type Network = 'tron' | 'bsc'

export type RegisteredWallet = {
  network: Network
  address: string
  status: 'pending' | 'verified'
  recon_status: 'checking' | 'matched' | 'mismatched'
  last_checked_at?: string | null
}

export type TransferRow = {
  tx_hash: string
  direction: 'in' | 'out'
  counterparty: string
  amount_usdt: number
  occurred_at: string
  classified: 'stake_deposit' | 'stake_withdrawal' | 'other'
}

const PATTERNS: Record<Network, RegExp> = {
  tron: /^T[1-9A-HJ-NP-Za-km-z]{33}$/,
  bsc: /^0x[a-fA-F0-9]{40}$/,
}

function fmtDate(iso: string) {
  try {
    return new Date(iso).toLocaleDateString('ja-JP', { month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit' })
  } catch { return iso }
}

export default function WalletClient({
  initialWallet,
  initialTransfers,
}: {
  initialWallet: RegisteredWallet | null
  initialTransfers: TransferRow[]
}) {
  const t = useTranslations('walletPage')
  const [network, setNetwork] = useState<Network>('tron')
  const [address, setAddress] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [apiError, setApiError] = useState('')
  const [wallet, setWallet] = useState<RegisteredWallet | null>(initialWallet)

  const trimmed = address.trim()
  const valid = trimmed.length > 0 && PATTERNS[network].test(trimmed)
  const showError = trimmed.length >= 10 && !valid

  async function handleSubmit() {
    if (!valid || submitting) return
    setSubmitting(true)
    setApiError('')
    try {
      const res = await fetch('/api/wallet', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ network, address: trimmed }),
      })
      const data = await res.json()
      if (!res.ok) {
        setApiError(String(data.error || 'registration failed'))
        return
      }
      setWallet(data.wallet as RegisteredWallet)
    } catch {
      setApiError('network error')
    } finally {
      setSubmitting(false)
    }
  }

  if (wallet) {
    const reconStatus = wallet.status === 'pending' && wallet.recon_status === 'checking'
      ? 'checking'
      : wallet.recon_status
    return (
      <div className="flex flex-col gap-4">
        <WalletStatus
          status={reconStatus}
          address={wallet.address}
          network={wallet.network}
          lastCheckedAt={wallet.last_checked_at || undefined}
        />
        <div className="bg-surface border border-white/[0.07] rounded-2xl p-6 flex flex-col gap-2">
          <div className="text-[13px] text-text-dim">
            {t('registeredAddr')} · {wallet.network === 'tron' ? 'TRON' : 'BNB Chain'}
          </div>
          <div className="font-mono tabular-nums text-[15px] break-all leading-relaxed">{wallet.address}</div>
        </div>
        <div className="bg-surface border border-white/[0.07] rounded-2xl overflow-hidden">
          <div className="px-6 py-4 text-[15px] font-semibold border-b border-white/[0.06]">{t('recentTitle')}</div>
          {initialTransfers.length ? (
            initialTransfers.map(tr => (
              <div key={`${tr.tx_hash}-${tr.direction}`} className="px-6 py-4 flex justify-between items-center border-b border-white/[0.04] last:border-b-0">
                <div>
                  <div className="text-[15px]">
                    {tr.classified === 'stake_deposit' ? 'Stake へ入金'
                      : tr.classified === 'stake_withdrawal' ? 'Stake から出金'
                      : tr.direction === 'in' ? '受取' : '送金'}
                  </div>
                  <div className="text-[13px] text-text-dim mt-0.5">{fmtDate(tr.occurred_at)}</div>
                </div>
                <span className="font-mono tabular-nums text-[15px] text-win">
                  ${Number(tr.amount_usdt).toLocaleString('en-US', { maximumFractionDigits: 2 })}
                </span>
              </div>
            ))
          ) : (
            <div className="px-6 py-5 text-sm text-text-muted leading-relaxed">{t('recentEmpty')}</div>
          )}
        </div>
        {wallet.status === 'pending' && (
          <p className="text-sm text-text-dim leading-relaxed m-0">{t('pendingNote')}</p>
        )}
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

      {apiError && (
        <div className="bg-lose/[0.06] border border-lose/[0.22] rounded-xl px-5 py-4 text-sm text-lose">{apiError}</div>
      )}

      <div className="flex gap-4 items-center flex-wrap">
        <button
          type="button"
          onClick={handleSubmit}
          disabled={!valid || submitting}
          className="bg-cyan text-[#001721] font-bold text-base rounded-xl px-7 py-4 hover:brightness-110 transition disabled:opacity-40 disabled:cursor-not-allowed"
        >
          {submitting ? '…' : t('submit')}
        </button>
        <a href="/me" className="text-[15px] text-text-muted hover:text-text transition">{t('later')}</a>
      </div>
    </div>
  )
}
