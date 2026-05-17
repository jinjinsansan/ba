'use client'

import { usePathname } from 'next/navigation'
import { LanguageSwitcher } from './LanguageSwitcher'

/**
 * 画面右上に固定表示する言語切替。
 * - /admin 配下では非表示 (admin は日本語固定方針)
 * - /me 配下では非表示 (AppShell の右上ハンバーガーと被るため、メンバー画面は
 *   日本語固定運用)
 * - ランディング (= サインインフォーム /) も非表示 (LoginForm に重ねない)
 */
export function FloatingLanguageSwitcher() {
  const pathname = usePathname()

  const hidden =
    pathname === '/' ||
    pathname.startsWith('/admin') ||
    pathname.startsWith('/me')

  if (hidden) return null

  return (
    <div className="fixed top-4 right-4 z-[100]">
      <LanguageSwitcher />
    </div>
  )
}
