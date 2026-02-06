'use client';

import Link from 'next/link';
import { ExchangeRateCard, PopularStocksList, StockSearch } from '@/components';
import { useIndexUsd, useExchangeAnalysis, useFavorites, useCurrentExchangeRate } from '@/hooks';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { DollarSign, TrendingUp, TrendingDown, ArrowRight, Moon, Sun, Gauge, Star, X } from 'lucide-react';
import { useTheme } from 'next-themes';

function IndexCard({ index, label }: { index: string; label: string }) {
  const { data, isLoading } = useIndexUsd(index, '1Y');

  if (isLoading || !data) {
    return (
      <Card className="flex-1">
        <CardHeader className="pb-2">
          <CardTitle className="text-sm font-medium">{label}</CardTitle>
        </CardHeader>
        <CardContent>
          <Skeleton className="h-7 w-24 mb-2" />
          <Skeleton className="h-4 w-32 mb-1" />
          <Skeleton className="h-4 w-20" />
        </CardContent>
      </Card>
    );
  }

  const usdPositive = data.change_usd >= 0;
  const krwPositive = data.change_krw >= 0;

  return (
    <Card className="flex-1">
      <CardHeader className="pb-2">
        <CardTitle className="text-sm font-medium flex items-center justify-between">
          {label}
          <Badge variant="outline" className="text-xs font-normal">1Y</Badge>
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-2">
        <div className="text-2xl font-bold">${data.current_usd.toFixed(2)}</div>
        <div className="text-sm text-muted-foreground">
          ₩{data.current_krw.toLocaleString()}
        </div>
        <div className="flex flex-wrap gap-2">
          <Badge variant={usdPositive ? 'default' : 'destructive'} className="text-xs">
            {usdPositive ? <TrendingUp className="h-3 w-3 mr-1" /> : <TrendingDown className="h-3 w-3 mr-1" />}
            USD {usdPositive ? '+' : ''}{data.change_usd.toFixed(1)}%
          </Badge>
          <Badge variant={krwPositive ? 'default' : 'destructive'} className="text-xs">
            KRW {krwPositive ? '+' : ''}{data.change_krw.toFixed(1)}%
          </Badge>
        </div>
        {data.fx_effect !== 0 && (
          <div className="text-xs text-muted-foreground">
            환율 영향: <span className={data.fx_effect >= 0 ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'}>
              {data.fx_effect >= 0 ? '+' : ''}{data.fx_effect.toFixed(1)}%p
            </span>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function ExchangeGauge() {
  const { data, isLoading } = useExchangeAnalysis();

  if (isLoading || !data) {
    return (
      <Card className="flex-1">
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
    <Card className="flex-1">
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
  const { data: exchangeRate } = useCurrentExchangeRate();
  const rate = exchangeRate?.rate || 1450;

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
  const { data: kospiData } = useIndexUsd('KS11', '1Y');

  const headline = kospiData
    ? kospiData.change_usd >= 0
      ? `올해 KOSPI는 달러로 +${kospiData.change_usd.toFixed(1)}% 올랐습니다`
      : `올해 KOSPI는 달러로 ${kospiData.change_usd.toFixed(1)}% 빠졌습니다`
    : '한국 주식의 실제 달러 가치를 확인하세요';

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
        <div className="container mx-auto">
          <div className="text-center mb-8">
            <h2 className="text-2xl sm:text-4xl font-bold mb-3">{headline}</h2>
            <p className="text-sm sm:text-lg text-muted-foreground max-w-2xl mx-auto">
              KRW 주가를 당일 환율로 나눈 USD 환산 차트로, 원화 상승과 달러 가치 변동을 한눈에 비교합니다.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 max-w-5xl mx-auto">
            <IndexCard index="KS11" label="KOSPI" />
            <IndexCard index="KQ11" label="KOSDAQ" />
            <ExchangeGauge />
          </div>

          <div className="text-center mt-6">
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
            <FavoritesList />
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
