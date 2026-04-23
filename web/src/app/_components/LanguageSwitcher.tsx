'use client';

import { useLocale, useTranslations } from 'next-intl';
import { useRouter } from 'next/navigation';
import { useTransition } from 'react';

const LOCALES = ['en', 'ja', 'ko', 'zh'] as const;
type LocaleCode = (typeof LOCALES)[number];

export function LanguageSwitcher() {
  const locale = useLocale() as LocaleCode;
  const t = useTranslations('language');
  const router = useRouter();
  const [pending, startTransition] = useTransition();

  const setLocale = (next: LocaleCode) => {
    if (next === locale) return;
    document.cookie = `NEXT_LOCALE=${next}; path=/; max-age=${60 * 60 * 24 * 365}; SameSite=Lax`;
    startTransition(() => {
      router.refresh();
    });
  };

  return (
    <div className="relative inline-block" aria-label={t('label')}>
      <select
        value={locale}
        onChange={(e) => setLocale(e.target.value as LocaleCode)}
        disabled={pending}
        className="bg-transparent text-xs tracking-widest text-text-muted uppercase border border-accent/20 hover:border-accent/60 focus:border-accent outline-none px-3 py-1.5 cursor-pointer transition-colors appearance-none pr-7"
        style={{
          backgroundImage: "url(\"data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='8' height='5' viewBox='0 0 8 5'><path fill='%23888' d='M0 0l4 5 4-5z'/></svg>\")",
          backgroundRepeat: 'no-repeat',
          backgroundPosition: 'right 8px center',
        }}
      >
        {LOCALES.map((l) => (
          <option key={l} value={l} className="bg-bg-primary text-text">
            {t(l)}
          </option>
        ))}
      </select>
    </div>
  );
}
