"""
=============================================================
  일일 KBO 데이터 수집 스크립트 (Selenium 기반)
=============================================================
기반: kbo_schedule_scraper.py (임안호님 작성, 검증됨)

두 가지 모드:
  1. 일일 모드 (기본): 어제 결과 + 오늘 일정 수집
     python scripts/daily_collect.py
  
  2. 범위 모드: 특정 기간 일괄 수집 (갭 메꾸기용)
     python scripts/daily_collect.py --from 2026-04-17 --to 2026-05-04

수집 대상:
  - games_history.csv 업데이트 (어제 결과 + 오늘 예정)
  - data/daily_schedule/YYYY-MM-DD.csv 생성 (오늘 일정)

필요한 패키지:
  pip install selenium webdriver-manager pandas
=============================================================
"""

import argparse
import re
import sys
import time
from datetime import datetime, timedelta, date
from pathlib import Path

import pandas as pd

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select, WebDriverWait
from selenium.common.exceptions import NoSuchElementException

try:
    from selenium.webdriver.chrome.service import Service
    from webdriver_manager.chrome import ChromeDriverManager
    USE_WDM = True
except ImportError:
    USE_WDM = False


# ============================================================
# 설정
# ============================================================
ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
GAMES_HISTORY = DATA_DIR / "games_history.csv"
DAILY_SCHEDULE_DIR = DATA_DIR / "daily_schedule"

BASE_URL = "https://www.koreabaseball.com/Schedule/Schedule.aspx"
HEADLESS = True
WAIT_SEC = 2.5
SERIES_TYPE = "정규시즌"

YEAR_SELECT_ID = "ddlYear"
MONTH_SELECT_ID = "ddlMonth"
SERIES_SELECT_ID = "ddlSeries"


# ============================================================
# 드라이버
# ============================================================
def create_driver():
    opts = Options()
    if HEADLESS:
        opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--window-size=1920,1080")
    opts.add_argument("--disable-gpu")
    opts.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
    )
    if USE_WDM:
        svc = Service(ChromeDriverManager().install())
        return webdriver.Chrome(service=svc, options=opts)
    return webdriver.Chrome(options=opts)


# ============================================================
# 드롭다운 선택 (임안호님 코드 기반)
# ============================================================
def safe_select(driver, element_id, value_text, wait_after=True):
    try:
        el = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, element_id))
        )
        sel = Select(el)
        current = sel.first_selected_option.text.strip()
        if current == value_text:
            return True
        sel.select_by_visible_text(value_text)
        if wait_after:
            time.sleep(WAIT_SEC + 1)
        return True
    except Exception as e:
        print(f"    [경고] {element_id}='{value_text}' 선택 실패: {e}")
        return False


def set_filters(driver, year, month, series_type=SERIES_TYPE):
    safe_select(driver, SERIES_SELECT_ID, series_type)
    safe_select(driver, YEAR_SELECT_ID, str(year))
    safe_select(driver, MONTH_SELECT_ID, f"{int(month):02d}")


# ============================================================
# 파싱 (임안호님 코드 그대로)
# ============================================================
def parse_schedule_table(driver, year, month):
    """KBO 일정/결과 테이블 파서."""
    games = []
    try:
        table = driver.find_element(By.ID, "tblScheduleList")
    except NoSuchElementException:
        print("    [경고] tblScheduleList 테이블을 찾을 수 없음")
        return games

    rows = table.find_elements(By.CSS_SELECTOR, "tbody tr")
    if not rows:
        return games

    current_date = None

    for tr in rows:
        # 날짜 셀 처리 (rowspan)
        day_cells = tr.find_elements(By.CSS_SELECTOR, "td.day")
        if day_cells:
            date_text = day_cells[0].text.strip()
            m = re.match(r"(\d{1,2})\.(\d{1,2})", date_text)
            if m:
                mm, dd = m.group(1), m.group(2)
                current_date = f"{year}-{mm.zfill(2)}-{dd.zfill(2)}"

        if not current_date:
            continue

        # 경기 정보 셀
        play_cells = tr.find_elements(By.CSS_SELECTOR, "td.play")
        if not play_cells:
            continue

        play = play_cells[0]
        game = parse_play_cell(play, current_date)
        if not game:
            continue

        # 구장
        all_tds = tr.find_elements(By.TAG_NAME, "td")
        stadium_idx = 7 if day_cells else 6
        if len(all_tds) > stadium_idx:
            game["venue"] = all_tds[stadium_idx].text.strip()

        # 시간
        time_cells = tr.find_elements(By.CSS_SELECTOR, "td.time")
        if time_cells:
            game["scheduled_time"] = time_cells[0].text.strip()

        games.append(game)

    return games


