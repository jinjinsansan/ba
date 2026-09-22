'use client'

import { useEffect } from 'react'
import { useRouter } from 'next/navigation'

// サーバーコンポーネントのページを一定間隔で取り直す (稼働状況の一覧など)。
export function AutoRefresh({ seconds = 30 }: { seconds?: number }) {
  const router = useRouter()
  useEffect(() => {
    const t = setInterval(() => router.refresh(), Math.max(10, seconds) * 1000)
    return () => clearInterval(t)
  }, [router, seconds])
  return null
}
