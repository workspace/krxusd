/**
 * Exchange Rate Hooks
 */
'use client';

import { useQuery } from '@tanstack/react-query';
import { getCurrentExchangeRate, getExchangeHistory } from '@/lib/api';

export function useCurrentExchangeRate() {
  return useQuery({
    queryKey: ['exchangeRate', 'current'],
    queryFn: getCurrentExchangeRate,
    staleTime: 1000 * 60, // 1 minute
    refetchInterval: 1000 * 60 * 5, // Refetch every 5 minutes
  });
}

export function useExchangeHistory(start: string, end?: string) {
  return useQuery({
    queryKey: ['exchangeRate', 'history', start, end],
    queryFn: () => getExchangeHistory(start, end),
    staleTime: 1000 * 60 * 5, // 5 minutes
  });
}
