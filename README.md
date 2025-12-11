# 지하수저류댐 지형 적합성 자동평가 모델

이 프로젝트는 지형 데이터(DEM)와 유역 데이터(SHP)를 분석하여 지하수저류댐 설치에 적합한 후보지를 자동으로 도출하는 웹 애플리케이션입니다.

## 🚀 Streamlit 배포

이 프로젝트는 Streamlit Cloud를 통해 배포할 수 있습니다.

### Streamlit Cloud 배포 방법

1. **GitHub 저장소 연결**
   - [Streamlit Cloud](https://streamlit.io/cloud)에 접속
   - GitHub 계정으로 로그인
   - "New app" 클릭
   - 저장소: `rucachi/NGII_ICUH` 선택
   - Main file path: `streamlit_app.py` 입력
   - "Deploy!" 클릭

2. **환경 변수 설정 (선택사항)**
   - Streamlit Cloud 대시보드에서 "Settings" → "Secrets" 클릭
   - DEM 파일 경로 등 필요한 환경 변수 설정

## 📦 로컬 실행

### 1. 환경 설정

Python 3.11 이상의 환경이 필요합니다.

```bash
# 1. 가상환경 생성 및 활성화
python -m venv .venv
.\.venv\Scripts\activate  # Windows
# source .venv/bin/activate  # Linux/Mac

# 2. 필수 라이브러리 설치
pip install -r requirements.txt
```

> **참고**: 만약 `geopandas`나 `rasterio` 설치 중 에러가 발생한다면, `pipwin`을 사용하여 설치해 보세요.
> ```bash
> pip install pipwin
> pipwin install gdal
> pipwin install rasterio
> pipwin install geopandas
> ```

### 2. 데이터 준비

웹 지도에서 유역 경계를 표시하기 위해 SHP 파일을 GeoJSON으로 변환해야 합니다.

```bash
python analysis/prepare_data.py
```

### 3. Streamlit 앱 실행

```bash
streamlit run streamlit_app.py
```

브라우저에서 자동으로 열리며, 기본 주소는 `http://localhost:8501`입니다.

### 4. Flask 앱 실행 (기존 방식)

기존 Flask 앱을 사용하려면:

```bash
python analysis/app.py
```

브라우저에서 `http://localhost:5000`에 접속합니다.

## 📖 사용 방법

### Streamlit 앱

1. **지도 분석 탭**
   - 지도에서 관심영역을 그립니다 (Folium 지도 도구 사용)
   - "영역 분석 실행" 버튼을 클릭합니다
   - 결과를 확인하고 GeoJSON 또는 CSV로 다운로드합니다

2. **결과 분석 탭**
   - 발견된 후보지 목록을 확인합니다
   - 상위 후보지의 상세 정보를 확인합니다
   - 전체 데이터를 테이블로 확인합니다

### Flask 앱 (기존)

1. 브라우저를 열고 **[http://localhost:5000](http://localhost:5000)** 에 접속합니다.
2. **기본 분석**: 지도에 표시된 후보지를 클릭하여 상세 정보를 확인합니다.
3. **관심영역 분석**:
    - 상단의 **"관심영역 그리기"** 버튼 클릭
    - 지도에 원하는 영역 드래그 (다각형 그리기)
    - **"영역 분석 실행"** 버튼 클릭
4. **보고서 저장**: 후보지 팝업에서 **"보고서 저장"** 버튼을 눌러 결과를 텍스트 파일로 다운로드합니다.

## 📁 프로젝트 구조

```
NGII/
├── streamlit_app.py          # Streamlit 메인 앱
├── requirements.txt           # Python 패키지 의존성
├── .gitignore                # Git 제외 파일 목록
├── README.md                  # 프로젝트 문서
├── analysis/                  # 분석 모듈
│   ├── app.py                # Flask 앱 (기존)
│   ├── main.py               # CLI 메인 스크립트
│   ├── terrain_analysis.py   # 지형 분석 클래스
│   ├── site_evaluation.py    # 후보지 평가 클래스
│   └── prepare_data.py       # 데이터 준비 스크립트
├── output/                    # 분석 결과 출력 디렉토리
├── SHP/                       # Shapefile 데이터
└── web/                       # Flask 웹 인터페이스
    ├── templates/
    └── static/
```

## 🔧 기술 스택

- **Python 3.11+**
- **Streamlit** - 웹 애플리케이션 프레임워크
- **Folium** - 인터랙티브 지도
- **GeoPandas** - 지리공간 데이터 처리
- **Rasterio** - 래스터 데이터 처리
- **NumPy, SciPy** - 수치 계산

## 📝 라이선스

이 프로젝트는 연구 및 교육 목적으로 개발되었습니다.
