"use client";

import { useQuery } from "@tanstack/react-query";
import {
  getStocks,
  getStockDetail,
  getStockRealtimePrice,
  getStocksRealtimePriceBatch,
} from "@/lib/api";

export function useStocks(params?: {
  market?: string;
  search?: string;
  page?: number;
  size?: number;
}) {
  return useQuery({
    queryKey: ["stocks", "list", params],
    queryFn: async () => {
      const response = await getStocks(params);
      if (!response.success || !response.data) {
        throw new Error(response.message || "Failed to fetch stocks");
      }
      return response.data;
    },
  });
}

export function useStockDetail(symbol: string) {
  return useQuery({
    queryKey: ["stocks", "detail", symbol],
    queryFn: async () => {
      const response = await getStockDetail(symbol);
      if (!response.success || !response.data) {
        throw new Error(response.message || "Failed to fetch stock detail");
      }
      return response.data;
    },
    enabled: !!symbol,
  });
}

export function useStockRealtimePrice(symbol: string) {
  return useQuery({
    queryKey: ["stocks", "realtime", symbol],
    queryFn: async () => {
      const response = await getStockRealtimePrice(symbol);
      if (!response.success || !response.data) {
        throw new Error(response.message || "Failed to fetch realtime price");
      }
      return response.data;
    },
    enabled: !!symbol,
    refetchInterval: 60000, // 1 minute
  });
}

export function useStocksRealtimePriceBatch(symbols: string[]) {
  return useQuery({
    queryKey: ["stocks", "realtime", "batch", symbols],
    queryFn: async () => {
      const response = await getStocksRealtimePriceBatch(symbols);
      if (!response.success || !response.data) {
        throw new Error(response.message || "Failed to fetch realtime prices");
      }
      return response.data;
    },
    enabled: symbols.length > 0,
    refetchInterval: 60000, // 1 minute
  });
}
