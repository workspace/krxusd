"use client";

import { useQuery } from "@tanstack/react-query";
import { getExchangeRate, getExchangeRateHistory } from "@/lib/api";

export function useExchangeRate() {
  return useQuery({
    queryKey: ["exchange", "rate"],
    queryFn: async () => {
      const response = await getExchangeRate();
      if (!response.success || !response.data) {
        throw new Error(response.message || "Failed to fetch exchange rate");
      }
      return response.data;
    },
    refetchInterval: 60000, // 1 minute
  });
}

export function useExchangeRateHistory(days: number = 30) {
  return useQuery({
    queryKey: ["exchange", "history", days],
    queryFn: async () => {
      const response = await getExchangeRateHistory(days);
      if (!response.success || !response.data) {
        throw new Error(response.message || "Failed to fetch exchange rate history");
      }
      return response.data;
    },
  });
}
