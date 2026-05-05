"""
=============================================================
  팀 스탯 자동 계산 스크립트
=============================================================
선수 개별 스탯에서 팀별 종합 스탯을 계산한다.

입력:
  data/players_latest_hitter.csv
  data/players_latest_pitcher.csv

출력:
  data/team_stats_latest.csv      ← 예측에 사용
  data/team_stats_snapshots/YYYY-MM-DD.csv  ← 누적 기록

계산 컬럼:
  타격: team_ops, top5_ops, hr_power, hitter_depth
  투수: team_era, ace_era, starter_era, bullpen_era, pitcher_depth

사용법:
  python scripts/compute_team_stats.py
=============================================================
"""

import sys
from datetime import datetime, date
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
HITTER_FILE = DATA_DIR / "players_latest_hitter.csv"
PITCHER_FILE = DATA_DIR / "players_latest_pitcher.csv"
OUTPUT_FILE = DATA_DIR / "team_stats_latest.csv"
SNAPSHOTS_DIR = DATA_DIR / "team_stats_snapshots"

TEAMS = ["KIA", "KT", "LG", "NC", "SSG", "두산", "롯데", "삼성", "키움", "한화"]


def parse_ip(ip_str):
    """이닝 표기 변환: '12 1/3' → 12.333."""
    if pd.isna(ip_str) or ip_str == "":
        return 0.0
    s = str(ip_str).strip()
    if " " in s:
        whole, frac = s.split(" ", 1)
        whole = float(whole)
        if "/" in frac:
            num, denom = frac.split("/")
            return whole + float(num) / float(denom)
        return whole
    if "/" in s:
        num, denom = s.split("/")
        return float(num) / float(denom)
    try:
        return float(s)
    except ValueError:
        return 0.0


def to_float(value, default=0.0):
    """안전한 float 변환."""
    if pd.isna(value) or value == "" or value == "-":
        return default
    try:
        return float(value)
    except (ValueError, TypeError):
        return default


def to_int(value, default=0):
    """안전한 int 변환."""
    if pd.isna(value) or value == "" or value == "-":
        return default
    try:
        return int(float(value))
    except (ValueError, TypeError):
        return default


def compute_hitter_stats(df_hitter, team):
    """팀의 타격 스탯 계산."""
    team_df = df_hitter[df_hitter["팀명"] == team].copy()
    
    if len(team_df) == 0:
        return None
    
    # 타석 수로 가중평균을 위해 PA를 숫자로
    team_df["PA_num"] = team_df["PA"].apply(to_int)
    team_df["OPS_num"] = team_df["OPS"].apply(to_float)
    team_df["HR_num"] = team_df["HR"].apply(to_int)
    
    # 1. 팀 OPS (타석 가중평균, 최소 30타석 이상만)
    qualified = team_df[team_df["PA_num"] >= 30]
    if len(qualified) > 0:
        total_pa = qualified["PA_num"].sum()
        if total_pa > 0:
            team_ops = (qualified["OPS_num"] * qualified["PA_num"]).sum() / total_pa
        else:
            team_ops = qualified["OPS_num"].mean()
    else:
        team_ops = team_df["OPS_num"].mean()
    
    # 2. Top 5 OPS (PA 기준 상위 + OPS 기준)
    pa_sorted = team_df.sort_values("PA_num", ascending=False).head(10)
    top5 = pa_sorted.sort_values("OPS_num", ascending=False).head(5)
    top5_ops = top5["OPS_num"].mean() if len(top5) > 0 else team_ops
    
    # 3. HR Power (팀 총 홈런)
    hr_power = team_df["HR_num"].sum()
    
    # 4. 타자 뎁스 (PA 30 이상 선수 수)
    hitter_depth = len(qualified)
    
    return {
        "team_ops": round(team_ops, 4),
        "top5_ops": round(top5_ops, 4),
        "hr_power": int(hr_power),
        "hitter_depth": int(hitter_depth),
    }


