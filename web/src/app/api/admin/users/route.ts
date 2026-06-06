import { createAdminClient } from '@/lib/supabase-admin'
import { createClient as createServerSupabase } from '@/lib/supabase-server'
import { NextRequest, NextResponse } from 'next/server'

export async function POST(req: NextRequest) {
  const serverSupabase = await createServerSupabase()
  const { data: { user } } = await serverSupabase.auth.getUser()
  if (!user) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })

  const { data: profile } = await serverSupabase.from('profiles').select('is_admin').eq('id', user.id).single()
  if (!profile?.is_admin) return NextResponse.json({ error: 'Forbidden' }, { status: 403 })

  const { userId, action, value } = await req.json()
  if (!userId) return NextResponse.json({ error: 'Missing userId' }, { status: 400 })
  const admin = createAdminClient()

  // すべての billing upsert で error を必ず確認する。従来は free_charge 等が upsert の
  // 結果を無視して ok:true を返し、DB 書き込みが失敗(特に billing 行が無い新規ユーザの
  // INSERT)しても管理者には成功に見え「無料にならない／何も変わらない」というサイレント
  // 失敗になっていた。失敗時は実エラーを 500 で返す。
  async function setBilling(patch: Record<string, unknown>) {
    return admin.from('billing').upsert(
      { user_id: userId, updated_at: new Date().toISOString(), ...patch },
      { onConflict: 'user_id' },
    )
  }
  function fail(error: { message?: string } | null) {
    return NextResponse.json({ error: error?.message || 'billing upsert failed' }, { status: 500 })
  }

  switch (action) {
    case 'suspend': {
      const { error } = await setBilling({ suspended: true })
      if (error) return fail(error)
      break
    }
    case 'unsuspend': {
      const { error } = await setBilling({ suspended: false })
      if (error) return fail(error)
      break
    }
    case 'set_rate': {
      const { error } = await setBilling({ profit_share_rate: value })
      if (error) return fail(error)
      break
    }
    case 'free_license': {
      const { error } = await setBilling({ bot_paid: true, suspended: false })
      if (error) return fail(error)
      break
    }
    case 'free_charge': {
      const { error } = await setBilling({ is_free: true, balance: 99999, suspended: false })
      if (error) return fail(error)
      break
    }
    case 'free_both': {
      const { error } = await setBilling({ bot_paid: true, is_free: true, balance: 99999, suspended: false })
      if (error) return fail(error)
      break
    }
    case 'unfree_charge': {
      const { data: billing } = await admin.from('billing').select('balance').eq('user_id', userId).maybeSingle()
      const resetBalance = (billing?.balance || 0) >= 99999
      const { error } = await setBilling({ is_free: false, balance: resetBalance ? 0 : (billing?.balance || 0) })
      if (error) return fail(error)
      break
    }
    case 'activate': {
      const { error } = await setBilling({ suspended: false })
      if (error) return fail(error)
      break
    }
    case 'deactivate': {
      const { error } = await setBilling({ suspended: true })
      if (error) return fail(error)
      break
    }
    case 'set_bot_config': {
      const { error } = await setBilling({ bot_config: value })
      if (error) return fail(error)
      break
    }
    default:
      return NextResponse.json({ error: 'Unknown action' }, { status: 400 })
  }

  return NextResponse.json({ ok: true })
}
