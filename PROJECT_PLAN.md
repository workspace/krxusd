# KRXUSD 프로젝트 기획서

## 1. 프로젝트 개요
*   **프로젝트명:** KRXUSD (가칭)
*   **목표:** 한국 거래소(KRX) 상장 주식의 가격을 실시간(또는 지연) 환율을 적용하여 달러(USD) 가치로 보여주는 정보 제공 서비스.
*   **핵심 가치:** 외국인 투자자 혹은 달러 자산을 운용하는 국내 투자자에게 직관적인 달러 환산 주가 정보를 제공.
*   **비즈니스 모델:** 웹사이트 트래픽 기반 광고 수익 (Google AdSense 등).

## 2. 주요 기능 (MVP)
1.  **메인 대시보드:**
    *   현재 원/달러 환율 표시.
    *   KOSPI, KOSDAQ 주요 지수 현황 (USD 환산 병기).
    *   실시간 인기/급상승 종목 리스트 (USD 가격 포함).
2.  **종목 검색 및 상세 페이지:**
    *   종목명/티커 검색 기능.
    *   해당 종목의 현재가 (KRW, USD), 등락률, 시가총액 (USD 환산).
    *   간단한 차트 (KRW vs USD 추세 비교).
3.  **환율 계산기:**
    *   사용자가 입력한 KRW 주식 가격을 현재 환율 기준으로 USD로 변환.

## 3. 기술 스택 (Home Server Optimized)
홈서버 리소스를 효율적으로 사용하고 Docker 호환성이 높은 스택으로 구성합니다.

### Frontend (SEO & UX Optimized)
*   **Framework:** **Next.js** (React 기반)
    *   *이유:* 광고 수익을 위해서는 검색 엔진 노출(SEO)이 필수적이므로, SSR(Server Side Rendering)이 강력한 Next.js가 적합합니다.
*   **UI Library:** **Hero UI 3.0 Beta** (구 NextUI)
    *   *이유:* Next.js와 호환성이 뛰어나며(Server Components 지원), 모던하고 세련된 디자인을 즉시 적용 가능. Tailwind CSS 기반이라 커스터마이징이 용이함.
*   **Styling:** Tailwind CSS (Hero UI의 기반).
*   **Animations:** Framer Motion (Hero UI 필수 의존성).
*   **State Management:** TanStack Query (서버 데이터 동기화).

### Backend (Data Processing)
*   **Framework:** **FastAPI** (Python)
    *   *이유:* 금융 데이터 수집(Pandas, Finance library 등)에 Python이 가장 유리하며, FastAPI는 비동기 처리를 지원하여 가볍고 빠릅니다.
*   **Data Source:** 
    *   주가 데이터: `finance-datareader`, `yfinance` (무료 라이브러리 활용) 또는 공공데이터포털 API.
    *   환율 데이터: `yfinance` 또는 수출입은행 환율 API.

### Database & Cache (Hybrid Strategy)
*   **Cache: Redis (Hot Data - In-Memory)**
    *   **역할:** **당일** 1분 단위 실시간 주가/환율, 실시간 인기 종목.
    *   **설정:** AOF(Append Only File)를 켜서 불의의 재시작 시 데이터 복구 지원.
    *   **Lifecycle:** 장 마감 후 '당일 데이터'는 DB로 이관하거나 초기화.
*   **Database: PostgreSQL (Cold Data - Disk)**
    *   **역할:** **과거** 일별 종가 데이터(Daily Close), 종목 마스터 정보.
    *   **이유:** 수천 개 종목의 과거 데이터를 RAM(Redis)에 두는 것은 비효율적. 디스크 기반의 RDBMS가 날짜별 조회 및 관리에 적합.

## 4. 시스템 아키텍처 (Docker & Portainer)
모든 서비스는 `docker-compose`로 묶여 Portainer 스택으로 배포됩니다.

