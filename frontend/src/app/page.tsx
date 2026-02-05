/**
 * KRXUSD - 메인 대시보드 페이지
 * 
 * 한국 주식의 USD 환산 가격을 보여주는 서비스
 */
import Link from 'next/link';
import { ExchangeRateCard, PopularStocksList, StockSearch } from '@/components';
import { DollarSign, TrendingUp, BarChart3 } from 'lucide-react';

export default function HomePage() {
  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <header className="border-b sticky top-0 bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60 z-50">
        <div className="container mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            <Link href="/" className="flex items-center gap-2">
              <div className="flex items-center justify-center w-10 h-10 bg-primary rounded-lg">
                <DollarSign className="h-6 w-6 text-primary-foreground" />
              </div>
              <div>
                <h1 className="text-xl font-bold">KRXUSD</h1>
                <p className="text-xs text-muted-foreground">한국 주식 USD 환산</p>
              </div>
            </Link>
            <StockSearch />
          </div>
        </div>
      </header>

      {/* Hero Section */}
      <section className="py-12 px-4 bg-gradient-to-b from-muted/50 to-background">
        <div className="container mx-auto text-center">
          <h2 className="text-4xl font-bold mb-4">
            한국 주식의 <span className="text-primary">실제 달러 가치</span>를 확인하세요
          </h2>
          <p className="text-lg text-muted-foreground max-w-2xl mx-auto mb-8">
            KRW 주가를 당일 환율로 나눈 USD 환산 차트로,
            원화 상승과 달러 가치 변동을 한눈에 비교할 수 있습니다.
          </p>
          
          {/* Key Features */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6 max-w-4xl mx-auto mt-8">
            <div className="flex flex-col items-center p-4">
              <div className="w-12 h-12 bg-primary/10 rounded-full flex items-center justify-center mb-3">
                <DollarSign className="h-6 w-6 text-primary" />
              </div>
              <h3 className="font-semibold mb-1">USD 환산 가격</h3>
              <p className="text-sm text-muted-foreground">
                당일 환율 기준 실시간 달러 가치
              </p>
            </div>
            <div className="flex flex-col items-center p-4">
              <div className="w-12 h-12 bg-primary/10 rounded-full flex items-center justify-center mb-3">
                <TrendingUp className="h-6 w-6 text-primary" />
              </div>
              <h3 className="font-semibold mb-1">KRW vs USD 비교</h3>
              <p className="text-sm text-muted-foreground">
                원화/달러 수익률 차이 한눈에
              </p>
            </div>
            <div className="flex flex-col items-center p-4">
              <div className="w-12 h-12 bg-primary/10 rounded-full flex items-center justify-center mb-3">
                <BarChart3 className="h-6 w-6 text-primary" />
              </div>
              <h3 className="font-semibold mb-1">환율 추이</h3>
              <p className="text-sm text-muted-foreground">
                USD/KRW 환율 변동 차트
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* Main Content */}
      <main className="container mx-auto px-4 py-8">
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Sidebar - Exchange Rate & Info */}
          <div className="lg:col-span-1 space-y-6">
            <ExchangeRateCard />
            
            {/* Quick Info Card */}
            <div className="bg-muted/50 rounded-lg p-4">
              <h3 className="font-semibold mb-3">USD 환산 공식</h3>
              <div className="bg-background rounded-md p-3 font-mono text-sm">
                <span className="text-primary">USD 가격</span> = KRW 가격 / 환율
              </div>
              <p className="text-sm text-muted-foreground mt-3">
                예시: ₩72,000 / 1,450 = <span className="font-semibold">$49.66</span>
              </p>
            </div>
          </div>
          
          {/* Main Content - Popular Stocks */}
          <div className="lg:col-span-2">
            <PopularStocksList />
          </div>
        </div>
      </main>

      {/* Footer */}
      <footer className="border-t mt-auto py-6">
        <div className="container mx-auto px-4 text-center text-sm text-muted-foreground">
          <p>
            KRXUSD - 한국 주식의 USD 환산 가격 서비스
          </p>
          <p className="mt-1">
            데이터는 투자 참고용이며, 실제 거래에는 적합하지 않을 수 있습니다.
          </p>
        </div>
      </footer>
    </div>
  );
}
