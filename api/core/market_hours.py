"""
KRX Market Hours Utility

한국 증권시장(KRX) 운영 시간 관리 유틸리티
- 정규장: 09:00 ~ 15:30 (KST)
- 시간외 단일가: 15:40 ~ 16:00 (KST)
- 공휴일/주말: 휴장

스케줄러는 장 운영 시간 내에서만 실시간 데이터를 업데이트합니다.
"""

from datetime import datetime, time, date, timedelta
from enum import Enum
from typing import NamedTuple
import pytz

# Korea Standard Time
KST = pytz.timezone("Asia/Seoul")

# Market hours configuration
MARKET_OPEN_TIME = time(9, 0)      # 09:00 KST
MARKET_CLOSE_TIME = time(15, 30)   # 15:30 KST
AFTER_HOURS_END = time(16, 0)      # 16:00 KST (시간외 종료)
PRE_MARKET_START = time(8, 30)     # 08:30 KST (장 시작 전 준비)


class MarketStatus(str, Enum):
    """시장 상태"""
    PRE_MARKET = "pre_market"           # 장 시작 전 (08:30 ~ 09:00)
    MARKET_OPEN = "market_open"         # 장중 (09:00 ~ 15:30)
    AFTER_HOURS = "after_hours"         # 시간외 (15:30 ~ 16:00)
    MARKET_CLOSED = "market_closed"     # 장 종료/휴장


class MarketHoursInfo(NamedTuple):
    """시장 운영 시간 정보"""
    status: MarketStatus
    is_trading_time: bool       # 실시간 업데이트가 필요한 시간인지
    current_time_kst: datetime
    market_open_at: datetime | None
    market_close_at: datetime | None
    next_open_at: datetime | None
    message: str


# KRX 공휴일 (2024-2025)
# 실제 운영에서는 외부 API 또는 데이터베이스에서 관리하는 것이 좋습니다
KRX_HOLIDAYS_2024 = {
    date(2024, 1, 1),    # 신정
    date(2024, 2, 9),    # 설날 연휴
    date(2024, 2, 10),   # 설날
    date(2024, 2, 11),   # 설날 연휴
    date(2024, 2, 12),   # 대체휴일
    date(2024, 3, 1),    # 삼일절
    date(2024, 4, 10),   # 국회의원선거일
    date(2024, 5, 1),    # 근로자의 날
    date(2024, 5, 6),    # 대체휴일
    date(2024, 5, 15),   # 부처님오신날
    date(2024, 6, 6),    # 현충일
    date(2024, 8, 15),   # 광복절
    date(2024, 9, 16),   # 추석 연휴
    date(2024, 9, 17),   # 추석
    date(2024, 9, 18),   # 추석 연휴
    date(2024, 10, 3),   # 개천절
    date(2024, 10, 9),   # 한글날
    date(2024, 12, 25),  # 크리스마스
    date(2024, 12, 31),  # 연말
}

KRX_HOLIDAYS_2025 = {
    date(2025, 1, 1),    # 신정
    date(2025, 1, 28),   # 설날 연휴
    date(2025, 1, 29),   # 설날
    date(2025, 1, 30),   # 설날 연휴
    date(2025, 3, 1),    # 삼일절
    date(2025, 3, 3),    # 대체휴일
    date(2025, 5, 1),    # 근로자의 날
    date(2025, 5, 5),    # 어린이날
    date(2025, 5, 6),    # 대체휴일 (부처님오신날)
    date(2025, 6, 6),    # 현충일
    date(2025, 8, 15),   # 광복절
    date(2025, 10, 3),   # 개천절
    date(2025, 10, 5),   # 추석 연휴
    date(2025, 10, 6),   # 추석
    date(2025, 10, 7),   # 추석 연휴
    date(2025, 10, 8),   # 대체휴일
    date(2025, 10, 9),   # 한글날
    date(2025, 12, 25),  # 크리스마스
    date(2025, 12, 31),  # 연말
}

# 전체 공휴일 합침
KRX_HOLIDAYS = KRX_HOLIDAYS_2024 | KRX_HOLIDAYS_2025


def get_kst_now() -> datetime:
    """현재 한국 시간(KST) 반환"""
    return datetime.now(KST)


def to_kst(dt: datetime) -> datetime:
    """datetime을 KST로 변환"""
    if dt.tzinfo is None:
        dt = KST.localize(dt)
    return dt.astimezone(KST)


def is_weekend(check_date: date) -> bool:
    """주말 여부 확인"""
    return check_date.weekday() >= 5  # 5=토요일, 6=일요일


def is_holiday(check_date: date) -> bool:
    """공휴일 여부 확인"""
    return check_date in KRX_HOLIDAYS


def is_trading_day(check_date: date) -> bool:
    """거래일 여부 확인 (주말/공휴일 제외)"""
    return not is_weekend(check_date) and not is_holiday(check_date)


def get_next_trading_day(from_date: date) -> date:
    """다음 거래일 계산"""
    next_day = from_date + timedelta(days=1)
    while not is_trading_day(next_day):
        next_day += timedelta(days=1)
    return next_day


