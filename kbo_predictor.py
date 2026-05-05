"""
============================================================
  KBO 예측 유틸리티 v3 (Streamlit 연동용)
============================================================
"""

import joblib
import pandas as pd
import numpy as np
import os

MODEL_PATH = "model/kbo_model.pkl"
_artifact = None


def load_model():
    global _artifact
    if _artifact is None:
        if not os.path.exists(MODEL_PATH):
            raise FileNotFoundError(f"{MODEL_PATH} 없음")
        _artifact = joblib.load(MODEL_PATH)
    return _artifact


def get_feature_info():
    art = load_model()
    return {
        "features": art["features"],
        "model_name": art["model_name"],
        "label_map": art["label_map"],
        "version": art.get("version", "v3"),
    }


def predict_kbo_game(feature_dict: dict) -> dict:
    art = load_model()
    features = art["features"]
    X = pd.DataFrame(
        [[feature_dict.get(f, 0) for f in features]], columns=features
    ).astype(float)
    if art.get("needs_scale") and art.get("scaler") is not None:
        X = art["scaler"].transform(X)
    proba = art["model"].predict_proba(X)[0]
    home_prob = float(proba[1])
    away_prob = float(proba[0])
    if abs(home_prob - 0.5) > 0.15:
        confidence = "높음"
    elif abs(home_prob - 0.5) > 0.08:
        confidence = "중간"
    else:
        confidence = "낮음"
    return {
        "home_win_prob": home_prob,
        "away_win_prob": away_prob,
        "predicted": "홈승" if home_prob > away_prob else "원정승",
        "confidence": confidence,
    }


def predict_with_defaults(
    home_team: str, away_team: str,
    home_team_ops: float = None, away_team_ops: float = None,
    home_team_era: float = None, away_team_era: float = None,
    home_last10_wr: float = 0.5, away_last10_wr: float = 0.5,
    home_season_wr: float = 0.5, away_season_wr: float = 0.5,
    home_home_wr: float = 0.5, away_away_wr: float = 0.5,
    h2h_home_wr: float = 0.5,
    home_run_diff: float = 0.0, away_run_diff: float = 0.0,
    home_streak: int = 0, away_streak: int = 0,
    rest_diff: int = 0, is_weekend: int = 0,
    home_starter_era: float = None, away_starter_era: float = None,
    home_bullpen_era: float = None, away_bullpen_era: float = None,
    home_ace_era: float = None, away_ace_era: float = None,
    home_pitcher_depth: int = None, away_pitcher_depth: int = None,
    home_top5_ops: float = None, away_top5_ops: float = None,
    home_hr_power: int = None, away_hr_power: int = None,
    home_hitter_depth: int = None, away_hitter_depth: int = None,
) -> dict:
    """고레벨: 모르는 값은 리그 평균 사용."""
    LEAGUE = {
        "OPS": 0.75, "ERA": 4.2, "STARTER": 4.0, "BULLPEN": 5.0,
        "ACE": 3.5, "P_DEPTH": 25, "TOP5": 0.9, "HR": 120, "H_DEPTH": 8,
    }
    h_ops = home_team_ops or LEAGUE["OPS"]
    a_ops = away_team_ops or LEAGUE["OPS"]
    h_era = home_team_era or LEAGUE["ERA"]
    a_era = away_team_era or LEAGUE["ERA"]
    h_star = home_starter_era or LEAGUE["STARTER"]
    a_star = away_starter_era or LEAGUE["STARTER"]
    h_bull = home_bullpen_era or LEAGUE["BULLPEN"]
    a_bull = away_bullpen_era or LEAGUE["BULLPEN"]
    h_ace = home_ace_era or LEAGUE["ACE"]
    a_ace = away_ace_era or LEAGUE["ACE"]
    h_pdep = home_pitcher_depth or LEAGUE["P_DEPTH"]
    a_pdep = away_pitcher_depth or LEAGUE["P_DEPTH"]
    h_top5 = home_top5_ops or LEAGUE["TOP5"]
    a_top5 = away_top5_ops or LEAGUE["TOP5"]
    h_hr = home_hr_power or LEAGUE["HR"]
    a_hr = away_hr_power or LEAGUE["HR"]
    h_hdep = home_hitter_depth or LEAGUE["H_DEPTH"]
    a_hdep = away_hitter_depth or LEAGUE["H_DEPTH"]
    
    feature_dict = {
        "home_era": h_era, "away_era": a_era,
        "home_ops": h_ops, "away_ops": a_ops,
        "home_last10_win_rate": home_last10_wr,
        "away_last10_win_rate": away_last10_wr,
        "home_season_win_rate": home_season_wr,
        "away_season_win_rate": away_season_wr,
        "home_home_win_rate": home_home_wr,
        "away_away_win_rate": away_away_wr,
        "h2h_home_win_rate": h2h_home_wr,
        "home_run_diff_last10": home_run_diff,
        "away_run_diff_last10": away_run_diff,
        "home_streak": home_streak, "away_streak": away_streak,
        "rest_diff": rest_diff, "is_weekend": is_weekend,
        "home_starter_era": h_star, "away_starter_era": a_star,
        "home_bullpen_era": h_bull, "away_bullpen_era": a_bull,
        "home_ace_era": h_ace, "away_ace_era": a_ace,
        "home_pitcher_depth": h_pdep, "away_pitcher_depth": a_pdep,
        "home_top5_ops": h_top5, "away_top5_ops": a_top5,
        "home_hr_power": h_hr, "away_hr_power": a_hr,
        "home_hitter_depth": h_hdep, "away_hitter_depth": a_hdep,
        "era_diff": a_era - h_era, "ops_diff": h_ops - a_ops,
        "last10_wr_diff": home_last10_wr - away_last10_wr,
        "season_wr_diff": home_season_wr - away_season_wr,
        "run_diff_gap": home_run_diff - away_run_diff,
        "streak_diff": home_streak - away_streak,
        "venue_wr_diff": home_home_wr - away_away_wr,
        "starter_era_diff": a_star - h_star,
        "bullpen_era_diff": a_bull - h_bull,
        "ace_era_diff": a_ace - h_ace,
        "top5_ops_diff": h_top5 - a_top5,
        "hr_power_diff": h_hr - a_hr,
        "hitter_depth_diff": h_hdep - a_hdep,
        "pitcher_depth_diff": h_pdep - a_pdep,
    }
    result = predict_kbo_game(feature_dict)
    result["home_team"] = home_team
    result["away_team"] = away_team
    return result


