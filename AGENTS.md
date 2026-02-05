# KRXUSD - 프로젝트 계획서

## 1. 프로젝트 개요

### 핵심 목표
**KRW 시장 주가를 해당 일 환율 종가로 나눈 USD 환산 차트를 제공하는 서비스**

투자자가 한국 주식의 실제 달러 가치 변동을 직관적으로 파악할 수 있게 합니다.
원화 기준으로는 상승한 것처럼 보이지만, 달러 기준으로는 하락한 경우를 시각적으로 확인할 수 있습니다.

### 핵심 가치 제안
```
USD 환산 주가 = KRW 주가 / 당일 USD/KRW 환율 종가
```

예시:
- 삼성전자 종가: 72,000 KRW
- 당일 환율 종가: 1,450 KRW/USD
- USD 환산 주가: $49.66

## 2. 기술 스택

### Frontend
| 기술 | 버전 | 용도 |
|------|------|------|
| Next.js | 15+ | App Router, SSR/SSG |
| TypeScript | 5+ | 타입 안정성 |
| shadcn/ui | latest | UI 컴포넌트 |
| Tailwind CSS | 3+ | 스타일링 |
| Recharts | 2+ | 차트 (shadcn/ui chart) |
| TanStack Query | 5+ | 서버 상태 관리 |

### Backend
| 기술 | 버전 | 용도 |
|------|------|------|
| FastAPI | 0.100+ | REST API |
| Python | 3.11+ | 런타임 |
| FinanceDataReader | latest | 주가/환율 데이터 |
| pytest | latest | 유닛 테스트 |
| Redis | 7+ | 캐싱 (선택) |
| PostgreSQL | 15+ | 히스토리 저장 (선택) |

## 3. 데이터 소스

### 3.1 주가 데이터: FinanceDataReader
```python
import FinanceDataReader as fdr

# 종목 리스트 조회
stocks = fdr.StockListing('KRX')  # KOSPI + KOSDAQ

# 개별 종목 OHLCV
samsung = fdr.DataReader('005930', '2024-01-01')
# Returns: Open, High, Low, Close, Volume, Change
```

**장점:**
- 무료, API 키 불필요
- KOSPI, KOSDAQ, KONEX 전체 지원
- 일봉 히스토리 데이터 제공

### 3.2 환율 데이터: FinanceDataReader
```python
import FinanceDataReader as fdr

# USD/KRW 환율 히스토리
usdkrw = fdr.DataReader('USD/KRW', '2024-01-01')
# Returns: Close (종가 환율)
```

**장점:**
- 동일 라이브러리로 통합 관리
- 일별 환율 종가 제공

## 4. 핵심 기능 명세

### 4.1 USD 환산 차트 (Core Feature)
**목표:** KRW 주가를 환율로 나눈 USD 가치 시계열 차트

**데이터 처리 로직:**
```python
def calculate_usd_price(stock_df, exchange_df):
    """
    KRW 주가를 USD로 환산
    
    Args:
        stock_df: 주가 데이터 (Close 컬럼)
        exchange_df: 환율 데이터 (Close 컬럼)
    
    Returns:
        DataFrame with USD_Close
    """
    merged = stock_df.join(exchange_df, lsuffix='_stock', rsuffix='_fx')
    merged['USD_Close'] = merged['Close_stock'] / merged['Close_fx']
    return merged
```

**차트 요구사항:**
- X축: 날짜
- Y축: USD 가격
- 비교 옵션: KRW vs USD 듀얼 차트
- 기간 선택: 1M, 3M, 6M, 1Y, 5Y, MAX

### 4.2 메인 대시보드
- 현재 USD/KRW 환율 표시
- KOSPI/KOSDAQ 지수 (USD 환산 병기)
- 인기/급등 종목 리스트

### 4.3 종목 검색
- 종목명/티커 검색
- 자동완성 지원
- 최근 검색 기록

### 4.4 종목 상세 페이지
- USD 환산 차트 (핵심)
- 현재가 (KRW / USD)
- 시가총액 (USD 환산)
- 등락률

## 5. API 설계

### 5.1 환율 API
```
GET /api/exchange/current
Response: { "rate": 1450.50, "date": "2026-02-06", "change": -5.2 }

GET /api/exchange/history?start=2024-01-01&end=2026-02-06
Response: { "data": [{ "date": "2024-01-01", "close": 1305.5 }, ...] }
```

### 5.2 주가 API
```
GET /api/stocks/search?q=삼성
Response: { "results": [{ "code": "005930", "name": "삼성전자", "market": "KOSPI" }] }

GET /api/stocks/{code}
Response: { "code": "005930", "name": "삼성전자", "price": 72000, "change": 1.5 }

GET /api/stocks/{code}/history?start=2024-01-01&period=1Y
Response: { "data": [{ "date": "2024-01-01", "open": 70000, "high": 72000, "low": 69000, "close": 71500, "volume": 12345678 }] }
```

### 5.3 USD 환산 API (핵심)
```
GET /api/stocks/{code}/usd?start=2024-01-01&period=1Y
Response: {
  "code": "005930",
  "name": "삼성전자",
  "data": [{
    "date": "2024-01-01",
    "krw_close": 71500,
    "exchange_rate": 1305.5,
    "usd_close": 54.77
  }, ...]
}
```

## 6. 개발 규칙

### 6.1 Mock Response 규칙 (중요!)
**API 키가 필요한 외부 API는 반드시 Mock 모드를 지원해야 합니다.**

