"""Exchange rate service with Mock support."""
from datetime import date, timedelta
import math
import random
from typing import Optional


def _isnan(v: object) -> bool:
    try:
        return math.isnan(float(v))  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return True

from app.config import settings
from app.schemas.exchange import (
    ExchangeRateResponse,
    ExchangeHistoryItem,
    ExchangeHistoryResponse,
)


class ExchangeService:
    """Exchange rate data service.
    
    Supports both real data (FinanceDataReader) and mock data for development.
    """
    
    def get_current_rate(self) -> ExchangeRateResponse:
        """Get current USD/KRW exchange rate."""
        if settings.use_mock:
            return self._mock_current_rate()
        return self._real_current_rate()
    
    def get_history(
        self,
        start_date: date,
        end_date: Optional[date] = None,
    ) -> ExchangeHistoryResponse:
        """Get exchange rate history."""
        if end_date is None:
            end_date = date.today()
            
        if settings.use_mock:
            return self._mock_history(start_date, end_date)
        return self._real_history(start_date, end_date)
    
    # ========== Mock implementations ==========
    
    def _mock_current_rate(self) -> ExchangeRateResponse:
        """Mock current exchange rate for frontend development."""
        return ExchangeRateResponse(
            rate=1450.50,
            date=date.today(),
            change=-5.20,
            change_percent=-0.36,
        )
    
    def _mock_history(
        self,
        start_date: date,
        end_date: date,
    ) -> ExchangeHistoryResponse:
        """Mock exchange rate history for frontend development."""
        data = []
        current_date = start_date
        base_rate = 1300.0
        
        while current_date <= end_date:
            # Skip weekends
            if current_date.weekday() < 5:
                # Generate realistic-looking rate with random walk
                daily_change = random.uniform(-10, 10)
                base_rate += daily_change
                base_rate = max(1200, min(1500, base_rate))  # Clamp range
                
                high = base_rate + random.uniform(0, 5)
                low = base_rate - random.uniform(0, 5)
                open_price = random.uniform(low, high)
                
                data.append(ExchangeHistoryItem(
                    date=current_date,
                    open=round(open_price, 2),
                    high=round(high, 2),
                    low=round(low, 2),
                    close=round(base_rate, 2),
                ))
            
            current_date += timedelta(days=1)
        
        return ExchangeHistoryResponse(data=data, count=len(data))
    
    # ========== Real implementations ==========
    
    def _real_current_rate(self) -> ExchangeRateResponse:
        """Get real current exchange rate using FinanceDataReader."""
        try:
            import FinanceDataReader as fdr
            
            # Get last 5 days to ensure we have data
            end = date.today()
            start = end - timedelta(days=5)
            df = fdr.DataReader('USD/KRW', start.isoformat())
            
            if df.empty:
                # Fallback to mock if no data
                return self._mock_current_rate()
            
            latest = df.iloc[-1]
            prev = df.iloc[-2] if len(df) > 1 else df.iloc[-1]
            
            rate = float(latest['Close'])
            prev_rate = float(prev['Close'])
            change = rate - prev_rate
            change_percent = (change / prev_rate) * 100
            
            return ExchangeRateResponse(
                rate=round(rate, 2),
                date=df.index[-1].date(),
                change=round(change, 2),
                change_percent=round(change_percent, 2),
            )
        except Exception:
            # Fallback to mock on any error
            return self._mock_current_rate()
    
    def _real_history(
        self,
        start_date: date,
        end_date: date,
    ) -> ExchangeHistoryResponse:
        """Get real exchange rate history using FinanceDataReader."""
        try:
            import FinanceDataReader as fdr
            
            df = fdr.DataReader('USD/KRW', start_date.isoformat(), end_date.isoformat())
            
            if df.empty:
                return self._mock_history(start_date, end_date)
            
            df = df.dropna(subset=['Close'])
            
            data = []
            for idx, row in df.iterrows():
                data.append(ExchangeHistoryItem(
                    date=idx.date(),
                    open=round(float(row['Open']), 2) if not _isnan(row['Open']) else round(float(row['Close']), 2),
                    high=round(float(row['High']), 2) if not _isnan(row['High']) else round(float(row['Close']), 2),
                    low=round(float(row['Low']), 2) if not _isnan(row['Low']) else round(float(row['Close']), 2),
                    close=round(float(row['Close']), 2),
                ))
            
            return ExchangeHistoryResponse(data=data, count=len(data))
        except Exception:
            return self._mock_history(start_date, end_date)
