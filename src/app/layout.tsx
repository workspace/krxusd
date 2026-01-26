import type { Metadata } from "next";
import { Providers } from "./providers";
import "./globals.css";

export const metadata: Metadata = {
  title: "KRXUSD - 한국 주식 달러 환산 서비스",
  description:
    "KRX 상장 주식의 가격을 실시간 환율 기준 USD로 확인하세요. 외국인 투자자와 달러 자산 운용자를 위한 직관적인 달러 환산 주가 정보 서비스.",
  keywords: ["KRX", "한국 주식", "USD", "환율", "달러 환산", "주식 투자"],
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="ko" suppressHydrationWarning>
      <body>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
