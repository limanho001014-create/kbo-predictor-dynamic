"""
=============================================================
  일일 KBO 선수 스탯 수집 스크립트
=============================================================
기반: kbo_team_scraper.py (임안호님 작성, 검증됨)

차이점:
  - 현재 연도만 수집 (2026)
  - 매일 덮어쓰기 (data/players_latest_hitter.csv)
  - kbo_data/kbo_YYYY_*.csv도 함께 갱신 (기존 호환)

사용법:
  python scripts/daily_collect_players.py
  
  # 특정 연도
  python scripts/daily_collect_players.py --year 2026

출력:
  data/players_latest_hitter.csv     ← 최신 (예측용)
  data/players_latest_pitcher.csv    ← 최신 (예측용)
  kbo_data/kbo_2026_hitter_full.csv  ← 갱신
  kbo_data/kbo_2026_pitcher_full.csv ← 갱신

소요 시간: 약 7~10분 (10팀 × 타자/투수)
=============================================================
"""

import argparse
import csv
import os
import sys
import time
from datetime import datetime, date
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import (
    NoSuchElementException, StaleElementReferenceException,
)

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
KBO_DATA_DIR = ROOT / "kbo_data"

SEASON_TYPE = "KBO 정규시즌"
HEADLESS = True
WAIT_SEC = 2.5

TEAMS = ["KIA", "KT", "LG", "NC", "SSG", "두산", "롯데", "삼성", "키움", "한화"]
BASE = "https://www.koreabaseball.com/Record/Player"

TARGETS = {
    "hitter": {
        "pages": [
            f"{BASE}/HitterBasic/Basic1.aspx",
            f"{BASE}/HitterBasic/Basic2.aspx",
        ],
        "label": "타자",
    },
    "pitcher": {
        "pages": [
            f"{BASE}/PitcherBasic/Basic1.aspx",
            f"{BASE}/PitcherBasic/Basic2.aspx",
        ],
        "label": "투수",
    },
}

SEASON_SELECT_ID = "cphContents_cphContents_cphContents_ddlSeason_ddlSeason"
SERIES_SELECT_ID = "cphContents_cphContents_cphContents_ddlSeries_ddlSeries"
TEAM_SELECT_ID = "cphContents_cphContents_cphContents_ddlTeam_ddlTeam"


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
# 드롭다운 (kbo_team_scraper.py 그대로)
# ============================================================
def safe_select(driver, element_id, value_text):
    try:
        el = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, element_id))
        )
        sel = Select(el)
        current = sel.first_selected_option.text.strip()
        if current == value_text:
            return True
        sel.select_by_visible_text(value_text)
        time.sleep(WAIT_SEC + 1)
        return True
    except Exception as e:
        print(f"    [경고] {element_id}='{value_text}' 선택 실패: {type(e).__name__}")
        return False


def set_filters(driver, year, team):
    safe_select(driver, SEASON_SELECT_ID, year)
    safe_select(driver, SERIES_SELECT_ID, SEASON_TYPE)
    safe_select(driver, TEAM_SELECT_ID, team)


# ============================================================
# 테이블 파싱 (kbo_team_scraper.py 그대로)
# ============================================================
def parse_table(driver):
    headers, rows = [], []
    
    table = None
    selectors = [
        "table.tData01.tt",
        "table.tData01",
        "table.tData",
        "#cphContents_cphContents_cphContents_udpContent table",
    ]
    for sel in selectors:
        try:
            t = driver.find_element(By.CSS_SELECTOR, sel)
            if t.find_elements(By.CSS_SELECTOR, "tbody tr"):
                table = t
                break
        except NoSuchElementException:
            continue
    
    if table is None:
        for t in driver.find_elements(By.TAG_NAME, "table"):
            tbody_rows = t.find_elements(By.CSS_SELECTOR, "tbody tr")
            if tbody_rows and len(tbody_rows[0].find_elements(By.TAG_NAME, "td")) >= 3:
                table = t
                break
    
    if table is None:
        return headers, rows
    
    for th in table.find_elements(By.CSS_SELECTOR, "thead th"):
        txt = th.text.strip()
        if txt:
            headers.append(txt)
    
    for tr in table.find_elements(By.CSS_SELECTOR, "tbody tr"):
        cells = [td.text.strip() for td in tr.find_elements(By.TAG_NAME, "td")]
        if cells and any(c for c in cells):
            rows.append(cells)
    return headers, rows


# ============================================================
# 페이지네이션 (kbo_team_scraper.py 그대로)
# ============================================================
def get_max_page(driver):
    nums = []
    for sel in [".paging a", "div.paging a"]:
        for a in driver.find_elements(By.CSS_SELECTOR, sel):
            t = a.text.strip()
            if t.isdigit():
                nums.append(int(t))
        if nums:
            break
    return max(nums) if nums else 1


def navigate_to_page(driver, target_page):
    for _ in range(5):
        for link in driver.find_elements(By.CSS_SELECTOR, ".paging a"):
            if link.text.strip() == str(target_page):
                try:
                    link.click()
                    time.sleep(WAIT_SEC)
                    return True
                except StaleElementReferenceException:
                    time.sleep(1)
                    break
        try:
            nxt = driver.find_element(By.CSS_SELECTOR, "a[href*='btnNext']")
            nxt.click()
            time.sleep(WAIT_SEC)
        except NoSuchElementException:
            break
    return False


def discover_total_pages(driver):
    try:
        last = driver.find_element(By.CSS_SELECTOR, "a[href*='btnLast']")
        last.click()
        time.sleep(WAIT_SEC)
        total = get_max_page(driver)
        first = driver.find_element(By.CSS_SELECTOR, "a[href*='btnFirst']")
        first.click()
        time.sleep(WAIT_SEC)
        return total
    except NoSuchElementException:
        return get_max_page(driver)


