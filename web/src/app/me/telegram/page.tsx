import { createClient } from '@/lib/supabase-server'
import { createAdminClient } from '@/lib/supabase-admin'
import { buildCustomerTelegramStartLink } from '@/lib/customer-telegram'
import { revalidatePath } from 'next/cache'
import { Card, CardHead } from '@/components/ui/Card'
import { PageHeader } from '@/components/ui/PageHeader'
import { Pill } from '@/components/ui/Pill'
import { Button } from '@/components/ui/Button'

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
    <div>
      <PageHeader
        kicker="Member · Telegram"
        title="Telegram 通知連携"
        sub={`紐付け先アカウント: ${user.email}`}
        right={telegramLinked ? <Pill tone="live" dot>連携済み</Pill> : <Pill tone="info">未連携</Pill>}
      />

      <Card padded={false}>
        <CardHead>受信できる通知</CardHead>
        <div className="px-5 py-5">
          <ul className="space-y-1.5 text-sm text-text-muted list-disc list-inside leading-relaxed mb-6">
            <li>日次精算の通知 (損益・手数料・未払い・残高)</li>
            <li>未払い → 入金反映の通知</li>
            <li>セッション開始/停止の通知</li>
          </ul>

          {telegramLinked ? (
            <div className="space-y-3">
              <div className="text-xs text-text-muted">
                {telegramUsername ? `連携先: @${telegramUsername}` : '連携先: Telegram アカウント'}
                {telegramLinkedAt && <span className="block mt-1">連携日時: {telegramLinkedAt}</span>}
              </div>
              <div className="flex flex-col sm:flex-row gap-2 pt-2">
                {telegramLink && (
                  <a href={telegramLink} target="_blank" rel="noreferrer">
                    <Button tone="primary" size="md">Telegram を開く</Button>
                  </a>
                )}
                <form action={unlinkTelegramAction}>
                  <Button tone="danger" size="md" type="submit">連携を解除</Button>
                </form>
              </div>
              <p className="text-xs text-text-dim">再連携は「Telegram を開く」→ /start で完了します。</p>
            </div>
          ) : telegramLink ? (
            <div className="space-y-3">
              <a href={telegramLink} target="_blank" rel="noreferrer">
                <Button tone="primary" size="lg">1 タップで連携する</Button>
              </a>
              <p className="text-xs text-text-muted">Telegram で /start が実行されると、このアカウントに紐づいて連携完了です。</p>
            </div>
          ) : (
            <div className="text-sm text-warn">現在は連携リンクを生成できません (環境変数未設定)。</div>
          )}
        </div>
      </Card>
    </div>
  )
}
