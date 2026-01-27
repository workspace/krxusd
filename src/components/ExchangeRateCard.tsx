"use client";

import { Card, CardBody, CardHeader, Skeleton, Chip } from "@heroui/react";
import { useExchangeRate } from "@/hooks";
import { formatNumber, formatPercent } from "@/lib/api";

export function ExchangeRateCard() {
  const { data, isLoading, error } = useExchangeRate();

  if (isLoading) {
    return (
      <Card className="w-full">
        <CardHeader className="pb-0 pt-4 px-4 flex-col items-start">
          <p className="text-tiny uppercase font-bold text-default-500">
            USD/KRW Exchange Rate
          </p>
          <Skeleton className="w-24 h-6 rounded mt-1" />
        </CardHeader>
        <CardBody className="py-4">
          <Skeleton className="w-32 h-10 rounded mb-2" />
          <Skeleton className="w-20 h-5 rounded" />
        </CardBody>
      </Card>
    );
  }

  if (error || !data) {
    return (
      <Card className="w-full">
        <CardHeader className="pb-0 pt-4 px-4 flex-col items-start">
          <p className="text-tiny uppercase font-bold text-default-500">
            USD/KRW Exchange Rate
          </p>
          <h4 className="font-bold text-large">Current Rate</h4>
        </CardHeader>
        <CardBody className="py-4">
          <p className="text-default-400">Unable to load data</p>
        </CardBody>
      </Card>
    );
  }

  const rate = parseFloat(data.rate);
  const changePercent = data.change_percent ? parseFloat(data.change_percent) : null;
  const change = data.change ? parseFloat(data.change) : null;
  const isPositive = changePercent !== null && changePercent > 0;
  const isNegative = changePercent !== null && changePercent < 0;

  return (
    <Card className="w-full">
      <CardHeader className="pb-0 pt-4 px-4 flex-col items-start">
        <div className="flex items-center justify-between w-full">
          <p className="text-tiny uppercase font-bold text-default-500">
            USD/KRW Exchange Rate
          </p>
          <Chip size="sm" variant="flat" color="primary" className="text-tiny">
            Live
          </Chip>
        </div>
        <h4 className="font-bold text-large">Current Rate</h4>
      </CardHeader>
      <CardBody className="py-4">
        <div className="flex items-baseline gap-2">
          <p className="text-3xl font-bold tabular-nums">
            {formatNumber(rate.toFixed(2))}
          </p>
          <span className="text-default-500 text-sm">KRW</span>
        </div>
        <div className="flex items-center gap-2 mt-2">
          {change !== null && (
            <span
              className={`text-sm font-medium ${
                isPositive
                  ? "text-danger"
                  : isNegative
                  ? "text-success"
                  : "text-default-500"
              }`}
            >
              {change > 0 ? "+" : ""}
              {change.toFixed(2)}
            </span>
          )}
          {changePercent !== null && (
            <Chip
              size="sm"
              variant="flat"
              color={isPositive ? "danger" : isNegative ? "success" : "default"}
              className="text-tiny"
            >
              {formatPercent(changePercent)}
            </Chip>
          )}
        </div>
        <p className="text-tiny text-default-400 mt-3">
          Source: {data.source} | Updated:{" "}
          {new Date(data.updated_at).toLocaleTimeString("ko-KR")}
        </p>
      </CardBody>
    </Card>
  );
}
