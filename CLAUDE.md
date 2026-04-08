# My Project

## 법원경매 크롤러 (court_auction_scraper.py)

대법원 법원경매정보 사이트(courtauction.go.kr)에서 **유찰횟수 5회 이상** 부동산 경매 목록을 수집하여 Excel 파일로 저장하는 스크립트.

### 파일 구성

| 파일 | 설명 |
|---|---|
| `court_auction_scraper.py` | 메인 크롤러 스크립트 |
| `requirements.txt` | Python 의존성 패키지 목록 |
| `setup_cron.sh` | cron 자동 실행 등록 스크립트 |
| `output/court_auction_YYYYMMDD.xlsx` | 수집 결과 Excel 파일 (날짜별) |
| `court_auction_scraper.log` | 실행 로그 |

### 수집 항목

| 컬럼 | 설명 |
|---|---|
| 법원명 | 담당 법원 이름 |
| 사건번호 | 경매 사건번호 (예: 2023타경12345) |
| 물건종류 | 아파트, 토지, 상가 등 |
| 소재지 | 물건 주소 |
| 감정가(원) | 감정평가 금액 |
| 최저입찰가(원) | 현재 회차 최저 입찰 금액 |
| 유찰횟수 | 입찰 실패 횟수 (5회 이상만 수집) |
| 매각기일 | 다음 경매 날짜 |
| 수집일시 | 크롤링 실행 시각 |

### 설치 및 실행

```bash
# 1. 의존성 설치
pip install -r requirements.txt

# 2. 즉시 실행
python court_auction_scraper.py

# 3. cron 자동 등록 (매일 오전 09:00 실행)
bash setup_cron.sh
```

### 주요 설정값 (court_auction_scraper.py)

| 상수 | 기본값 | 설명 |
|---|---|---|
| `MIN_FAILED_BIDS` | `5` | 유찰횟수 최솟값 |
| `REQUEST_DELAY` | `1.5` | 요청 간격(초) |
| `OUTPUT_DIR` | `output/` | Excel 저장 경로 |

### 동작 방식

1. `https://www.courtauction.go.kr` 접속 → JSESSIONID 쿠키 획득
2. `/PDS0101.do` 엔드포인트에 POST 요청 (검색 파라미터: 부동산, 유찰 5회 이상, 전국)
3. BeautifulSoup으로 결과 테이블 파싱 → 전체 페이지 순회
4. 유찰횟수 클라이언트 측 재검증 후 수집
5. `output/court_auction_YYYYMMDD.xlsx` 로 저장 (유찰횟수 내림차순 정렬)

### cron 스케줄

```
0 9 * * *  python /path/to/court_auction_scraper.py >> court_auction_scraper.log 2>&1
```

`setup_cron.sh` 실행 시 자동으로 위 항목이 crontab에 등록됩니다.

### 의존성

```
requests>=2.31.0
beautifulsoup4>=4.12.0
lxml>=5.1.0
pandas>=2.2.0
openpyxl>=3.1.2
urllib3>=2.0.0
```

### 주의사항

- 법원경매 사이트 서버 부하를 줄이기 위해 요청 간 1.5초 딜레이 적용
- HTTP 500/502/503/504 오류 시 최대 3회 자동 재시도
- 사이트 구조 변경 시 `parse_auction_rows()` 내 CSS 셀렉터 수정 필요
- JS 렌더링 의존도가 높아질 경우 Selenium + ChromeDriver 방식으로 전환 필요
