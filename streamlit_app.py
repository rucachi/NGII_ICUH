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
    layout="wide"
)

# 제목
st.title("🏔️ 지하수저류댐 지형 적합성 자동평가 모델")
st.markdown("---")

# DEM 경로 설정 (환경변수 또는 기본값)
DEM_PATH = os.getenv("DEM_PATH", "output/dummy_dem.tif")
OUTPUT_DIR = "output/aoi_analysis"

# 세션 상태 초기화
if 'candidates' not in st.session_state:
    st.session_state.candidates = None
if 'aoi_geometry' not in st.session_state:
    st.session_state.aoi_geometry = None
if 'geometry_notified' not in st.session_state:
    st.session_state.geometry_notified = False
if 'folium_map' not in st.session_state:
    st.session_state.folium_map = None

# 사이드바
with st.sidebar:
    st.header("⚙️ 설정")
    
    # DEM 파일 업로드
    uploaded_dem = st.file_uploader("DEM 파일 업로드 (GeoTIFF)", type=['tif', 'tiff'])
    
    if uploaded_dem:
        # 임시 파일로 저장
        with tempfile.NamedTemporaryFile(delete=False, suffix='.tif') as tmp_file:
            tmp_file.write(uploaded_dem.read())
            DEM_PATH = tmp_file.name
            st.success(f"DEM 파일 업로드 완료: {uploaded_dem.name}")
    
    st.markdown("---")
    st.info("""
    **사용 방법:**
    1. 지도에서 관심영역을 그립니다
    2. '영역 분석 실행' 버튼을 클릭합니다
    3. 결과를 확인하고 다운로드합니다
    """)

# 메인 컨텐츠
tab1, tab2 = st.tabs(["🗺️ 지도 분석", "📊 결과 분석"])

with tab1:
    st.header("관심영역 선택 및 분석")
    
    # 기본 지도 생성 (한국 중심)
    col1, col2 = st.columns([2, 1])
    
    with col1:
        # Folium 지도 생성 (세션 상태에 캐싱하여 재사용)
        try:
            # 지도가 세션 상태에 없으면 생성
            if st.session_state.folium_map is None:
                m = folium.Map(
                    location=[36.5, 127.5],  # 한국 중심
                    zoom_start=7,
                    tiles='OpenStreetMap'
                )
                
                # Draw 플러그인 추가 (영역 그리기 도구)
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
                
                # 기존 후보지 표시
                if os.path.exists("output/candidates.geojson"):
                    try:
                        existing_candidates = gpd.read_file("output/candidates.geojson")
                        for idx, row in existing_candidates.iterrows():
                            folium.CircleMarker(
                                location=[row.geometry.y, row.geometry.x],
                                radius=5,
                                popup=f"점수: {row['score']:.1f}",
                                color='blue',
                                fill=True
                            ).add_to(m)
                    except:
                        pass
                
                # 세션 상태에 저장
                st.session_state.folium_map = m
            else:
                # 기존 지도 재사용
                m = st.session_state.folium_map
            
            # 지도 표시 및 상호작용
            # 고유하고 안정적인 key 사용, returned_objects를 최소화하여 리렌더링 방지
            # zoom과 center를 명시적으로 전달하지 않아 지도가 자체적으로 관리하도록 함
            map_data = st_folium(
                m, 
                width=700, 
                height=500, 
                key="folium_map_component",  # 고유하고 안정적인 key
                returned_objects=["all_drawings"],  # 최소한의 객체만 반환
                use_container_width=False
            )
            
            # 그려진 영역 처리
            if map_data and isinstance(map_data, dict):
                if map_data.get("all_drawings"):
                    drawings = map_data["all_drawings"]
                    if drawings and len(drawings) > 0:
                        # 마지막 그려진 영역 사용
                        last_drawing = drawings[-1]
                        if isinstance(last_drawing, dict) and "geometry" in last_drawing:
                            st.session_state.aoi_geometry = last_drawing["geometry"]
                            if not st.session_state.geometry_notified:
                                st.success("✅ 관심영역이 선택되었습니다!")
                                st.session_state.geometry_notified = True
                                
        except Exception as e:
            # 오류 발생 시 지도 캐시 초기화
            st.session_state.folium_map = None
            st.error("⚠️ 지도 로딩 중 오류가 발생했습니다.")
            st.info("💡 페이지를 새로고침해주세요.")
            if st.button("🔄 페이지 새로고침", key="refresh_map"):
                st.session_state.folium_map = None
                st.rerun()
    
    with col2:
        st.subheader("분석 실행")
        
        if st.button("🔍 영역 분석 실행", type="primary", use_container_width=True):
            # 알림 상태 리셋
            st.session_state.geometry_notified = False
            
            if st.session_state.aoi_geometry is None:
                st.error("먼저 지도에서 관심영역을 그려주세요!")
            else:
                with st.spinner("분석 중... 잠시만 기다려주세요."):
                    try:
                        # 출력 디렉토리 생성
                        os.makedirs(OUTPUT_DIR, exist_ok=True)
                        
                        # TerrainAnalyzer 초기화
                        analyzer = TerrainAnalyzer(DEM_PATH, OUTPUT_DIR)
                        
                        # 1. DEM 클리핑
                        dem, transform, meta, clipped_path = analyzer.clip_dem_by_geometry(
                            st.session_state.aoi_geometry
                        )
                        
                        # 2. 지형 지수 계산
                        slope = analyzer.calculate_slope(dem)
                        curv = analyzer.calculate_curvature(dem)
                        flow = analyzer.calculate_flow_accumulation(dem)
                        twi = analyzer.calculate_twi(slope, flow)
                        
                        # 3. 후보지 평가
                        evaluator = SiteEvaluator(OUTPUT_DIR)
                        candidates = evaluator.evaluate(
                            slope, curv, twi, flow, transform, meta['crs']
                        )
                        
                        st.session_state.candidates = candidates
                        
                        if candidates.empty:
                            st.warning("선택한 영역에서 적합한 후보지를 찾을 수 없습니다.")
                        else:
                            st.success(f"✅ {len(candidates)}개의 후보지가 발견되었습니다!")
                            st.rerun()  # 결과 탭으로 자동 이동
                            
                    except Exception as e:
                        st.error(f"분석 중 오류가 발생했습니다: {str(e)}")
                        st.exception(e)
        
        st.markdown("---")
        
        # 결과 다운로드
        if st.session_state.candidates is not None and not st.session_state.candidates.empty:
            st.subheader("📥 결과 다운로드")
            
            # GeoJSON 다운로드
            geojson_str = st.session_state.candidates.to_json()
            st.download_button(
                label="GeoJSON 다운로드",
                data=geojson_str,
                file_name="candidates.geojson",
                mime="application/json",
                use_container_width=True
            )
            
            # CSV 다운로드
            csv_str = st.session_state.candidates.drop(columns='geometry').to_csv(index=False)
            st.download_button(
                label="CSV 다운로드",
                data=csv_str,
                file_name="candidates.csv",
                mime="text/csv",
                use_container_width=True
            )

