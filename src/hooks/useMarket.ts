"use client";

import { useQuery } from "@tanstack/react-query";
import { getMarketStatus, getPopularStocks, getPopularStocksDetail } from "@/lib/api";

export function useMarketStatus() {
  return useQuery({
    queryKey: ["market", "status"],
    queryFn: async () => {
      const response = await getMarketStatus();
      if (!response.success || !response.data) {
        throw new Error(response.message || "Failed to fetch market status");
      }
      return response.data;
    },
    refetchInterval: 60000, // 1 minute
  });
}

export function usePopularStocks() {
  return useQuery({
    queryKey: ["market", "popular"],
    queryFn: async () => {
      const response = await getPopularStocks();
      if (!response.success || !response.data) {
        throw new Error(response.message || "Failed to fetch popular stocks");
      }
      return response.data;
    },
    refetchInterval: 5 * 60 * 1000, // 5 minutes
  });
}

export function usePopularStocksDetail() {
  return useQuery({
    queryKey: ["market", "popular", "detail"],
    queryFn: async () => {
      const response = await getPopularStocksDetail();
      if (!response.success || !response.data) {
        throw new Error(response.message || "Failed to fetch popular stocks detail");
      }
      return response.data;
    },
    refetchInterval: 5 * 60 * 1000, // 5 minutes
  });
}
