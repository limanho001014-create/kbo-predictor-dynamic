# KBO 승부 예측 Streamlit 앱 🎯

> 곽건님, 바로 시작할 수 있는 MVP 스타터 팩입니다.

---

## 📦 포함된 파일

```
streamlit_app/
├── app.py                          ← 메인 앱 (실행 파일)
├── kbo_predictor.py                ← 예측 모듈 (유현성 제작)
├── requirements.txt                ← 필요 패키지
├── README.md                       ← 이 파일
│
├── model/                          ← 학습된 v3 모델
│   ├── kbo_model.pkl              (검증셋 정확도 58.6%)
│   └── kbo_feature_list.txt
│
├── kbo_data/                       ← 팀 스탯 자동 채움용
│   ├── kbo_2025_hitter_full.csv
│   ├── kbo_2025_pitcher_full.csv
│   ├── kbo_2026_hitter_full.csv
│   └── kbo_2026_pitcher_full.csv
│
└── .streamlit/                     ← 테마 설정
    └── config.toml                (다크모드 + 주황색)
```

---

## 🚀 3단계로 시작하기

### Step 1: 폴더 위치 확인

이 폴더 그대로 **작업 위치에 두기**:

```
C:\Users\anho0\Downloads\캡스톤 데이터\streamlit_app\
```

### Step 2: 패키지 설치

VSCode에서 이 폴더 열고 (`Ctrl + K, Ctrl + O`) 터미널에서:

```powershell
python -m pip install -r requirements.txt
```

설치 확인:
```powershell
streamlit --version
```

### Step 3: 앱 실행

```powershell
streamlit run app.py
```

브라우저가 자동으로 열리면서 `http://localhost:8501` 접속!

종료: 터미널에서 `Ctrl + C`

---

## 🎨 현재 기능

### ✅ 구현 완료
- [x] 홈팀/원정팀 선택 드롭다운
- [x] 2025 시즌 팀 스탯 자동 조회 및 표시
- [x] v3 모델 기반 승률 예측
- [x] 고급 옵션 (시즌 승률, 연승/연패 등)
- [x] 결과 시각화 (메트릭 + 바 차트)
- [x] 확신도 표시 (높음/중간/낮음)
- [x] 팀 스탯 비교 탭
- [x] 모델 설명 탭
- [x] 다크모드 테마

### 🔧 곽건님이 개선할 수 있는 부분
- [ ] Plotly 인터랙티브 차트로 업그레이드
- [ ] EPL 탭 추가 (있다면)
- [ ] 맞대결 이력 시각화
- [ ] 선수 개인 기록 조회 기능
- [ ] Streamlit Community Cloud 배포

---

## 🐛 에러가 날 때

### `ModuleNotFoundError: kbo_predictor`
→ `app.py`와 `kbo_predictor.py`가 같은 폴더에 있는지 확인

### `FileNotFoundError: model/kbo_model.pkl`
→ 폴더 구조가 맞는지 확인 (`model/` 폴더 안에 pkl 파일)
→ 터미널 현재 위치가 `streamlit_app/`인지 `dir`로 확인

### `streamlit 명령을 찾을 수 없음`
→ 대신 `python -m streamlit run app.py` 사용

### 예측이 항상 비슷한 값이 나옴
→ 정상입니다! KBO 홈 어드밴티지(51%)가 반영된 결과예요
→ 팀 스탯 차이가 크면 그만큼 예측값도 기울어집니다

---

## 💡 개발 팁

### 파일 저장하면 자동 새로고침
`.streamlit/config.toml`에 `runOnSave = true` 설정되어 있어서,
`Ctrl+S` 하면 브라우저가 자동 업데이트됩니다.

### 코드 수정 후
터미널에서 앱 재시작 안 해도 됨. 그냥 브라우저 우측 상단 "Rerun" 버튼.

### 캐싱 활용
- `@st.cache_data`: 데이터 로드 (팀 스탯 등)
- `@st.cache_resource`: 모델 같은 큰 객체

---

## 📞 문의

- **모델 관련 이슈**: 유현성
- **데이터 관련 이슈**: 임안호

막히면 **터미널 에러 메시지 전체 스크린샷** 공유해주세요.

---

## 🎯 최종 목표 (8주차)

1. 기능 완성 (승부 예측 + 팀 스탯 + 순위)
2. 심사위원이 사용해볼 수 있는 URL 공개 배포
3. 발표 시연 (실시간 예측 데모)

**Good luck! 🍀**