```python
# config.py
USE_MOCK = os.getenv("USE_MOCK", "true").lower() == "true"

# service.py
class ExchangeService:
    def get_rate(self):
        if settings.USE_MOCK:
            return self._mock_rate()
        return self._real_rate()
    
    def _mock_rate(self):
        """프론트엔드 개발용 목 데이터"""
        return {
            "rate": 1450.50,
            "date": "2026-02-06",
            "change": -5.2
        }
```

**목적:**
- 프론트엔드 개발이 백엔드 API 키 없이도 진행 가능
- CI/CD 파이프라인에서 테스트 가능
- 외부 API 장애 시에도 개발 가능

### 6.2 테스트 규칙
**모든 API 엔드포인트는 반드시 유닛 테스트를 포함해야 합니다.**

```python
# tests/test_exchange_api.py
import pytest
from fastapi.testclient import TestClient

class TestExchangeAPI:
    def test_get_current_rate(self, client):
        response = client.get("/api/exchange/current")
        assert response.status_code == 200
        data = response.json()
        assert "rate" in data
        assert "date" in data
        
    def test_get_history(self, client):
        response = client.get("/api/exchange/history?start=2024-01-01")
        assert response.status_code == 200
        data = response.json()
        assert "data" in data
        assert len(data["data"]) > 0
```

**테스트 커버리지 목표:** 80% 이상

### 6.3 코드 스타일
- Python: Black + isort + mypy
- TypeScript: ESLint + Prettier
- 커밋 메시지: Conventional Commits

## 7. 프로젝트 구조

```
krxusd/
├── AGENTS.md                 # 이 문서
├── PROJECT_PLAN.md           # 원본 기획서
├── docker-compose.yml
│
├── frontend/                 # Next.js App
│   ├── src/
│   │   ├── app/
│   │   │   ├── page.tsx              # 메인 대시보드
│   │   │   ├── stocks/[code]/page.tsx # 종목 상세
│   │   │   └── layout.tsx
│   │   ├── components/
│   │   │   ├── ui/                   # shadcn/ui 컴포넌트
│   │   │   ├── charts/               # 차트 컴포넌트
│   │   │   │   └── UsdPriceChart.tsx # 핵심 USD 차트
│   │   │   ├── dashboard/            # 대시보드 컴포넌트
│   │   │   └── search/               # 검색 컴포넌트
│   │   ├── lib/
│   │   │   ├── api.ts                # API 클라이언트
│   │   │   └── utils.ts
│   │   └── hooks/
│   │       ├── useExchangeRate.ts
│   │       └── useStockPrice.ts
│   ├── components.json               # shadcn/ui 설정
│   ├── tailwind.config.ts
│   └── package.json
│
├── backend/                  # FastAPI App
│   ├── app/
│   │   ├── main.py
│   │   ├── config.py                 # USE_MOCK 설정
│   │   ├── routers/
│   │   │   ├── exchange.py
│   │   │   ├── stocks.py
│   │   │   └── health.py
│   │   ├── services/
│   │   │   ├── exchange_service.py   # 환율 서비스 (Mock 지원)
│   │   │   ├── stock_service.py      # 주가 서비스 (Mock 지원)
│   │   │   └── usd_converter.py      # USD 환산 로직
│   │   ├── schemas/
│   │   │   ├── exchange.py
│   │   │   └── stock.py
│   │   └── tests/
│   │       ├── conftest.py
│   │       ├── test_exchange_api.py
│   │       └── test_stock_api.py
│   ├── requirements.txt
│   └── pytest.ini
│
└── docker/
    ├── frontend.Dockerfile
    └── backend.Dockerfile
```

## 8. 구현 단계

### Phase 1: 프로젝트 초기화 (Day 1)
- [x] AGENTS.md 작성
- [ ] 기존 코드 정리
- [ ] Next.js + shadcn/ui 설정
- [ ] FastAPI 기본 구조 설정
- [ ] Mock 모드 구현

### Phase 2: 백엔드 API (Day 1-2)
- [ ] 환율 API 구현 + 테스트
- [ ] 주가 API 구현 + 테스트
- [ ] USD 환산 API 구현 + 테스트
- [ ] Mock 데이터 생성

### Phase 3: 프론트엔드 기본 (Day 2-3)
- [ ] 레이아웃 구성
- [ ] 메인 대시보드 UI
- [ ] USD 환산 차트 컴포넌트 (핵심!)
- [ ] API 연동

### Phase 4: 검색 및 상세 (Day 3-4)
- [ ] 종목 검색 기능
- [ ] 종목 상세 페이지
- [ ] 차트 기간 선택

### Phase 5: 마무리 (Day 4-5)
- [ ] 반응형 UI
- [ ] 다크 모드
- [ ] SEO 최적화
- [ ] Docker 설정

## 9. 성공 기준

### MVP 완료 조건
1. ✅ USD/KRW 환율 조회 API 동작
2. ✅ 주가 조회 API 동작
3. ✅ USD 환산 차트가 정확히 표시됨
4. ✅ 종목 검색 가능
5. ✅ 모든 API에 유닛 테스트 존재
6. ✅ Mock 모드로 프론트엔드 단독 개발 가능

### 품질 기준
- 테스트 커버리지 80% 이상
- Lighthouse 성능 점수 90+ 
- 모바일 반응형 지원

---

## 부록: 빠른 시작

### 개발 환경 실행
```bash
# Backend (Mock 모드)
cd backend
pip install -r requirements.txt
USE_MOCK=true uvicorn app.main:app --reload

# Frontend
cd frontend
pnpm install
pnpm dev
```

### 테스트 실행
```bash
# Backend 테스트
cd backend
pytest -v --cov=app

# Frontend 테스트
cd frontend
pnpm test
```
