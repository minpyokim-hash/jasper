"""
대법원 법원경매정보(courtauction.go.kr) 크롤러
유찰횟수 5회 이상 부동산 경매 목록을 수집하여 Excel로 저장
"""

import time
import logging
import re
from datetime import datetime
from pathlib import Path

import requests
from bs4 import BeautifulSoup
import pandas as pd

# ── 로그 설정 ────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("court_auction_scraper.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)

# ── 상수 ─────────────────────────────────────────────────────────────────────
BASE_URL = "https://www.courtauction.go.kr"
SEARCH_URL = f"{BASE_URL}/PDS0101.do"          # 물건검색 엔드포인트
DETAIL_URL = f"{BASE_URL}/PDS0102.do"          # 목록 조회

MIN_FAILED_BIDS = 5                             # 유찰횟수 최솟값
REQUEST_DELAY = 1.5                             # 요청 간격(초) — 서버 부하 최소화
OUTPUT_DIR = Path("output")
OUTPUT_DIR.mkdir(exist_ok=True)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Referer": BASE_URL,
}

# 부동산 물건종류 코드 (법원경매 기준)
REAL_ESTATE_CODES = {
    "001": "토지",
    "002": "건물",
    "003": "아파트",
    "004": "다세대(빌라)",
    "005": "단독/다가구",
    "006": "오피스텔",
    "007": "상가·사무실",
    "008": "공장·창고",
    "009": "임야",
    "010": "농지",
    "011": "기타",
}


# ── 유틸리티 ──────────────────────────────────────────────────────────────────

def parse_amount(text: str) -> int | None:
    """
    '1,234,000,000원' 또는 '1,234,000,000' 형태의 금액 문자열을 정수로 변환.
    변환 불가 시 None 반환.
    """
    if not text:
        return None
    cleaned = re.sub(r"[^\d]", "", text)
    return int(cleaned) if cleaned else None


def format_amount(value: int | None) -> str:
    """정수 금액을 '1,234,000,000' 형식의 문자열로 변환."""
    if value is None:
        return ""
    return f"{value:,}"


def safe_text(tag) -> str:
    """BeautifulSoup 태그에서 안전하게 텍스트를 추출."""
    return tag.get_text(strip=True) if tag else ""


# ── 세션 ──────────────────────────────────────────────────────────────────────

def create_session() -> requests.Session:
    """공통 헤더와 재시도 어댑터가 설정된 세션을 반환."""
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry

    retry = Retry(
        total=3,
        backoff_factor=1,
        status_forcelist=[500, 502, 503, 504],
    )
    session = requests.Session()
    session.headers.update(HEADERS)
    session.mount("https://", HTTPAdapter(max_retries=retry))
    session.mount("http://", HTTPAdapter(max_retries=retry))
    return session


def init_session(session: requests.Session) -> bool:
    """
    메인 페이지를 방문해 쿠키·세션 토큰을 획득.
    법원경매 사이트는 JSESSIONID 기반 세션 관리를 사용.
    """
    try:
        resp = session.get(BASE_URL, timeout=15)
        resp.raise_for_status()
        logger.info("세션 초기화 완료 (쿠키: %s)", dict(session.cookies))
        return True
    except requests.RequestException as exc:
        logger.error("세션 초기화 실패: %s", exc)
        return False


# ── 검색 폼 파라미터 ──────────────────────────────────────────────────────────

def build_search_params(page: int = 1) -> dict:
    """
    법원경매 물건검색 POST 폼 파라미터를 구성.

    주요 파라미터:
      - jiwonNm        : 법원명 (공백=전국)
      - saKindCd       : 경매종류 (0002=부동산)
      - mulKindCd      : 물건종류 코드 (공백=전체)
      - yuchalCntMin   : 유찰횟수 최솟값
      - pageNo         : 페이지 번호
      - pageSize       : 페이지당 항목 수 (최대 100)
    """
    return {
        "jiwonNm": "",           # 전국
        "saKindCd": "0002",      # 부동산 경매
        "mulKindCd": "",         # 전체 물건종류
        "yuchalCntMin": str(MIN_FAILED_BIDS),
        "yuchalCntMax": "",
        "pageNo": str(page),
        "pageSize": "100",
        "orderByType": "1",      # 매각기일 오름차순
    }