if __name__ == "__main__":
    print("=" * 60)
    print("  KBO v3 예측 유틸리티 테스트")
    print("=" * 60)
    
    info = get_feature_info()
    print(f"\n📦 모델: {info['model_name']} (버전: {info['version']})")
    print(f"   피처 수: {len(info['features'])}")
    
    print("\n🎯 예측 1: 강한 투수진(한화) vs 약한 투수진(키움)")
    r = predict_with_defaults(
        home_team="한화", away_team="키움",
        home_team_era=2.5, away_team_era=4.5,
        home_starter_era=2.8, away_starter_era=5.0,
        home_ace_era=1.9, away_ace_era=4.2,
        home_top5_ops=0.95, away_top5_ops=0.75,
        home_season_wr=0.60, away_season_wr=0.40,
    )
    print(f"   홈승: {r['home_win_prob']*100:.1f}%  원정승: {r['away_win_prob']*100:.1f}%")
    print(f"   예측: {r['predicted']} (확신도: {r['confidence']})")
    
    print("\n🎯 예측 2: 대등한 팀 (LG vs 두산)")
    r = predict_with_defaults(
        home_team="LG", away_team="두산",
        home_season_wr=0.52, away_season_wr=0.51,
    )
    print(f"   홈승: {r['home_win_prob']*100:.1f}%  원정승: {r['away_win_prob']*100:.1f}%")
    print(f"   예측: {r['predicted']} (확신도: {r['confidence']})")
    
    print("\n" + "=" * 60)
    print("  ✅ v3 모델 정상 동작, Streamlit 연동 OK")
    print("=" * 60)
