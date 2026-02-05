/**
 * Stock Data Hooks
 */
'use client';

import { useQuery } from '@tanstack/react-query';
import {
  searchStocks,
  getPopularStocks,
  getStockInfo,
  getStockHistory,
  getStockUsdHistory,
  getStockCurrentUsd,
} from '@/lib/api';

export function useStockSearch(query: string, limit = 20) {
  return useQuery({
    queryKey: ['stocks', 'search', query, limit],
    queryFn: () => searchStocks(query, limit),
    enabled: query.length > 0,
    staleTime: 1000 * 60, // 1 minute
  });
}

export function usePopularStocks(limit = 10) {
  return useQuery({
    queryKey: ['stocks', 'popular', limit],
    queryFn: () => getPopularStocks(limit),
    staleTime: 1000 * 60, // 1 minute
    refetchInterval: 1000 * 60 * 5, // Refetch every 5 minutes
  });
}

export function useStockInfo(code: string) {
  return useQuery({
    queryKey: ['stocks', 'info', code],
    queryFn: () => getStockInfo(code),
    enabled: !!code,
    staleTime: 1000 * 60, // 1 minute
  });
}

export function useStockHistory(code: string, start: string, end?: string) {
  return useQuery({
    queryKey: ['stocks', 'history', code, start, end],
    queryFn: () => getStockHistory(code, start, end),
    enabled: !!code && !!start,
    staleTime: 1000 * 60 * 5, // 5 minutes
  });
}

// 핵심 훅: USD 환산 데이터
export function useStockUsdHistory(code: string, start: string, end?: string) {
  return useQuery({
    queryKey: ['stocks', 'usd', code, start, end],
    queryFn: () => getStockUsdHistory(code, start, end),
    enabled: !!code && !!start,
    staleTime: 1000 * 60 * 5, // 5 minutes
  });
}

export function useStockCurrentUsd(code: string) {
  return useQuery({
    queryKey: ['stocks', 'usd', 'current', code],
    queryFn: () => getStockCurrentUsd(code),
    enabled: !!code,
    staleTime: 1000 * 60, // 1 minute
    refetchInterval: 1000 * 60 * 5, // Refetch every 5 minutes
  });
}