def get_previous_trading_day(from_date: date) -> date:
    """이전 거래일 계산"""
    prev_day = from_date - timedelta(days=1)
    while not is_trading_day(prev_day):
        prev_day -= timedelta(days=1)
    return prev_day


def get_market_status(check_time: datetime | None = None) -> MarketHoursInfo:
    """
    현재 시장 상태 조회

    Args:
        check_time: 확인할 시간 (기본값: 현재 시간)

    Returns:
        MarketHoursInfo 객체
    """
    if check_time is None:
        check_time = get_kst_now()
    else:
        check_time = to_kst(check_time)

    current_date = check_time.date()
    current_time = check_time.time()

    # 오늘 장 시간 계산
    today_open = KST.localize(datetime.combine(current_date, MARKET_OPEN_TIME))
    today_close = KST.localize(datetime.combine(current_date, MARKET_CLOSE_TIME))

    # 주말/공휴일 체크
    if not is_trading_day(current_date):
        next_trading = get_next_trading_day(current_date)
        next_open = KST.localize(datetime.combine(next_trading, MARKET_OPEN_TIME))

        return MarketHoursInfo(
            status=MarketStatus.MARKET_CLOSED,
            is_trading_time=False,
            current_time_kst=check_time,
            market_open_at=None,
            market_close_at=None,
            next_open_at=next_open,
            message="시장 휴장 (주말 또는 공휴일)",
        )

    # 장 시작 전 (PRE_MARKET: 08:30 ~ 09:00)
    if PRE_MARKET_START <= current_time < MARKET_OPEN_TIME:
        return MarketHoursInfo(
            status=MarketStatus.PRE_MARKET,
            is_trading_time=False,  # 아직 실시간 데이터 불필요
            current_time_kst=check_time,
            market_open_at=today_open,
            market_close_at=today_close,
            next_open_at=today_open,
            message="장 시작 대기 중",
        )

    # 장중 (MARKET_OPEN: 09:00 ~ 15:30)
    if MARKET_OPEN_TIME <= current_time < MARKET_CLOSE_TIME:
        return MarketHoursInfo(
            status=MarketStatus.MARKET_OPEN,
            is_trading_time=True,  # 실시간 업데이트 필요!
            current_time_kst=check_time,
            market_open_at=today_open,
            market_close_at=today_close,
            next_open_at=None,
            message="장 운영 중",
        )

    # 시간외 (AFTER_HOURS: 15:30 ~ 16:00)
    if MARKET_CLOSE_TIME <= current_time < AFTER_HOURS_END:
        next_trading = get_next_trading_day(current_date)
        next_open = KST.localize(datetime.combine(next_trading, MARKET_OPEN_TIME))

        return MarketHoursInfo(
            status=MarketStatus.AFTER_HOURS,
            is_trading_time=True,  # 시간외에도 업데이트 제공
            current_time_kst=check_time,
            market_open_at=today_open,
            market_close_at=today_close,
            next_open_at=next_open,
            message="시간외 거래 중",
        )

    # 장 종료 후 (16:00 이후 또는 08:30 이전)
    if current_time >= AFTER_HOURS_END:
        next_trading = get_next_trading_day(current_date)
    else:
        # 00:00 ~ 08:30 사이
        next_trading = current_date if is_trading_day(current_date) else get_next_trading_day(current_date)

    next_open = KST.localize(datetime.combine(next_trading, MARKET_OPEN_TIME))

    return MarketHoursInfo(
        status=MarketStatus.MARKET_CLOSED,
        is_trading_time=False,
        current_time_kst=check_time,
        market_open_at=None,
        market_close_at=None,
        next_open_at=next_open,
        message="장 종료",
    )


def should_update_realtime() -> bool:
    """
    실시간 업데이트가 필요한 시간인지 확인

    스케줄러에서 사용하는 핵심 함수입니다.
    장중(09:00~15:30) 및 시간외(15:30~16:00)에만 True를 반환합니다.
    """
    market_info = get_market_status()
    return market_info.is_trading_time


def get_market_status_dict() -> dict:
    """
    시장 상태를 딕셔너리로 반환 (API 응답용)
    """
    info = get_market_status()
    return {
        "status": info.status.value,
        "is_trading_time": info.is_trading_time,
        "current_time_kst": info.current_time_kst.isoformat(),
        "market_open_at": info.market_open_at.isoformat() if info.market_open_at else None,
        "market_close_at": info.market_close_at.isoformat() if info.market_close_at else None,
        "next_open_at": info.next_open_at.isoformat() if info.next_open_at else None,
        "message": info.message,
    }


def get_trading_minutes_remaining() -> int:
    """
    오늘 남은 거래 시간(분) 계산

    Returns:
        남은 거래 시간(분), 장 종료 시 0
    """
    market_info = get_market_status()

    if not market_info.is_trading_time:
        return 0

    now = market_info.current_time_kst
    close_time = KST.localize(
        datetime.combine(now.date(), MARKET_CLOSE_TIME)
    )

    if now >= close_time:
        return 0

    remaining = close_time - now
    return int(remaining.total_seconds() // 60)
