'use client';

import { use, useMemo, useState, useEffect, useCallback } from 'react';
import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';
import { useStockInfo, useStockUsdHistory, useCurrentExchangeRate, useFavorites } from '@/hooks';
import { UsdPriceChart, StockSearch } from '@/components';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import {
  DollarSign,
  TrendingUp,
  TrendingDown,
  ArrowLeft,
  Calendar,
  Moon,
  Sun,
  HelpCircle,
  Star,
  Share2,
  Check,
} from 'lucide-react';
import { useTheme } from 'next-themes';
import { calculateAnalysis } from '@/lib/analysis';

const PERIODS = ['1M', '3M', '6M', '1Y', '5Y', 'MAX'] as const;
type Period = (typeof PERIODS)[number];

function getDateRange(period: Period): { start: string; end: string } {
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
  }

  return {
    start: start.toISOString().split('T')[0],
    end: end.toISOString().split('T')[0],
  };
}

function InfoTip({ text }: { text: string }) {
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <HelpCircle className="h-3.5 w-3.5 text-muted-foreground/60 hover:text-muted-foreground cursor-help" />
      </TooltipTrigger>
      <TooltipContent side="top" className="max-w-[240px] text-xs">
        {text}
      </TooltipContent>
    </Tooltip>
  );
}

