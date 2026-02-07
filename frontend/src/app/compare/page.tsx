'use client';

import { useState, useCallback, useMemo, useEffect } from 'react';
import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';
import { useCompareStocksUsd, useStockSearch } from '@/hooks';
import { useDebounce } from '@/hooks/useDebounce';
import { StockSearch } from '@/components';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Skeleton } from '@/components/ui/skeleton';
import {
  ChartContainer,
  ChartTooltip,
  type ChartConfig,
} from '@/components/ui/chart';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Legend,
  ReferenceLine,
  TooltipProps,
} from 'recharts';
import { DollarSign, Search, X, Moon, Sun, TrendingUp, TrendingDown, Sparkles } from 'lucide-react';
import { useTheme } from 'next-themes';

const CHART_COLORS = [
  'var(--chart-1)',
  'var(--chart-2)',
  'var(--chart-3)',
  'var(--chart-4)',
  'var(--chart-5)',
  '#e879f9',
  '#38bdf8',
  '#34d399',
  '#fb923c',
  '#a78bfa',
];

const PERIODS = ['1M', '3M', '6M', '1Y', '5Y'] as const;
type Period = (typeof PERIODS)[number];

interface Preset {
  id: string;
  name: string;
  description: string;
  stocks: { code: string; name: string }[];
}

const PRESETS: Preset[] = [
  {
    id: 'top10',
    name: '시총 Top 10',
    description: '시가총액 기준 상위 10개 종목',
    stocks: [
      { code: '005930', name: '삼성전자' },
      { code: '000660', name: 'SK하이닉스' },
      { code: '373220', name: 'LG에너지솔루션' },
      { code: '207940', name: '삼성바이오로직스' },
      { code: '005380', name: '현대차' },
      { code: '000270', name: '기아' },
      { code: '035420', name: 'NAVER' },
      { code: '006400', name: '삼성SDI' },
      { code: '068270', name: '셀트리온' },
      { code: '035720', name: '카카오' },
    ],
  },
  {
    id: 'semiconductor',
    name: '반도체',
    description: '반도체 대장주',
    stocks: [
      { code: '005930', name: '삼성전자' },
      { code: '000660', name: 'SK하이닉스' },
    ],
  },
  {
    id: 'shipbuilding',
    name: '조선',
    description: '조선업 대장주',
    stocks: [
      { code: '009540', name: 'HD한국조선해양' },
      { code: '042660', name: '한화오션' },
    ],
  },
  {
    id: 'finance',
    name: '금융',
    description: '금융업 대장주',
    stocks: [
      { code: '105560', name: 'KB금융' },
      { code: '055550', name: '신한지주' },
    ],
  },
  {
    id: 'sp500-etf',
    name: 'S&P500 ETF',
    description: 'S&P500 추종 ETF 운용사별 비교',
    stocks: [
      { code: '360750', name: 'TIGER 미국S&P500' },
      { code: '379800', name: 'KODEX 미국S&P500' },
      { code: '360200', name: 'ACE 미국S&P500' },
      { code: '379780', name: 'RISE 미국S&P500' },
      { code: '433330', name: 'SOL 미국S&P500' },
    ],
  },
  {
    id: 'nasdaq100-etf',
    name: '나스닥100 ETF',
    description: '나스닥100 추종 ETF 운용사별 비교',
    stocks: [
      { code: '133690', name: 'TIGER 미국나스닥100' },
      { code: '379810', name: 'KODEX 미국나스닥100' },
      { code: '367380', name: 'ACE 미국나스닥100' },
      { code: '368590', name: 'RISE 미국나스닥100' },
    ],
  },
  {
    id: 'us-dividend',
    name: '미국배당다우존스',
    description: '한국판 SCHD 운용사별 비교',
    stocks: [
      { code: '458730', name: 'TIGER 미국배당다우존스' },
      { code: '446720', name: 'SOL 미국배당다우존스' },
      { code: '402970', name: 'ACE 미국배당다우존스' },
    ],
  },
  {
    id: 'us-tech-top10',
    name: '미국테크TOP10',
    description: '미국 빅테크 집중투자 ETF 비교',
    stocks: [
      { code: '381170', name: 'TIGER 미국테크TOP10 INDXX' },
      { code: '473460', name: 'SOL 미국테크TOP10' },
      { code: '466920', name: 'ACE 미국빅테크TOP7 Plus' },
    ],
  },
  {
    id: 'covered-call',
    name: '커버드콜',
    description: '커버드콜 전략 ETF 비교',
    stocks: [
      { code: '441680', name: 'TIGER 미국나스닥100커버드콜(합성)' },
      { code: '441640', name: 'KODEX 미국배당커버드콜액티브' },
      { code: '482730', name: 'TIGER 미국S&P500타겟데일리커버드콜' },
    ],
  },
];

