/**
 * Stock Detail Page - 종목 상세 페이지
 * 
 * USD 환산 차트를 보여주는 핵심 페이지
 */
'use client';

import { use, useMemo } from 'react';
import Link from 'next/link';
import { useStockInfo, useStockUsdHistory, useCurrentExchangeRate } from '@/hooks';
import { UsdPriceChart, StockSearch } from '@/components';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { 
  DollarSign, 
  TrendingUp, 
  TrendingDown, 
  ArrowLeft,
  Calendar
} from 'lucide-react';

// Date helpers
function getDateRange(period: string): { start: string; end: string } {
  const end = new Date();
  const start = new Date();
  
  switch (period) {
    case '1M':
      start.setMonth(start.getMonth() - 1);
      break;
    case '3M':
      start.setMonth(start.getMonth() - 3);
      break;
    case '6M':
      start.setMonth(start.getMonth() - 6);
      break;
    case '1Y':
      start.setFullYear(start.getFullYear() - 1);
      break;
    case '5Y':
      start.setFullYear(start.getFullYear() - 5);
      break;
    case 'MAX':
      start.setFullYear(start.getFullYear() - 10);
      break;
    default:
      start.setMonth(start.getMonth() - 3);
  }
  
  return {
    start: start.toISOString().split('T')[0],
    end: end.toISOString().split('T')[0],
  };
}

export default function StockDetailPage({ 
  params 
}: { 
  params: Promise<{ code: string }> 
}) {
  const { code } = use(params);
  
  // Default period: 3 months
  const dateRange = useMemo(() => getDateRange('3M'), []);
  
  // Fetch data
  const { data: stockInfo, isLoading: infoLoading } = useStockInfo(code);
  const { data: usdHistory, isLoading: historyLoading } = useStockUsdHistory(
    code, 
    dateRange.start, 
    dateRange.end
  );
  const { data: exchangeRate } = useCurrentExchangeRate();
  
  const isLoading = infoLoading || historyLoading;
  const rate = exchangeRate?.rate || 1450;

  if (isLoading) {
    return (
      <div className="min-h-screen bg-background">
        <Header />
        <main className="container mx-auto px-4 py-8">
          <div className="mb-6">
            <Skeleton className="h-10 w-48 mb-2" />
            <Skeleton className="h-6 w-32" />
          </div>
          <Skeleton className="h-[500px] w-full rounded-lg" />
        </main>
      </div>
    );
  }

  if (!stockInfo || !usdHistory) {
    return (
      <div className="min-h-screen bg-background">
        <Header />
        <main className="container mx-auto px-4 py-8">
          <Card>
            <CardContent className="py-8 text-center">
              <p className="text-destructive">종목 정보를 찾을 수 없습니다.</p>
              <Link href="/" className="text-primary hover:underline mt-2 inline-block">
                홈으로 돌아가기
              </Link>
            </CardContent>
          </Card>
        </main>
      </div>
    );
  }

  const usdPrice = stockInfo.price / rate;
  const isPositive = stockInfo.change_percent >= 0;

  return (
    <div className="min-h-screen bg-background">
      <Header />
      
      <main className="container mx-auto px-4 py-8">
        {/* Back Button */}
        <Link 
          href="/"
          className="inline-flex items-center gap-2 text-muted-foreground hover:text-foreground mb-6"
        >
          <ArrowLeft className="h-4 w-4" />
          뒤로 가기
        </Link>

        {/* Stock Info Header */}
        <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 mb-8">
          <div>
            <div className="flex items-center gap-3">
              <h1 className="text-3xl font-bold">{stockInfo.name}</h1>
              <Badge variant="outline">{stockInfo.market}</Badge>
            </div>
            <p className="text-muted-foreground">{stockInfo.code}</p>
          </div>
          
          <div className="flex gap-6">
            {/* USD Price Card */}
            <Card className="min-w-[180px]">
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium flex items-center gap-2">
                  <DollarSign className="h-4 w-4 text-primary" />
                  USD 환산
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-3xl font-bold text-primary">
                  ${usdPrice.toFixed(2)}
                </div>
              </CardContent>
            </Card>
            
            {/* KRW Price Card */}
            <Card className="min-w-[180px]">
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium">KRW 현재가</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">
                  ₩{stockInfo.price.toLocaleString()}
                </div>
                <Badge 
                  variant={isPositive ? 'default' : 'destructive'} 
                  className="mt-1"
                >
                  {isPositive ? (
                    <TrendingUp className="h-3 w-3 mr-1" />
                  ) : (
                    <TrendingDown className="h-3 w-3 mr-1" />
                  )}
                  {isPositive ? '+' : ''}{stockInfo.change_percent.toFixed(2)}%
                </Badge>
              </CardContent>
            </Card>
          </div>
        </div>

        {/* USD Chart - 핵심 컴포넌트 */}
        <UsdPriceChart
          data={usdHistory.data}
          stockName={stockInfo.name}
          stockCode={stockInfo.code}
        />
        
        {/* Additional Info */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mt-8">
          <Card>
            <CardHeader>
              <CardTitle className="text-sm">거래량</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-xl font-semibold">
                {stockInfo.volume.toLocaleString()}주
              </div>
            </CardContent>
          </Card>
          
          <Card>
            <CardHeader>
              <CardTitle className="text-sm">현재 환율</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-xl font-semibold">
                ₩{rate.toLocaleString()}
              </div>
              <p className="text-sm text-muted-foreground">USD/KRW</p>
            </CardContent>
          </Card>
          
          <Card>
            <CardHeader>
              <CardTitle className="text-sm">데이터 기간</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="flex items-center gap-2">
                <Calendar className="h-4 w-4 text-muted-foreground" />
                <span>{usdHistory.count}일</span>
              </div>
              <p className="text-sm text-muted-foreground mt-1">
                {dateRange.start} ~ {dateRange.end}
              </p>
            </CardContent>
          </Card>
        </div>
      </main>
    </div>
  );
}

// Header Component
function Header() {
  return (
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
  );
}
