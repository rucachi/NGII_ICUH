import streamlit as st
import os
import numpy as np
import rasterio
from rasterio.transform import xy
import geopandas as gpd
from shapely.geometry import Point, Polygon, box
import folium
from streamlit_folium import folium_static
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
    .block-container {
        padding-top: 1rem;
        padding-bottom: 1rem;
    }
    
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
    
    .main-header h2 {
        margin: 0 0 0.5rem 0;
        font-size: 1.2rem;
        opacity: 0.9;
    }
    
    .main-header p {
        margin: 0.5rem 0 0 0;
        opacity: 0.9;
        font-size: 0.95rem;
    }
    
    .stButton > button {
        width: 100%;
        border-radius: 8px;
        font-weight: 500;
    }
    
    .stDownloadButton > button {
        width: 100%;
        border-radius: 8px;
    }
    
    .coord-input {
        background-color: #f8f9fa;
        padding: 1rem;
        border-radius: 8px;
        margin-bottom: 1rem;
    }
</style>
""", unsafe_allow_html=True)

# DEM 경로 설정
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
    
    # 관심영역 설정
    st.markdown("#### 📍 관심영역 설정")
    
    aoi_method = st.radio(
        "입력 방식",
        ["좌표 직접 입력", "GeoJSON 파일 업로드"],
        horizontal=True
    )
    
    if aoi_method == "좌표 직접 입력":
        st.markdown("**영역 좌표 (위도/경도)**")
        
        col1, col2 = st.columns(2)
        with col1:
            min_lat = st.number_input("최소 위도", value=36.0, format="%.4f", step=0.01)
            min_lon = st.number_input("최소 경도", value=127.0, format="%.4f", step=0.01)
        with col2:
            max_lat = st.number_input("최대 위도", value=36.5, format="%.4f", step=0.01)
            max_lon = st.number_input("최대 경도", value=127.5, format="%.4f", step=0.01)
        
        if st.button("✅ 영역 설정", use_container_width=True):
            # GeoJSON 형식으로 변환
            st.session_state.aoi_geometry = {
                "type": "Polygon",
                "coordinates": [[
                    [min_lon, min_lat],
                    [max_lon, min_lat],
                    [max_lon, max_lat],
                    [min_lon, max_lat],
                    [min_lon, min_lat]
                ]]
            }
            st.success("✅ 영역이 설정되었습니다!")
            st.rerun()
    
    else:  # GeoJSON 파일 업로드
        uploaded_aoi = st.file_uploader(
            "GeoJSON 파일",
            type=['geojson', 'json'],
            help="관심영역 폴리곤이 포함된 GeoJSON 파일"
        )
        
        if uploaded_aoi:
            try:
                aoi_data = json.load(uploaded_aoi)
                if aoi_data.get("type") == "FeatureCollection":
                    st.session_state.aoi_geometry = aoi_data["features"][0]["geometry"]
                elif aoi_data.get("type") == "Feature":
                    st.session_state.aoi_geometry = aoi_data["geometry"]
                else:
                    st.session_state.aoi_geometry = aoi_data
                st.success("✅ 영역이 설정되었습니다!")
            except Exception as e:
                st.error(f"파일 읽기 오류: {e}")
    
    st.markdown("---")
    
    # 분석 실행
    st.markdown("#### 🔬 분석 실행")
    
    if st.session_state.aoi_geometry:
        st.info("✅ 관심영역이 설정되었습니다.")
    else:
        st.warning("⚠️ 관심영역을 설정해주세요.")
    
    analyze_clicked = st.button(
        "🚀 분석 시작",
        type="primary",
        use_container_width=True,
        disabled=(st.session_state.aoi_geometry is None)
    )
    
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
    with st.expander("💡 사용 방법"):
        st.markdown("""
        1. DEM 파일을 업로드합니다
        2. 관심영역을 **좌표로 입력**하거나 **GeoJSON 업로드**
        3. **분석 시작** 버튼을 클릭합니다
        4. 결과를 지도에서 확인하고 다운로드합니다
        """)

# ===== 메인 컨텐츠 =====
st.markdown("""
<div class="main-header">
    <h2>(재)국제도시물정보과학연구원</h2>
    <h1>🏔️ 지하수저류댐 지형 적합성 자동평가</h1>
    <p>관심영역을 설정하고 최적의 후보지를 찾아보세요</p>