# ============================================================
# 한 팀 × 한 URL 수집
# ============================================================
def scrape_team_url(driver, url, year, team):
    driver.get(url)
    time.sleep(WAIT_SEC + 1)
    
    set_filters(driver, year, team)
    
    total = discover_total_pages(driver)
    all_headers, all_rows = [], []
    
    for pg in range(1, total + 1):
        if pg > 1:
            navigate_to_page(driver, pg)
        headers, rows = parse_table(driver)
        if not all_headers and headers:
            all_headers = headers
        all_rows.extend(rows)
    
    return all_headers, all_rows


# ============================================================
# Basic1 + Basic2 병합
# ============================================================
def merge_basic(h1, r1, h2, r2):
    if not r2:
        return h1, r1
    skip = 4
    b2 = {}
    for row in r2:
        if len(row) >= skip:
            b2[(row[1], row[2])] = row[skip:]
    extra_headers = h2[skip:] if len(h2) > skip else []
    merged_h = h1 + extra_headers
    fill = [""] * len(extra_headers)
    merged_r = []
    for row in r1:
        if len(row) >= 3:
            merged_r.append(row + b2.get((row[1], row[2]), fill))
        else:
            merged_r.append(row + fill)
    return merged_h, merged_r


# ============================================================
# CSV 저장 (메타데이터 추가)
# ============================================================
def save_csv(filepath, headers, rows):
    filepath = Path(filepath)
    filepath.parent.mkdir(parents=True, exist_ok=True)
    
    with open(filepath, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        if headers:
            w.writerow(headers)
        w.writerows(rows)


# ============================================================
# 메인 수집 로직
# ============================================================
def collect_all_players(driver, year):
    """모든 팀의 타자/투수 데이터 수집."""
    results = {}  # {"hitter": (headers, rows), "pitcher": (headers, rows)}
    
    for key, cfg in TARGETS.items():
        label = cfg["label"]
        urls = cfg["pages"]
        
        print(f"\n  📊 [{label}] - 팀별 수집")
        
        all_headers = []
        all_rows = []
        
        for team in TEAMS:
            print(f"    • {team:4s} ... ", end="", flush=True)
            
            try:
                # Basic1
                h1, r1 = scrape_team_url(driver, urls[0], year, team)
                # Basic2
                h2, r2 = scrape_team_url(driver, urls[1], year, team)
                # 병합
                headers, rows = merge_basic(h1, r1, h2, r2)
                
                if not all_headers and headers:
                    all_headers = headers
                all_rows.extend(rows)
                
                print(f"{len(rows)}명")
            except Exception as e:
                print(f"❌ 실패: {e}")
                continue
        
        results[key] = (all_headers, all_rows)
        print(f"  → 합계: {len(all_rows)}명")
    
    return results


def save_results(results, year):
    """수집 결과 저장 (양쪽 위치에)."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    for key, (headers, rows) in results.items():
        if not rows:
            print(f"⚠️ {key}: 수집된 데이터 없음")
            continue
        
        # 1. data/players_latest_*.csv (예측용 최신)
        latest_path = DATA_DIR / f"players_latest_{key}.csv"
        save_csv(latest_path, headers, rows)
        print(f"  ✓ {latest_path.relative_to(ROOT)}: {len(rows)}명")
        
        # 2. kbo_data/kbo_YYYY_*_full.csv (기존 호환)
        legacy_path = KBO_DATA_DIR / f"kbo_{year}_{key}_full.csv"
        save_csv(legacy_path, headers, rows)
        print(f"  ✓ {legacy_path.relative_to(ROOT)}: {len(rows)}명")
    
    # 메타데이터 (수집 시각)
    meta_path = DATA_DIR / "players_latest_meta.txt"
    with open(meta_path, "w", encoding="utf-8") as f:
        f.write(f"last_updated: {timestamp}\n")
        f.write(f"year: {year}\n")
        f.write(f"hitter_count: {len(results.get('hitter', ([], []))[1])}\n")
        f.write(f"pitcher_count: {len(results.get('pitcher', ([], []))[1])}\n")
    print(f"  ✓ {meta_path.relative_to(ROOT)}")


# ============================================================
# 메인
# ============================================================
def main():
    parser = argparse.ArgumentParser(description="KBO 일일 선수 스탯 수집")
    parser.add_argument(
        "--year",
        type=str,
        default=str(date.today().year),
        help="수집할 연도 (기본: 현재 연도)",
    )
    args = parser.parse_args()
    
    year = args.year
    
    print("=" * 60)
    print(f"  일일 선수 스탯 수집 - {year}년")
    print(f"  대상: 10개 구단 × 타자/투수")
    print(f"  예상 소요: 약 7~10분")
    print("=" * 60)
    
    if not DATA_DIR.exists():
        print(f"❌ {DATA_DIR}가 없습니다.")
        sys.exit(1)
    
    print("\nChrome 드라이버 시작 중...")
    driver = create_driver()
    
    start_time = time.time()
    
    try:
        results = collect_all_players(driver, year)
        
        print("\n" + "─" * 60)
        print("  💾 결과 저장 중...")
        print("─" * 60)
        save_results(results, year)
        
        elapsed = time.time() - start_time
        print(f"\n{'=' * 60}")
        print(f"  ✅ 수집 완료 (소요 시간: {elapsed/60:.1f}분)")
        print(f"{'=' * 60}")
    
    except KeyboardInterrupt:
        print("\n⚠️ 사용자가 중단했습니다.")
    except Exception as e:
        print(f"\n❌ 오류: {e}")
        import traceback
        traceback.print_exc()
    finally:
        driver.quit()


if __name__ == "__main__":
    main()