export default function StockDetailPage({
  params,
}: {
  params: Promise<{ code: string }>;
}) {
  const { code } = use(params);
  const router = useRouter();
  const searchParams = useSearchParams();
  const [copied, setCopied] = useState(false);

  const [selectedPeriod, setSelectedPeriod] = useState<Period>(() => {
    const p = searchParams.get('period');
    return PERIODS.includes(p as Period) ? (p as Period) : '3M';
  });

  useEffect(() => {
    const params = new URLSearchParams();
    if (selectedPeriod !== '3M') params.set('period', selectedPeriod);
    const qs = params.toString();
    router.replace(`/stocks/${code}${qs ? `?${qs}` : ''}`, { scroll: false });
  }, [selectedPeriod, code, router]);

  const handleShare = useCallback(() => {
    const url = window.location.href;
    navigator.clipboard.writeText(url).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  }, []);

  const dateRange = useMemo(() => getDateRange(selectedPeriod), [selectedPeriod]);

  const { data: stockInfo, isLoading: infoLoading } = useStockInfo(code);
  const {
    data: usdHistory,
    isLoading: historyLoading,
    isFetching: historyFetching,
  } = useStockUsdHistory(code, dateRange.start, dateRange.end);
  const { data: exchangeRate } = useCurrentExchangeRate();
  const { isFavorite, toggleFavorite, hydrated } = useFavorites();

  const rate = exchangeRate?.rate || 1450;

  const analysis = useMemo(() => {
    if (!usdHistory?.data || usdHistory.data.length < 2) return null;
    return calculateAnalysis(usdHistory.data);
  }, [usdHistory]);

  const hasInitialData = !!stockInfo && !!usdHistory;
  const isInitialLoad = infoLoading && !hasInitialData;

  if (isInitialLoad) {
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

  if (!stockInfo) {
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
    <TooltipProvider delayDuration={200}>
      <div className="min-h-screen bg-background">
        <Header />

        <main className="container mx-auto px-4 py-8">
          <Link
            href="/"
            className="inline-flex items-center gap-2 text-muted-foreground hover:text-foreground mb-6"
          >
            <ArrowLeft className="h-4 w-4" />
            뒤로 가기
          </Link>

          <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 mb-8">
            <div>
              <div className="flex items-center gap-3">
                <h1 className="text-3xl font-bold">{stockInfo.name}</h1>
                <Badge variant="outline">{stockInfo.market}</Badge>
                {hydrated && (
                  <button
                    onClick={() => toggleFavorite(code, stockInfo.name)}
                    className="p-1.5 rounded-lg hover:bg-muted transition-colors"
                  >
                    <Star
                      className={`h-5 w-5 ${
                        isFavorite(code)
                          ? 'fill-yellow-500 text-yellow-500'
                          : 'text-muted-foreground'
                      }`}
                    />
                  </button>
                )}
              </div>
              <p className="text-muted-foreground">{stockInfo.code}</p>
            </div>

            <div className="flex flex-wrap gap-4">
              <Card className="min-w-[150px] flex-1">
                <CardHeader className="pb-2">
                  <CardTitle className="text-sm font-medium flex items-center gap-2">
                    <DollarSign className="h-4 w-4 text-primary" />
                    USD 환산
                    <InfoTip text="KRW 현재가를 오늘 USD/KRW 환율 종가로 나눈 값입니다." />
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="text-2xl sm:text-3xl font-bold text-primary">
                    ${usdPrice.toFixed(2)}
                  </div>
                </CardContent>
              </Card>

              <Card className="min-w-[150px] flex-1">
                <CardHeader className="pb-2">
                  <CardTitle className="text-sm font-medium">KRW 현재가</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="text-xl sm:text-2xl font-bold">
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

          <div className="flex items-center gap-2 mb-4">
            {PERIODS.map((p) => (
              <button
                key={p}
                onClick={() => setSelectedPeriod(p)}
                disabled={historyFetching}
                className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                  selectedPeriod === p
                    ? 'bg-primary text-primary-foreground'
                    : 'bg-muted text-muted-foreground hover:bg-muted/80'
                } ${historyFetching ? 'opacity-60' : ''}`}
              >
                {p}
              </button>
            ))}
            {historyFetching && (
              <div className="flex items-center ml-2">
                <div className="h-4 w-4 border-2 border-primary border-t-transparent rounded-full animate-spin" />
              </div>
            )}
            <div className="ml-auto">
              <button
                onClick={handleShare}
                className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium bg-muted text-muted-foreground hover:bg-muted/80 transition-colors"
              >
                {copied ? <Check className="h-4 w-4 text-green-500" /> : <Share2 className="h-4 w-4" />}
                {copied ? '복사됨' : '공유'}
              </button>
            </div>
          </div>

          <div className={`transition-opacity duration-200 ${historyFetching ? 'opacity-50' : 'opacity-100'}`}>
            {usdHistory && (
              <UsdPriceChart
                data={usdHistory.data}
                stockName={stockInfo.name}
                stockCode={stockInfo.code}
              />
            )}
          </div>

          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mt-8">
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm text-muted-foreground flex items-center gap-1.5">
                  거래량
                  <InfoTip text="오늘 하루 동안 거래된 주식 수입니다." />
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-lg font-semibold">
                  {stockInfo.volume.toLocaleString()}
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm text-muted-foreground flex items-center gap-1.5">
                  현재 환율
                  <InfoTip text="USD/KRW 환율 종가입니다. USD 환산 가격 계산에 사용됩니다." />
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-lg font-semibold">₩{rate.toLocaleString()}</div>
              </CardContent>
            </Card>

            {analysis && (
              <>
                <Card>
                  <CardHeader className="pb-2">
                    <CardTitle className="text-sm text-muted-foreground flex items-center gap-1.5">
                      USD 변동성
                      <InfoTip text="일일 수익률의 표준편차에 √252를 곱해 연환산한 값입니다. 높을수록 가격 변동이 큽니다." />
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="text-lg font-semibold">
                      {analysis.volatility.usd.toFixed(1)}%
                    </div>
                    <p className="text-xs text-muted-foreground">
                      KRW {analysis.volatility.krw.toFixed(1)}%
                    </p>
                  </CardContent>
                </Card>

                <Card>
                  <CardHeader className="pb-2">
                    <CardTitle className="text-sm text-muted-foreground flex items-center gap-1.5">
                      최대 낙폭 (MDD)
                      <InfoTip text="선택 기간 내 고점 대비 최대 하락 폭입니다. 투자 시 감내해야 할 최악의 손실을 나타냅니다." />
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="text-lg font-semibold text-destructive">
                      {analysis.drawdown.usdMax.toFixed(1)}%
                    </div>
                    <p className="text-xs text-muted-foreground">
                      KRW {analysis.drawdown.krwMax.toFixed(1)}%
                    </p>
                  </CardContent>
                </Card>

                <Card>
                  <CardHeader className="pb-2">
                    <CardTitle className="text-sm text-muted-foreground flex items-center gap-1.5">
                      52주 고가
                      <InfoTip text="최근 252거래일(약 1년) 중 USD 환산 종가 기준 최고가입니다." />
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="text-lg font-semibold text-green-600 dark:text-green-400">
                      ${analysis.high52w.usd.toFixed(2)}
                    </div>
                    <p className="text-xs text-muted-foreground">
                      ₩{analysis.high52w.krw.toLocaleString()}
                    </p>
                  </CardContent>
                </Card>

                <Card>
                  <CardHeader className="pb-2">
                    <CardTitle className="text-sm text-muted-foreground flex items-center gap-1.5">
                      52주 저가
                      <InfoTip text="최근 252거래일(약 1년) 중 USD 환산 종가 기준 최저가입니다." />
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="text-lg font-semibold text-red-600 dark:text-red-400">
                      ${analysis.low52w.usd.toFixed(2)}
                    </div>
                    <p className="text-xs text-muted-foreground">
                      ₩{analysis.low52w.krw.toLocaleString()}
                    </p>
                  </CardContent>
                </Card>

                <Card>
                  <CardHeader className="pb-2">
                    <CardTitle className="text-sm text-muted-foreground flex items-center gap-1.5">
                      환율 영향
                      <InfoTip text="USD 총수익률에서 KRW 주가 수익률을 뺀 값입니다. 양수면 원화 약세로 달러 수익이 늘어난 것, 음수면 원화 강세로 깎인 것입니다." />
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className={`text-lg font-semibold ${analysis.attribution.fxEffect >= 0 ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'}`}>
                      {analysis.attribution.fxEffect >= 0 ? '+' : ''}{analysis.attribution.fxEffect.toFixed(2)}%
                    </div>
                    <p className="text-xs text-muted-foreground">
                      주가 {analysis.attribution.stockReturn >= 0 ? '+' : ''}{analysis.attribution.stockReturn.toFixed(2)}%
                    </p>
                  </CardContent>
                </Card>

                <Card>
                  <CardHeader className="pb-2">
                    <CardTitle className="text-sm text-muted-foreground flex items-center gap-1.5">
                      데이터 기간
                      <InfoTip text="차트에 표시된 거래일 수입니다. 주말·공휴일은 제외됩니다." />
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="flex items-center gap-2">
                      <Calendar className="h-4 w-4 text-muted-foreground" />
                      <span className="text-lg font-semibold">{usdHistory?.count ?? 0}일</span>
                    </div>
                  </CardContent>
                </Card>
              </>
            )}
          </div>
        </main>
      </div>
    </TooltipProvider>
  );
}

function Header() {
  const { theme, setTheme } = useTheme();

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
  );
}
