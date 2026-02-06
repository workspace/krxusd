/**
 * Financial analysis utilities for USD-converted stock data.
 *
 * All calculations use close prices only (OHLC not available in USD).
 * Volatility is annualized assuming 252 trading days.
 */
import type { UsdConvertedData } from './api';

export interface AnalysisResult {
  normalizedReturns: { date: string; usd: number; krw: number }[];
  attribution: {
    totalReturn: number;
    stockReturn: number;
    fxEffect: number;
  };
  volatility: {
    usd: number;
    krw: number;
  };
  drawdown: {
    usdSeries: { date: string; value: number }[];
    krwSeries: { date: string; value: number }[];
    usdMax: number;
    krwMax: number;
  };
  high52w: { usd: number; krw: number };
  low52w: { usd: number; krw: number };
}

function dailyReturns(values: number[]): number[] {
  const returns: number[] = [];
  for (let i = 1; i < values.length; i++) {
    returns.push((values[i] - values[i - 1]) / values[i - 1]);
  }
  return returns;
}

function stdDev(values: number[]): number {
  if (values.length < 2) return 0;
  const mean = values.reduce((a, b) => a + b, 0) / values.length;
  const variance = values.reduce((sum, v) => sum + (v - mean) ** 2, 0) / (values.length - 1);
  return Math.sqrt(variance);
}

function annualizedVolatility(dailyReturnValues: number[]): number {
  return stdDev(dailyReturnValues) * Math.sqrt(252) * 100;
}

function drawdownSeries(prices: number[]): { series: number[]; max: number } {
  let peak = prices[0];
  const series: number[] = [];
  let max = 0;

  for (const price of prices) {
    if (price > peak) peak = price;
    const dd = ((price - peak) / peak) * 100;
    series.push(dd);
    if (dd < max) max = dd;
  }

  return { series, max };
}

export function calculateAnalysis(data: UsdConvertedData[]): AnalysisResult {
  const usdPrices = data.map((d) => d.usd_close);
  const krwPrices = data.map((d) => d.krw_close);
  const dates = data.map((d) => d.date);
  const rates = data.map((d) => d.exchange_rate);

  const firstUsd = usdPrices[0];
  const firstKrw = krwPrices[0];

  const normalizedReturns = data.map((d) => ({
    date: d.date,
    usd: (d.usd_close / firstUsd) * 100,
    krw: (d.krw_close / firstKrw) * 100,
  }));

  const lastUsd = usdPrices[usdPrices.length - 1];
  const lastKrw = krwPrices[krwPrices.length - 1];
  const firstRate = rates[0];
  const lastRate = rates[rates.length - 1];

  const totalReturn = ((lastUsd - firstUsd) / firstUsd) * 100;
  const stockReturn = ((lastKrw - firstKrw) / firstKrw) * 100;
  const fxEffect = totalReturn - stockReturn;

  const usdDailyReturns = dailyReturns(usdPrices);
  const krwDailyReturns = dailyReturns(krwPrices);

  const usdDd = drawdownSeries(usdPrices);
  const krwDd = drawdownSeries(krwPrices);

  const usdDrawdownSeries = dates.map((date, i) => ({ date, value: usdDd.series[i] }));
  const krwDrawdownSeries = dates.map((date, i) => ({ date, value: krwDd.series[i] }));

  const lookback = Math.min(data.length, 252);
  const recent = data.slice(-lookback);
  const recentUsd = recent.map((d) => d.usd_close);
  const recentKrw = recent.map((d) => d.krw_close);

  return {
    normalizedReturns,
    attribution: { totalReturn, stockReturn, fxEffect },
    volatility: {
      usd: annualizedVolatility(usdDailyReturns),
      krw: annualizedVolatility(krwDailyReturns),
    },
    drawdown: {
      usdSeries: usdDrawdownSeries,
      krwSeries: krwDrawdownSeries,
      usdMax: usdDd.max,
      krwMax: krwDd.max,
    },
    high52w: {
      usd: Math.max(...recentUsd),
      krw: Math.max(...recentKrw),
    },
    low52w: {
      usd: Math.min(...recentUsd),
      krw: Math.min(...recentKrw),
    },
  };
}
