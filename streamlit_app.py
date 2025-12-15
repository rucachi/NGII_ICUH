import streamlit as st
import os
import numpy as np
import rasterio
from rasterio.transform import xy
import geopandas as gpd
from shapely.geometry import Point, shape
import folium
from folium.plugins import Draw
from streamlit_folium import st_folium
import tempfile
import json

# Import analysis modules
import sys
sys.path.append('analysis')
from terrain_analysis import TerrainAnalyzer
from site_evaluation import SiteEvaluator

# 페이지 설정
st.set_page_config(
    page_title="지하수저류댐 적합성 평가",
    page_icon="🏔️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 커스텀 CSS 스타일
st.markdown("""
<style>
    /* 메인 컨테이너 패딩 조정 */
    .block-container {
        padding-top: 1rem;
        padding-bottom: 1rem;
    }
    
    /* 헤더 스타일 */
    .main-header {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 1.5rem;
        border-radius: 10px;
        margin-bottom: 1rem;
        color: white;
        text-align: center;
    }
    
    .main-header h1 {
        margin: 0;
        font-size: 1.8rem;
        font-weight: 600;
    }
    
    .main-header p {
        margin: 0.5rem 0 0 0;
        opacity: 0.9;
        font-size: 0.95rem;
    }
    
    /* 통계 카드 스타일 */
    .stat-card {
        background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
        padding: 1rem;
        border-radius: 10px;
        text-align: center;
        margin-bottom: 0.5rem;
    }
    
    .stat-card h3 {
        margin: 0;
        font-size: 1.5rem;
        color: #2d3748;
    }
    
    .stat-card p {
        margin: 0.25rem 0 0 0;
        color: #718096;
        font-size: 0.85rem;
    }
    
    /* 사이드바 스타일 */
    .sidebar .sidebar-content {
        background-color: #f8f9fa;
    }
    
    /* 버튼 스타일 개선 */
    .stButton > button {
        width: 100%;
        border-radius: 8px;
        font-weight: 500;
        transition: all 0.3s ease;
    }
    
    .stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(0,0,0,0.15);
    }
    
    /* 다운로드 버튼 */
    .stDownloadButton > button {
        width: 100%;
        border-radius: 8px;
    }
    
    /* 정보 박스 */
    .info-box {
        background-color: #e8f4f8;
        border-left: 4px solid #0ea5e9;
        padding: 1rem;
        border-radius: 0 8px 8px 0;
        margin: 1rem 0;
    }
    
    /* Expander 스타일 */
    .streamlit-expanderHeader {
        font-weight: 500;
        color: #2d3748;
    }
</style>
""", unsafe_allow_html=True)

# DEM 경로 설정 (환경변수 또는 기본값)
DEM_PATH = os.getenv("DEM_PATH", "output/dummy_dem.tif")
OUTPUT_DIR = "output/aoi_analysis"

# 세션 상태 초기화
if 'candidates' not in st.session_state:
    st.session_state.candidates = None
if 'aoi_geometry' not in st.session_state:
    st.session_state.aoi_geometry = None
if 'analysis_complete' not in st.session_state:
    st.session_state.analysis_complete = False

# ===== 사이드바 =====
with st.sidebar:
    # 로고/타이틀
    st.markdown("### 🏔️ 지하수저류댐")
    st.markdown("**지형 적합성 평가 시스템**")
    st.markdown("---")
    
    # DEM 파일 업로드
    st.markdown("#### 📁 데이터 업로드")
    uploaded_dem = st.file_uploader(
        "DEM 파일 (GeoTIFF)", 
        type=['tif', 'tiff'],
        help="분석할 지역의 수치표고모델(DEM) 파일을 업로드하세요."
    )
    
    if uploaded_dem:
        with tempfile.NamedTemporaryFile(delete=False, suffix='.tif') as tmp_file:
            tmp_file.write(uploaded_dem.read())
            DEM_PATH = tmp_file.name
            st.success(f"✅ {uploaded_dem.name}")
    
    st.markdown("---")
    
    # 분석 실행 섹션
    st.markdown("#### 🔬 분석 실행")
    
    # AOI 상태 표시
    if st.session_state.aoi_geometry:
        st.info("✅ 관심영역이 선택되었습니다.")
    else:
        st.warning("⚠️ 지도에서 관심영역을 그려주세요.")
    
    # 분석 버튼
    analyze_clicked = st.button(
        "🚀 분석 시작",
        type="primary",
        use_container_width=True,
        disabled=(st.session_state.aoi_geometry is None)
    )
    
    # 분석 로직
    if analyze_clicked and st.session_state.aoi_geometry:
        with st.spinner("분석 중..."):
            try:
                os.makedirs(OUTPUT_DIR, exist_ok=True)
                analyzer = TerrainAnalyzer(DEM_PATH, OUTPUT_DIR)
                
                dem, transform, meta, clipped_path = analyzer.clip_dem_by_geometry(
                    st.session_state.aoi_geometry
                )
                
                slope = analyzer.calculate_slope(dem)
                curv = analyzer.calculate_curvature(dem)
                flow = analyzer.calculate_flow_accumulation(dem)
                twi = analyzer.calculate_twi(slope, flow)
                
                evaluator = SiteEvaluator(OUTPUT_DIR)
                candidates = evaluator.evaluate(
                    slope, curv, twi, flow, transform, meta['crs']
                )
                
                st.session_state.candidates = candidates
                st.session_state.analysis_complete = True
                
                if candidates.empty:
                    st.warning("적합한 후보지가 없습니다.")
                else:
                    st.success(f"✅ {len(candidates)}개 후보지 발견!")
                    st.rerun()
                    
            except Exception as e:
                st.error(f"오류: {str(e)}")
    
    st.markdown("---")
    
    # 결과 통계 및 다운로드
    if st.session_state.candidates is not None and not st.session_state.candidates.empty:
        candidates = st.session_state.candidates
        
        st.markdown("#### 📊 분석 결과")
        
        # 통계 카드
        col1, col2 = st.columns(2)
        with col1:
            st.metric("후보지", f"{len(candidates)}개")
        with col2:
            st.metric("최고점수", f"{candidates['score'].max():.1f}")
        
        col1, col2 = st.columns(2)
        with col1:
            st.metric("평균점수", f"{candidates['score'].mean():.1f}")
        with col2:
            st.metric("평균경사", f"{candidates['slope'].mean():.1f}°")
        
        st.markdown("---")
        
        # 다운로드 버튼
        st.markdown("#### 💾 다운로드")
        
        geojson_str = candidates.to_json()
        st.download_button(
            "📍 GeoJSON",
            data=geojson_str,
            file_name="candidates.geojson",
            mime="application/json",
            use_container_width=True
        )
        
        csv_str = candidates.drop(columns='geometry').to_csv(index=False)
        st.download_button(
            "📄 CSV",
            data=csv_str,
            file_name="candidates.csv",
            mime="text/csv",
            use_container_width=True
        )
    
    st.markdown("---")
    
    # 사용 방법
    with st.expander("💡 사용 방법"):
        st.markdown("""
        1. DEM 파일을 업로드합니다
        2. 지도에서 **관심영역을 그립니다**
        3. **분석 시작** 버튼을 클릭합니다
        4. 결과를 지도에서 확인하고 다운로드합니다
        """)

# ===== 메인 컨텐츠 =====
# 헤더
st.markdown("""
<div class="main-header">
    <h2 style="margin-bottom: 0.5rem; font-size: 1.2rem; opacity: 0.9;">(재)국제도시물정보과학연구원</h2>
    <h1>🏔️ 지하수저류댐 지형 적합성 자동평가</h1>
    <p>지도에서 관심영역을 선택하고 최적의 후보지를 찾아보세요</p>
</div>
""", unsafe_allow_html=True)

# Folium 지도 생성
try:
    m = folium.Map(
        location=[36.5, 127.5],
        zoom_start=7,
        tiles='cartodbpositron'  # 더 현대적인 타일
    )
    
    # Draw 플러그인
    draw = Draw(
        export=True,
        position='topleft',
        draw_options={
            'polyline': False,
            'polygon': True,
            'rectangle': True,
            'circle': False,
            'marker': False,
            'circlemarker': False
        }
    )
    draw.add_to(m)
    
    # 분석 결과가 있으면 지도에 마커 추가
    if st.session_state.candidates is not None and not st.session_state.candidates.empty:
        candidates = st.session_state.candidates
        
        # 점수 범위 계산 (색상 그라데이션용)
        min_score = candidates['score'].min()
        max_score = candidates['score'].max()
        score_range = max_score - min_score if max_score != min_score else 1
        
        for idx, row in candidates.iterrows():
            # 점수에 따른 색상 (높을수록 빨강, 낮을수록 노랑)
            normalized_score = (row['score'] - min_score) / score_range
            
            # 색상 계산 (노랑 → 주황 → 빨강)
            if normalized_score < 0.5:
                # 노랑(#FFD700) → 주황(#FF8C00)
                r = 255
                g = int(215 - (215 - 140) * (normalized_score * 2))
                b = 0
            else:
                # 주황(#FF8C00) → 빨강(#FF0000)
                r = 255
                g = int(140 - 140 * ((normalized_score - 0.5) * 2))
                b = 0
            
            color = f'#{r:02x}{g:02x}{b:02x}'
            
            # 팝업 내용
            popup_html = f"""
            <div style="font-family: sans-serif; min-width: 200px;">
                <h4 style="margin: 0 0 10px 0; color: #2d3748;">🎯 후보지 #{idx+1}</h4>
                <table style="width: 100%; border-collapse: collapse;">
                    <tr><td style="padding: 4px 0;"><b>점수</b></td><td style="text-align: right; color: {color}; font-weight: bold;">{row['score']:.1f}</td></tr>
                    <tr><td style="padding: 4px 0;"><b>경사도</b></td><td style="text-align: right;">{row['slope']:.2f}°</td></tr>
                    <tr><td style="padding: 4px 0;"><b>곡률</b></td><td style="text-align: right;">{row['curvature']:.4f}</td></tr>
                    <tr><td style="padding: 4px 0;"><b>TWI</b></td><td style="text-align: right;">{row['twi']:.2f}</td></tr>
                    <tr><td style="padding: 4px 0;"><b>유량</b></td><td style="text-align: right;">{row['flow_acc']:.2f}</td></tr>
                </table>
                <div style="margin-top: 10px; padding: 8px; background: #f0f4f8; border-radius: 4px; font-size: 0.9em;">
                    <b>선정 이유:</b><br>{row['reason']}
                </div>
            </div>
            """
            
            folium.CircleMarker(
                location=[row.geometry.y, row.geometry.x],
                radius=10,
                popup=folium.Popup(popup_html, max_width=300),
                tooltip=f"점수: {row['score']:.1f}",
                color='white',
                weight=2,
                fill=True,
                fillColor=color,
                fillOpacity=0.8
            ).add_to(m)
    
    # 기존 후보지 표시 코드 제거됨 (앱 시작 시 깨끗한 지도)
    
    # 지도 표시
    map_data = st_folium(
        m, 
        height=600,
        use_container_width=True,
        key="main_map",
        returned_objects=["all_drawings"]
    )
    
    # 그린 영역 처리
    if map_data and map_data.get("all_drawings"):
        drawings = map_data["all_drawings"]
        if drawings and len(drawings) > 0:
            last_drawing = drawings[-1]
            if isinstance(last_drawing, dict) and "geometry" in last_drawing:
                if st.session_state.aoi_geometry != last_drawing["geometry"]:
                    st.session_state.aoi_geometry = last_drawing["geometry"]
                    st.session_state.analysis_complete = False
                    st.rerun()

except Exception as e:
    st.error(f"⚠️ 지도 로딩 오류: {e}")
    if st.button("🔄 새로고침"):
        st.rerun()

# ===== 하단: 후보지 테이블 =====
if st.session_state.candidates is not None and not st.session_state.candidates.empty:
    st.markdown("---")
    
    with st.expander("📋 **전체 후보지 목록** (클릭하여 펼치기)", expanded=False):
        candidates = st.session_state.candidates
        
        # 데이터 표시용 컬럼 선택
        display_df = candidates.drop(columns='geometry').copy()
        display_df = display_df.sort_values('score', ascending=False)
        display_df.index = range(1, len(display_df) + 1)
        display_df.index.name = '순위'
        
        # 컬럼명 한글화
        display_df.columns = ['점수', '경사도', '곡률', 'TWI', '유량누적', '선정이유']
        
        st.dataframe(
            display_df,
            use_container_width=True,
            height=300
        )

# 푸터
st.markdown("---")
st.caption("지하수저류댐 지형 적합성 자동평가 모델 v2.0 | 현대적 UI")
