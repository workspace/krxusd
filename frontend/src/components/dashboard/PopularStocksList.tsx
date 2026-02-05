/**
 * Popular Stocks List Component
 * 
 * 인기 종목 리스트를 표시합니다.
 */
'use client';

import Link from 'next/link';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { TrendingUp, TrendingDown, Flame } from 'lucide-react';
import { usePopularStocks, useCurrentExchangeRate } from '@/hooks';

export function PopularStocksList() {
  const { data: stocks, isLoading: stocksLoading, error: stocksError } = usePopularStocks(10);
  const { data: exchangeRate, isLoading: rateLoading } = useCurrentExchangeRate();

  const isLoading = stocksLoading || rateLoading;

  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Flame className="h-5 w-5 text-orange-500" />
            인기 종목
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            {[...Array(5)].map((_, i) => (
              <div key={i} className="flex items-center justify-between">
                <Skeleton className="h-6 w-32" />
                <Skeleton className="h-6 w-24" />
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    );
  }

  if (stocksError || !stocks) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Flame className="h-5 w-5 text-orange-500" />
            인기 종목
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-destructive text-sm">종목 정보를 불러올 수 없습니다.</p>
        </CardContent>
      </Card>
    );
  }

  const rate = exchangeRate?.rate || 1450;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Flame className="h-5 w-5 text-orange-500" />
          인기 종목
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="space-y-3">
          {stocks.map((stock) => {
            const usdPrice = stock.price / rate;
            const isPositive = stock.change_percent >= 0;

            return (
              <Link
                key={stock.code}
                href={`/stocks/${stock.code}`}
                className="flex items-center justify-between p-3 rounded-lg hover:bg-muted transition-colors"
              >
                <div className="flex items-center gap-3">
                  <div>
                    <div className="font-medium">{stock.name}</div>
                    <div className="text-sm text-muted-foreground">
                      {stock.code} · {stock.market}
                    </div>
                  </div>
                </div>
                <div className="text-right">
                  <div className="font-medium">
                    ${usdPrice.toFixed(2)}
                  </div>
                  <div className="flex items-center gap-1 text-sm">
                    <span className="text-muted-foreground">
                      ₩{stock.price.toLocaleString()}
                    </span>
                    <Badge
                      variant={isPositive ? 'default' : 'destructive'}
                      className="ml-2 text-xs"
                    >
                      {isPositive ? (
                        <TrendingUp className="h-3 w-3 mr-1" />
                      ) : (
                        <TrendingDown className="h-3 w-3 mr-1" />
                      )}
                      {isPositive ? '+' : ''}{stock.change_percent.toFixed(2)}%
                    </Badge>
                  </div>
                </div>
              </Link>
            );
          })}
        </div>
      </CardContent>
    </Card>
  );
}
