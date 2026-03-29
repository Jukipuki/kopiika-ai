import type { Metadata } from "next";
import { DM_Sans } from "next/font/google";
import { SessionProvider } from "next-auth/react";
import { NextIntlClientProvider } from "next-intl";
import { getLocale, getMessages } from "next-intl/server";
import { Toaster } from "sonner";
import "./globals.css";
import { cn } from "@/lib/utils";
import QueryProvider from "@/lib/query/query-provider";

const dmSans = DM_Sans({
  variable: "--font-dm-sans",
  subsets: ["latin", "latin-ext"],
});

export const metadata: Metadata = {
  title: "Kopiika AI",
  description:
    "AI-powered personal finance education platform",
};

export default async function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  const locale = await getLocale();
  const messages = await getMessages();

  return (
    <html lang={locale} className={cn("dark h-full antialiased", dmSans.variable)}>
      <body className="min-h-full flex flex-col font-sans">
        <SessionProvider>
          <QueryProvider>
            <NextIntlClientProvider locale={locale} messages={messages}>
              {children}
              <Toaster position="top-right" richColors />
            </NextIntlClientProvider>
          </QueryProvider>
        </SessionProvider>
      </body>
    </html>
  );
}