function getDateRange(period: Period): { start: string; end: string } {
  const end = new Date();
  const start = new Date();
  switch (period) {
    case '1M': start.setMonth(start.getMonth() - 1); break;
    case '3M': start.setMonth(start.getMonth() - 3); break;
    case '6M': start.setMonth(start.getMonth() - 6); break;
    case '1Y': start.setFullYear(start.getFullYear() - 1); break;
    case '5Y': start.setFullYear(start.getFullYear() - 5); break;
  }
  return {
    start: start.toISOString().split('T')[0],
    end: end.toISOString().split('T')[0],
  };
}

interface SelectedStock {
  code: string;
  name: string;
}

function CompareSearchInput({ onSelect, selectedCodes }: {
  onSelect: (stock: SelectedStock) => void;
  selectedCodes: string[];
}) {
  const [query, setQuery] = useState('');
  const [isFocused, setIsFocused] = useState(false);
  const debouncedQuery = useDebounce(query, 300);
  const { data: searchResults, isLoading } = useStockSearch(debouncedQuery, 10);

  const showResults = isFocused && query.length > 0;

  const handleSelect = useCallback((code: string, name: string) => {
    onSelect({ code, name });
    setQuery('');
    setIsFocused(false);
  }, [onSelect]);

  return (
    <div className="relative w-full max-w-md">
      <div className="relative">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
        <Input
          placeholder="비교할 종목을 검색하세요..."
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onFocus={() => setIsFocused(true)}
          onBlur={() => setTimeout(() => setIsFocused(false), 200)}
          className="pl-10"
        />
      </div>

      {showResults && (
        <Card className="absolute top-full mt-2 w-full z-50 shadow-lg">
          <CardContent className="p-2">
            {isLoading ? (
              <div className="p-4 text-center text-muted-foreground">검색 중...</div>
            ) : searchResults && searchResults.results.length > 0 ? (
              <div className="space-y-1">
                {searchResults.results.map((stock) => {
                  const alreadySelected = selectedCodes.includes(stock.code);
                  return (
                    <button
                      key={stock.code}
                      onClick={() => !alreadySelected && handleSelect(stock.code, stock.name)}
                      disabled={alreadySelected}
                      className={`w-full flex items-center justify-between p-3 rounded-lg text-left transition-colors ${
                        alreadySelected ? 'opacity-40 cursor-not-allowed' : 'hover:bg-muted'
                      }`}
                    >
                      <div>
                        <div className="font-medium">{stock.name}</div>
                        <div className="text-sm text-muted-foreground">
                          {stock.code} · {stock.market}
                        </div>
                      </div>
                      {alreadySelected && (
                        <Badge variant="outline" className="text-xs">추가됨</Badge>
                      )}
                    </button>
                  );
                })}
              </div>
            ) : (
              <div className="p-4 text-center text-muted-foreground">검색 결과가 없습니다.</div>
            )}
          </CardContent>
        </Card>
      )}
    </div>
  );
}

