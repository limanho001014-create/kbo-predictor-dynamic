"""
=============================================================
  일일 KBO 경기 예측 스크립트 (최종)
=============================================================
오늘 경기 일정에 대해 자동으로 예측을 생성한다.

워크플로우:
  1. data/daily_schedule/YYYY-MM-DD.csv  ← 오늘 일정
  2. data/team_stats_latest.csv          ← 팀 스탯
  3. data/games_history.csv              ← 팀 폼 계산용
  4. kbo_predictor.predict_with_defaults() ← 예측

출력:
  data/predictions_log.csv 업데이트

사용법:
  python scripts/daily_predict.py
  python scripts/daily_predict.py --date 2026-05-05
=============================================================
"""

import argparse
import sys
from datetime import datetime, date
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
DAILY_SCHEDULE_DIR = DATA_DIR / "daily_schedule"
PREDICTIONS_LOG = DATA_DIR / "predictions_log.csv"
TEAM_STATS = DATA_DIR / "team_stats_latest.csv"
GAMES_HISTORY = DATA_DIR / "games_history.csv"

sys.path.insert(0, str(ROOT))

MODEL_VERSION = "v3-dynamic"


def load_predictor():
    try:
        import kbo_predictor
        return kbo_predictor
    except ImportError as e:
        print(f"❌ kbo_predictor를 import할 수 없습니다: {e}")
        sys.exit(1)


def load_today_schedule(target_date):
    schedule_file = DAILY_SCHEDULE_DIR / f"{target_date.strftime('%Y-%m-%d')}.csv"
    if not schedule_file.exists():
        print(f"❌ 일정 파일이 없습니다: {schedule_file}")
        sys.exit(1)
    return pd.read_csv(schedule_file)


def load_team_stats():
    if not TEAM_STATS.exists():
        print(f"⚠️ {TEAM_STATS} 없음. 리그 평균값으로 예측합니다.")
        return {}
    df = pd.read_csv(TEAM_STATS)
    return {row["team"]: row.to_dict() for _, row in df.iterrows()}


def compute_team_form(games_df, team, target_date):
    """games_history에서 팀의 최근 폼 계산."""
    finished = games_df[
        (games_df["status"] == "종료") &
        (games_df["game_date"] < target_date.strftime("%Y-%m-%d"))
    ]
    
    team_games = finished[
        (finished["home_team"] == team) | (finished["away_team"] == team)
    ].copy()
    
    if len(team_games) == 0:
        return {
            "season_wr": 0.5, "last10_wr": 0.5,
            "home_wr": 0.5, "away_wr": 0.5,
            "run_diff_last10": 0.0, "streak": 0,
        }
    
    team_games["is_home"] = team_games["home_team"] == team
    team_games["won"] = team_games.apply(
        lambda r: (r["winner"] == "홈승" and r["is_home"]) or 
                  (r["winner"] == "원정승" and not r["is_home"]),
        axis=1
    )
    
    season_wr = team_games["won"].mean()
    last10 = team_games.sort_values("game_date").tail(10)
    last10_wr = last10["won"].mean() if len(last10) > 0 else 0.5
    
    home_games = team_games[team_games["is_home"]]
    away_games = team_games[~team_games["is_home"]]
    home_wr = home_games["won"].mean() if len(home_games) > 0 else 0.5
    away_wr = away_games["won"].mean() if len(away_games) > 0 else 0.5
    
    if len(last10) > 0:
        run_diffs = []
        for _, r in last10.iterrows():
            try:
                hs = float(r["home_score"])
                as_ = float(r["away_score"])
                run_diffs.append((hs - as_) if r["is_home"] else (as_ - hs))
            except (ValueError, TypeError):
                continue
        run_diff_last10 = sum(run_diffs) / len(run_diffs) if run_diffs else 0.0
    else:
        run_diff_last10 = 0.0
    
    streak = 0
    sorted_games = team_games.sort_values("game_date", ascending=False)
    if len(sorted_games) > 0:
        first_won = sorted_games.iloc[0]["won"]
        for _, r in sorted_games.iterrows():
            if r["won"] == first_won:
                streak += 1 if first_won else -1
            else:
                break
    
    return {
        "season_wr": round(float(season_wr), 4),
        "last10_wr": round(float(last10_wr), 4),
        "home_wr": round(float(home_wr), 4),
        "away_wr": round(float(away_wr), 4),
        "run_diff_last10": round(float(run_diff_last10), 2),
        "streak": int(streak),
    }