def compute_pitcher_stats(df_pitcher, team):
    """팀의 투수 스탯 계산."""
    team_df = df_pitcher[df_pitcher["팀명"] == team].copy()
    
    if len(team_df) == 0:
        return None
    
    # IP를 숫자로 변환
    team_df["IP_num"] = team_df["IP"].apply(parse_ip)
    team_df["ERA_num"] = team_df["ERA"].apply(to_float)
    team_df["G_num"] = team_df["G"].apply(to_int)
    team_df["GS_num"] = team_df.get("GS", pd.Series([0]*len(team_df))).apply(to_int) if "GS" in team_df.columns else 0
    
    # 등판수 5경기 이상만 신뢰
    qualified = team_df[team_df["G_num"] >= 5]
    
    # 1. 팀 ERA (이닝 가중평균)
    if len(qualified) > 0:
        total_ip = qualified["IP_num"].sum()
        if total_ip > 0:
            team_era = (qualified["ERA_num"] * qualified["IP_num"]).sum() / total_ip
        else:
            team_era = qualified["ERA_num"].mean()
    else:
        team_era = team_df["ERA_num"].mean() if len(team_df) > 0 else 4.5
    
    # 2. 에이스 ERA (이닝 가장 많은 5명 중 최저 ERA)
    if len(qualified) > 0:
        top_innings = qualified.sort_values("IP_num", ascending=False).head(5)
        ace_era = top_innings["ERA_num"].min() if len(top_innings) > 0 else team_era
    else:
        ace_era = team_era
    
    # 3. 선발 ERA (이닝 많은 상위 5명 평균 = 선발진으로 간주)
    if len(qualified) > 0:
        starters = qualified.sort_values("IP_num", ascending=False).head(5)
        # 이닝 가중평균
        ip_sum = starters["IP_num"].sum()
        if ip_sum > 0:
            starter_era = (starters["ERA_num"] * starters["IP_num"]).sum() / ip_sum
        else:
            starter_era = starters["ERA_num"].mean()
    else:
        starter_era = team_era
    
    # 4. 불펜 ERA (이닝 적은 나머지 평균)
    if len(qualified) > 5:
        relievers = qualified.sort_values("IP_num", ascending=False).iloc[5:]
        ip_sum = relievers["IP_num"].sum()
        if ip_sum > 0:
            bullpen_era = (relievers["ERA_num"] * relievers["IP_num"]).sum() / ip_sum
        else:
            bullpen_era = relievers["ERA_num"].mean()
    else:
        bullpen_era = team_era + 0.8  # 일반적으로 선발보다 살짝 높음
    
    # 5. 투수 뎁스 (등판 5회 이상 선수 수)
    pitcher_depth = len(qualified)
    
    return {
        "team_era": round(team_era, 3),
        "ace_era": round(ace_era, 3),
        "starter_era": round(starter_era, 3),
        "bullpen_era": round(bullpen_era, 3),
        "pitcher_depth": int(pitcher_depth),
    }


def compute_all_team_stats():
    """모든 팀의 스탯 계산."""
    # 데이터 로드
    if not HITTER_FILE.exists():
        print(f"❌ {HITTER_FILE} 없음. daily_collect_players.py 먼저 실행하세요.")
        sys.exit(1)
    if not PITCHER_FILE.exists():
        print(f"❌ {PITCHER_FILE} 없음. daily_collect_players.py 먼저 실행하세요.")
        sys.exit(1)
    
    df_hitter = pd.read_csv(HITTER_FILE)
    df_pitcher = pd.read_csv(PITCHER_FILE)
    
    print(f"✓ 타자 데이터 로드: {len(df_hitter)}명")
    print(f"✓ 투수 데이터 로드: {len(df_pitcher)}명")
    
    # 팀 컬럼명 자동 감지
    team_col_hitter = "팀명" if "팀명" in df_hitter.columns else "team"
    team_col_pitcher = "팀명" if "팀명" in df_pitcher.columns else "team"
    
    if team_col_hitter != "팀명":
        df_hitter = df_hitter.rename(columns={team_col_hitter: "팀명"})
    if team_col_pitcher != "팀명":
        df_pitcher = df_pitcher.rename(columns={team_col_pitcher: "팀명"})
    
    # 각 팀 계산
    team_stats = []
    for team in TEAMS:
        hitter_stats = compute_hitter_stats(df_hitter, team)
        pitcher_stats = compute_pitcher_stats(df_pitcher, team)
        
        if hitter_stats is None or pitcher_stats is None:
            print(f"  ⚠️ {team}: 데이터 부족, 스킵")
            continue
        
        row = {"team": team, **hitter_stats, **pitcher_stats}
        team_stats.append(row)
        print(f"  ✓ {team:4s} | OPS={hitter_stats['team_ops']:.3f} ERA={pitcher_stats['team_era']:.2f} 에이스={pitcher_stats['ace_era']:.2f}")
    
    return team_stats


def save_team_stats(team_stats):
    """팀 스탯을 두 곳에 저장."""
    if not team_stats:
        print("⚠️ 저장할 데이터 없음")
        return
    
    df = pd.DataFrame(team_stats)
    
    # 1. 최신 파일 (예측용)
    df.to_csv(OUTPUT_FILE, index=False, encoding="utf-8-sig")
    print(f"\n✓ {OUTPUT_FILE.relative_to(ROOT)}")
    
    # 2. 스냅샷 (날짜별 누적)
    SNAPSHOTS_DIR.mkdir(parents=True, exist_ok=True)
    snapshot_path = SNAPSHOTS_DIR / f"{date.today().strftime('%Y-%m-%d')}.csv"
    df["snapshot_date"] = date.today().strftime("%Y-%m-%d")
    df.to_csv(snapshot_path, index=False, encoding="utf-8-sig")
    print(f"✓ {snapshot_path.relative_to(ROOT)}")


def main():
    print("=" * 60)
    print("  팀 스탯 자동 계산")
    print("=" * 60)
    
    print("\n[1/2] 선수 데이터에서 팀 스탯 계산 중...")
    team_stats = compute_all_team_stats()
    
    print("\n[2/2] 결과 저장 중...")
    save_team_stats(team_stats)
    
    print("\n" + "=" * 60)
    print("  ✅ 완료")
    print("=" * 60)


if __name__ == "__main__":
    main()
