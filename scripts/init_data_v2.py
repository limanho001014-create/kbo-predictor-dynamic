"""
초기 데이터베이스 구축 스크립트 (v2 - 개선판).
기존 kbo_schedule_2024~2026.csv를 통합해서
games_history.csv 하나로 만든다.

v2 개선사항:
- 점수 없는 경기 → "미정" / "예정" 으로 분류 (이전엔 무승부)
- 진짜 무승부와 미래 경기 명확히 구분

사용법:
    python scripts/init_data.py

실행 결과:
    data/games_history.csv 생성
"""
import pandas as pd
from pathlib import Path
from datetime import datetime
import sys


# 프로젝트 루트
ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
KBO_DATA_DIR = ROOT / "kbo_data"


def load_existing_schedules():
    """기존 kbo_schedule_*.csv 파일들을 모두 읽어서 통합."""
    schedule_files = sorted(KBO_DATA_DIR.glob("kbo_schedule_20*.csv"))
    if not schedule_files:
        print(f"❌ {KBO_DATA_DIR}에 kbo_schedule_*.csv 파일이 없습니다.")
        sys.exit(1)
    
    dfs = []
    for f in schedule_files:
        if "all" in f.name:
            continue
        print(f"  ✓ {f.name} 로드")
        df = pd.read_csv(f)
        dfs.append(df)
    
    combined = pd.concat(dfs, ignore_index=True)
    print(f"\n총 {len(combined)}경기 로드됨 (정제 전)")
    return combined


def normalize_columns(df):
    """기존 컬럼을 새 표준 형식으로 변환."""
    
    # 필수 컬럼 확인
    required = ["game_date", "home_team", "away_team", "home_score", "away_score"]
    for col in required:
        if col not in df.columns:
            print(f"❌ 필수 컬럼 누락: {col}")
            sys.exit(1)
    
    # 날짜 정규화
    df["game_date"] = pd.to_datetime(df["game_date"]).dt.strftime("%Y-%m-%d")
    
    # season이 없으면 game_date에서 추출
    if "season" not in df.columns:
        df["season"] = pd.to_datetime(df["game_date"]).dt.year
    
    # ⭐ 핵심 변경: winner와 status를 점수 유무로 정확히 분류
    def calc_winner_and_status(row):
        try:
            h = float(row["home_score"]) if pd.notna(row["home_score"]) else None
            a = float(row["away_score"]) if pd.notna(row["away_score"]) else None
            
            # 점수가 없으면 미래 경기 또는 미정
            if h is None or a is None:
                return pd.Series({"winner": "미정", "status": "예정"})
            
            # 점수가 있으면 결과 계산
            if h > a:
                return pd.Series({"winner": "홈승", "status": "종료"})
            elif a > h:
                return pd.Series({"winner": "원정승", "status": "종료"})
            else:
                return pd.Series({"winner": "무승부", "status": "종료"})
        except (ValueError, TypeError):
            return pd.Series({"winner": "미정", "status": "취소"})
    
    # winner와 status 재계산
    result = df.apply(calc_winner_and_status, axis=1)
    df["winner"] = result["winner"]
    df["status"] = result["status"]
    
    # 추가 컬럼들 (기본값으로 채움)
    if "venue" not in df.columns:
        df["venue"] = ""
    if "doubleheader" not in df.columns:
        df["doubleheader"] = "N"
    if "source" not in df.columns:
        df["source"] = "KBO"
    if "collected_at" not in df.columns:
        df["collected_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # 표준 컬럼 순서
    standard_cols = [
        "game_date", "season", "home_team", "away_team",
        "home_score", "away_score", "winner",
        "status", "venue", "doubleheader",
        "source", "collected_at",
    ]
    df = df[standard_cols]
    
    # 중복 제거
    before = len(df)
    df = df.drop_duplicates(
        subset=["game_date", "home_team", "away_team"],
        keep="first",
    )
    after = len(df)
    if before != after:
        print(f"  중복 {before - after}건 제거 → {after}경기 남음")
    
    # 날짜순 정렬
    df = df.sort_values(["game_date", "home_team"]).reset_index(drop=True)
    
    return df


def create_predictions_log_template():
    """빈 predictions_log.csv 생성 (헤더만)."""
    columns = [
        "prediction_id",
        "game_date",
        "home_team",
        "away_team",
        "predicted_winner",
        "home_win_prob",
        "away_win_prob",
        "model_version",
        "predicted_at",
        "actual_winner",
        "is_correct",
        "scored_at",
    ]
    df = pd.DataFrame(columns=columns)
    return df


def main():
    print("=" * 60)
    print("초기 데이터베이스 구축 시작 (v2)")
    print("=" * 60)
    
    # 출력 디렉토리 준비
    DATA_DIR.mkdir(exist_ok=True)
    (DATA_DIR / "daily_schedule").mkdir(exist_ok=True)
    (DATA_DIR / "team_stats_snapshots").mkdir(exist_ok=True)
    
    # 1. games_history.csv 생성
    print("\n[1/2] games_history.csv 생성 중...")
    schedule_df = load_existing_schedules()
    games_df = normalize_columns(schedule_df)
    
    out_path = DATA_DIR / "games_history.csv"
    games_df.to_csv(out_path, index=False, encoding="utf-8-sig")
    print(f"\n✓ {out_path}")
    print(f"  - 총 {len(games_df)}경기")
    print(f"  - 기간: {games_df['game_date'].min()} ~ {games_df['game_date'].max()}")
    print(f"  - 시즌: {sorted(games_df['season'].unique().tolist())}")
    
    # 결과 분포 (status별)
    print(f"\n  📊 상태별 분포:")
    for status, count in games_df["status"].value_counts().items():
        print(f"    {status}: {count}건")
    
    # 종료 경기만의 결과 분포
    finished = games_df[games_df["status"] == "종료"]
    if len(finished) > 0:
        print(f"\n  📊 종료된 경기 결과 분포 ({len(finished)}건):")
        for winner, count in finished["winner"].value_counts().items():
            pct = count / len(finished) * 100
            print(f"    {winner}: {count}건 ({pct:.1f}%)")
    
    # 시즌별 종료 경기 수
    print(f"\n  📊 시즌별 종료 경기:")
    for season, group in finished.groupby("season"):
        print(f"    {season}: {len(group)}경기")
    
    # 2. predictions_log.csv 생성
    print("\n[2/2] predictions_log.csv 템플릿 생성 중...")
    pred_df = create_predictions_log_template()
    out_path = DATA_DIR / "predictions_log.csv"
    pred_df.to_csv(out_path, index=False, encoding="utf-8-sig")
    print(f"✓ {out_path} (헤더만, 0건)")
    
    print("\n" + "=" * 60)
    print("✅ 초기화 완료!")
    print("=" * 60)
    print(f"\n다음 단계:")
    print(f"  1. {DATA_DIR}/ 폴더 확인")
    print(f"  2. games_history.csv 열어서 status 컬럼 확인")
    print(f"  3. Day 2: daily_collect.py 작성")


if __name__ == "__main__":
    main()
