"""USD Converter Service - 핵심 비즈니스 로직.

KRW 주가를 해당 일 환율 종가로 나눠 USD 환산 가격을 계산합니다.
"""
from datetime import date
from typing import Optional

from app.config import settings
from app.schemas.stock import UsdConvertedData, StockUsdPriceHistory
from app.services.exchange_service import ExchangeService
from app.services.stock_service import StockService


class UsdConverterService:
    """USD 환산 서비스.
    
    핵심 공식: USD 환산 주가 = KRW 주가 / 당일 USD/KRW 환율 종가
    """
    
    def __init__(self):
        self.exchange_service = ExchangeService()
        self.stock_service = StockService()
    
    def get_usd_converted_history(
        self,
        code: str,
        start_date: date,
        end_date: Optional[date] = None,
    ) -> Optional[StockUsdPriceHistory]:
        """
        주가를 USD로 환산한 히스토리 데이터 반환.
        
        Args:
            code: 종목 코드
            start_date: 시작일
            end_date: 종료일 (기본값: 오늘)
            
        Returns:
            USD 환산 주가 히스토리
        """
        if end_date is None:
            end_date = date.today()
        
        # Get stock info
        stock_info = self.stock_service.get_stock_info(code)
        if stock_info is None:
            return None
        
        # Get stock price history
        stock_history = self.stock_service.get_history(code, start_date, end_date)
        if not stock_history:
            return None
        
        # Get exchange rate history
        exchange_history = self.exchange_service.get_history(start_date, end_date)
        
        # Create date-indexed exchange rate map
        exchange_map = {item.date: item.close for item in exchange_history.data}
        
        # Convert prices to USD
        converted_data = []
        for stock_day in stock_history:
            # Find matching exchange rate for the same day
            exchange_rate = exchange_map.get(stock_day.date)
            
            if exchange_rate is None:
                # Try to find nearest available rate (for holidays mismatch)
                for i in range(1, 5):  # Look up to 4 days back
                    from datetime import timedelta
                    prev_date = stock_day.date - timedelta(days=i)
                    if prev_date in exchange_map:
                        exchange_rate = exchange_map[prev_date]
                        break
            
            if exchange_rate is None:
                # Skip if no exchange rate found
                continue
            
            # 핵심 계산: USD 가격 = KRW 가격 / 환율
            usd_close = stock_day.close / exchange_rate
            
            converted_data.append(UsdConvertedData(
                date=stock_day.date,
                krw_close=stock_day.close,
                exchange_rate=round(exchange_rate, 2),
                usd_close=round(usd_close, 4),
            ))
        
        return StockUsdPriceHistory(
            code=code,
            name=stock_info.name,
            data=converted_data,
            count=len(converted_data),
        )
    
    def get_current_usd_price(self, code: str) -> Optional[dict]:
        """
        현재 주가의 USD 환산 가격 반환.
        
        Returns:
            {
                "code": "005930",
                "name": "삼성전자",
                "krw_price": 72000,
                "exchange_rate": 1450.50,
                "usd_price": 49.66
            }
        """
        stock_info = self.stock_service.get_stock_info(code)
        if stock_info is None:
            return None
        
        exchange_rate = self.exchange_service.get_current_rate()
        
        usd_price = stock_info.price / exchange_rate.rate
        
        return {
            "code": code,
            "name": stock_info.name,
            "krw_price": stock_info.price,
            "exchange_rate": exchange_rate.rate,
            "usd_price": round(usd_price, 4),
            "krw_change": stock_info.change,
            "krw_change_percent": stock_info.change_percent,
        }
