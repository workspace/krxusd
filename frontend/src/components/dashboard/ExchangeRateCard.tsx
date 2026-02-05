/**
 * Exchange Rate Card Component
 * 
 * 현재 USD/KRW 환율을 표시합니다.
 */
'use client';

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { TrendingUp, TrendingDown, DollarSign } from 'lucide-react';
import { useCurrentExchangeRate } from '@/hooks';

export function ExchangeRateCard() {
  const { data, isLoading, error } = useCurrentExchangeRate();

  if (isLoading) {
    return (
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm font-medium flex items-center gap-2">
            <DollarSign className="h-4 w-4" />
            USD/KRW 환율
          </CardTitle>
        </CardHeader>
        <CardContent>
          <Skeleton className="h-8 w-32 mb-2" />
          <Skeleton className="h-4 w-24" />
        </CardContent>
      </Card>
    );
  }

  if (error || !data) {
    return (
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm font-medium flex items-center gap-2">
            <DollarSign className="h-4 w-4" />
            USD/KRW 환율
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-destructive text-sm">환율 정보를 불러올 수 없습니다.</p>
        </CardContent>
      </Card>
    );
  }

  const isPositive = data.change >= 0;

  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-sm font-medium flex items-center gap-2">
          <DollarSign className="h-4 w-4" />
          USD/KRW 환율
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="flex items-baseline gap-2">
          <span className="text-3xl font-bold">
            ₩{data.rate.toLocaleString()}
          </span>
          <Badge variant={isPositive ? 'default' : 'destructive'} className="flex items-center gap-1">
            {isPositive ? (
              <TrendingUp className="h-3 w-3" />
            ) : (
              <TrendingDown className="h-3 w-3" />
            )}
            {isPositive ? '+' : ''}{data.change.toFixed(2)} ({data.change_percent.toFixed(2)}%)
          </Badge>
        </div>
        <p className="text-sm text-muted-foreground mt-1">
          {new Date(data.date).toLocaleDateString('ko-KR')} 기준
        </p>
      </CardContent>
    </Card>
  );
}
