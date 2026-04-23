'use client'

import { usePathname } from 'next/navigation'
import { LanguageSwitcher } from './LanguageSwitcher'

/**
 * 画面右上に固定表示する言語切替。
 * - /admin 配下では非表示 (admin は日本語固定方針)
 * - ランディング (/) ではヘッダー nav 内にも LanguageSwitcher を出しているが、
 *   重複を避けるため / では非表示にする
 */
export function FloatingLanguageSwitcher() {
  const pathname = usePathname()

  const hidden =
    pathname === '/' ||
    pathname.startsWith('/admin')

  if (hidden) return null

  return (
    <div className="fixed top-4 right-4 z-[100]">
      <LanguageSwitcher />
    </div>
  )
}
