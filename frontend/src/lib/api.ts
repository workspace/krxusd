/**
 * API Client for KRXUSD Backend
 */

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

// Types
export interface ExchangeRate {
  rate: number;
  date: string;
  change: number;
  change_percent: number;
}

export interface ExchangeHistoryItem {
  date: string;
  open: number;
  high: number;
  low: number;
  close: number;
}

export interface StockInfo {
  code: string;
  name: string;
  market: string;
  price: number;
  change: number;
  change_percent: number;
  volume: number;
  market_cap?: number;
}

export interface StockSearchResult {
  results: StockInfo[];
  count: number;
}

export interface StockPriceHistory {
  date: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export interface UsdConvertedData {
  date: string;
  krw_close: number;
  exchange_rate: number;
  usd_close: number;
}

export interface StockUsdHistory {
  code: string;
  name: string;
  data: UsdConvertedData[];
  count: number;
}

export interface StockCurrentUsd {
  code: string;
  name: string;
  krw_price: number;
  exchange_rate: number;
  usd_price: number;
  krw_change: number;
  krw_change_percent: number;
}

// API Functions

async function fetchApi<T>(endpoint: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${endpoint}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...options?.headers,
    },
  });

  if (!response.ok) {
    throw new Error(`API Error: ${response.status} ${response.statusText}`);
  }

  return response.json();
}

// Exchange Rate APIs

export async function getCurrentExchangeRate(): Promise<ExchangeRate> {
  return fetchApi<ExchangeRate>('/api/exchange/current');
}

export async function getExchangeHistory(
  start: string,
  end?: string
): Promise<{ data: ExchangeHistoryItem[]; count: number }> {
  const params = new URLSearchParams({ start });
  if (end) params.append('end', end);
  return fetchApi(`/api/exchange/history?${params}`);
}

// Stock APIs

export async function searchStocks(
  query: string,
  limit = 20
): Promise<StockSearchResult> {
  const params = new URLSearchParams({ q: query, limit: limit.toString() });
  return fetchApi(`/api/stocks/search?${params}`);
}

export async function getPopularStocks(limit = 10): Promise<StockInfo[]> {
  const params = new URLSearchParams({ limit: limit.toString() });
  return fetchApi(`/api/stocks/popular?${params}`);
}

export async function getStockInfo(code: string): Promise<StockInfo> {
  return fetchApi(`/api/stocks/${code}`);
}

export async function getStockHistory(
  code: string,
  start: string,
  end?: string
): Promise<StockPriceHistory[]> {
  const params = new URLSearchParams({ start });
  if (end) params.append('end', end);
  return fetchApi(`/api/stocks/${code}/history?${params}`);
}

// USD Conversion APIs (핵심!)

export async function getStockUsdHistory(
  code: string,
  start: string,
  end?: string
): Promise<StockUsdHistory> {
  const params = new URLSearchParams({ start });
  if (end) params.append('end', end);
  return fetchApi(`/api/stocks/${code}/usd?${params}`);
}

export async function getStockCurrentUsd(code: string): Promise<StockCurrentUsd> {
  return fetchApi(`/api/stocks/${code}/usd/current`);
}

// Compare APIs

export interface CompareStockData {
  name: string;
  data: { date: string; usd: number; krw: number; normalized: number }[];
}

export interface CompareUsdResponse {
  codes: string[];
  stocks: Record<string, CompareStockData>;
}

export async function compareStocksUsd(
  codes: string[],
  start?: string,
  end?: string
): Promise<CompareUsdResponse> {
  const params = new URLSearchParams({ codes: codes.join(',') });
  if (start) params.append('start', start);
  if (end) params.append('end', end);
  return fetchApi(`/api/stocks/compare/usd?${params}`);
}

// Index USD APIs

export interface IndexUsdData {
  date: string;
  krw_close: number;
  usd_close: number;
  exchange_rate: number;
}

export interface IndexUsdResponse {
  index: string;
  name: string;
  period: string;
  current_krw: number;
  current_usd: number;
  change_krw: number;
  change_usd: number;
  fx_effect: number;
  data: IndexUsdData[];
  count: number;
}

export async function getIndexUsd(
  index: string = 'KS11',
  period: string = '1Y'
): Promise<IndexUsdResponse> {
  const params = new URLSearchParams({ index, period });
  return fetchApi(`/api/stocks/index/usd?${params}`);
}

// Correlation API

export interface CorrelationResponse {
  correlation: number | null;
  sample_size: number;
  interpretation?: string;
}

export async function getStockCorrelation(
  code: string,
  start?: string
): Promise<CorrelationResponse> {
  const params = new URLSearchParams();
  if (start) params.append('start', start);
  const qs = params.toString();
  return fetchApi(`/api/stocks/${code}/correlation${qs ? `?${qs}` : ''}`);
}

// Exchange Analysis API

export interface ExchangeAnalysis {
  current: number;
  percentile_5y: number;
  ma20: number | null;
  ma60: number | null;
  ma120: number | null;
  ma200: number | null;
  high_5y: number;
  low_5y: number;
  high_1y: number;
  low_1y: number;
  data_points: number;
}

export async function getExchangeAnalysis(): Promise<ExchangeAnalysis> {
  return fetchApi('/api/exchange/analysis');
}

// Health check
export async function healthCheck(): Promise<{ status: string; mock_mode: boolean }> {
  return fetchApi('/api/health');
}
