import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import { Providers } from "./providers";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "KRXUSD - 한국 주식 USD 환산 차트",
  description: "한국 주식(KOSPI/KOSDAQ)의 USD 환산 가격을 실시간으로 확인하세요. KRW 가격을 환율로 나눈 실제 달러 가치를 시각화합니다.",
  keywords: ["한국주식", "USD환산", "환율", "KOSPI", "KOSDAQ", "주가차트", "달러가치"],
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="ko">
      <body
        className={`${geistSans.variable} ${geistMono.variable} antialiased`}
      >
        <Providers>
          {children}
        </Providers>
      </body>
    </html>
  );
}
