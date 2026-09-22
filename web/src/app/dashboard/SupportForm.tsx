'use client'

// お問い合わせフォーム — 2026-09-23 作り直し (オーナー「問い合わせページらしくわかりやすく」)
// 種類を選ぶ → 大きな入力欄 (書いてほしいことの例つき) → 送信後ははっきり「受け付けました」。
// 種類は support_tickets の本文の先頭に [種類] として入れる (テーブルは変えない)。

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { useTranslations } from 'next-intl'

const CATS = ['usage', 'bug', 'billing', 'account', 'other'] as const

export default function SupportForm() {
  const t = useTranslations('dashboard.support')
  const router = useRouter()
  const [cat, setCat] = useState<(typeof CATS)[number]>('usage')
  const [message, setMessage] = useState('')
  const [loading, setLoading] = useState(false)
  const [sent, setSent] = useState(false)
  const [error, setError] = useState('')

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!message.trim()) return
    setLoading(true)
    setError('')
    const res = await fetch('/api/tickets', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: `[${t(`categories.${cat}`)}] ${message.trim()}` }),
    })
    setLoading(false)
    if (res.ok) {
      setMessage('')
      setSent(true)
      router.refresh()   // 下の「これまでのお問い合わせ」に今の分を出す
    } else {
      setError('送信できませんでした。時間をおいてもう一度お試しください。')
    }
  }

  if (sent) {
    return (
      <div className="bg-surface border border-win/40 rounded-2xl p-6">
        <div className="text-[20px] font-bold text-win">✓ {t('sentTitle')}</div>
        <p className="text-[15px] text-text-muted mt-2 leading-relaxed">{t('sentBody')}</p>
        <button type="button" onClick={() => setSent(false)} className="mt-4 text-[15px] text-cyan hover:underline">
          {t('newAnother')} →
        </button>
      </div>
    )
  }

  return (
    <form onSubmit={handleSubmit} className="bg-surface border border-white/[0.07] rounded-2xl p-5 sm:p-6 flex flex-col gap-5">
      <div>
        <div className="text-[15px] font-semibold mb-2">{t('category')}</div>
        <div className="flex flex-wrap gap-2">
          {CATS.map(c => (
            <button
              key={c}
              type="button"
              onClick={() => setCat(c)}
              className={[
                'px-4 py-2 rounded-xl border text-[14px] transition',
                cat === c ? 'border-cyan bg-cyan/15 text-cyan font-semibold' : 'border-white/[0.12] text-text-muted hover:text-text',
              ].join(' ')}
            >
              {t(`categories.${c}`)}
            </button>
          ))}
        </div>
      </div>

      <div>
        <label htmlFor="support-message" className="text-[15px] font-semibold block mb-2">{t('messageLabel')}</label>
        <textarea
          id="support-message"
          value={message}
          onChange={e => setMessage(e.target.value)}
          rows={7}
          required
          placeholder={t('placeholder')}
          className="w-full rounded-xl bg-surface-3 border border-white/[0.12] px-4 py-3 text-[15px] leading-relaxed text-text placeholder:text-text-dim focus:outline-none focus:border-cyan"
        />
        <div className="mt-3 rounded-xl bg-surface-2 border border-white/[0.07] px-4 py-3">
          <div className="text-[14px] text-text-muted font-semibold">{t('hintTitle')}</div>
          <ul className="mt-1 text-[14px] text-text-muted list-disc pl-5 leading-relaxed">
            {(t.raw('hints') as string[]).map((h, i) => <li key={i}>{h}</li>)}
          </ul>
        </div>
      </div>

      {error && <div className="text-[14px] text-lose">{error}</div>}

      <button
        type="submit"
        disabled={loading || !message.trim()}
        className="self-start bg-cyan text-[#001721] font-bold text-[16px] rounded-xl px-8 py-3.5 hover:brightness-110 transition disabled:opacity-50"
      >
        {loading ? t('sending') : t('send')}
      </button>
    </form>
  )
}
