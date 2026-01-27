"use client";

import { Chip, Skeleton } from "@heroui/react";
import { useMarketStatus } from "@/hooks";

const statusConfig: Record<string, { color: "success" | "warning" | "danger" | "default"; label: string }> = {
  market_open: { color: "success", label: "Market Open" },
  pre_market: { color: "warning", label: "Pre-Market" },
  market_close: { color: "default", label: "Market Closed" },
  after_hours: { color: "default", label: "After Hours" },
};

export function MarketStatusBadge() {
  const { data, isLoading, error } = useMarketStatus();

  if (isLoading) {
    return <Skeleton className="w-24 h-6 rounded-full" />;
  }

  if (error || !data) {
    return (
      <Chip size="sm" variant="flat" color="default">
        Unknown
      </Chip>
    );
  }

  const config = statusConfig[data.status] || { color: "default", label: data.status };

  return (
    <div className="flex items-center gap-2">
      <Chip size="sm" variant="dot" color={config.color}>
        {config.label}
      </Chip>
      <span className="text-tiny text-default-400">
        {data.current_time_kst}
      </span>
    </div>
  );
}
