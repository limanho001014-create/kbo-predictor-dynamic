# 팀 로고 폴더

이 폴더에 10개 팀의 로고 이미지를 넣으면 앱에 자동 표시됩니다.

## 필요한 파일

| 팀 | 파일명 |
|---|---|
| KIA 타이거즈 | `kia.png` |
| KT 위즈 | `kt.png` |
| LG 트윈스 | `lg.png` |
| NC 다이노스 | `nc.png` |
| SSG 랜더스 | `ssg.png` |
| 두산 베어스 | `doosan.png` |
| 롯데 자이언츠 | `lotte.png` |
| 삼성 라이온즈 | `samsung.png` |
| 키움 히어로즈 | `kiwoom.png` |
| 한화 이글스 | `hanwha.png` |

## 🚀 방법 1: 자동 다운로드 (추천, 먼저 시도)

터미널에서:
```bash
python download_logos.py
```

KBO 공식 사이트에서 자동 다운로드를 시도합니다. 실패한 팀은 수동 방법 참고.

## ✋ 방법 2: 수동 다운로드 (확실함)

### 단계별

1. **https://www.koreabaseball.com/** 접속
2. 상단 메뉴 **"기록/순위"** → **"팀 순위"**
3. 순위표에 각 팀 로고가 표시됨
4. 로고 위에서 **우클릭 → "이미지를 다른 이름으로 저장"**
5. 파일명을 위 표의 영문 이름으로 저장 (예: `kia.png`)
6. 이 `logos/` 폴더에 저장

### 팁
- 해상도: 작은 것보다 큰 게 좋음 (최소 100x100 이상)
- 파일 형식: PNG 권장 (배경 투명 처리)
- 확장자는 `.png` / `.jpg` / `.jpeg` / `.svg` 모두 지원

## 🎨 방법 3: 위키피디아에서 가져오기

공식 사이트에서 못 받으면, 각 팀 위키피디아 페이지에서도 공식 엠블럼 확인 가능:

- [KIA 타이거즈](https://ko.wikipedia.org/wiki/KIA_%ED%83%80%EC%9D%B4%EA%B1%B0%EC%8A%A4)
- [KT 위즈](https://ko.wikipedia.org/wiki/KT_%EC%9C%84%EC%A6%88)
- [LG 트윈스](https://ko.wikipedia.org/wiki/LG_%ED%8A%B8%EC%9C%88%EC%8A%A4)
- [NC 다이노스](https://ko.wikipedia.org/wiki/NC_%EB%8B%A4%EC%9D%B4%EB%85%B8%EC%8A%A4)
- [SSG 랜더스](https://ko.wikipedia.org/wiki/SSG_%EB%9E%9C%EB%8D%94%EC%8A%A4)
- [두산 베어스](https://ko.wikipedia.org/wiki/%EB%91%90%EC%82%B0_%EB%B2%A0%EC%96%B4%EC%8A%A4)
- [롯데 자이언츠](https://ko.wikipedia.org/wiki/%EB%A1%AF%EB%8D%B0_%EC%9E%90%EC%9D%B4%EC%96%B8%EC%B8%A0)
- [삼성 라이온즈](https://ko.wikipedia.org/wiki/%EC%82%BC%EC%84%B1_%EB%9D%BC%EC%9D%B4%EC%98%A8%EC%A6%88)
- [키움 히어로즈](https://ko.wikipedia.org/wiki/%ED%82%A4%EC%9B%80_%ED%9E%88%EC%96%B4%EB%A1%9C%EC%A6%88)
- [한화 이글스](https://ko.wikipedia.org/wiki/%ED%95%9C%ED%99%94_%EC%9D%B4%EA%B8%80%EC%8A%A4)

## ⚠️ 저작권 고지

팀 로고는 각 구단 및 KBO의 **등록 상표**입니다.
본 앱은 **학술/교육 목적**의 캡스톤 프로젝트로, 영리 목적으로 배포하지 않습니다.

## 🔄 로고 확인

파일을 넣은 후 Streamlit 앱을 다시 실행하면 자동 반영됩니다.
앱 사이드바의 **"✅ 로고 10/10 로드 완료"** 메시지로 확인 가능.