</div>
""", unsafe_allow_html=True)

# Folium 지도 생성
try:
    # 지도 중심 계산
    if st.session_state.aoi_geometry:
        coords = st.session_state.aoi_geometry.get("coordinates", [])
        if coords and len(coords) > 0:
            flat_coords = coords[0] if isinstance(coords[0][0], list) else coords
            lats = [c[1] for c in flat_coords]
            lons = [c[0] for c in flat_coords]
            center_lat = sum(lats) / len(lats)
            center_lon = sum(lons) / len(lons)
            zoom = 10
        else:
            center_lat, center_lon, zoom = 36.5, 127.5, 7
    else:
        center_lat, center_lon, zoom = 36.5, 127.5, 7
    
    m = folium.Map(
        location=[center_lat, center_lon],
        zoom_start=zoom,
        tiles='cartodbpositron'
    )
    
    # AOI 영역 표시
    if st.session_state.aoi_geometry:
        folium.GeoJson(
            st.session_state.aoi_geometry,
            style_function=lambda x: {
                'fillColor': '#3388ff',
                'color': '#3388ff',
                'weight': 2,
                'fillOpacity': 0.2
            },
            name="관심영역"
        ).add_to(m)
    
    # 분석 결과 마커 추가
    if st.session_state.candidates is not None and not st.session_state.candidates.empty:
        candidates = st.session_state.candidates
        
        min_score = candidates['score'].min()
        max_score = candidates['score'].max()
        score_range = max_score - min_score if max_score != min_score else 1
        
        for idx, row in candidates.iterrows():
            normalized_score = (row['score'] - min_score) / score_range
            
            if normalized_score < 0.5:
                r = 255
                g = int(215 - (215 - 140) * (normalized_score * 2))
                b = 0
            else:
                r = 255
                g = int(140 - 140 * ((normalized_score - 0.5) * 2))
                b = 0
            
            color = f'#{r:02x}{g:02x}{b:02x}'
            
            popup_html = f"""
            <div style="font-family: sans-serif; min-width: 180px;">
                <h4 style="margin: 0 0 8px 0;">🎯 후보지 #{idx+1}</h4>
                <p><b>점수:</b> <span style="color:{color}; font-weight:bold;">{row['score']:.1f}</span></p>
                <p><b>경사도:</b> {row['slope']:.2f}°</p>
                <p><b>TWI:</b> {row['twi']:.2f}</p>
                <p style="font-size:0.85em; background:#f0f4f8; padding:6px; border-radius:4px;">
                    {row['reason']}
                </p>
            </div>
            """
            
            folium.CircleMarker(
                location=[row.geometry.y, row.geometry.x],
                radius=10,
                popup=folium.Popup(popup_html, max_width=250),
                tooltip=f"점수: {row['score']:.1f}",
                color='white',
                weight=2,
                fill=True,
                fillColor=color,
                fillOpacity=0.8
            ).add_to(m)
    
    # 정적 지도 출력 (folium_static 사용 - removeChild 오류 방지)
    folium_static(m, width=None, height=600)

except Exception as e:
    st.error(f"⚠️ 지도 로딩 오류: {e}")
    if st.button("🔄 새로고침"):
        st.rerun()

# ===== 하단: 후보지 테이블 =====
if st.session_state.candidates is not None and not st.session_state.candidates.empty:
    st.markdown("---")
    
    with st.expander("📋 **전체 후보지 목록** (클릭하여 펼치기)", expanded=False):
        candidates = st.session_state.candidates
        
        display_df = candidates.drop(columns='geometry').copy()
        display_df = display_df.sort_values('score', ascending=False)
        display_df.index = range(1, len(display_df) + 1)
        display_df.index.name = '순위'
        display_df.columns = ['점수', '경사도', '곡률', 'TWI', '유량누적', '선정이유']
        
        st.dataframe(display_df, use_container_width=True, height=300)

# 푸터
st.markdown("---")
st.caption("지하수저류댐 지형 적합성 자동평가 모델 v2.0 | (재)국제도시물정보과학연구원")
