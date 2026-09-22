// app/me/support/page.tsx — お問い合わせ (2026-09-23 作り直し)
// 何のページかを先に書き、フォームの下に「これまでのお問い合わせ」と管理者の返信を出す。

import { getTranslations } from 'next-intl/server'
import { createClient } from '@/lib/supabase-server'
import SupportForm from '../../dashboard/SupportForm'

export const dynamic = 'force-dynamic'

type Ticket = { id: string; message: string; status: string | null; admin_reply: string | null; created_at: string }

export default async function SupportPage() {
  const t = await getTranslations('dashboard.support')
  const supabase = await createClient()
  const { data: { user } } = await supabase.auth.getUser()
  const { data } = user
    ? await supabase.from('support_tickets').select('id, message, status, admin_reply, created_at')
        .eq('user_id', user.id).order('created_at', { ascending: false }).limit(50)
    : { data: [] }
  const tickets = (data || []) as Ticket[]

  return (
    <div className="flex flex-col gap-5">
      <div>
        <div className="text-[24px] sm:text-[30px] font-bold tracking-tight">{t('pageTitle')}</div>
        <div className="text-[15px] text-text-muted mt-1.5 leading-relaxed max-w-3xl">{t('pageSub')}</div>
      </div>

      <SupportForm />

      <div className="bg-surface border border-white/[0.07] rounded-2xl p-5 sm:p-6">
        <div className="text-[17px] font-semibold mb-3">{t('historyTitle')}</div>
        {tickets.length === 0 ? (
          <div className="text-[15px] text-text-muted">{t('historyNone')}</div>
        ) : (
          <div className="flex flex-col gap-3">
            {tickets.map(tk => {
              const st = tk.status === 'replied' ? 'replied' : tk.status === 'closed' ? 'closed' : 'open'
              const pill = st === 'replied' ? 'text-win border-win/40 bg-win/10'
                : st === 'closed' ? 'text-text-muted border-white/[0.12] bg-white/[0.04]'
                : 'text-warn border-warn/40 bg-warn/10'
              return (
                <div key={tk.id} className="rounded-xl border border-white/[0.08] bg-surface-2 p-4">
                  <div className="flex items-center justify-between gap-2 mb-2">
                    <span className="text-[13px] text-text-dim font-mono">{new Date(tk.created_at).toLocaleString('ja-JP', { timeZone: 'Asia/Tokyo' })}</span>
                    <span className={`px-2.5 py-0.5 rounded-full border text-[12px] font-semibold ${pill}`}>
                      {st === 'replied' ? t('statusReplied') : st === 'closed' ? t('statusClosed') : t('statusOpen')}
                    </span>
                  </div>
                  <div className="text-[15px] whitespace-pre-wrap leading-relaxed">{tk.message}</div>
                  {tk.admin_reply && (
                    <div className="mt-3 rounded-lg border-l-4 border-cyan bg-cyan/[0.06] px-3 py-2">
                      <div className="text-[13px] text-cyan font-semibold">{t('reply')}</div>
                      <div className="text-[15px] whitespace-pre-wrap leading-relaxed mt-0.5">{tk.admin_reply}</div>
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        )}
      </div>
    </div>
  )
}