export default function ComparePage() {
  const { theme, setTheme } = useTheme();
  const router = useRouter();
  const searchParams = useSearchParams();

  const [selectedStocks, setSelectedStocks] = useState<SelectedStock[]>([]);
  const [selectedPeriod, setSelectedPeriod] = useState<Period>(() => {
    const p = searchParams.get('period');
    return PERIODS.includes(p as Period) ? (p as Period) : '3M';
  });
  const [initialized, setInitialized] = useState(false);

  useEffect(() => {
    if (initialized) return;
    
    const codesParam = searchParams.get('codes');
    if (codesParam) {
      const codes = codesParam.split(',').filter(Boolean);
      setSelectedStocks(codes.map((code) => ({ code, name: code })));
    } else {
      setSelectedStocks(PRESETS[0].stocks);
    }
    setInitialized(true);
  }, [searchParams, initialized]);

  const dateRange = useMemo(() => getDateRange(selectedPeriod), [selectedPeriod]);
  const codes = useMemo(() => selectedStocks.map((s) => s.code), [selectedStocks]);

  const { data: compareData, isLoading: compareLoading, isFetching } = useCompareStocksUsd(
    codes,
    dateRange.start,
    dateRange.end
  );

  useEffect(() => {
    if (!initialized) return;
    const params = new URLSearchParams();
    if (codes.length > 0) params.set('codes', codes.join(','));
    if (selectedPeriod !== '3M') params.set('period', selectedPeriod);
    const qs = params.toString();
    router.replace(`/compare${qs ? `?${qs}` : ''}`, { scroll: false });
  }, [codes, selectedPeriod, initialized, router]);

  useEffect(() => {
    if (compareData && selectedStocks.some((s) => s.name === s.code)) {
      setSelectedStocks((prev) =>
        prev.map((s) => {
          const stockData = compareData.stocks[s.code];
          return stockData ? { ...s, name: stockData.name } : s;
        })
      );
    }
  }, [compareData, selectedStocks]);

  const handleAddStock = useCallback((stock: SelectedStock) => {
    setSelectedStocks((prev) => {
      if (prev.length >= 10) return prev;
      if (prev.some((s) => s.code === stock.code)) return prev;
      return [...prev, stock];
    });
  }, []);

  const handlePresetSelect = useCallback((preset: Preset) => {
    setSelectedStocks(preset.stocks.slice(0, 10));
  }, []);

  const handleRemoveStock = useCallback((code: string) => {
    setSelectedStocks((prev) => prev.filter((s) => s.code !== code));
  }, []);

  const chartConfig = useMemo(() => {
    const config: ChartConfig = {};
    selectedStocks.forEach((stock, i) => {
      config[stock.code] = {
        label: stock.name !== stock.code ? stock.name : stock.code,
        color: CHART_COLORS[i % CHART_COLORS.length],
      };
    });
    return config;
  }, [selectedStocks]);

  const chartData = useMemo(() => {
    if (!compareData?.stocks) return [];

    const allDates = new Set<string>();
    Object.values(compareData.stocks).forEach((stock) => {
      stock.data.forEach((d) => allDates.add(d.date));
    });

    const sortedDates = Array.from(allDates).sort();
    return sortedDates.map((date) => {
      const point: Record<string, string | number> = { date };
      let exchangeRate: number | null = null;
      
      Object.entries(compareData.stocks).forEach(([code, stock]) => {
        const dayData = stock.data.find((d) => d.date === date);
        if (dayData) {
          point[code] = dayData.normalized;
          if (exchangeRate === null && dayData.krw && dayData.usd) {
            exchangeRate = dayData.krw / dayData.usd;
          }
        }
      });
      
      if (exchangeRate !== null) {
        point.exchangeRate = exchangeRate;
      }
      return point;
    });
  }, [compareData]);

  const formatDate = (value: string) => {
    const d = new Date(value);
    return `${d.getMonth() + 1}/${d.getDate()}`;
  };

  const CustomTooltip = useCallback(({ active, payload, label }: TooltipProps<number, string>) => {
    if (!active || !payload || payload.length === 0 || !label) return null;

    const date = new Date(label);
    const formattedDate = `${date.getFullYear()}.${String(date.getMonth() + 1).padStart(2, '0')}.${String(date.getDate()).padStart(2, '0')}`;
    
    const firstPayload = payload[0]?.payload as Record<string, number> | undefined;
    const exchangeRate = firstPayload?.exchangeRate;
    
    const sortedPayload = [...payload]
      .filter((p) => p.dataKey !== 'exchangeRate' && typeof p.value === 'number')
      .sort((a, b) => (b.value as number) - (a.value as number));

    return (
      <div className="bg-background border rounded-lg shadow-lg p-3 min-w-[180px]">
        <div className="text-sm font-medium mb-2">{formattedDate}</div>
        {exchangeRate && (
          <div className="text-xs text-muted-foreground mb-2 pb-2 border-b">
            USD/KRW: {exchangeRate.toFixed(2)}원
          </div>
        )}
        <div className="space-y-1.5">
          {sortedPayload.map((entry) => {
            const code = String(entry.dataKey);
            const stock = selectedStocks.find((s) => s.code === code);
            const stockName = stock?.name !== stock?.code ? stock?.name : code;
            const returnPct = (entry.value as number) - 100;
            return (
              <div key={code} className="flex items-center justify-between gap-3 text-sm">
                <div className="flex items-center gap-2">
                  <span
                    className="w-2.5 h-2.5 rounded-full flex-shrink-0"
                    style={{ backgroundColor: entry.color }}
                  />
                  <span className="truncate max-w-[100px]">{stockName}</span>
                </div>
                <span className={returnPct >= 0 ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'}>
                  {returnPct >= 0 ? '+' : ''}{returnPct.toFixed(2)}%
                </span>
              </div>
            );
          })}
        </div>
      </div>
    );
  }, [selectedStocks]);

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

      <main className="container mx-auto px-4 py-8">
        <div className="mb-8">
          <h2 className="text-2xl font-bold mb-2">종목 비교</h2>
          <p className="text-muted-foreground">
            최대 10개 종목의 USD 환산 수익률을 비교합니다. (기준값 = 100)
          </p>
        </div>

        <div className="flex flex-col sm:flex-row gap-4 mb-4">
          <CompareSearchInput
            onSelect={handleAddStock}
            selectedCodes={codes}
          />
          {selectedStocks.length >= 10 && (
            <p className="text-sm text-destructive self-center">최대 10개까지 추가 가능합니다.</p>
          )}
        </div>

        <div className="mb-6">
          <div className="flex items-center gap-2 mb-3">
            <Sparkles className="h-4 w-4 text-muted-foreground" />
            <span className="text-sm text-muted-foreground">빠른 선택</span>
          </div>
          <div className="flex flex-wrap gap-2">
            {PRESETS.map((preset) => (
              <button
                key={preset.id}
                onClick={() => handlePresetSelect(preset)}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm rounded-full border border-border bg-background hover:bg-muted hover:border-primary/50 transition-colors"
                title={preset.description}
              >
                {preset.name}
                <span className="text-xs text-muted-foreground">({preset.stocks.length})</span>
              </button>
            ))}
          </div>
        </div>

        {selectedStocks.length > 0 && (
          <div className="flex flex-wrap gap-2 mb-6">
            {selectedStocks.map((stock, i) => (
              <Badge
                key={stock.code}
                variant="secondary"
                className="text-sm py-1.5 px-3 gap-2"
              >
                <span
                  className="w-2.5 h-2.5 rounded-full inline-block"
                  style={{ backgroundColor: CHART_COLORS[i % CHART_COLORS.length] }}
                />
                {stock.name !== stock.code ? stock.name : stock.code}
                <button
                  onClick={() => handleRemoveStock(stock.code)}
                  className="hover:text-destructive transition-colors"
                >
                  <X className="h-3.5 w-3.5" />
                </button>
              </Badge>
            ))}
          </div>
        )}

        {selectedStocks.length > 0 && (
          <div className="flex gap-2 mb-6">
            {PERIODS.map((p) => (
              <button
                key={p}
                onClick={() => setSelectedPeriod(p)}
                disabled={isFetching}
                className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                  selectedPeriod === p
                    ? 'bg-primary text-primary-foreground'
                    : 'bg-muted text-muted-foreground hover:bg-muted/80'
                } ${isFetching ? 'opacity-60' : ''}`}
              >
                {p}
              </button>
            ))}
            {isFetching && (
              <div className="flex items-center ml-2">
                <div className="h-4 w-4 border-2 border-primary border-t-transparent rounded-full animate-spin" />
              </div>
            )}
          </div>
        )}

        {selectedStocks.length === 0 ? (
          <Card>
            <CardContent className="py-16 text-center">
              <div className="text-4xl mb-4 opacity-20">
                <TrendingUp className="h-16 w-16 mx-auto" />
              </div>
              <p className="text-lg font-medium text-muted-foreground mb-2">
                종목을 추가하여 USD 수익률을 비교해보세요
              </p>
              <p className="text-sm text-muted-foreground">
                위 검색창에서 종목을 검색하고 클릭하면 비교 차트에 추가됩니다.
              </p>
            </CardContent>
          </Card>
        ) : compareLoading && !compareData ? (
          <Card>
            <CardContent className="py-8">
              <Skeleton className="h-[400px] w-full" />
            </CardContent>
          </Card>
        ) : chartData.length > 0 ? (
          <Card>
            <CardHeader>
              <CardTitle>USD 환산 정규화 수익률</CardTitle>
            </CardHeader>
            <CardContent>
              <div className={`transition-opacity duration-200 ${isFetching ? 'opacity-50' : 'opacity-100'}`}>
                <ChartContainer config={chartConfig} className="h-[400px] w-full aspect-auto">
                  <LineChart data={chartData}>
                    <CartesianGrid strokeDasharray="3 3" vertical={false} />
                    <XAxis
                      dataKey="date"
                      tickLine={false}
                      axisLine={false}
                      tickFormatter={formatDate}
                      tick={{ fontSize: 12 }}
                    />
                    <YAxis
                      tickLine={false}
                      axisLine={false}
                      tickFormatter={(v) => `${v.toFixed(0)}`}
                      tick={{ fontSize: 12 }}
                      width={50}
                    />
                    <ReferenceLine y={100} stroke="var(--border)" strokeDasharray="3 3" />
                    <ChartTooltip content={CustomTooltip} />
                    <Legend />
                    {selectedStocks.map((stock, i) => (
                      <Line
                        key={stock.code}
                        type="monotone"
                        dataKey={stock.code}
                        stroke={CHART_COLORS[i % CHART_COLORS.length]}
                        strokeWidth={2}
                        dot={false}
                        name={stock.name !== stock.code ? stock.name : stock.code}
                        connectNulls
                      />
                    ))}
                  </LineChart>
                </ChartContainer>
              </div>
            </CardContent>
          </Card>
        ) : null}

        {compareData?.stocks && selectedStocks.length > 0 && (
          <Card className="mt-6">
            <CardContent className="p-0">
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead>
                    <tr className="border-b text-sm text-muted-foreground">
                      <th className="text-left p-4 font-medium">종목</th>
                      <th className="text-right p-4 font-medium">시작가 (USD)</th>
                      <th className="text-right p-4 font-medium">현재가 (USD)</th>
                      <th className="text-right p-4 font-medium">수익률</th>
                    </tr>
                  </thead>
                  <tbody>
                    {selectedStocks
                      .map((stock, i) => {
                        const stockData = compareData.stocks[stock.code];
                        if (!stockData || stockData.data.length < 2) return null;
                        const first = stockData.data[0];
                        const last = stockData.data[stockData.data.length - 1];
                        const returnPct = last.normalized - 100;
                        return { stock, stockData, first, last, returnPct, colorIndex: i };
                      })
                      .filter((item): item is NonNullable<typeof item> => item !== null)
                      .sort((a, b) => b.returnPct - a.returnPct)
                      .map(({ stock, stockData, first, last, returnPct, colorIndex }) => {
                        const isPositive = returnPct >= 0;
                        return (
                          <tr key={stock.code} className="border-b last:border-b-0 hover:bg-muted/50 transition-colors">
                            <td className="p-4">
                              <Link href={`/stocks/${stock.code}`} className="flex items-center gap-2 hover:underline">
                                <span
                                  className="w-3 h-3 rounded-full flex-shrink-0"
                                  style={{ backgroundColor: CHART_COLORS[colorIndex % CHART_COLORS.length] }}
                                />
                                <span className="font-medium">{stockData.name}</span>
                                <span className="text-sm text-muted-foreground">{stock.code}</span>
                              </Link>
                            </td>
                            <td className="p-4 text-right font-mono">${first.usd.toFixed(2)}</td>
                            <td className="p-4 text-right font-mono">${last.usd.toFixed(2)}</td>
                            <td className="p-4 text-right">
                              <span className={`inline-flex items-center text-xs font-mono px-2 py-1 rounded-md ${
                                isPositive 
                                  ? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400' 
                                  : 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400'
                              }`}>
                                {isPositive ? <TrendingUp className="h-3 w-3 mr-1" /> : <TrendingDown className="h-3 w-3 mr-1" />}
                                {isPositive ? '+' : ''}{returnPct.toFixed(2)}%
                              </span>
                            </td>
                          </tr>
                        );
                      })}
                  </tbody>
                </table>
              </div>
            </CardContent>
          </Card>
        )}
      </main>
    </div>
  );
}
