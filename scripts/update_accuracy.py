"""
=============================================================
  예측 정확도 채점 스크립트
=============================================================
predictions_log.csv의 PENDING 예측을
games_history.csv의 실제 결과와 비교해서 채점한다.

워크플로우:
  1. predictions_log.csv 로드
  2. is_correct == "PENDING" 인 예측 찾기
  3. 게임 날짜가 지났는지 확인
  4. games_history.csv에서 실제 결과 조회
  5. 비교 → actual_winner, is_correct 업데이트

사용법:
  python scripts/update_accuracy.py
  
출력:
  - predictions_log.csv 업데이트
  - 누적 정확도 통계 표시
  - 모델 버전별 정확도
=============================================================
"""

import sys
from datetime import datetime, date
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
PREDICTIONS_LOG = DATA_DIR / "predictions_log.csv"
GAMES_HISTORY = DATA_DIR / "games_history.csv"


def load_predictions():
    """예측 로그 로드."""
    if not PREDICTIONS_LOG.exists():
        print(f"❌ {PREDICTIONS_LOG} 없음. 먼저 daily_predict.py를 실행하세요.")
        sys.exit(1)
    
    df = pd.read_csv(PREDICTIONS_LOG)
    print(f"✓ 예측 로그 로드: 총 {len(df)}건")
    return df


def load_games():
    """경기 결과 로드."""
    if not GAMES_HISTORY.exists():
        print(f"❌ {GAMES_HISTORY} 없음.")
        sys.exit(1)
    
    df = pd.read_csv(GAMES_HISTORY)
    print(f"✓ 경기 히스토리 로드: 총 {len(df)}경기")
    return df


def find_actual_result(games_df, game_date, home_team, away_team):
    """
    games_history에서 해당 경기의 실제 결과를 찾는다.
    
    Returns:
        (actual_winner, status) 또는 (None, None) if not found
        actual_winner: "홈승", "원정승", "무승부", "취소" 또는 None
    """
    match = games_df[
        (games_df["game_date"] == game_date) &
        (games_df["home_team"] == home_team) &
        (games_df["away_team"] == away_team)
    ]
    
    if len(match) == 0:
        return None, None
    
    row = match.iloc[0]
    status = row["status"]
    winner = row["winner"]
    
    # 종료된 경기만 채점
    if status != "종료":
        return None, status
    
    return winner, status


def update_predictions(predictions_df, games_df):
    """
    PENDING 예측을 채점한다.
    
    Returns:
        (updated_count, scored_count, still_pending_count)
    """
    today = date.today().strftime("%Y-%m-%d")
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # PENDING 예측만 필터링
    pending_mask = predictions_df["is_correct"] == "PENDING"
    pending = predictions_df[pending_mask]
    
    print(f"\n📋 채점 대기중인 예측: {len(pending)}건")
    
    if len(pending) == 0:
        print("  채점할 예측 없음")
        return 0, 0, 0
    
    updated_count = 0
    scored_count = 0
    still_pending_count = 0
    cancelled_count = 0
    
    for idx, row in pending.iterrows():
        game_date = row["game_date"]
        home_team = row["home_team"]
        away_team = row["away_team"]
        predicted = row["predicted_winner"]
        
        # 미래 경기는 스킵
        if game_date >= today:
            still_pending_count += 1
            continue
        
        # 실제 결과 조회
        actual_winner, status = find_actual_result(
            games_df, game_date, home_team, away_team
        )
        
        if actual_winner is None:
            if status == "예정":
                # 어제 경기인데 아직 결과가 안 들어옴
                print(f"  ⏳ {game_date} {away_team} vs {home_team}: 결과 미수집")
                still_pending_count += 1
            else:
                print(f"  ⚠️ {game_date} {away_team} vs {home_team}: 데이터 없음")
                still_pending_count += 1
            continue
        
        # 취소된 경기는 채점 제외
        if actual_winner in ["취소", "미정"]:
            predictions_df.at[idx, "actual_winner"] = actual_winner
            predictions_df.at[idx, "is_correct"] = "CANCELLED"
            predictions_df.at[idx, "scored_at"] = now
            cancelled_count += 1
            print(f"  🚫 {game_date} {away_team} vs {home_team}: {actual_winner}")
            continue
        
        # 무승부는 채점 제외 (둘 중 하나만 맞출 수 없음)
        if actual_winner == "무승부":
            predictions_df.at[idx, "actual_winner"] = "무승부"
            predictions_df.at[idx, "is_correct"] = "DRAW"
            predictions_df.at[idx, "scored_at"] = now
            print(f"  🤝 {game_date} {away_team} vs {home_team}: 무승부")
            continue
        
        # 정상 채점
        is_correct = (predicted == actual_winner)
        predictions_df.at[idx, "actual_winner"] = actual_winner
        predictions_df.at[idx, "is_correct"] = "TRUE" if is_correct else "FALSE"
        predictions_df.at[idx, "scored_at"] = now
        
        emoji = "✅" if is_correct else "❌"
        winner_team = home_team if actual_winner == "홈승" else away_team
        predicted_team = home_team if predicted == "홈승" else away_team
        
        print(f"  {emoji} {game_date} {away_team} vs {home_team}")
        print(f"     예측: {predicted_team} → 실제: {winner_team}")
        
        updated_count += 1
        if is_correct:
            scored_count += 1
    
    return updated_count, scored_count, still_pending_count