# ── 파싱 ──────────────────────────────────────────────────────────────────────

def parse_total_pages(soup: BeautifulSoup) -> int:
    """결과 페이지 수를 파싱. 파싱 실패 시 1 반환."""
    # 법원경매 사이트는 '총 N건' 또는 페이지네이션 버튼으로 전체 건수를 표시
    total_tag = soup.select_one(".totalCnt, #totalCnt, .total_count")
    if total_tag:
        m = re.search(r"[\d,]+", safe_text(total_tag))
        if m:
            total = int(m.group().replace(",", ""))
            pages = (total + 99) // 100
            logger.info("총 %d건, %d 페이지", total, pages)
            return pages

    # 페이지 버튼으로 추정
    page_links = soup.select("a.pageNum, .paging a, #pagination a")
    if page_links:
        nums = []
        for a in page_links:
            m = re.search(r"\d+", safe_text(a))
            if m:
                nums.append(int(m.group()))
        if nums:
            return max(nums)

    return 1


def parse_auction_rows(soup: BeautifulSoup) -> list[dict]:
    """
    검색 결과 테이블에서 경매 물건 행을 파싱.

    법원경매 사이트 결과 테이블 컬럼 순서 (일반적):
      0: 법원/사건번호
      1: 물건종류
      2: 물건소재지
      3: 감정가
      4: 최저입찰가
      5: 유찰횟수
      6: 매각기일
    """
    results = []

    # 결과 테이블 후보 셀렉터 (사이트 변경에 대비해 여러 개 시도)
    table = (
        soup.select_one("table.Ltbl_list")
        or soup.select_one("table#searchListTable")
        or soup.select_one(".list_area table")
        or soup.select_one("table.list")
    )

    if not table:
        logger.warning("결과 테이블을 찾을 수 없습니다.")
        return results

    rows = table.select("tbody tr")
    if not rows:
        rows = table.select("tr")[1:]  # thead 없을 경우 첫 행 skip

    for row in rows:
        cells = row.select("td")
        if len(cells) < 6:
            continue

        try:
            # ── 사건번호 (법원명 + 사건번호) ──────────────────────────────
            case_cell = cells[0]
            case_text = safe_text(case_cell)
            # 예: '서울중앙지방법원\n2023타경12345'
            lines = [l.strip() for l in case_cell.get_text("\n").splitlines() if l.strip()]
            court_name = lines[0] if len(lines) >= 2 else ""
            case_number = lines[1] if len(lines) >= 2 else case_text

            # ── 물건종류 ──────────────────────────────────────────────────
            mul_kind = safe_text(cells[1])

            # ── 소재지 ────────────────────────────────────────────────────
            location = safe_text(cells[2])

            # ── 감정가 ────────────────────────────────────────────────────
            appraisal_raw = safe_text(cells[3])
            appraisal_val = parse_amount(appraisal_raw)

            # ── 최저입찰가 ────────────────────────────────────────────────
            min_bid_raw = safe_text(cells[4])
            min_bid_val = parse_amount(min_bid_raw)

            # ── 유찰횟수 ──────────────────────────────────────────────────
            failed_raw = safe_text(cells[5])
            m = re.search(r"\d+", failed_raw)
            failed_cnt = int(m.group()) if m else 0

            # 유찰횟수 5회 미만이면 skip (서버 필터가 적용되지 않은 경우 대비)
            if failed_cnt < MIN_FAILED_BIDS:
                continue

            # ── 매각기일 ──────────────────────────────────────────────────
            sale_date = safe_text(cells[6]) if len(cells) > 6 else ""

            results.append(
                {
                    "법원명": court_name,
                    "사건번호": case_number,
                    "물건종류": mul_kind,
                    "소재지": location,
                    "감정가(원)": format_amount(appraisal_val),
                    "최저입찰가(원)": format_amount(min_bid_val),
                    "유찰횟수": failed_cnt,
                    "매각기일": sale_date,
                    "수집일시": datetime.now().strftime("%Y-%m-%d %H:%M"),
                }
            )
        except (IndexError, ValueError) as exc:
            logger.debug("행 파싱 오류: %s", exc)
            continue

    return results


# ── 크롤러 메인 ───────────────────────────────────────────────────────────────

