"""Stock data service with Mock support and in-memory caching."""
from datetime import date, timedelta
import math
import random
import time
import threading
import logging
from typing import Optional

from app.config import settings
from app.schemas.stock import (
    StockInfo,
    StockSearchResult,
    StockPriceHistory,
)

logger = logging.getLogger(__name__)

MOCK_STOCKS = {
    "005930": {"name": "삼성전자", "market": "KOSPI", "base_price": 72000},
    "000660": {"name": "SK하이닉스", "market": "KOSPI", "base_price": 135000},
    "035720": {"name": "카카오", "market": "KOSPI", "base_price": 45000},
    "035420": {"name": "NAVER", "market": "KOSPI", "base_price": 180000},
    "051910": {"name": "LG화학", "market": "KOSPI", "base_price": 380000},
    "006400": {"name": "삼성SDI", "market": "KOSPI", "base_price": 420000},
    "028260": {"name": "삼성물산", "market": "KOSPI", "base_price": 125000},
    "003670": {"name": "포스코퓨처엠", "market": "KOSPI", "base_price": 280000},
    "105560": {"name": "KB금융", "market": "KOSPI", "base_price": 65000},
    "055550": {"name": "신한지주", "market": "KOSPI", "base_price": 45000},
    "373220": {"name": "LG에너지솔루션", "market": "KOSPI", "base_price": 380000},
    "207940": {"name": "삼성바이오로직스", "market": "KOSPI", "base_price": 780000},
    "000270": {"name": "기아", "market": "KOSPI", "base_price": 95000},
    "005380": {"name": "현대차", "market": "KOSPI", "base_price": 210000},
    "068270": {"name": "셀트리온", "market": "KOSPI", "base_price": 175000},
    "247540": {"name": "에코프로비엠", "market": "KOSDAQ", "base_price": 180000},
    "086520": {"name": "에코프로", "market": "KOSDAQ", "base_price": 95000},
    "376300": {"name": "디어유", "market": "KOSDAQ", "base_price": 45000},
    "293490": {"name": "카카오게임즈", "market": "KOSDAQ", "base_price": 25000},
    "263750": {"name": "펄어비스", "market": "KOSDAQ", "base_price": 42000},
}

TOP_CODES = [
    "005930", "000660", "373220", "207940", "005380",
    "000270", "068270", "035420", "035720", "051910",
    "006400", "105560", "055550", "028260", "003670",
]

LISTING_TTL = 3600  # 1 hour
PRICE_TTL = 60      # 60 seconds


class _StockCache:
    """In-memory cache for KRX listing and stock prices."""

    def __init__(self) -> None:
        self._listing: list[dict] | None = None
        self._listing_ts: float = 0
        self._prices: dict[str, dict] = {}
        self._prices_ts: dict[str, float] = {}
        self._popular: list[StockInfo] | None = None
        self._popular_ts: float = 0
        self._lock = threading.Lock()

    def get_listing(self) -> list[dict]:
        now = time.time()
        if self._listing and (now - self._listing_ts) < LISTING_TTL:
            return self._listing

        try:
            import FinanceDataReader as fdr

            rows: list[dict] = []

            krx = fdr.StockListing('KRX')
            for _, row in krx.iterrows():
                rows.append({
                    "code": str(row.get("Code", "")),
                    "name": str(row.get("Name", "")),
                    "market": str(row.get("Market", "KOSPI")),
                })

            try:
                etf = fdr.StockListing('ETF/KR')
                for _, row in etf.iterrows():
                    rows.append({
                        "code": str(row.get("Symbol", "")),
                        "name": str(row.get("Name", "")),
                        "market": "ETF",
                    })
            except Exception:
                logger.warning("Failed to fetch ETF listing, skipping")

            with self._lock:
                self._listing = rows
                self._listing_ts = now
            logger.info("Listing cached: %d stocks + ETFs", len(rows))
            return rows
        except Exception as e:
            logger.warning("Failed to fetch KRX listing: %s", e)
            if self._listing:
                return self._listing
            return []

    def get_price(self, code: str) -> dict | None:
        now = time.time()
        ts = self._prices_ts.get(code, 0)
        if code in self._prices and (now - ts) < PRICE_TTL:
            return self._prices[code]

        try:
            import FinanceDataReader as fdr
            end = date.today()
            start = end - timedelta(days=7)
            df = fdr.DataReader(code, start.isoformat())
            if df.empty:
                return self._prices.get(code)

            latest = df.iloc[-1]
            prev = df.iloc[-2] if len(df) > 1 else latest
            price = float(latest['Close'])
            prev_price = float(prev['Close'])
            change = price - prev_price
            change_pct = (change / prev_price) * 100 if prev_price else 0

            data = {
                "price": round(price, 0),
                "change": round(change, 0),
                "change_percent": round(change_pct, 2),
                "volume": int(latest['Volume']),
            }
            with self._lock:
                self._prices[code] = data
                self._prices_ts[code] = now
            return data
        except Exception:
            return self._prices.get(code)

    def get_popular(self, limit: int) -> list[StockInfo] | None:
        now = time.time()
        if self._popular and (now - self._popular_ts) < PRICE_TTL:
            return self._popular[:limit]
        return None

    def set_popular(self, stocks: list[StockInfo]) -> None:
        with self._lock:
            self._popular = stocks
            self._popular_ts = time.time()


