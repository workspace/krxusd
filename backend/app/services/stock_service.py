"""Stock data service with Mock support."""
from datetime import date, timedelta
import random
from typing import Optional

from app.config import settings
from app.schemas.stock import (
    StockInfo,
    StockSearchResult,
    StockPriceHistory,
)


# Mock data for popular Korean stocks
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


class StockService:
    """Stock data service.
    
    Supports both real data (FinanceDataReader) and mock data for development.
    """
    
    def search(self, query: str, limit: int = 20) -> StockSearchResult:
        """Search stocks by name or code."""
        if settings.use_mock:
            return self._mock_search(query, limit)
        return self._real_search(query, limit)
    
    def get_stock_info(self, code: str) -> Optional[StockInfo]:
        """Get stock basic information."""
        if settings.use_mock:
            return self._mock_stock_info(code)
        return self._real_stock_info(code)
    
    def get_history(
        self,
        code: str,
        start_date: date,
        end_date: Optional[date] = None,
    ) -> list[StockPriceHistory]:
        """Get stock price history."""
        if end_date is None:
            end_date = date.today()
            
        if settings.use_mock:
            return self._mock_history(code, start_date, end_date)
        return self._real_history(code, start_date, end_date)
    
    def get_popular_stocks(self, limit: int = 10) -> list[StockInfo]:
        """Get popular/trending stocks."""
        if settings.use_mock:
            return self._mock_popular_stocks(limit)
        return self._real_popular_stocks(limit)
    
    # ========== Mock implementations ==========
    
    def _mock_search(self, query: str, limit: int) -> StockSearchResult:
        """Mock stock search for frontend development."""
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
        """Mock stock info for frontend development."""
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
        self,
        code: str,
        start_date: date,
        end_date: date,
    ) -> list[StockPriceHistory]:
        """Mock stock price history for frontend development."""
        if code not in MOCK_STOCKS:
            return []
        
        base_price = MOCK_STOCKS[code]["base_price"]
        data = []
        current_date = start_date
        
        while current_date <= end_date:
            # Skip weekends
            if current_date.weekday() < 5:
                # Generate realistic-looking price with random walk
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
        """Mock popular stocks for frontend development."""
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
        """Search stocks using FinanceDataReader."""
        try:
            import FinanceDataReader as fdr
            
            # Get all KRX stocks
            df = fdr.StockListing('KRX')
            query_lower = query.lower()
            
            # Filter by name or code
            mask = (
                df['Name'].str.lower().str.contains(query_lower, na=False) |
                df['Code'].str.contains(query, na=False)
            )
            filtered = df[mask].head(limit)
            
            results = []
            for _, row in filtered.iterrows():
                results.append(StockInfo(
                    code=row['Code'],
                    name=row['Name'],
                    market=row.get('Market', 'KOSPI'),
                    price=0,  # Would need separate call for current price
                    change=0,
                    change_percent=0,
                    volume=0,
                ))
            
            return StockSearchResult(results=results, count=len(results))
        except Exception:
            return self._mock_search(query, limit)
    
    def _real_stock_info(self, code: str) -> Optional[StockInfo]:
        """Get real stock info using FinanceDataReader."""
        try:
            import FinanceDataReader as fdr
            
            # Get recent data
            end = date.today()
            start = end - timedelta(days=5)
            df = fdr.DataReader(code, start.isoformat())
            
            if df.empty:
                return self._mock_stock_info(code)
            
            # Get stock name from listing
            listing = fdr.StockListing('KRX')
            stock_row = listing[listing['Code'] == code]
            
            if stock_row.empty:
                return self._mock_stock_info(code)
            
            name = stock_row.iloc[0]['Name']
            market = stock_row.iloc[0].get('Market', 'KOSPI')
            
            latest = df.iloc[-1]
            prev = df.iloc[-2] if len(df) > 1 else df.iloc[-1]
            
            price = float(latest['Close'])
            prev_price = float(prev['Close'])
            change = price - prev_price
            change_percent = (change / prev_price) * 100
            
            return StockInfo(
                code=code,
                name=name,
                market=market,
                price=round(price, 0),
                change=round(change, 0),
                change_percent=round(change_percent, 2),
                volume=int(latest['Volume']),
            )
        except Exception:
            return self._mock_stock_info(code)
    
    def _real_history(
        self,
        code: str,
        start_date: date,
        end_date: date,
    ) -> list[StockPriceHistory]:
        """Get real stock price history using FinanceDataReader."""
        try:
            import FinanceDataReader as fdr
            
            df = fdr.DataReader(code, start_date.isoformat(), end_date.isoformat())
            
            if df.empty:
                return self._mock_history(code, start_date, end_date)
            
            data = []
            for idx, row in df.iterrows():
                data.append(StockPriceHistory(
                    date=idx.date(),
                    open=round(float(row['Open']), 0),
                    high=round(float(row['High']), 0),
                    low=round(float(row['Low']), 0),
                    close=round(float(row['Close']), 0),
                    volume=int(row['Volume']),
                ))
            
            return data
        except Exception:
            return self._mock_history(code, start_date, end_date)
    
    def _real_popular_stocks(self, limit: int) -> list[StockInfo]:
        """Get real popular stocks - fallback to mock for now."""
        # In production, would query by trading volume or market cap
        return self._mock_popular_stocks(limit)
