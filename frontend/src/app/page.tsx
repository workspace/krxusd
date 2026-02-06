'use client';

import Link from 'next/link';
import { ExchangeRateCard, PopularStocksList, StockSearch } from '@/components';
import { useExchangeAnalysis, useFavorites, useCurrentExchangeRate } from '@/hooks';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { DollarSign, TrendingUp, BarChart3, ArrowRight, Moon, Sun, Gauge, Star, X } from 'lucide-react';
import { useTheme } from 'next-themes';

function ExchangeGauge() {
  const { data, isLoading } = useExchangeAnalysis();

  if (isLoading || !data) {
    return (
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm font-medium flex items-center gap-2">
            <Gauge className="h-4 w-4" />
            환율 수준
          </CardTitle>
        </CardHeader>
        <CardContent>
          <Skeleton className="h-7 w-28 mb-2" />
          <Skeleton className="h-6 w-full mb-2" />
          <Skeleton className="h-4 w-32" />
        </CardContent>
      </Card>
    );
  }

  const pct = data.percentile_5y;
  const gaugeColor = pct >= 70 ? 'bg-red-500' : pct >= 40 ? 'bg-yellow-500' : 'bg-green-500';
  const gaugeLabel = pct >= 70 ? '고환율 구간' : pct >= 40 ? '보통 구간' : '저환율 구간';

  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-sm font-medium flex items-center gap-2">
          <Gauge className="h-4 w-4" />
          환율 수준 (5년 기준)
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="text-2xl font-bold">₩{data.current.toLocaleString()}</div>

        <div>
          <div className="flex justify-between text-xs text-muted-foreground mb-1">
            <span>₩{data.low_5y.toLocaleString()}</span>
            <span className="font-medium">{pct.toFixed(0)}%</span>
            <span>₩{data.high_5y.toLocaleString()}</span>
          </div>
          <div className="h-3 bg-muted rounded-full overflow-hidden relative">
            <div
              className="absolute inset-y-0 left-0 bg-gradient-to-r from-green-500 via-yellow-500 to-red-500 rounded-full opacity-30"
              style={{ width: '100%' }}
            />
            <div
              className={`absolute top-1/2 -translate-y-1/2 w-4 h-4 rounded-full border-2 border-background shadow-md ${gaugeColor}`}
              style={{ left: `clamp(0%, calc(${pct}% - 8px), calc(100% - 16px))` }}
            />
          </div>
          <div className="text-xs text-muted-foreground mt-1 text-center">{gaugeLabel}</div>
        </div>

        <div className="grid grid-cols-2 gap-2 text-xs">
          <div className="text-muted-foreground">
            1년 범위: ₩{data.low_1y.toLocaleString()} ~ ₩{data.high_1y.toLocaleString()}
          </div>
          <div className="text-right text-muted-foreground">
            MA200: ₩{data.ma200?.toLocaleString() ?? '-'}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

function FavoritesList() {
  const { favorites, removeFavorite, hydrated } = useFavorites();

  if (!hydrated || favorites.length === 0) return null;

  return (
    <Card className="mb-6">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Star className="h-5 w-5 fill-yellow-500 text-yellow-500" />
          즐겨찾기
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="space-y-2">
          {favorites.map((fav) => (
            <div key={fav.code} className="flex items-center justify-between p-3 rounded-lg hover:bg-muted transition-colors">
              <Link href={`/stocks/${fav.code}`} className="flex-1">
                <div className="font-medium">{fav.name}</div>
                <div className="text-sm text-muted-foreground">{fav.code}</div>
              </Link>
              <button
                onClick={() => removeFavorite(fav.code)}
                className="p-1.5 rounded-lg hover:bg-destructive/10 text-muted-foreground hover:text-destructive transition-colors"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}

export default function HomePage() {
  const { theme, setTheme } = useTheme();

  return (
    <div className="min-h-screen bg-background">
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
            <div className="flex items-center gap-3">
              <StockSearch />
              <button
                onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')}
                className="p-2 rounded-lg hover:bg-muted transition-colors"
              >
                <Sun className="h-5 w-5 hidden dark:block" />
                <Moon className="h-5 w-5 block dark:hidden" />
              </button>
            </div>
          </div>
        </div>
      </header>

      <section className="py-8 sm:py-12 px-4 bg-gradient-to-b from-muted/50 to-background">
        <div className="container mx-auto text-center">
          <h2 className="text-2xl sm:text-4xl font-bold mb-4">
            한국 주식의 <span className="text-primary">실제 달러 가치</span>를 확인하세요
          </h2>
          <p className="text-sm sm:text-lg text-muted-foreground max-w-2xl mx-auto mb-8">
            원화로는 오른 것 같은데, 달러로도 올랐을까?{' '}
            KRW 주가를 당일 환율로 나눈 USD 환산 차트로 진짜 수익률을 확인합니다.
          </p>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-6 max-w-4xl mx-auto">
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
              <h3 className="font-semibold mb-1">종목 비교</h3>
              <p className="text-sm text-muted-foreground">
                여러 종목의 달러 수익률을 한 차트에
              </p>
            </div>
          </div>

          <div className="mt-8">
            <Link
              href="/compare"
              className="inline-flex items-center gap-2 px-6 py-3 bg-primary text-primary-foreground rounded-lg font-medium hover:opacity-90 transition-opacity"
            >
              종목 비교하기
              <ArrowRight className="h-4 w-4" />
            </Link>
          </div>
        </div>
      </section>

      <main className="container mx-auto px-4 py-8">
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="lg:col-span-1 space-y-6">
            <ExchangeRateCard />
            <ExchangeGauge />

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

          <div className="lg:col-span-2">
            <FavoritesList />
            <PopularStocksList />
          </div>
        </div>
      </main>

      <footer className="border-t mt-auto py-6">
        <div className="container mx-auto px-4 text-center text-sm text-muted-foreground">
          <p>KRXUSD - 한국 주식의 USD 환산 가격 서비스</p>
          <p className="mt-1">데이터는 투자 참고용이며, 실제 거래에는 적합하지 않을 수 있습니다.</p>
        </div>
      </footer>
    </div>
  );
}
