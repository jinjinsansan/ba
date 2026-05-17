import { createClient } from '@/lib/supabase-server'

export default async function DownloadPage() {
  const supabase = await createClient()
  const { data: { user } } = await supabase.auth.getUser()
  if (!user) return null

  const [{ data: deliverables }, { data: latestOrder }] = await Promise.all([
    supabase.from('deliverables').select('*').eq('user_id', user.id).order('created_at', { ascending: false }),
    supabase.from('orders').select('*').eq('user_id', user.id).order('created_at', { ascending: false }).limit(1).maybeSingle(),
  ])

  const hasPackage = latestOrder?.status === 'delivered' || latestOrder?.status === 'confirmed'
  const latest = deliverables?.[0]
  const latestDate = latest?.created_at ? new Date(latest.created_at).toISOString().split('T')[0] : ''

  return (
    <div className="space-y-6">
      <div>
        <div className="hud-label mb-2">Download</div>
        <h1 className="text-2xl sm:text-3xl font-hud">ソフトウェア ダウンロード</h1>
      </div>

      <div className="p-6 rounded-2xl glass-card">
        {latest ? (
          <div className="space-y-4">
            <div>
              <div className="text-xs text-text-muted mb-1">最新バージョン</div>
              <div className="text-3xl font-black text-text">v{latest.version}</div>
              {latestDate && <div className="text-xs text-text-muted mt-1">Updated: {latestDate}</div>}
            </div>
            <a
              href={`/api/download?file=${latest.file_path}`}
              className="btn-primary inline-block px-8 py-3 w-full sm:w-auto text-center text-sm"
            >
              BAFATHER v{latest.version} をダウンロード
            </a>
            {latest.file_path && (
              <div className="text-[11px] text-text-dim break-all">Direct URL: {latest.file_path}</div>
            )}
          </div>
        ) : hasPackage ? (
          <p className="text-text-muted">配布物を準備中です。準備でき次第このページに表示されます。</p>
        ) : (
          <p className="text-text-muted">ライセンスを購入するとここにダウンロードボタンが表示されます。</p>
        )}
      </div>

      {/* Version history */}
      {deliverables && deliverables.length > 1 && (
        <div className="p-5 rounded-2xl glass-card">
          <h2 className="text-lg font-bold mb-4">バージョン履歴</h2>
          <div className="space-y-2">
            {deliverables.slice(1).map(d => (
              <div key={d.id} className="flex items-center justify-between text-sm border-t border-accent/10 pt-2">
                <div>
                  <span className="text-text font-semibold">v{d.version}</span>
                  <span className="text-text-dim text-xs ml-2">{d.created_at ? new Date(d.created_at).toISOString().split('T')[0] : ''}</span>
                </div>
                <a href={`/api/download?file=${d.file_path}`} className="text-xs text-accent hover:underline">ダウンロード</a>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
