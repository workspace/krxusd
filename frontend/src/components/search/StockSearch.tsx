/**
 * Stock Search Component
 * 
 * 종목 검색 기능을 제공합니다.
 */
'use client';

import { useState, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { Input } from '@/components/ui/input';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Search, TrendingUp, TrendingDown } from 'lucide-react';
import { useStockSearch, useCurrentExchangeRate } from '@/hooks';
import { useDebounce } from '@/hooks/useDebounce';

export function StockSearch() {
  const router = useRouter();
  const [query, setQuery] = useState('');
  const [isFocused, setIsFocused] = useState(false);
  const debouncedQuery = useDebounce(query, 300);
  
  const { data: searchResults, isLoading } = useStockSearch(debouncedQuery, 10);
  const { data: exchangeRate } = useCurrentExchangeRate();

  const handleSelect = useCallback((code: string) => {
    router.push(`/stocks/${code}`);
    setQuery('');
    setIsFocused(false);
  }, [router]);

  const rate = exchangeRate?.rate || 1450;
  const showResults = isFocused && query.length > 0;

  return (
    <div className="relative w-full max-w-lg">
      <div className="relative">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
        <Input
          placeholder="종목명 또는 코드 검색..."
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
              <div className="p-4 text-center text-muted-foreground">
                검색 중...
              </div>
            ) : searchResults && searchResults.results.length > 0 ? (
              <div className="space-y-1">
                {searchResults.results.map((stock) => {
                  const usdPrice = stock.price / rate;
                  const isPositive = stock.change_percent >= 0;

                  return (
                    <button
                      key={stock.code}
                      onClick={() => handleSelect(stock.code)}
                      className="w-full flex items-center justify-between p-3 rounded-lg hover:bg-muted transition-colors text-left"
                    >
                      <div>
                        <div className="font-medium">{stock.name}</div>
                        <div className="text-sm text-muted-foreground">
                          {stock.code} · {stock.market}
                        </div>
                      </div>
                      <div className="text-right">
                        <div className="font-medium">
                          ${usdPrice.toFixed(2)}
                        </div>
                        <div className="flex items-center gap-1 text-sm">
                          <Badge
                            variant={isPositive ? 'default' : 'destructive'}
                            className="text-xs"
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
                    </button>
                  );
                })}
              </div>
            ) : (
              <div className="p-4 text-center text-muted-foreground">
                검색 결과가 없습니다.
              </div>
            )}
          </CardContent>
        </Card>
      )}
    </div>
  );
}
