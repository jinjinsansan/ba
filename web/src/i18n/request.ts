import { getRequestConfig } from 'next-intl/server';
import { cookies, headers } from 'next/headers';

export const SUPPORTED_LOCALES = ['en', 'ja', 'ko', 'zh'] as const;
export type Locale = (typeof SUPPORTED_LOCALES)[number];
// 2026-08-06: 既定を en → ja に変更。旧トップは日本語ハードコードだったため
// 露呈しなかったが、新LPは i18n 経由なので Cookie 未設定の初回訪問が英語になっていた。
// 解決順: NEXT_LOCALE Cookie(ユーザーの明示選択) → Accept-Language → ja。
export const DEFAULT_LOCALE: Locale = 'ja';

function normalize(value: string | undefined): Locale | null {
  return (SUPPORTED_LOCALES as readonly string[]).includes(value ?? '')
    ? (value as Locale)
    : null;
}

function fromAcceptLanguage(header: string | null): Locale | null {
  if (!header) return null;
  // "ja,en-US;q=0.9,en;q=0.8" → q 降順で最初にサポートされる言語を返す
  const langs = header
    .split(',')
    .map(part => {
      const [tag, ...params] = part.trim().split(';');
      const qParam = params.find(p => p.trim().startsWith('q='));
      const q = qParam ? parseFloat(qParam.split('=')[1]) : 1;
      return { tag: tag.trim().toLowerCase(), q: Number.isFinite(q) ? q : 0 };
    })
    .sort((a, b) => b.q - a.q);
  for (const { tag } of langs) {
    const primary = tag.split('-')[0];
    const hit = normalize(primary);
    if (hit) return hit;
  }
  return null;
}

export default getRequestConfig(async () => {
  const c = await cookies();
  const h = await headers();
  const locale =
    normalize(c.get('NEXT_LOCALE')?.value) ??
    fromAcceptLanguage(h.get('accept-language')) ??
    DEFAULT_LOCALE;

  return {
    locale,
    messages: (await import(`../../messages/${locale}.json`)).default,
  };
});
