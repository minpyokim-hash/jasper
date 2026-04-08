#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# setup_cron.sh
# 법원경매 크롤러를 매일 오전 9시에 자동 실행하도록 crontab에 등록합니다.
# 사용법: bash setup_cron.sh
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_BIN="${PYTHON_BIN:-$(command -v python3)}"
SCRAPER="${SCRIPT_DIR}/court_auction_scraper.py"
LOG_FILE="${SCRIPT_DIR}/court_auction_scraper.log"

# ── 사전 확인 ─────────────────────────────────────────────────────────────────
if [[ ! -f "$SCRAPER" ]]; then
    echo "[오류] 스크립트를 찾을 수 없습니다: $SCRAPER"
    exit 1
fi

if ! command -v python3 &>/dev/null; then
    echo "[오류] python3 가 설치되어 있지 않습니다."
    exit 1
fi

echo "[정보] Python 경로: $PYTHON_BIN"
echo "[정보] 스크립트 경로: $SCRAPER"

# ── 패키지 설치 ───────────────────────────────────────────────────────────────
echo "[정보] 의존성 패키지를 설치합니다..."
"$PYTHON_BIN" -m pip install -r "${SCRIPT_DIR}/requirements.txt" -q

# ── output 디렉터리 생성 ──────────────────────────────────────────────────────
mkdir -p "${SCRIPT_DIR}/output"

# ── crontab 등록 ──────────────────────────────────────────────────────────────
# 형식: 분 시 일 월 요일  명령
CRON_JOB="0 9 * * * $PYTHON_BIN $SCRAPER >> $LOG_FILE 2>&1"
CRON_MARKER="# court-auction-scraper"

# 기존 등록 항목 제거 후 재등록 (중복 방지)
( crontab -l 2>/dev/null | grep -v "$CRON_MARKER" ; \
  echo "$CRON_MARKER" ; \
  echo "$CRON_JOB" ) | crontab -

echo ""
echo "✅  crontab 등록 완료!"
echo "    스케줄: 매일 오전 09:00"
echo "    명령어: $PYTHON_BIN $SCRAPER"
echo "    로그:   $LOG_FILE"
echo ""
echo "현재 등록된 crontab:"
echo "─────────────────────────────────────────────────────────"
crontab -l
echo "─────────────────────────────────────────────────────────"
echo ""
echo "▶  지금 즉시 실행하려면:"
echo "   $PYTHON_BIN $SCRAPER"
echo ""
echo "▶  crontab 제거하려면:"
echo "   crontab -e  # 해당 줄을 삭제"
