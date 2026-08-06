import type { Metadata } from "next";
import { NextIntlClientProvider } from 'next-intl';
import { getLocale, getMessages } from 'next-intl/server';
import { FloatingLanguageSwitcher } from './_components/FloatingLanguageSwitcher';
import "./globals.css";

export const metadata: Metadata = {
  title: "bafather — バカラ コピートレードGUI 会員サイト",
  description: "エンジンの判断をGUIで受け取り、自分の口座で実行するコピートレードサービス。料金は30日 $200 のサブスクと、プラスで終わった週の純利益の30%のみ。",
};

export default async function RootLayout({ children }: { children: React.ReactNode }) {
  const locale = await getLocale();
  const messages = await getMessages();

  return (
    <html lang={locale}>
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link
          rel="stylesheet"
          href="https://fonts.googleapis.com/css2?family=Orbitron:wght@500;700&family=Inter:wght@400;500;600;700&family=Noto+Sans+JP:wght@400;500;700&family=JetBrains+Mono:wght@400;500;600;700&display=swap"
        />
      </head>
      <body className="min-h-screen bg-bg-primary text-text antialiased font-body">
        <NextIntlClientProvider locale={locale} messages={messages}>
          <FloatingLanguageSwitcher />
          {children}
        </NextIntlClientProvider>
      </body>
    </html>
  );
}