def compute_h2h(games_df, home_team, away_team, target_date):
    """홈팀의 맞대결 승률."""
    finished = games_df[
        (games_df["status"] == "종료") &
        (games_df["game_date"] < target_date.strftime("%Y-%m-%d"))
    ]
    
    h2h = finished[
        ((finished["home_team"] == home_team) & (finished["away_team"] == away_team)) |
        ((finished["home_team"] == away_team) & (finished["away_team"] == home_team))
    ].copy()
    
    if len(h2h) == 0:
        return 0.5
    
    h2h["home_won"] = h2h.apply(
        lambda r: (r["winner"] == "홈승" and r["home_team"] == home_team) or
                  (r["winner"] == "원정승" and r["away_team"] == home_team),
        axis=1
    )
    return round(float(h2h["home_won"].mean()), 4)


def predict_game(predictor, home_team, away_team, target_date, team_stats, games_df):
    home_form = compute_team_form(games_df, home_team, target_date)
    away_form = compute_team_form(games_df, away_team, target_date)
    h2h_home_wr = compute_h2h(games_df, home_team, away_team, target_date)
    
    home_stats = team_stats.get(home_team, {})
    away_stats = team_stats.get(away_team, {})
    
    kwargs = {
        "home_team": home_team, "away_team": away_team,
        "home_season_wr": home_form["season_wr"],
        "away_season_wr": away_form["season_wr"],
        "home_last10_wr": home_form["last10_wr"],
        "away_last10_wr": away_form["last10_wr"],
        "home_home_wr": home_form["home_wr"],
        "away_away_wr": away_form["away_wr"],
        "home_run_diff": home_form["run_diff_last10"],
        "away_run_diff": away_form["run_diff_last10"],
        "home_streak": home_form["streak"],
        "away_streak": away_form["streak"],
        "h2h_home_wr": h2h_home_wr,
        "is_weekend": 1 if target_date.weekday() >= 5 else 0,
    }
    
    if home_stats:
        kwargs.update({
            "home_team_ops": home_stats.get("team_ops"),
            "home_team_era": home_stats.get("team_era"),
            "home_starter_era": home_stats.get("starter_era"),
            "home_bullpen_era": home_stats.get("bullpen_era"),
            "home_ace_era": home_stats.get("ace_era"),
            "home_top5_ops": home_stats.get("top5_ops"),
            "home_hr_power": home_stats.get("hr_power"),
            "home_hitter_depth": home_stats.get("hitter_depth"),
            "home_pitcher_depth": home_stats.get("pitcher_depth"),
        })
    if away_stats:
        kwargs.update({
            "away_team_ops": away_stats.get("team_ops"),
            "away_team_era": away_stats.get("team_era"),
            "away_starter_era": away_stats.get("starter_era"),
            "away_bullpen_era": away_stats.get("bullpen_era"),
            "away_ace_era": away_stats.get("ace_era"),
            "away_top5_ops": away_stats.get("top5_ops"),
            "away_hr_power": away_stats.get("hr_power"),
            "away_hitter_depth": away_stats.get("hitter_depth"),
            "away_pitcher_depth": away_stats.get("pitcher_depth"),
        })
    
    try:
        return predictor.predict_with_defaults(**kwargs)
    except Exception as e:
        print(f"  ⚠️ 예측 실패: {e}")
        return None


