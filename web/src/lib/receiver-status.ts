// 受け子の生存報告 (receiver_status) の読み方をまとめる — 2026-09-22
// 受け子 GUI は 1 分ごとに報告するので、2.5 分来なければ「オフライン」とみなす。

export const RECEIVER_ONLINE_SEC = 150

export type ReceiverStatus = {
  user_id: string
  product: 'bacopy' | 'kbjapan' | 'kbkorea'
  executor_id: string
  email: string | null
  last_seen_at: string
  engine_running: boolean
  app_version: string | null
  engine_sha: string | null
  os: string | null
  table_name: string | null
  balance: number | null
  bets_today: number | null
  wins_today: number | null
  losses_today: number | null
  ties_today: number | null
  bet_errors_today: number | null
  last_bet_at: string | null
  payload: Record<string, unknown> | null
}

export function secondsSince(isoStr: string | null | undefined): number | null {
  if (!isoStr) return null
  const t = new Date(isoStr).getTime()
  return Number.isFinite(t) ? Math.max(0, Math.round((Date.now() - t) / 1000)) : null
}

export function isOnline(r: Pick<ReceiverStatus, 'last_seen_at'>): boolean {
  const s = secondsSince(r.last_seen_at)
  return s !== null && s < RECEIVER_ONLINE_SEC
}

/** 'running' = GUI もエンジンも動いている / 'idle' = GUI は開いているがエンジン停止 / 'offline' */
export function receiverState(r: Pick<ReceiverStatus, 'last_seen_at' | 'engine_running'>): 'running' | 'idle' | 'offline' {
  if (!isOnline(r)) return 'offline'
  return r.engine_running ? 'running' : 'idle'
}

export function fmtAgo(sec: number | null): string {
  if (sec === null) return '-'
  if (sec < 60) return `${sec}秒前`
  if (sec < 3600) return `${Math.floor(sec / 60)}分前`
  if (sec < 86400) return `${Math.floor(sec / 3600)}時間前`
  return `${Math.floor(sec / 86400)}日前`
}

export const PRODUCT_LABEL: Record<string, string> = { bacopy: 'BACOPY', kbjapan: 'KBJAPAN', kbkorea: 'KBKOREA' }
export const PRODUCT_TEAM: Record<string, string> = { bacopy: '田辺版', kbjapan: '梶原版', kbkorea: '韓国版' }
export const PRODUCT_CLASS: Record<string, string> = {
  bacopy: 'bg-amber-500/15 text-amber-300',
  kbjapan: 'bg-rose-500/15 text-rose-300',
  kbkorea: 'bg-sky-500/15 text-sky-300',
}