with tab2:
    st.header("분석 결과")
    
    if st.session_state.candidates is not None and not st.session_state.candidates.empty:
        candidates = st.session_state.candidates
        
        # 통계 정보
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("총 후보지 수", len(candidates))
        with col2:
            st.metric("평균 점수", f"{candidates['score'].mean():.1f}")
        with col3:
            st.metric("최고 점수", f"{candidates['score'].max():.1f}")
        with col4:
            st.metric("평균 경사도", f"{candidates['slope'].mean():.1f}°")
        
        st.markdown("---")
        
        # 상위 후보지 표시
        st.subheader("🏆 상위 후보지")
        top_candidates = candidates.head(10)
        
        for idx, row in top_candidates.iterrows():
            with st.expander(f"후보지 #{idx+1} - 점수: {row['score']:.1f}"):
                col1, col2 = st.columns(2)
                with col1:
                    st.write(f"**위치:** {row.geometry.y:.6f}°N, {row.geometry.x:.6f}°E")
                    st.write(f"**경사도:** {row['slope']:.2f}°")
                    st.write(f"**곡률:** {row['curvature']:.4f}")
                with col2:
                    st.write(f"**TWI:** {row['twi']:.2f}")
                    st.write(f"**유량 누적:** {row['flow_acc']:.2f}")
                    st.write(f"**이유:** {row['reason']}")
        
        # 데이터프레임 표시
        st.markdown("---")
        st.subheader("전체 후보지 데이터")
        st.dataframe(
            candidates.drop(columns='geometry').sort_values('score', ascending=False),
            use_container_width=True
        )
        
    else:
        st.info("👈 왼쪽 탭에서 관심영역을 선택하고 분석을 실행해주세요.")

# 푸터
st.markdown("---")
st.caption("지하수저류댐 지형 적합성 자동평가 모델 v1.0")