def parse_play_cell(play_td, current_date):
    """td.play 셀에서 경기 정보 추출."""
    team_spans = play_td.find_elements(By.XPATH, "./span")
    if len(team_spans) < 2:
        return None

    away_team = team_spans[0].text.strip()
    home_team = team_spans[-1].text.strip()

    if not away_team or not home_team:
        return None

    away_score = home_score = None
    status = "예정"
    winner = "미정"

    try:
        em = play_td.find_element(By.TAG_NAME, "em")
        win_spans = em.find_elements(By.CSS_SELECTOR, "span.win")
        lose_spans = em.find_elements(By.CSS_SELECTOR, "span.lose")
        same_spans = em.find_elements(By.CSS_SELECTOR, "span.same")

        if win_spans and lose_spans:
            # 정상 종료
            em_spans = em.find_elements(By.TAG_NAME, "span")
            score_spans = [s for s in em_spans if s.text.strip().isdigit()]
            if len(score_spans) >= 2:
                away_score = int(score_spans[0].text.strip())
                home_score = int(score_spans[-1].text.strip())

                home_score_cls = score_spans[-1].get_attribute("class") or ""
                if "win" in home_score_cls:
                    winner = "홈승"
                    status = "종료"
                elif "lose" in home_score_cls:
                    winner = "원정승"
                    status = "종료"
        elif same_spans:
            # 0-0 또는 동점 (예정 또는 무승부)
            em_spans = em.find_elements(By.TAG_NAME, "span")
            score_spans = [s for s in em_spans if s.text.strip().isdigit()]
            if len(score_spans) >= 2:
                a = int(score_spans[0].text.strip())
                h = int(score_spans[-1].text.strip())
                if a == 0 and h == 0:
                    status = "예정"
                else:
                    away_score = a
                    home_score = h
                    winner = "무승부"
                    status = "종료"
        else:
            # vs만 있음 → 미경기
            em_text = em.text.strip()
            if any(k in em_text for k in ["취소", "연기", "우천"]):
                status = "취소"
            else:
                status = "예정"
    except NoSuchElementException:
        pass

    # 취소 체크
    full_text = play_td.text
    if any(k in full_text for k in ["취소", "우천취소", "연기"]):
        status = "취소"
        home_score = away_score = None
        winner = "취소"

    return {
        "game_date": current_date,
        "home_team": home_team,
        "away_team": away_team,
        "home_score": home_score,
        "away_score": away_score,
        "winner": winner,
        "status": status,
        "venue": "",
        "scheduled_time": "",
    }


# ============================================================
# 데이터 처리
# ============================================================
def append_to_games_history(games):
    """수집한 경기를 games_history.csv에 추가/업데이트."""
    if not games:
        return 0

    new_df = pd.DataFrame(games)
    new_df["season"] = pd.to_datetime(new_df["game_date"]).dt.year
    new_df["doubleheader"] = "N"
    new_df["source"] = "KBO"
    new_df["collected_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    standard_cols = [
        "game_date", "season", "home_team", "away_team",
        "home_score", "away_score", "winner",
        "status", "venue", "doubleheader",
        "source", "collected_at",
    ]
    for col in standard_cols:
        if col not in new_df.columns:
            new_df[col] = ""
    new_df = new_df[standard_cols]

    if GAMES_HISTORY.exists():
        existing_df = pd.read_csv(GAMES_HISTORY)
    else:
        existing_df = pd.DataFrame(columns=standard_cols)

    # 중복 키 처리
    key_cols = ["game_date", "home_team", "away_team"]
    new_keys = set(new_df[key_cols].apply(tuple, axis=1))
    existing_keys = existing_df[key_cols].apply(tuple, axis=1)
    existing_df = existing_df[~existing_keys.isin(new_keys)]

    combined = pd.concat([existing_df, new_df], ignore_index=True)
    combined = combined.sort_values(["game_date", "home_team"]).reset_index(drop=True)
    combined.to_csv(GAMES_HISTORY, index=False, encoding="utf-8-sig")

    return len(new_df)


def save_daily_schedule(games, target_date):
    """오늘 경기 일정을 daily_schedule/YYYY-MM-DD.csv로 저장."""
    if not games:
        return

    df = pd.DataFrame(games)
    schedule_cols = ["game_date", "away_team", "home_team", "venue", "scheduled_time", "status"]
    for col in schedule_cols:
        if col not in df.columns:
            df[col] = ""
    df = df[schedule_cols]

    DAILY_SCHEDULE_DIR.mkdir(parents=True, exist_ok=True)
    out_path = DAILY_SCHEDULE_DIR / f"{target_date.strftime('%Y-%m-%d')}.csv"
    df.to_csv(out_path, index=False, encoding="utf-8-sig")
    print(f"  ✓ 일정 저장: {out_path.name}")


# ============================================================
# 모드별 실행
# ============================================================
def fetch_month(driver, year, month):
    """특정 년/월 데이터 수집."""
    print(f"  → {year}년 {month}월 KBO 사이트 접속...")
    set_filters(driver, year, month)
    games = parse_schedule_table(driver, year, month)
    print(f"  ✓ {len(games)}경기 파싱됨")
    return games


