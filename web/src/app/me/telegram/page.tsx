import { createClient } from '@/lib/supabase-server'
import { createAdminClient } from '@/lib/supabase-admin'
import { buildCustomerTelegramStartLink } from '@/lib/customer-telegram'
import { revalidatePath } from 'next/cache'

export default async function TelegramPage() {
  const supabase = await createClient()
  const { data: { user } } = await supabase.auth.getUser()
  if (!user) return null

  const { data: billing } = await supabase
    .from('billing')
    .select('bot_config')
    .eq('user_id', user.id)
    .single()

  const botConfig = (billing?.bot_config && typeof billing.bot_config === 'object')
    ? (billing.bot_config as Record<string, unknown>)
    : {}
  const telegramLinked = !!botConfig.customer_telegram_chat_id
  const telegramUsername = String(botConfig.customer_telegram_username || '').trim()
  const telegramLinkedAtRaw = String(botConfig.customer_telegram_linked_at || '').trim()
  const telegramLinkedAt = telegramLinkedAtRaw ? new Date(telegramLinkedAtRaw).toLocaleString('ja-JP') : ''
  const telegramLink = buildCustomerTelegramStartLink(user.id)

  async function unlinkTelegramAction() {
    'use server'
    const actionSupabase = await createClient()
    const { data: { user: actionUser } } = await actionSupabase.auth.getUser()
    if (!actionUser) return
    const actionAdmin = createAdminClient()
    const { data: row } = await actionAdmin
      .from('billing')
      .select('bot_config')
      .eq('user_id', actionUser.id)
      .maybeSingle()
    const currentConfig = row?.bot_config && typeof row.bot_config === 'object'
      ? ({ ...(row.bot_config as Record<string, unknown>) })
      : {}
    delete currentConfig.customer_telegram_chat_id
    delete currentConfig.customer_telegram_username
    delete currentConfig.customer_telegram_linked_at
    currentConfig.customer_telegram_enabled = false
    await actionAdmin.from('billing').upsert({
      user_id: actionUser.id,
      bot_config: currentConfig,
      updated_at: new Date().toISOString(),
    }, { onConflict: 'user_id' })
    revalidatePath('/me/telegram')
  }

  return (
    <div className="space-y-6">
      <div>
        <div className="hud-label mb-2">Telegram</div>
        <h1 className="text-2xl sm:text-3xl font-hud">Telegram 通知連携</h1>
        <p className="text-text-muted text-sm mt-2 break-all">紐付け先アカウント: {user.email}</p>
      </div>

      <div className="p-6 rounded-2xl glass-card">
        <h2 className="text-lg font-bold mb-3">受信できる通知</h2>
        <ul className="text-sm text-text-muted space-y-2 list-disc list-inside mb-6">
          <li>日次精算の通知 (損益・手数料・未払い・残高)</li>
          <li>未払い → 入金反映の通知</li>
          <li>セッション開始/停止の通知</li>
        </ul>

        {telegramLinked ? (
          <div className="space-y-3">
            <div className="text-sm text-green-400 font-semibold">✓ 連携済み</div>
            <div className="text-xs text-text-muted">
              {telegramUsername ? `連携先: @${telegramUsername}` : '連携先: Telegram アカウント'}
              {telegramLinkedAt && <span className="block">連携日時: {telegramLinkedAt}</span>}
            </div>
            <div className="flex flex-col sm:flex-row gap-2 pt-2">
              {telegramLink && (
                <a href={telegramLink} target="_blank" rel="noreferrer" className="btn-primary inline-block px-5 py-2.5 text-center text-sm">
                  Telegram を開く
                </a>
              )}
              <form action={unlinkTelegramAction}>
                <button type="submit" className="btn-outline px-5 py-2.5 w-full sm:w-auto text-sm">
                  連携を解除
                </button>
              </form>
            </div>
            <p className="text-xs text-text-dim">再連携は「Telegram を開く」→ /start で完了します。</p>
          </div>
        ) : telegramLink ? (
          <div className="space-y-3">
            <a href={telegramLink} target="_blank" rel="noreferrer" className="btn-primary inline-block px-6 py-3 text-sm">
              1 タップで連携する
            </a>
            <p className="text-xs text-text-muted">Telegram で /start が実行されると、このアカウントに紐づいて連携完了です。</p>
          </div>
        ) : (
          <div className="text-sm text-yellow-400">現在は連携リンクを生成できません (環境変数未設定)。</div>
        )}
      </div>
    </div>
  )
}