def append_to_predictions_log(predictions):
    if not predictions:
        return 0
    
    new_df = pd.DataFrame(predictions)
    standard_cols = [
        "prediction_id", "game_date", "home_team", "away_team",
        "predicted_winner", "home_win_prob", "away_win_prob",
        "model_version", "predicted_at",
        "actual_winner", "is_correct", "scored_at",
    ]
    for col in standard_cols:
        if col not in new_df.columns:
            new_df[col] = ""
    new_df = new_df[standard_cols]
    
    if PREDICTIONS_LOG.exists():
        existing_df = pd.read_csv(PREDICTIONS_LOG)
    else:
        existing_df = pd.DataFrame(columns=standard_cols)
    
    new_keys = set(new_df["prediction_id"])
    existing_df = existing_df[~existing_df["prediction_id"].isin(new_keys)]
    
    combined = pd.concat([existing_df, new_df], ignore_index=True)
    combined = combined.sort_values(["game_date", "home_team"]).reset_index(drop=True)
    combined.to_csv(PREDICTIONS_LOG, index=False, encoding="utf-8-sig")
    
    return len(new_df)


def run_predictions(target_date):
    print("=" * 60)
    print(f"일일 예측 - 날짜: {target_date}")
    print(f"모델: {MODEL_VERSION}")
    print("=" * 60)
    
    print("\n[1/4] 데이터 로드 중...")
    schedule_df = load_today_schedule(target_date)
    print(f"  ✓ 일정: {len(schedule_df)}경기")
    
    if len(schedule_df) == 0:
        print("⚠️ 오늘 경기 없음")
        return
    
    team_stats = load_team_stats()
    print(f"  ✓ 팀 스탯: {len(team_stats)}팀")
    
    games_df = pd.read_csv(GAMES_HISTORY)
    print(f"  ✓ 경기 히스토리: {len(games_df)}경기")
    
    print("\n[2/4] 예측 모델 로드 중...")
    predictor = load_predictor()
    info = predictor.get_feature_info()
    print(f"  ✓ {info['model_name']} (버전: {info['version']})")
    
    print(f"\n[3/4] 예측 시작...")
    predictions = []
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    for idx, row in schedule_df.iterrows():
        home_team = row["home_team"]
        away_team = row["away_team"]
        game_date = row["game_date"]
        
        print(f"\n  [{idx+1}/{len(schedule_df)}] {away_team} vs {home_team}")
        
        result = predict_game(predictor, home_team, away_team, target_date, team_stats, games_df)
        if result is None:
            continue
        
        prediction_id = f"PRED_{game_date}_{home_team}_{away_team}"
        
        predictions.append({
            "prediction_id": prediction_id,
            "game_date": game_date,
            "home_team": home_team,
            "away_team": away_team,
            "predicted_winner": result["predicted"],
            "home_win_prob": round(result["home_win_prob"], 4),
            "away_win_prob": round(result["away_win_prob"], 4),
            "model_version": MODEL_VERSION,
            "predicted_at": now,
            "actual_winner": "",
            "is_correct": "PENDING",
            "scored_at": "",
        })
        
        winner = home_team if result["predicted"] == "홈승" else away_team
        prob = max(result["home_win_prob"], result["away_win_prob"]) * 100
        print(f"    → {winner} 승리 예측 ({prob:.1f}%, 확신도: {result['confidence']})")
        print(f"      홈({home_team}) {result['home_win_prob']*100:.1f}% vs 원정({away_team}) {result['away_win_prob']*100:.1f}%")
    
    print(f"\n[4/4] 결과 저장 중...")
    if predictions:
        added = append_to_predictions_log(predictions)
        print(f"  ✓ {added}개 예측 기록됨")
    
    print("\n" + "=" * 60)
    print("✅ 예측 완료")
    print("=" * 60)
    
    if predictions:
        print(f"\n📊 오늘의 예측 요약:")
        for p in predictions:
            winner = p["home_team"] if p["predicted_winner"] == "홈승" else p["away_team"]
            prob = max(p["home_win_prob"], p["away_win_prob"]) * 100
            print(f"  {p['away_team']:4s} vs {p['home_team']:4s}: {winner} 승리 ({prob:.1f}%)")


def main():
    parser = argparse.ArgumentParser(description="KBO 일일 경기 예측")
    parser.add_argument(
        "--date",
        type=lambda s: datetime.strptime(s, "%Y-%m-%d").date(),
        default=date.today(),
    )
    args = parser.parse_args()
    
    if not DATA_DIR.exists():
        print(f"❌ {DATA_DIR}가 없습니다.")
        sys.exit(1)
    
    run_predictions(args.date)


if __name__ == "__main__":
    main()
