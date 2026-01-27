"use client";

import {
  Card,
  CardBody,
  CardHeader,
  Skeleton,
  Chip,
  Tabs,
  Tab,
  Divider,
} from "@heroui/react";
import { usePopularStocks, useStocksRealtimePriceBatch, useExchangeRate } from "@/hooks";
import { formatNumber, formatPercent, formatUSD, formatVolume, formatKRW } from "@/lib/api";
import { useMemo } from "react";

interface StockRowProps {
  rank: number;
  symbol: string;
  price: number;
  priceUSD: number | null;
  change: number;
  changePercent: number;
  volume: number;
}

function StockRow({
  rank,
  symbol,
  price,
  priceUSD,
  change,
  changePercent,
  volume,
}: StockRowProps) {
  const isPositive = changePercent > 0;
  const isNegative = changePercent < 0;

  return (
    <div className="flex items-center justify-between py-3 px-1">
      <div className="flex items-center gap-3">
        <span className="text-default-400 font-medium w-6 text-center">
          {rank}
        </span>
        <div>
          <p className="font-medium text-sm">{symbol}</p>
          <p className="text-tiny text-default-400">
            Vol: {formatVolume(volume)}
          </p>
        </div>
      </div>
      <div className="text-right">
        <p className="font-semibold text-sm tabular-nums">
          {formatKRW(price)}
        </p>
        {priceUSD !== null && (
          <p className="text-tiny text-default-500 tabular-nums">
            {formatUSD(priceUSD)}
          </p>
        )}
        <Chip
          size="sm"
          variant="flat"
          color={isPositive ? "success" : isNegative ? "danger" : "default"}
          className="text-tiny mt-1"
        >
          {formatPercent(changePercent)}
        </Chip>
      </div>
    </div>
  );
}

function StockRowSkeleton() {
  return (
    <div className="flex items-center justify-between py-3 px-1">
      <div className="flex items-center gap-3">
        <Skeleton className="w-6 h-5 rounded" />
        <div>
          <Skeleton className="w-16 h-4 rounded mb-1" />
          <Skeleton className="w-12 h-3 rounded" />
        </div>
      </div>
      <div className="flex flex-col items-end gap-1">
        <Skeleton className="w-20 h-4 rounded" />
        <Skeleton className="w-14 h-3 rounded" />
        <Skeleton className="w-12 h-5 rounded" />
      </div>
    </div>
  );
}

export function PopularStocksList() {
  const { data: popularData, isLoading: popularLoading } = usePopularStocks();
  const { data: exchangeData } = useExchangeRate();

  // Get unique symbols from both lists
  const allSymbols = useMemo(() => {
    if (!popularData) return [];
    const combined = [...(popularData.market_cap || []), ...(popularData.volume || [])];
    return [...new Set(combined)];
  }, [popularData]);

  // Fetch real-time prices for all symbols
  const { data: pricesData, isLoading: pricesLoading } = useStocksRealtimePriceBatch(allSymbols);

  const isLoading = popularLoading || pricesLoading;
  const exchangeRate = exchangeData ? parseFloat(exchangeData.rate) : null;

  const renderStockList = (symbols: string[], title: string) => {
    if (!symbols || symbols.length === 0) {
      return (
        <div className="py-8 text-center text-default-400">
          No data available
        </div>
      );
    }

    return (
      <div className="divide-y divide-divider">
        {symbols.slice(0, 10).map((symbol, index) => {
          const priceInfo = pricesData?.prices?.[symbol];

          if (!priceInfo) {
            return <StockRowSkeleton key={symbol} />;
          }

          const price = parseFloat(priceInfo.close_price);
          const priceUSD = exchangeRate ? price / exchangeRate : null;
          const change = parseFloat(priceInfo.change);
          const changePercent = parseFloat(priceInfo.change_percent);

          return (
            <StockRow
              key={symbol}
              rank={index + 1}
              symbol={symbol}
              price={price}
              priceUSD={priceUSD}
              change={change}
              changePercent={changePercent}
              volume={priceInfo.volume}
            />
          );
        })}
      </div>
    );
  };

  if (isLoading && !popularData) {
    return (
      <Card className="w-full">
        <CardHeader className="pb-0 pt-4 px-4 flex-col items-start">
          <p className="text-tiny uppercase font-bold text-default-500">
            Popular Stocks
          </p>
          <Skeleton className="w-32 h-6 rounded mt-1" />
        </CardHeader>
        <CardBody className="py-4">
          {[...Array(5)].map((_, i) => (
            <StockRowSkeleton key={i} />
          ))}
        </CardBody>
      </Card>
    );
  }

  return (
    <Card className="w-full">
      <CardHeader className="pb-2 pt-4 px-4 flex-col items-start">
        <div className="flex items-center justify-between w-full">
          <p className="text-tiny uppercase font-bold text-default-500">
            Popular Stocks
          </p>
          <Chip size="sm" variant="flat" color="secondary" className="text-tiny">
            Top 10
          </Chip>
        </div>
        <h4 className="font-bold text-large">Trending Now</h4>
      </CardHeader>
      <CardBody className="py-2 px-4">
        <Tabs
          aria-label="Popular stocks tabs"
          variant="underlined"
          classNames={{
            tabList: "gap-6 w-full relative rounded-none p-0 border-b border-divider",
            cursor: "w-full bg-primary",
            tab: "max-w-fit px-0 h-10",
            tabContent: "group-data-[selected=true]:text-primary font-medium",
          }}
        >
          <Tab key="market_cap" title="Market Cap">
            {renderStockList(popularData?.market_cap || [], "Market Cap")}
          </Tab>
          <Tab key="volume" title="Volume">
            {renderStockList(popularData?.volume || [], "Volume")}
          </Tab>
        </Tabs>
      </CardBody>
    </Card>
  );
}
