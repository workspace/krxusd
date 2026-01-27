"use client";

import {
  Card,
  CardBody,
  CardHeader,
  Skeleton,
  Chip,
  Tabs,
  Tab,
  Tooltip,
} from "@heroui/react";
import {
  usePopularStocksDetail,
  useStocksRealtimePriceBatch,
  useExchangeRate,
} from "@/hooks";
import {
  formatPercent,
  formatUSD,
  formatVolume,
  formatKRW,
  formatMarketCap,
} from "@/lib/api";
import { useMemo } from "react";

interface MarketCapRowProps {
  rank: number;
  symbol: string;
  name: string;
  market: string;
  marketCapKRW: number | null;
  marketCapUSD: number | null;
  changePercent?: number;
}

function MarketCapRow({
  rank,
  symbol,
  name,
  market,
  marketCapKRW,
  marketCapUSD,
  changePercent,
}: MarketCapRowProps) {
  const isPositive = changePercent !== undefined && changePercent > 0;
  const isNegative = changePercent !== undefined && changePercent < 0;

  return (
    <div className="flex items-center justify-between py-3 px-1">
      <div className="flex items-center gap-3">
        <span className="text-default-400 font-medium w-6 text-center">
          {rank}
        </span>
        <div>
          <div className="flex items-center gap-2">
            <p className="font-medium text-sm">{symbol}</p>
            <Chip size="sm" variant="flat" className="text-tiny h-4">
              {market}
            </Chip>
          </div>
          <Tooltip content={name} placement="bottom">
            <p className="text-tiny text-default-400 truncate max-w-[120px]">
              {name}
            </p>
          </Tooltip>
        </div>
      </div>
      <div className="text-right">
        <p className="font-semibold text-sm tabular-nums">
          {marketCapKRW ? `₩${formatMarketCap(marketCapKRW)}` : "-"}
        </p>
        {marketCapUSD !== null && (
          <p className="text-tiny text-default-500 tabular-nums">
            ${formatMarketCap(marketCapUSD)}
          </p>
        )}
        {changePercent !== undefined && (
          <Chip
            size="sm"
            variant="flat"
            color={isPositive ? "success" : isNegative ? "danger" : "default"}
            className="text-tiny mt-1"
          >
            {formatPercent(changePercent)}
          </Chip>
        )}
      </div>
    </div>
  );
}

interface VolumeRowProps {
  rank: number;
  symbol: string;
  name: string;
  price: number;
  priceUSD: number | null;
  changePercent: number;
  volume: number;
}

function VolumeRow({
  rank,
  symbol,
  name,
  price,
  priceUSD,
  changePercent,
  volume,
}: VolumeRowProps) {
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
        <p className="font-semibold text-sm tabular-nums">{formatKRW(price)}</p>
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

function RowSkeleton() {
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
  const { data: detailData, isLoading: detailLoading } =
    usePopularStocksDetail();
  const { data: exchangeData } = useExchangeRate();

  // Get all unique symbols for real-time prices
  const allSymbols = useMemo(() => {
    if (!detailData) return [];
    const marketCapSymbols = detailData.market_cap?.map((item) => item.symbol) || [];
    const volumeSymbols = detailData.volume?.map((item) => item.symbol) || [];
    return [...new Set([...marketCapSymbols, ...volumeSymbols])];
  }, [detailData]);

  // Fetch real-time prices for all stocks
  const { data: pricesData, isLoading: pricesLoading } =
    useStocksRealtimePriceBatch(allSymbols);

  const isLoading = detailLoading;
  const exchangeRate = exchangeData ? parseFloat(exchangeData.rate) : null;

  const renderMarketCapList = () => {
    if (!detailData?.market_cap || detailData.market_cap.length === 0) {
      return (
        <div className="py-8 text-center text-default-400">
          No data available
        </div>
      );
    }

    return (
      <div className="divide-y divide-divider">
        {detailData.market_cap.slice(0, 10).map((item, index) => {
          const priceInfo = pricesData?.prices?.[item.symbol];
          const changePercent = priceInfo
            ? parseFloat(priceInfo.change_percent)
            : undefined;

          return (
            <MarketCapRow
              key={item.symbol}
              rank={index + 1}
              symbol={item.symbol}
              name={item.name}
              market={item.market}
              marketCapKRW={item.market_cap_krw}
              marketCapUSD={item.market_cap_usd}
              changePercent={changePercent}
            />
          );
        })}
      </div>
    );
  };

  const renderVolumeList = () => {
    if (!detailData?.volume || detailData.volume.length === 0) {
      return (
        <div className="py-8 text-center text-default-400">
          No data available
        </div>
      );
    }

    if (pricesLoading && !pricesData) {
      return (
        <div className="divide-y divide-divider">
          {[...Array(5)].map((_, i) => (
            <RowSkeleton key={i} />
          ))}
        </div>
      );
    }

    return (
      <div className="divide-y divide-divider">
        {detailData.volume.slice(0, 10).map((item, index) => {
          const priceInfo = pricesData?.prices?.[item.symbol];

          if (!priceInfo) {
            return <RowSkeleton key={item.symbol} />;
          }

          const price = parseFloat(priceInfo.close_price);
          const priceUSD = exchangeRate ? price / exchangeRate : null;
          const changePercent = parseFloat(priceInfo.change_percent);

          return (
            <VolumeRow
              key={item.symbol}
              rank={index + 1}
              symbol={item.symbol}
              name={item.name}
              price={price}
              priceUSD={priceUSD}
              changePercent={changePercent}
              volume={priceInfo.volume}
            />
          );
        })}
      </div>
    );
  };

  if (isLoading && !detailData) {
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
            <RowSkeleton key={i} />
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
          <div className="flex items-center gap-2">
            {exchangeRate && (
              <Tooltip content={`USD/KRW: ${exchangeRate.toFixed(2)}`}>
                <Chip
                  size="sm"
                  variant="flat"
                  color="primary"
                  className="text-tiny"
                >
                  USD
                </Chip>
              </Tooltip>
            )}
            <Chip size="sm" variant="flat" color="secondary" className="text-tiny">
              Top 10
            </Chip>
          </div>
        </div>
        <h4 className="font-bold text-large">Trending Now</h4>
      </CardHeader>
      <CardBody className="py-2 px-4">
        <Tabs
          aria-label="Popular stocks tabs"
          variant="underlined"
          classNames={{
            tabList:
              "gap-6 w-full relative rounded-none p-0 border-b border-divider",
            cursor: "w-full bg-primary",
            tab: "max-w-fit px-0 h-10",
            tabContent: "group-data-[selected=true]:text-primary font-medium",
          }}
        >
          <Tab key="market_cap" title="Market Cap">
            {renderMarketCapList()}
          </Tab>
          <Tab key="volume" title="Volume">
            {renderVolumeList()}
          </Tab>
        </Tabs>
      </CardBody>
    </Card>
  );
}