def run_daily_mode(driver):
    """일일 모드: 어제 + 오늘."""
    today = date.today()
    yesterday = today - timedelta(days=1)

    print("=" * 60)
    print(f"일일 수집 모드 - 오늘: {today}")
    print("=" * 60)

    # 사이트 첫 로드
    driver.get(BASE_URL)
    time.sleep(WAIT_SEC + 1)

    # 어제와 오늘이 같은 월이면 한 번만
    months_to_fetch = []
    months_to_fetch.append((today.year, today.month))
    if (yesterday.year, yesterday.month) != (today.year, today.month):
        months_to_fetch.append((yesterday.year, yesterday.month))

    all_games = []
    for year, month in months_to_fetch:
        games = fetch_month(driver, year, month)
        all_games.extend(games)
        time.sleep(2)

    yesterday_str = yesterday.strftime("%Y-%m-%d")
    today_str = today.strftime("%Y-%m-%d")

    yesterday_games = [g for g in all_games if g["game_date"] == yesterday_str]
    today_games = [g for g in all_games if g["game_date"] == today_str]

    # 어제 결과
    print(f"\n어제({yesterday}) 결과: {len(yesterday_games)}경기")
    if yesterday_games:
        added = append_to_games_history(yesterday_games)
        print(f"  ✓ {added}경기 추가/업데이트")
        for g in yesterday_games[:5]:
            score = f"{g['away_score']}-{g['home_score']}" if g.get('home_score') is not None else "예정"
            print(f"    {g['away_team']} vs {g['home_team']}: {score} ({g['status']})")

    # 오늘 일정
    print(f"\n오늘({today}) 일정: {len(today_games)}경기")
    if today_games:
        save_daily_schedule(today_games, today)
        append_to_games_history(today_games)
        for g in today_games[:5]:
            print(f"    {g.get('scheduled_time', '')} {g['away_team']} vs {g['home_team']} @ {g.get('venue', '')}")

    print("\n" + "=" * 60)
    print("✅ 일일 수집 완료")
    print("=" * 60)


def run_range_mode(driver, from_date, to_date):
    """범위 모드: 갭 메꾸기."""
    print("=" * 60)
    print(f"범위 수집 모드: {from_date} ~ {to_date}")
    print("=" * 60)

    # 월 단위로 묶기
    months_to_fetch = set()
    current = from_date
    while current <= to_date:
        months_to_fetch.add((current.year, current.month))
        if current.month == 12:
            current = date(current.year + 1, 1, 1)
        else:
            current = date(current.year, current.month + 1, 1)

    months_to_fetch = sorted(months_to_fetch)
    print(f"\n수집할 월: {len(months_to_fetch)}개")
    for y, m in months_to_fetch:
        print(f"  - {y}-{m:02d}")

    # 사이트 첫 로드
    driver.get(BASE_URL)
    time.sleep(WAIT_SEC + 1)

    all_games = []
    for i, (year, month) in enumerate(months_to_fetch, 1):
        print(f"\n[{i}/{len(months_to_fetch)}] {year}-{month:02d} 수집 중...")
        games = fetch_month(driver, year, month)
        all_games.extend(games)
        if i < len(months_to_fetch):
            time.sleep(2)

    # 날짜 범위 필터
    from_str = from_date.strftime("%Y-%m-%d")
    to_str = to_date.strftime("%Y-%m-%d")
    filtered_games = [g for g in all_games if from_str <= g["game_date"] <= to_str]

    print(f"\n총 {len(filtered_games)}경기 ({from_str} ~ {to_str})")

    from collections import Counter
    status_count = Counter(g["status"] for g in filtered_games)
    for status, count in sorted(status_count.items()):
        print(f"  {status}: {count}건")

    if filtered_games:
        added = append_to_games_history(filtered_games)
        print(f"\n✓ {added}경기 games_history.csv에 추가/업데이트됨")

    print("\n" + "=" * 60)
    print("✅ 범위 수집 완료")
    print("=" * 60)


# ============================================================
# 메인
# ============================================================
def main():
    parser = argparse.ArgumentParser(description="KBO 일일 데이터 수집 (Selenium)")
    parser.add_argument(
        "--from", dest="from_date",
        type=lambda s: datetime.strptime(s, "%Y-%m-%d").date(),
        help="범위 모드 시작 날짜 (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--to", dest="to_date",
        type=lambda s: datetime.strptime(s, "%Y-%m-%d").date(),
        help="범위 모드 종료 날짜 (YYYY-MM-DD)",
    )
    args = parser.parse_args()

    if not DATA_DIR.exists():
        print(f"❌ {DATA_DIR}가 없습니다. init_data_v2.py를 먼저 실행하세요.")
        sys.exit(1)

    print("Chrome 드라이버 시작 중...")
    driver = create_driver()

    try:
        if args.from_date and args.to_date:
            run_range_mode(driver, args.from_date, args.to_date)
        elif args.from_date or args.to_date:
            print("❌ --from과 --to를 모두 지정해야 합니다.")
            sys.exit(1)
        else:
            run_daily_mode(driver)
    except KeyboardInterrupt:
        print("\n⚠️ 사용자가 중단했습니다.")
    except Exception as e:
        print(f"\n❌ 오류 발생: {e}")
        import traceback
        traceback.print_exc()
    finally:
        driver.quit()


if __name__ == "__main__":
    main()
