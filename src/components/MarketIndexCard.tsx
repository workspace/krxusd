"use client";

import { Card, CardBody, CardHeader, Skeleton, Chip } from "@heroui/react";
import { useStockRealtimePrice } from "@/hooks";
import { useExchangeRate } from "@/hooks";
import { formatNumber, formatPercent, formatUSD } from "@/lib/api";

interface MarketIndexCardProps {
  market: "KOSPI" | "KOSDAQ";
  symbol: string;
  title?: string;
}

export function MarketIndexCard({ market, symbol, title }: MarketIndexCardProps) {
  const { data: priceData, isLoading: priceLoading, error: priceError } = useStockRealtimePrice(symbol);
  const { data: exchangeData, isLoading: exchangeLoading } = useExchangeRate();

  const isLoading = priceLoading || exchangeLoading;

  if (isLoading) {
    return (
      <Card className="w-full">
        <CardHeader className="pb-0 pt-4 px-4 flex-col items-start">
          <p className="text-tiny uppercase font-bold text-default-500">{market}</p>
          <Skeleton className="w-24 h-6 rounded mt-1" />
        </CardHeader>
        <CardBody className="py-4">
          <Skeleton className="w-28 h-10 rounded mb-2" />
          <Skeleton className="w-24 h-5 rounded mb-2" />
          <Skeleton className="w-20 h-4 rounded" />
        </CardBody>
      </Card>
    );
  }

  if (priceError || !priceData) {
    return (
      <Card className="w-full">
        <CardHeader className="pb-0 pt-4 px-4 flex-col items-start">
          <p className="text-tiny uppercase font-bold text-default-500">{market}</p>
          <h4 className="font-bold text-large">{title || "Index"}</h4>
        </CardHeader>
        <CardBody className="py-4">
          <p className="text-default-400">Unable to load data</p>
        </CardBody>
      </Card>
    );
  }

  const price = parseFloat(priceData.close_price);
  const changePercent = parseFloat(priceData.change_percent);
  const change = parseFloat(priceData.change);
  const isPositive = changePercent > 0;
  const isNegative = changePercent < 0;

  // Calculate USD equivalent if we have exchange rate
  const exchangeRate = exchangeData ? parseFloat(exchangeData.rate) : null;
  const priceUSD = exchangeRate ? price / exchangeRate : null;

  return (
    <Card className="w-full">
      <CardHeader className="pb-0 pt-4 px-4 flex-col items-start">
        <div className="flex items-center justify-between w-full">
          <p className="text-tiny uppercase font-bold text-default-500">{market}</p>
          <Chip
            size="sm"
            variant="flat"
            color={isPositive ? "success" : isNegative ? "danger" : "default"}
            className="text-tiny"
          >
            {formatPercent(changePercent)}
          </Chip>
        </div>
        <h4 className="font-bold text-large">{title || priceData.symbol}</h4>
      </CardHeader>
      <CardBody className="py-4">
        <div className="flex items-baseline gap-2">
          <p className="text-3xl font-bold tabular-nums">
            {formatNumber(price.toFixed(2))}
          </p>
        </div>
        <div className="flex items-center gap-2 mt-1">
          <span
            className={`text-sm font-medium ${
              isPositive
                ? "text-success"
                : isNegative
                ? "text-danger"
                : "text-default-500"
            }`}
          >
            {change > 0 ? "+" : ""}
            {change.toFixed(2)}
          </span>
        </div>
        {priceUSD !== null && (
          <p className="text-small text-default-500 mt-2">
            USD: {formatUSD(priceUSD)}
          </p>
        )}
        <p className="text-tiny text-default-400 mt-2">
          Volume: {formatNumber(priceData.volume)}
        </p>
      </CardBody>
    </Card>
  );
}

// Wrapper components for convenience
export function KospiIndexCard() {
  return <MarketIndexCard market="KOSPI" symbol="KOSPI" title="KOSPI Index" />;
}

export function KosdaqIndexCard() {
  return <MarketIndexCard market="KOSDAQ" symbol="KOSDAQ" title="KOSDAQ Index" />;
}