def show_accuracy_summary(predictions_df):
    """누적 정확도 통계 표시."""
    # 채점 완료된 예측만 필터
    scored = predictions_df[
        predictions_df["is_correct"].isin(["TRUE", "FALSE"])
    ].copy()
    
    if len(scored) == 0:
        print("\n📊 아직 채점된 예측이 없습니다.")
        return
    
    print(f"\n{'=' * 60}")
    print(f"  📊 누적 정확도 통계")
    print(f"{'=' * 60}")
    
    # 전체 통계
    total = len(scored)
    correct = (scored["is_correct"] == "TRUE").sum()
    accuracy = correct / total * 100
    
    print(f"\n  전체:")
    print(f"    채점 경기: {total}건")
    print(f"    적중: {correct}건")
    print(f"    정확도: {accuracy:.1f}%")
    
    # 모델 버전별 통계
    if "model_version" in scored.columns:
        print(f"\n  모델 버전별:")
        for version in scored["model_version"].unique():
            v_data = scored[scored["model_version"] == version]
            v_total = len(v_data)
            v_correct = (v_data["is_correct"] == "TRUE").sum()
            v_acc = v_correct / v_total * 100
            print(f"    {version}: {v_correct}/{v_total} ({v_acc:.1f}%)")
    
    # 최근 7일 정확도
    today = date.today()
    seven_days_ago = (today - pd.Timedelta(days=7)).strftime("%Y-%m-%d")
    recent = scored[scored["game_date"] >= seven_days_ago]
    
    if len(recent) > 0:
        r_total = len(recent)
        r_correct = (recent["is_correct"] == "TRUE").sum()
        r_acc = r_correct / r_total * 100
        print(f"\n  최근 7일:")
        print(f"    채점 경기: {r_total}건")
        print(f"    정확도: {r_acc:.1f}%")
    
    # 확률대별 정확도 (모델 calibration 검증)
    print(f"\n  확률대별 정확도:")
    
    # 홈승 예측한 경우의 평균 확률 vs 실제 적중률
    scored["max_prob"] = scored[["home_win_prob", "away_win_prob"]].max(axis=1)
    
    bins = [0.5, 0.55, 0.60, 0.65, 0.70, 1.01]
    bin_labels = ["50-55%", "55-60%", "60-65%", "65-70%", "70%+"]
    
    scored["prob_bin"] = pd.cut(scored["max_prob"], bins=bins, labels=bin_labels, right=False)
    
    for bin_label in bin_labels:
        bin_data = scored[scored["prob_bin"] == bin_label]
        if len(bin_data) > 0:
            b_total = len(bin_data)
            b_correct = (bin_data["is_correct"] == "TRUE").sum()
            b_acc = b_correct / b_total * 100
            print(f"    {bin_label}: {b_correct}/{b_total} ({b_acc:.1f}%)")


def main():
    print("=" * 60)
    print("  예측 정확도 채점")
    print("=" * 60)
    
    print("\n[1/3] 데이터 로드 중...")
    predictions_df = load_predictions()
    games_df = load_games()
    
    print("\n[2/3] 채점 진행...")
    updated, correct, still_pending = update_predictions(predictions_df, games_df)
    
    print("\n[3/3] 결과 저장 중...")
    if updated > 0 or still_pending > 0:
        predictions_df.to_csv(PREDICTIONS_LOG, index=False, encoding="utf-8-sig")
        print(f"  ✓ {PREDICTIONS_LOG.relative_to(ROOT)} 업데이트됨")
    
    # 채점 결과 요약
    print(f"\n{'=' * 60}")
    print(f"  📋 오늘의 채점 결과")
    print(f"{'=' * 60}")
    print(f"  채점 완료: {updated}건")
    if updated > 0:
        accuracy = correct / updated * 100
        print(f"  적중: {correct}건 ({accuracy:.1f}%)")
    print(f"  대기 중: {still_pending}건")
    
    # 전체 누적 통계
    show_accuracy_summary(predictions_df)
    
    print(f"\n{'=' * 60}")
    print("  ✅ 채점 완료")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
