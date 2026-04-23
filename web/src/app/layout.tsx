import type { Metadata } from "next";
import { NextIntlClientProvider } from 'next-intl';
import { getLocale, getMessages } from 'next-intl/server';
import { FloatingLanguageSwitcher } from './_components/FloatingLanguageSwitcher';
import "./globals.css";

export const metadata: Metadata = {
  title: "LAPLACE - AI Baccarat Prediction Engine",
  description: "AI-powered baccarat prediction with automated bet execution",
};

export default async function RootLayout({ children }: { children: React.ReactNode }) {
  const locale = await getLocale();
  const messages = await getMessages();

  return (
    <html lang={locale}>
      <body className="min-h-screen bg-bg-primary text-text antialiased font-body">
        <NextIntlClientProvider locale={locale} messages={messages}>
          <FloatingLanguageSwitcher />
          {children}
        </NextIntlClientProvider>
      </body>
    </html>
  );
}