_cache = _StockCache()


class StockService:
    def search(self, query: str, limit: int = 20) -> StockSearchResult:
        if settings.use_mock:
            return self._mock_search(query, limit)
        return self._real_search(query, limit)

    def get_stock_info(self, code: str) -> Optional[StockInfo]:
        if settings.use_mock:
            return self._mock_stock_info(code)
        return self._real_stock_info(code)

    def get_history(
        self,
        code: str,
        start_date: date,
        end_date: Optional[date] = None,
    ) -> list[StockPriceHistory]:
        if end_date is None:
            end_date = date.today()
        if settings.use_mock:
            return self._mock_history(code, start_date, end_date)
        return self._real_history(code, start_date, end_date)

    def get_popular_stocks(self, limit: int = 10) -> list[StockInfo]:
        if settings.use_mock:
            return self._mock_popular_stocks(limit)
        return self._real_popular_stocks(limit)

    # ========== Mock implementations ==========

    def _mock_search(self, query: str, limit: int) -> StockSearchResult:
        results = []
        query_lower = query.lower()
        for code, info in MOCK_STOCKS.items():
            if query_lower in info["name"].lower() or query in code:
                change = random.uniform(-3, 3)
                results.append(StockInfo(
                    code=code,
                    name=info["name"],
                    market=info["market"],
                    price=info["base_price"],
                    change=round(info["base_price"] * change / 100, 0),
                    change_percent=round(change, 2),
                    volume=random.randint(100000, 10000000),
                    market_cap=info["base_price"] * random.randint(1000000, 100000000),
                ))
                if len(results) >= limit:
                    break
        return StockSearchResult(results=results, count=len(results))

    def _mock_stock_info(self, code: str) -> Optional[StockInfo]:
        if code not in MOCK_STOCKS:
            return None
        info = MOCK_STOCKS[code]
        change = random.uniform(-3, 3)
        return StockInfo(
            code=code,
            name=info["name"],
            market=info["market"],
            price=info["base_price"],
            change=round(info["base_price"] * change / 100, 0),
            change_percent=round(change, 2),
            volume=random.randint(100000, 10000000),
            market_cap=info["base_price"] * random.randint(1000000, 100000000),
        )

    def _mock_history(
        self, code: str, start_date: date, end_date: date,
    ) -> list[StockPriceHistory]:
        if code not in MOCK_STOCKS:
            return []
        base_price = MOCK_STOCKS[code]["base_price"]
        data = []
        current_date = start_date
        while current_date <= end_date:
            if current_date.weekday() < 5:
                daily_change = random.uniform(-0.03, 0.03)
                base_price *= (1 + daily_change)
                base_price = max(base_price * 0.5, min(base_price * 1.5, base_price))
                high = base_price * (1 + random.uniform(0, 0.02))
                low = base_price * (1 - random.uniform(0, 0.02))
                open_price = random.uniform(low, high)
                data.append(StockPriceHistory(
                    date=current_date,
                    open=round(open_price, 0),
                    high=round(high, 0),
                    low=round(low, 0),
                    close=round(base_price, 0),
                    volume=random.randint(100000, 10000000),
                ))
            current_date += timedelta(days=1)
        return data

    def _mock_popular_stocks(self, limit: int) -> list[StockInfo]:
        results = []
        for code, info in list(MOCK_STOCKS.items())[:limit]:
            change = random.uniform(-3, 3)
            results.append(StockInfo(
                code=code,
                name=info["name"],
                market=info["market"],
                price=info["base_price"],
                change=round(info["base_price"] * change / 100, 0),
                change_percent=round(change, 2),
                volume=random.randint(100000, 10000000),
                market_cap=info["base_price"] * random.randint(1000000, 100000000),
            ))
        return results

    # ========== Real implementations ==========

    def _real_search(self, query: str, limit: int) -> StockSearchResult:
        listing = _cache.get_listing()
        if not listing:
            return self._mock_search(query, limit)

        query_lower = query.lower()
        matched = []
        for row in listing:
            if query_lower in row["name"].lower() or query in row["code"]:
                matched.append(row)
                if len(matched) >= limit:
                    break

        results = []
        for row in matched:
            price_data = _cache.get_price(row["code"])
            if price_data:
                results.append(StockInfo(
                    code=row["code"],
                    name=row["name"],
                    market=row["market"],
                    price=price_data["price"],
                    change=price_data["change"],
                    change_percent=price_data["change_percent"],
                    volume=price_data["volume"],
                    market_cap=None,
                ))
            else:
                results.append(StockInfo(
                    code=row["code"],
                    name=row["name"],
                    market=row["market"],
                    price=0,
                    change=0,
                    change_percent=0,
                    volume=0,
                    market_cap=None,
                ))

        return StockSearchResult(results=results, count=len(results))

    def _real_stock_info(self, code: str) -> Optional[StockInfo]:
        listing = _cache.get_listing()
        name = code
        market = "KOSPI"
        for row in listing:
            if row["code"] == code:
                name = row["name"]
                market = row["market"]
                break
        else:
            if not listing:
                return self._mock_stock_info(code)

        price_data = _cache.get_price(code)
        if not price_data:
            return None

        return StockInfo(
            code=code,
            name=name,
            market=market,
            price=price_data["price"],
            change=price_data["change"],
            change_percent=price_data["change_percent"],
            volume=price_data["volume"],
            market_cap=None,
        )

    def _real_history(
        self, code: str, start_date: date, end_date: date,
    ) -> list[StockPriceHistory]:
        try:
            import FinanceDataReader as fdr
            df = fdr.DataReader(code, start_date.isoformat(), end_date.isoformat())
            if df.empty:
                return self._mock_history(code, start_date, end_date)

            df = df.dropna(subset=['Close'])

            data = []
            for idx, row in df.iterrows():
                close = float(row['Close'])
                if math.isnan(close):
                    continue
                o = float(row['Open']) if not math.isnan(float(row['Open'])) else close
                h = float(row['High']) if not math.isnan(float(row['High'])) else close
                lo = float(row['Low']) if not math.isnan(float(row['Low'])) else close
                v = int(row['Volume']) if not math.isnan(float(row['Volume'])) else 0
                data.append(StockPriceHistory(
                    date=idx.date(),
                    open=round(o, 0),
                    high=round(h, 0),
                    low=round(lo, 0),
                    close=round(close, 0),
                    volume=v,
                ))
            return data
        except Exception:
            return self._mock_history(code, start_date, end_date)

    def _real_popular_stocks(self, limit: int) -> list[StockInfo]:
        cached = _cache.get_popular(limit)
        if cached:
            return cached

        listing = _cache.get_listing()
        name_map: dict[str, dict] = {}
        for row in listing:
            name_map[row["code"]] = row

        results = []
        for code in TOP_CODES[:limit]:
            price_data = _cache.get_price(code)
            if not price_data:
                continue
            row = name_map.get(code, {"name": code, "market": "KOSPI"})
            results.append(StockInfo(
                code=code,
                name=row["name"],
                market=row["market"],
                price=price_data["price"],
                change=price_data["change"],
                change_percent=price_data["change_percent"],
                volume=price_data["volume"],
                market_cap=None,
            ))

        if results:
            _cache.set_popular(results)
        return results if results else self._mock_popular_stocks(limit)
