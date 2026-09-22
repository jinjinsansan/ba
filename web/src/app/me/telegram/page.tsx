import { redirect } from 'next/navigation'

// ★2026-09-23 オーナー判断でメニューから外した (telegram)。古いリンクで来た人はマイページへ。
//   受け子の状態と今日の成績はマイページ (/me) に出している。
export default function RemovedTelegramPage() {
  redirect('/me')
}
