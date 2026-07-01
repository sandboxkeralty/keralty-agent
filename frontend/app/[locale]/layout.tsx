import type { Metadata } from "next";
import { Carlito, Geist_Mono } from "next/font/google";
import "../globals.css";
import { NextIntlClientProvider } from 'next-intl';
import { getMessages } from 'next-intl/server';
import { AppShell } from "@/components/layout/AppShell";

// Carlito is metric-compatible with Calibri, the body font used throughout
// branding/Template_Keralty.pptx — the closest freely-licensed web font match.
const carlito = Carlito({
  variable: "--font-carlito",
  subsets: ["latin"],
  weight: ["400", "700"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Keralty Assistant",
  description: "Intelligent Agent System for Keralty",
};

export default async function RootLayout({
  children,
  params
}: Readonly<{
  children: React.ReactNode;
  params: Promise<{ locale: string }>;
}>) {
  const { locale } = await params;
  const messages = await getMessages({ locale });
  
  return (
    <html lang={locale}>
      <body className={`${carlito.variable} ${geistMono.variable} antialiased bg-gray-50 text-gray-900`}>
        <NextIntlClientProvider messages={messages} locale={locale}>
          <AppShell>{children}</AppShell>
        </NextIntlClientProvider>
      </body>
    </html>
  );
}
