'use client';

import { useMemo } from 'react';
import {
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
  type ChartConfig,
} from '@/components/ui/chart';
import {
  Line,
  LineChart,
  XAxis,
  YAxis,
  CartesianGrid,
  Legend,
  Area,
  ComposedChart,
  ReferenceLine,
} from 'recharts';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import type { UsdConvertedData } from '@/lib/api';
import { calculateAnalysis } from '@/lib/analysis';

interface UsdPriceChartProps {
  data: UsdConvertedData[];
  stockName: string;
  stockCode: string;
}

const chartConfig = {
  usd_close: { label: 'USD 가격', color: 'hsl(var(--chart-1))' },
  krw_close: { label: 'KRW 가격', color: 'hsl(var(--chart-2))' },
  exchange_rate: { label: '환율', color: 'hsl(var(--chart-3))' },
  usd: { label: 'USD 수익률', color: 'hsl(var(--chart-1))' },
  krw: { label: 'KRW 수익률', color: 'hsl(var(--chart-2))' },
  usdDrawdown: { label: 'USD 낙폭', color: 'hsl(var(--chart-1))' },
  krwDrawdown: { label: 'KRW 낙폭', color: 'hsl(var(--chart-2))' },
} satisfies ChartConfig;

export function UsdPriceChart({ data, stockName, stockCode }: UsdPriceChartProps) {
  const chartData = useMemo(() => {
    return data.map((item) => ({
      date: item.date,
      usd_close: item.usd_close,
      krw_close: item.krw_close,
      exchange_rate: item.exchange_rate,
      formattedDate: new Date(item.date).toLocaleDateString('ko-KR'),
    }));
  }, [data]);

  const priceChange = useMemo(() => {
    if (data.length < 2) return { usd: 0, krw: 0 };
    const first = data[0];
    const last = data[data.length - 1];
    return {
      usd: ((last.usd_close - first.usd_close) / first.usd_close) * 100,
      krw: ((last.krw_close - first.krw_close) / first.krw_close) * 100,
    };
  }, [data]);

  const analysis = useMemo(() => {
    if (data.length < 2) return null;
    return calculateAnalysis(data);
  }, [data]);

  const formatUsd = (value: number) => `$${value.toFixed(2)}`;
  const formatKrw = (value: number) => `₩${value.toLocaleString()}`;
  const formatPercent = (value: number) => `${value.toFixed(1)}%`;
  const formatDate = (value: string) => {
    const d = new Date(value);
    return `${d.getMonth() + 1}/${d.getDate()}`;
  };

  return (
    <Card className="w-full">
      <CardHeader>
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
          <div>
            <CardTitle className="text-xl sm:text-2xl">
              {stockName} ({stockCode})
            </CardTitle>
            <CardDescription>
              USD 환산 주가 차트
            </CardDescription>
          </div>
          <div className="text-right">
            <div className="text-sm text-muted-foreground">기간 수익률</div>
            <div className="flex gap-4">
              <div>
                <span className="text-sm text-muted-foreground">USD: </span>
                <span className={priceChange.usd >= 0 ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'}>
                  {priceChange.usd >= 0 ? '+' : ''}{priceChange.usd.toFixed(2)}%
                </span>
              </div>
              <div>
                <span className="text-sm text-muted-foreground">KRW: </span>
                <span className={priceChange.krw >= 0 ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'}>
                  {priceChange.krw >= 0 ? '+' : ''}{priceChange.krw.toFixed(2)}%
                </span>
              </div>
            </div>
          </div>
        </div>
      </CardHeader>
      <CardContent>
        <Tabs defaultValue="usd" className="w-full">
          <TabsList className="mb-4 flex-wrap h-auto gap-1">
            <TabsTrigger value="usd">USD 환산</TabsTrigger>
            <TabsTrigger value="compare">KRW vs USD</TabsTrigger>
            <TabsTrigger value="returns">수익률 비교</TabsTrigger>
            <TabsTrigger value="drawdown">낙폭 분석</TabsTrigger>
            <TabsTrigger value="exchange">환율</TabsTrigger>
          </TabsList>

          <TabsContent value="usd">
            <ChartContainer config={chartConfig} className="h-[400px] w-full">
              <ComposedChart data={chartData}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} />
                <XAxis dataKey="date" tickLine={false} axisLine={false} tickFormatter={formatDate} tick={{ fontSize: 12 }} />
                <YAxis tickLine={false} axisLine={false} tickFormatter={formatUsd} tick={{ fontSize: 12 }} width={80} />
                <ChartTooltip
                  content={
                    <ChartTooltipContent
                      formatter={(value, name) => {
                        if (name === 'usd_close') return [formatUsd(value as number), 'USD 가격'];
                        return [value, name];
                      }}
                    />
                  }
                />
                <defs>
                  <linearGradient id="usdGradient" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="hsl(var(--chart-1))" stopOpacity={0.3} />
                    <stop offset="95%" stopColor="hsl(var(--chart-1))" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <Area type="monotone" dataKey="usd_close" stroke="hsl(var(--chart-1))" fill="url(#usdGradient)" strokeWidth={2} />
              </ComposedChart>
            </ChartContainer>
          </TabsContent>

          <TabsContent value="compare">
            <ChartContainer config={chartConfig} className="h-[400px] w-full">
              <LineChart data={chartData}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} />
                <XAxis dataKey="date" tickLine={false} axisLine={false} tickFormatter={formatDate} tick={{ fontSize: 12 }} />
                <YAxis yAxisId="usd" tickLine={false} axisLine={false} tickFormatter={formatUsd} tick={{ fontSize: 12 }} width={80} orientation="left" />
                <YAxis yAxisId="krw" tickLine={false} axisLine={false} tickFormatter={formatKrw} tick={{ fontSize: 12 }} width={100} orientation="right" />
                <ChartTooltip
                  content={
                    <ChartTooltipContent
                      formatter={(value, name) => {
                        if (name === 'usd_close') return [formatUsd(value as number), 'USD'];
                        if (name === 'krw_close') return [formatKrw(value as number), 'KRW'];
                        return [value, name];
                      }}
                    />
                  }
                />
                <Legend />
                <Line yAxisId="usd" type="monotone" dataKey="usd_close" stroke="hsl(var(--chart-1))" strokeWidth={2} dot={false} name="USD 가격" />
                <Line yAxisId="krw" type="monotone" dataKey="krw_close" stroke="hsl(var(--chart-2))" strokeWidth={2} dot={false} name="KRW 가격" />
              </LineChart>
            </ChartContainer>
          </TabsContent>

          <TabsContent value="returns">
            {analysis && (
              <>
                <div className="flex gap-4 mb-3 text-sm">
                  <span className="text-muted-foreground">
                    환율 영향: <span className={analysis.attribution.fxEffect >= 0 ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'}>
                      {analysis.attribution.fxEffect >= 0 ? '+' : ''}{analysis.attribution.fxEffect.toFixed(2)}%p
                    </span>
                  </span>
                  <span className="text-muted-foreground">
                    주가 수익: <span className={analysis.attribution.stockReturn >= 0 ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'}>
                      {analysis.attribution.stockReturn >= 0 ? '+' : ''}{analysis.attribution.stockReturn.toFixed(2)}%
                    </span>
                  </span>
                </div>
                <ChartContainer config={chartConfig} className="h-[400px] w-full">
                  <LineChart data={analysis.normalizedReturns}>
                    <CartesianGrid strokeDasharray="3 3" vertical={false} />
                    <XAxis dataKey="date" tickLine={false} axisLine={false} tickFormatter={formatDate} tick={{ fontSize: 12 }} />
                    <YAxis tickLine={false} axisLine={false} tickFormatter={(v) => `${v.toFixed(0)}`} tick={{ fontSize: 12 }} width={50} />
                    <ReferenceLine y={100} stroke="hsl(var(--border))" strokeDasharray="3 3" />
                    <ChartTooltip
                      content={
                        <ChartTooltipContent
                          formatter={(value, name) => {
                            const v = (value as number) - 100;
                            const label = name === 'usd' ? 'USD' : 'KRW';
                            return [`${v >= 0 ? '+' : ''}${v.toFixed(2)}%`, label];
                          }}
                        />
                      }
                    />
                    <Legend />
                    <Line type="monotone" dataKey="usd" stroke="hsl(var(--chart-1))" strokeWidth={2} dot={false} name="USD 수익률" />
                    <Line type="monotone" dataKey="krw" stroke="hsl(var(--chart-2))" strokeWidth={2} dot={false} name="KRW 수익률" />
                  </LineChart>
                </ChartContainer>
              </>
            )}
          </TabsContent>

          <TabsContent value="drawdown">
            {analysis && (
              <>
                <div className="flex gap-4 mb-3 text-sm">
                  <span className="text-muted-foreground">
                    USD MDD: <span className="text-red-600 dark:text-red-400">{analysis.drawdown.usdMax.toFixed(1)}%</span>
                  </span>
                  <span className="text-muted-foreground">
                    KRW MDD: <span className="text-red-600 dark:text-red-400">{analysis.drawdown.krwMax.toFixed(1)}%</span>
                  </span>
                </div>
                <ChartContainer config={chartConfig} className="h-[400px] w-full">
                  <ComposedChart data={analysis.drawdown.usdSeries.map((item, i) => ({
                    date: item.date,
                    usdDrawdown: item.value,
                    krwDrawdown: analysis.drawdown.krwSeries[i]?.value ?? 0,
                  }))}>
                    <CartesianGrid strokeDasharray="3 3" vertical={false} />
                    <XAxis dataKey="date" tickLine={false} axisLine={false} tickFormatter={formatDate} tick={{ fontSize: 12 }} />
                    <YAxis tickLine={false} axisLine={false} tickFormatter={formatPercent} tick={{ fontSize: 12 }} width={60} />
                    <ReferenceLine y={0} stroke="hsl(var(--border))" />
                    <ChartTooltip
                      content={
                        <ChartTooltipContent
                          formatter={(value, name) => {
                            const label = name === 'usdDrawdown' ? 'USD 낙폭' : 'KRW 낙폭';
                            return [`${(value as number).toFixed(2)}%`, label];
                          }}
                        />
                      }
                    />
                    <Legend />
                    <defs>
                      <linearGradient id="ddUsdGrad" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="hsl(var(--chart-1))" stopOpacity={0.2} />
                        <stop offset="95%" stopColor="hsl(var(--chart-1))" stopOpacity={0.05} />
                      </linearGradient>
                    </defs>
                    <Area type="monotone" dataKey="usdDrawdown" stroke="hsl(var(--chart-1))" fill="url(#ddUsdGrad)" strokeWidth={2} name="USD 낙폭" />
                    <Line type="monotone" dataKey="krwDrawdown" stroke="hsl(var(--chart-2))" strokeWidth={1.5} dot={false} strokeDasharray="4 2" name="KRW 낙폭" />
                  </ComposedChart>
                </ChartContainer>
              </>
            )}
          </TabsContent>

          <TabsContent value="exchange">
            <ChartContainer config={chartConfig} className="h-[400px] w-full">
              <LineChart data={chartData}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} />
                <XAxis dataKey="date" tickLine={false} axisLine={false} tickFormatter={formatDate} tick={{ fontSize: 12 }} />
                <YAxis tickLine={false} axisLine={false} tickFormatter={(v) => `₩${v.toLocaleString()}`} tick={{ fontSize: 12 }} width={80} domain={['dataMin - 50', 'dataMax + 50']} />
                <ChartTooltip
                  content={
                    <ChartTooltipContent
                      formatter={(value) => [`₩${(value as number).toLocaleString()}`, 'USD/KRW 환율']}
                    />
                  }
                />
                <Line type="monotone" dataKey="exchange_rate" stroke="hsl(var(--chart-3))" strokeWidth={2} dot={false} name="환율" />
              </LineChart>
            </ChartContainer>
          </TabsContent>
        </Tabs>
      </CardContent>
    </Card>
  );
}
