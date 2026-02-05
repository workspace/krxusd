/**
 * USD Price Chart Component - 핵심 컴포넌트
 * 
 * KRW 주가를 환율로 나눈 USD 환산 가격 차트를 표시합니다.
 */
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
  ResponsiveContainer,
  Legend,
  Area,
  ComposedChart,
} from 'recharts';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import type { UsdConvertedData } from '@/lib/api';

interface UsdPriceChartProps {
  data: UsdConvertedData[];
  stockName: string;
  stockCode: string;
}

const chartConfig = {
  usd_close: {
    label: 'USD 가격',
    color: 'hsl(var(--chart-1))',
  },
  krw_close: {
    label: 'KRW 가격',
    color: 'hsl(var(--chart-2))',
  },
  exchange_rate: {
    label: '환율',
    color: 'hsl(var(--chart-3))',
  },
} satisfies ChartConfig;

export function UsdPriceChart({ data, stockName, stockCode }: UsdPriceChartProps) {
  // Format data for charts
  const chartData = useMemo(() => {
    return data.map((item) => ({
      date: item.date,
      usd_close: item.usd_close,
      krw_close: item.krw_close,
      exchange_rate: item.exchange_rate,
      // For display in tooltip
      formattedDate: new Date(item.date).toLocaleDateString('ko-KR'),
    }));
  }, [data]);

  // Calculate price change
  const priceChange = useMemo(() => {
    if (data.length < 2) return { usd: 0, krw: 0 };
    const first = data[0];
    const last = data[data.length - 1];
    return {
      usd: ((last.usd_close - first.usd_close) / first.usd_close) * 100,
      krw: ((last.krw_close - first.krw_close) / first.krw_close) * 100,
    };
  }, [data]);

  const formatUsd = (value: number) => `$${value.toFixed(2)}`;
  const formatKrw = (value: number) => `₩${value.toLocaleString()}`;
  const formatDate = (value: string) => {
    const date = new Date(value);
    return `${date.getMonth() + 1}/${date.getDate()}`;
  };

  return (
    <Card className="w-full">
      <CardHeader>
        <div className="flex items-center justify-between">
          <div>
            <CardTitle className="text-2xl">
              {stockName} ({stockCode})
            </CardTitle>
            <CardDescription>
              USD 환산 주가 차트 - KRW 가격 / 환율
            </CardDescription>
          </div>
          <div className="text-right">
            <div className="text-sm text-muted-foreground">기간 수익률</div>
            <div className="flex gap-4">
              <div>
                <span className="text-sm text-muted-foreground">USD: </span>
                <span className={priceChange.usd >= 0 ? 'text-green-600' : 'text-red-600'}>
                  {priceChange.usd >= 0 ? '+' : ''}{priceChange.usd.toFixed(2)}%
                </span>
              </div>
              <div>
                <span className="text-sm text-muted-foreground">KRW: </span>
                <span className={priceChange.krw >= 0 ? 'text-green-600' : 'text-red-600'}>
                  {priceChange.krw >= 0 ? '+' : ''}{priceChange.krw.toFixed(2)}%
                </span>
              </div>
            </div>
          </div>
        </div>
      </CardHeader>
      <CardContent>
        <Tabs defaultValue="usd" className="w-full">
          <TabsList className="mb-4">
            <TabsTrigger value="usd">USD 환산 가격</TabsTrigger>
            <TabsTrigger value="compare">KRW vs USD 비교</TabsTrigger>
            <TabsTrigger value="exchange">환율 추이</TabsTrigger>
          </TabsList>

          {/* USD 환산 가격 탭 - 핵심 차트 */}
          <TabsContent value="usd">
            <ChartContainer config={chartConfig} className="h-[400px] w-full">
              <ComposedChart data={chartData}>
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
                  tickFormatter={formatUsd}
                  tick={{ fontSize: 12 }}
                  width={80}
                />
                <ChartTooltip
                  content={
                    <ChartTooltipContent
                      formatter={(value, name) => {
                        if (name === 'usd_close') {
                          return [formatUsd(value as number), 'USD 가격'];
                        }
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
                <Area
                  type="monotone"
                  dataKey="usd_close"
                  stroke="hsl(var(--chart-1))"
                  fill="url(#usdGradient)"
                  strokeWidth={2}
                />
              </ComposedChart>
            </ChartContainer>
          </TabsContent>

          {/* KRW vs USD 비교 탭 */}
          <TabsContent value="compare">
            <ChartContainer config={chartConfig} className="h-[400px] w-full">
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
                  yAxisId="usd"
                  tickLine={false}
                  axisLine={false}
                  tickFormatter={formatUsd}
                  tick={{ fontSize: 12 }}
                  width={80}
                  orientation="left"
                />
                <YAxis
                  yAxisId="krw"
                  tickLine={false}
                  axisLine={false}
                  tickFormatter={formatKrw}
                  tick={{ fontSize: 12 }}
                  width={100}
                  orientation="right"
                />
                <ChartTooltip
                  content={
                    <ChartTooltipContent
                      formatter={(value, name) => {
                        if (name === 'usd_close') {
                          return [formatUsd(value as number), 'USD'];
                        }
                        if (name === 'krw_close') {
                          return [formatKrw(value as number), 'KRW'];
                        }
                        return [value, name];
                      }}
                    />
                  }
                />
                <Legend />
                <Line
                  yAxisId="usd"
                  type="monotone"
                  dataKey="usd_close"
                  stroke="hsl(var(--chart-1))"
                  strokeWidth={2}
                  dot={false}
                  name="USD 가격"
                />
                <Line
                  yAxisId="krw"
                  type="monotone"
                  dataKey="krw_close"
                  stroke="hsl(var(--chart-2))"
                  strokeWidth={2}
                  dot={false}
                  name="KRW 가격"
                />
              </LineChart>
            </ChartContainer>
          </TabsContent>

          {/* 환율 추이 탭 */}
          <TabsContent value="exchange">
            <ChartContainer config={chartConfig} className="h-[400px] w-full">
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
                  tickFormatter={(v) => `₩${v.toLocaleString()}`}
                  tick={{ fontSize: 12 }}
                  width={80}
                  domain={['dataMin - 50', 'dataMax + 50']}
                />
                <ChartTooltip
                  content={
                    <ChartTooltipContent
                      formatter={(value) => [
                        `₩${(value as number).toLocaleString()}`,
                        'USD/KRW 환율',
                      ]}
                    />
                  }
                />
                <Line
                  type="monotone"
                  dataKey="exchange_rate"
                  stroke="hsl(var(--chart-3))"
                  strokeWidth={2}
                  dot={false}
                  name="환율"
                />
              </LineChart>
            </ChartContainer>
          </TabsContent>
        </Tabs>
      </CardContent>
    </Card>
  );
}