def scrape_all_pages(session: requests.Session) -> list[dict]:
    """전체 페이지를 순회하며 유찰 5회 이상 부동산 경매 목록 수집."""
    all_items: list[dict] = []
    page = 1

    while True:
        params = build_search_params(page)
        logger.info("페이지 %d 수집 중...", page)

        try:
            # 법원경매는 POST 방식 검색 폼 사용
            resp = session.post(SEARCH_URL, data=params, timeout=20)
            resp.raise_for_status()
            resp.encoding = "utf-8"
        except requests.RequestException as exc:
            logger.error("페이지 %d 요청 실패: %s", page, exc)
            break

        soup = BeautifulSoup(resp.text, "html.parser")

        # 첫 페이지에서 총 페이지 수 확인
        if page == 1:
            total_pages = parse_total_pages(soup)
            logger.info("총 페이지 수: %d", total_pages)
            if total_pages == 0:
                logger.warning("검색 결과가 없습니다.")
                break

        rows = parse_auction_rows(soup)
        logger.info("  → %d건 파싱", len(rows))
        all_items.extend(rows)

        if page >= total_pages:
            break

        page += 1
        time.sleep(REQUEST_DELAY)

    return all_items


# ── Excel 저장 ────────────────────────────────────────────────────────────────

def save_to_excel(records: list[dict]) -> Path:
    """수집 결과를 날짜별 Excel 파일로 저장하고 경로를 반환."""
    if not records:
        logger.warning("저장할 데이터가 없습니다.")
        return None

    df = pd.DataFrame(
        records,
        columns=[
            "법원명",
            "사건번호",
            "물건종류",
            "소재지",
            "감정가(원)",
            "최저입찰가(원)",
            "유찰횟수",
            "매각기일",
            "수집일시",
        ],
    )

    # 유찰횟수 내림차순 정렬
    df.sort_values("유찰횟수", ascending=False, inplace=True)
    df.reset_index(drop=True, inplace=True)

    date_str = datetime.now().strftime("%Y%m%d")
    filename = OUTPUT_DIR / f"court_auction_{date_str}.xlsx"

    with pd.ExcelWriter(filename, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="경매목록")

        # ── 셀 서식 적용 ──────────────────────────────────────────────────
        ws = writer.sheets["경매목록"]
        from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
        from openpyxl.utils import get_column_letter

        header_fill = PatternFill("solid", fgColor="1F4E79")
        header_font = Font(color="FFFFFF", bold=True, size=11)
        center_align = Alignment(horizontal="center", vertical="center", wrap_text=True)
        thin = Side(style="thin", color="BFBFBF")
        border = Border(left=thin, right=thin, top=thin, bottom=thin)

        # 헤더 행 서식
        for col_idx, cell in enumerate(ws[1], start=1):
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = center_align
            cell.border = border

        # 데이터 행 서식 + 열 너비 자동 조정
        col_widths = [len(str(col)) for col in df.columns]

        for row in ws.iter_rows(min_row=2):
            for col_idx, cell in enumerate(row):
                cell.alignment = Alignment(
                    horizontal="center", vertical="center", wrap_text=True
                )
                cell.border = border
                val_len = len(str(cell.value)) if cell.value else 0
                if val_len > col_widths[col_idx]:
                    col_widths[col_idx] = val_len

        for i, width in enumerate(col_widths, start=1):
            ws.column_dimensions[get_column_letter(i)].width = min(width + 4, 40)

        # 첫 행 고정
        ws.freeze_panes = "A2"

    logger.info("Excel 저장 완료: %s (%d건)", filename, len(df))
    return filename


# ── 진입점 ────────────────────────────────────────────────────────────────────

def main():
    logger.info("=" * 60)
    logger.info("법원경매 크롤러 시작 — 유찰 %d회 이상 부동산", MIN_FAILED_BIDS)
    logger.info("=" * 60)

    session = create_session()

    if not init_session(session):
        logger.error("세션 초기화 실패로 종료합니다.")
        return

    records = scrape_all_pages(session)

    if records:
        saved_path = save_to_excel(records)
        logger.info("완료: 총 %d건 수집 → %s", len(records), saved_path)
    else:
        logger.warning("수집된 데이터가 없습니다.")

    logger.info("=" * 60)


if __name__ == "__main__":
    main()
