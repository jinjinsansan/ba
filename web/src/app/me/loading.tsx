// 会員ページの読み込み中 (2026-09-23)。メニューは残したまま、中身の場所に仮の枠を出す。
// サーバーでの準備を待つ間も画面がすぐ切り替わるので、押しても反応しないように見えない。
export default function MeLoading() {
  const box = 'bg-surface border border-white/[0.07] rounded-2xl animate-pulse'
  return (
    <div className="flex flex-col gap-5" aria-busy="true" aria-label="loading">
      <div className="h-8 w-56 rounded-lg bg-surface-2 animate-pulse" />
      <div className={`${box} h-36`} />
      <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
        <div className={`${box} h-40`} />
        <div className={`${box} h-40`} />
      </div>
      <div className={`${box} h-48`} />
    </div>
  )
}