```mermaid
graph TD
    User[사용자] -->|Web Request| Nginx[Nginx Proxy Manager]
    Nginx --> FE[Frontend: Next.js]
    FE --> BE[Backend: FastAPI]
    
    BE -->|Read/Write (Real-time)| Redis[Redis: Today's 1-min Data]
    BE -->|Read/Write (History)| DB[PostgreSQL: Daily Close Data]
    BE -->|Fetch Data| External[금융 API]
```

## 5. 데이터 흐름 및 로직 (Smart Synchronization)
데이터의 연속성을 보장하면서도 불필요한 요청을 최소화하는 **Gap Filling (결측 보정)** 전략을 사용합니다.

1.  **과거 데이터 동기화 (History Sync - Lazy Loading):**
    *   사용자가 특정 종목 상세 페이지에 접속 시:
        1.  **Check DB:** PostgreSQL에서 해당 종목의 `최신 저장 날짜(Last Saved Date)` 조회.
        2.  **Case A (No Data):** 데이터가 아예 없으면 -> 상장일 ~ 어제까지 전체 수집 후 저장 (`Insert`).
        3.  **Case B (Gap Detected):** `Last Saved Date` < `어제` -> **(Last Saved Date + 1일) ~ 어제** 구간의 데이터만 추가 수집 후 저장 (`Append`).
        4.  **Case C (Up-to-date):** `Last Saved Date` == `어제` -> 추가 작업 없음.
    *   *결과:* 항상 최신 상태의 과거 데이터(History)가 확보됨.

2.  **실시간 데이터 (Intraday Real-time):**
    *   사용자가 보고 있는 종목에 대해서만, 혹은 메인 페이지 인기 종목에 대해서만 주기적으로(1분) Redis 업데이트.
    *   만약 아무도 조회하지 않는 종목이라면 실시간 데이터 수집도 생략 가능 (선택 사항).

3.  **일일 업데이트 (Daily Append - Optional):**
    *   *참고:* 위의 '과거 데이터 동기화' 로직(Case B) 덕분에, 굳이 매일 밤 모든 종목을 업데이트하는 배치 작업을 돌릴 필요가 없어집니다. (사용자가 조회하는 순간 채워지므로)
    *   다만, 메인 페이지 노출 종목 등 '자주 조회되는 종목'은 사용자 경험(속도)을 위해 장 마감 후 미리 업데이트해두는 배치를 권장합니다.

## 6. Portainer 배포 구성안 (docker-compose.yml 초안)
```yaml
version: '3.8'

services:
  # 1. Frontend
  krxusd-web:
    image: krxusd-web:latest
    build: ./frontend
    restart: unless-stopped
    ports:
      - "3000:3000"
    environment:
      - API_URL=http://krxusd-api:8000

  # 2. Backend
  krxusd-api:
    image: krxusd-api:latest
    build: ./backend
    restart: unless-stopped
    ports:
      - "8000:8000"
    environment:
      - REDIS_URL=redis://krxusd-redis:6379
    depends_on:
      - krxusd-redis

  # 3. Cache
  krxusd-redis:
    image: redis:alpine
    restart: unless-stopped
```

## 7. 수익화 전략 (AdSense)
1.  **SEO 구조화:** `meta` 태그, `sitemap.xml`, `robots.txt`를 철저히 설정하여 구글 검색 최적화.
2.  **반응형 디자인:** 모바일 트래픽 비중이 높으므로 모바일 UI 최적화 필수.
3.  **광고 배치:**
    *   상단 환율 정보 아래 (배너)
    *   종목 리스트 사이 (인피드 광고)
    *   상세 페이지 사이드바

## 8. 개발 로드맵
1.  **1주차:** 프로젝트 세팅 (Next.js, FastAPI, Docker) 및 환율/주가 데이터 수집 로직 구현 (Redis 연동).
2.  **2주차:** 메인 페이지 UI 개발 및 USD 환산 로직 적용.
3.  **3주차:** 종목 검색 기능 및 상세 페이지 개발.
4.  **4주차:** 배포 (Portainer), 도메인 연결, 구글 서치 콘솔 및 애드센스 신청.
