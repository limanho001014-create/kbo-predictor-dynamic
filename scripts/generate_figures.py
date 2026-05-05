"""
=============================================================
  발표 자료용 figure 3종 자동 생성 스크립트
=============================================================
출력:
  figures/feature_importance_kbo.png
  figures/confusion_matrix_kbo.png
  figures/roc_curve_kbo.png

사용법:
  python scripts/generate_figures.py

요구사항:
  - model/kbo_model.pkl (학습된 모델 번들)
  - model/kbo_feature_list.txt
  - data/games_history.csv (테스트 데이터)
=============================================================
"""

import os
import sys
import joblib
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib as mpl
from sklearn.metrics import (
    confusion_matrix,
    roc_curve,
    auc,
    ConfusionMatrixDisplay,
)

# 한글 폰트 설정 (운영체제별)
if sys.platform.startswith("win"):
    mpl.rcParams["font.family"] = "Malgun Gothic"
elif sys.platform == "darwin":
    mpl.rcParams["font.family"] = "AppleGothic"
else:
    mpl.rcParams["font.family"] = "NanumGothic"
mpl.rcParams["axes.unicode_minus"] = False

# 경로
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODEL_PATH = os.path.join(ROOT, "model", "kbo_model.pkl")
FEATURE_LIST_PATH = os.path.join(ROOT, "model", "kbo_feature_list.txt")
GAMES_PATH = os.path.join(ROOT, "data", "games_history.csv")
OUTPUT_DIR = os.path.join(ROOT, "figures")

os.makedirs(OUTPUT_DIR, exist_ok=True)


def load_model_bundle():
    """kbo_model.pkl 로드 (모델 + 메타정보 번들 가정)"""
    bundle = joblib.load(MODEL_PATH)
    if isinstance(bundle, dict):
        model = bundle.get("model") or bundle.get("clf") or bundle
        features = bundle.get("features") or bundle.get("feature_names")
    else:
        model = bundle
        features = None

    if features is None:
        with open(FEATURE_LIST_PATH, encoding="utf-8") as f:
            features = [l.strip() for l in f if l.strip()]
    return model, features


def load_test_data(features):
    """테스트 데이터 로드 — games_history.csv에서 필요한 피처/라벨만 추출"""
    df = pd.read_csv(GAMES_PATH)

    # 라벨 컬럼 자동 탐색
    label_col = None
    for cand in ["home_win", "label", "y", "result", "target"]:
        if cand in df.columns:
            label_col = cand
            break
    if label_col is None:
        raise ValueError("라벨 컬럼을 찾을 수 없습니다. (home_win/label/y/result/target)")

    # 누락 피처는 0으로 채움
    for f in features:
        if f not in df.columns:
            df[f] = 0.0

    X = df[features].fillna(0)
    y = df[label_col].astype(int)
    # 마지막 20%를 테스트로 사용 (시계열 가정)
    n = len(df)
    split = int(n * 0.8)
    return X.iloc[split:], y.iloc[split:]


# =============================================================
# 1) Feature Importance
# =============================================================
def plot_feature_importance(model, features, top_n=15):
    importances = None
    if hasattr(model, "feature_importances_"):
        importances = model.feature_importances_
    elif hasattr(model, "coef_"):
        importances = np.abs(model.coef_).ravel()
    else:
        print("⚠️  모델이 feature_importances_를 제공하지 않습니다.")
        return

    idx = np.argsort(importances)[::-1][:top_n]
    sel_feat = [features[i] for i in idx]
    sel_imp = importances[idx]

    fig, ax = plt.subplots(figsize=(10, 6))
    ax.barh(range(len(sel_feat))[::-1], sel_imp[::-1], color="#3b82f6")
    ax.set_yticks(range(len(sel_feat))[::-1])
    ax.set_yticklabels(sel_feat[::-1], fontsize=10)
    ax.set_xlabel("중요도 (Importance)", fontsize=11)
    ax.set_title(f"피처 중요도 Top {top_n} (KBO 승부 예측 모델)", fontsize=13, pad=12)
    ax.grid(axis="x", linestyle="--", alpha=0.5)
    plt.tight_layout()
    out = os.path.join(OUTPUT_DIR, "feature_importance_kbo.png")
    plt.savefig(out, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  ✅ {out}")


# =============================================================
# 2) Confusion Matrix
# =============================================================
def plot_confusion_matrix(model, X_test, y_test):
    y_pred = model.predict(X_test)
    cm = confusion_matrix(y_test, y_pred)

    fig, ax = plt.subplots(figsize=(6, 5))
    disp = ConfusionMatrixDisplay(
        confusion_matrix=cm,
        display_labels=["원정승", "홈승"],
    )
    disp.plot(ax=ax, cmap="Blues", values_format="d", colorbar=False)
    ax.set_title("Confusion Matrix (테스트셋)", fontsize=13, pad=12)
    ax.set_xlabel("예측", fontsize=11)
    ax.set_ylabel("실제", fontsize=11)
    plt.tight_layout()
    out = os.path.join(OUTPUT_DIR, "confusion_matrix_kbo.png")
    plt.savefig(out, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  ✅ {out}")


# =============================================================
# 3) ROC Curve
# =============================================================
def plot_roc_curve(model, X_test, y_test):
    if not hasattr(model, "predict_proba"):
        print("⚠️  predict_proba 미지원 모델입니다.")
        return

    y_score = model.predict_proba(X_test)[:, 1]
    fpr, tpr, _ = roc_curve(y_test, y_score)
    roc_auc = auc(fpr, tpr)

    fig, ax = plt.subplots(figsize=(6, 5))
    ax.plot(fpr, tpr, color="#ef4444", lw=2.2,
            label=f"ROC (AUC = {roc_auc:.3f})")
    ax.plot([0, 1], [0, 1], color="gray", lw=1, linestyle="--",
            label="Random (AUC = 0.5)")
    ax.set_xlim([0.0, 1.0])
    ax.set_ylim([0.0, 1.05])
    ax.set_xlabel("False Positive Rate", fontsize=11)
    ax.set_ylabel("True Positive Rate", fontsize=11)
    ax.set_title("ROC Curve (KBO 승부 예측 모델)", fontsize=13, pad=12)
    ax.legend(loc="lower right", fontsize=10)
    ax.grid(linestyle="--", alpha=0.5)
    plt.tight_layout()
    out = os.path.join(OUTPUT_DIR, "roc_curve_kbo.png")
    plt.savefig(out, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  ✅ {out}")


def main():
    print("=" * 60)
    print("  📊 발표 자료용 figure 생성")
    print("=" * 60)

    print("\n[1/3] 모델 & 데이터 로드...")
    model, features = load_model_bundle()
    print(f"  - 모델: {type(model).__name__}")
    print(f"  - 피처 수: {len(features)}")

    X_test, y_test = load_test_data(features)
    print(f"  - 테스트 샘플: {len(X_test)}건")

    print("\n[2/3] Feature Importance 그리는 중...")
    plot_feature_importance(model, features)

    print("\n[3/3] Confusion Matrix & ROC 그리는 중...")
    plot_confusion_matrix(model, X_test, y_test)
    plot_roc_curve(model, X_test, y_test)

    print("\n" + "=" * 60)
    print(f"  🎉 완료! → {OUTPUT_DIR}/")
    print("=" * 60)


if __name__ == "__main__":
    main()
