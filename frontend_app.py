import streamlit as st
import requests
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import numpy as np
import json
from typing import Dict, List, Any, Optional

# 페이지 설정
st.set_page_config(
    page_title="한국인 영어 실력 분석 대시보드",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# API 서버 설정
API_BASE_URL = "http://localhost:8002"

# 영어 레벨 매핑
LEVEL_MAPPING = {
    'IG': 1, 'TL': 2, 'TM': 3, 'TH': 4, 'NA': 5
}

LEVEL_NAMES = {
    'IG': 'Intermediate General',
    'TL': 'Talented Low', 
    'TM': 'Talented Middle',
    'TH': 'Talented High',
    'NA': 'Native-like'
}

@st.cache_data(ttl=300)  # 5분 캐시
def api_request(endpoint: str, method: str = "GET", data: dict = None) -> dict:
    """API 요청 함수"""
    try:
        url = f"{API_BASE_URL}{endpoint}"
        
        if method == "GET":
            response = requests.get(url)
        elif method == "POST":
            response = requests.post(url, json=data or {})
        else:
            raise ValueError(f"지원하지 않는 HTTP 메서드: {method}")
        
        response.raise_for_status()
        return response.json()
    
    except requests.exceptions.ConnectionError:
        st.error("❌ API 서버에 연결할 수 없습니다. 서버가 실행 중인지 확인해주세요.")
        st.stop()
    except requests.exceptions.HTTPError as e:
        st.error(f"❌ API 요청 실패: {e}")
        st.stop()
    except Exception as e:
        st.error(f"❌ 오류 발생: {e}")
        st.stop()

def check_api_health():
    """API 서버 상태 확인"""
    try:
        health = api_request("/health")
        if health.get("status") == "healthy":
            return True, health
        else:
            return False, health
    except:
        return False, None

def get_filter_data():
    """필터링을 위한 데이터 가져오기"""
    locations = api_request("/data/locations")
    levels = api_request("/data/levels")
    return locations, levels

def create_filter_request(age_range, selected_locations, selected_levels):
    """필터 요청 객체 생성"""
    filters = {}
    
    if age_range[0] > 20:
        filters["age_min"] = age_range[0]
    if age_range[1] < 40:
        filters["age_max"] = age_range[1]
    
    if selected_locations and "전체" not in selected_locations:
        filters["locations"] = selected_locations
    
    if selected_levels and "전체" not in selected_levels:
        filters["levels"] = selected_levels
    
    return filters

def display_hypothesis_result(result: dict, hypothesis_num: int):
    """가설 결과 표시"""
    st.subheader(f"📊 통계 분석 결과")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("가설 결과", result['result'])
    
    with col2:
        st.metric("p-value", f"{result['p_value']:.6f}")
    
    with col3:
        if result.get('effect_size'):
            st.metric("효과 크기", f"{result['effect_size']:.4f}")
        elif result.get('correlation'):
            st.metric("상관계수", f"{result['correlation']:.4f}")
    
    # 결론 표시
    if result['result'] == "채택":
        st.success(f"✅ {result['conclusion']}")
    elif result['result'] == "기각":
        st.error(f"❌ {result['conclusion']}")
    else:
        st.warning(f"🤔 {result['conclusion']}")
    
    # 상세 통계 표시
    with st.expander("상세 통계 정보"):
        st.json(result['statistics'])

def main():
    # 타이틀
    st.title("🎯 한국인 영어 실력 데이터 분석")
    st.markdown("### FastAPI 백엔드를 활용한 전문적인 통계 분석")
    
    # API 서버 상태 확인
    is_healthy, health_info = check_api_health()
    
    if not is_healthy:
        st.error("❌ API 서버가 응답하지 않습니다. 서버를 먼저 실행해주세요.")
        st.code("cd /Users/juun0.han/projects/kor_eng_da && uv run python api_server.py")
        st.stop()
    
    # 서버 상태 표시
    with st.expander("🖥️ 서버 상태"):
        st.success(f"✅ API 서버 연결됨 - {health_info.get('record_count', 0):,}개 레코드")
        st.caption(f"마지막 확인: {health_info.get('timestamp', 'N/A')}")
    
    # 필터 데이터 가져오기
    locations, levels = get_filter_data()
    
    # 사이드바 - 필터
    st.sidebar.header("🔍 데이터 필터")
    
    # 연령 필터
    age_range = st.sidebar.slider(
        "연령대 선택",
        min_value=20,
        max_value=40,
        value=(20, 40)
    )
    
    # 지역 필터
    location_options = ['전체'] + locations
    selected_locations = st.sidebar.multiselect("지역 선택", location_options, default=['전체'])
    
    # 영어 레벨 필터
    level_options = ['전체'] + levels
    selected_levels = st.sidebar.multiselect("영어 레벨 선택", level_options, default=['전체'])
    
    # 필터 적용
    filters = create_filter_request(age_range, selected_locations, selected_levels)
    
    # 데이터 요약 가져오기
    try:
        summary = api_request("/data/summary", "POST", filters)
        chart_data = api_request("/data/chart_data", "POST", filters)
    except Exception as e:
        st.error(f"데이터를 가져오는데 실패했습니다: {e}")
        st.stop()
    
    # 메인 대시보드
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("총 참가자 수", f"{summary['total_participants']:,}")
    
    with col2:
        st.metric("평균 연령", f"{summary['average_age']:.1f}세")
    
    with col3:
        st.metric("수도권 비율", f"{summary['metropolitan_ratio']*100:.1f}%")
    
    with col4:
        st.metric("영어권 거주 경험", f"{summary['experience_ratio']*100:.1f}%")
    
    # 탭 생성
    tab1, tab2, tab3, tab4 = st.tabs(["📈 가설 1: 연령별 분석", "🏙️ 가설 2: 지역별 분석", "🌍 가설 3: 영어권 경험", "📊 전체 데이터 개요"])
    
    # 가설 1: 연령별 분석
    with tab1:
        st.header("가설 1: 연령대가 낮을수록 점수가 높을 것이다")
        
        # API에서 분석 결과 가져오기
        h1_result = api_request("/analysis/hypothesis1", "POST", filters)
        
        col1, col2 = st.columns(2)
        
        with col1:
            # 연령대별 평균 점수 박스플롯
            if chart_data.get('age_group_stats'):
                age_group_data = chart_data['age_group_stats']
                
                # 데이터 준비
                ages = chart_data['age_vs_score']['ages']
                scores = chart_data['age_vs_score']['scores']
                levels = chart_data['age_vs_score']['levels']
                
                df_plot = pd.DataFrame({
                    'age': ages,
                    'score': scores,
                    'level': levels
                })
                
                # 연령대 그룹 생성
                def create_age_groups(age):
                    if age < 25:
                        return '20대 초반'
                    elif age < 30:
                        return '20대 후반'
                    elif age < 35:
                        return '30대 초반'
                    elif age < 40:
                        return '30대 후반'
                    else:
                        return '40대 이상'
                
                df_plot['age_group'] = df_plot['age'].apply(create_age_groups)
                
                fig1 = px.box(
                    df_plot, 
                    x='age_group', 
                    y='score',
                    title="연령대별 영어 실력 분포",
                    labels={'score': '영어 실력 점수', 'age_group': '연령대'}
                )
                st.plotly_chart(fig1, use_container_width=True)
        
        with col2:
            # 연령과 점수의 산점도
            fig2 = px.scatter(
                df_plot, 
                x='age', 
                y='score',
                color='level',
                title="연령 vs 영어 실력 상관관계",
                labels={'score': '영어 실력 점수', 'age': '연령'}
            )
            st.plotly_chart(fig2, use_container_width=True)
        
        # 통계 분석 결과 표시
        display_hypothesis_result(h1_result, 1)
    
    # 가설 2: 지역별 분석
    with tab2:
        st.header("가설 2: 수도권(서울/경기)일수록 점수가 높을 것이다")
        
        # API에서 분석 결과 가져오기
        h2_result = api_request("/analysis/hypothesis2", "POST", filters)
        
        col1, col2 = st.columns(2)
        
        with col1:
            # 수도권 vs 비수도권 박스플롯
            metro_scores = chart_data['metro_comparison']['metro_scores']
            non_metro_scores = chart_data['metro_comparison']['non_metro_scores']
            
            df_metro = pd.DataFrame({
                'region': ['수도권'] * len(metro_scores) + ['비수도권'] * len(non_metro_scores),
                'score': metro_scores + non_metro_scores
            })
            
            fig3 = px.box(
                df_metro, 
                x='region', 
                y='score',
                title="수도권 vs 비수도권 영어 실력 비교",
                labels={'score': '영어 실력 점수', 'region': '지역'}
            )
            st.plotly_chart(fig3, use_container_width=True)
        
        with col2:
            # 지역별 평균 점수
            location_stats = chart_data['location_stats']
            if location_stats.get('mean'):
                location_means = pd.DataFrame({
                    'location': list(location_stats['mean'].keys()),
                    'mean_score': list(location_stats['mean'].values()),
                    'count': [location_stats['count'].get(loc, 0) for loc in location_stats['mean'].keys()]
                })
                
                # 30명 이상인 지역만 표시
                location_means = location_means[location_means['count'] >= 30].sort_values('mean_score')
                
                fig4 = px.bar(
                    location_means.head(10),
                    x='mean_score',
                    y='location',
                    orientation='h',
                    title="지역별 평균 영어 실력 (상위 10개)",
                    labels={'mean_score': '평균 점수', 'location': '지역'}
                )
                st.plotly_chart(fig4, use_container_width=True)
        
        # 통계 분석 결과 표시
        display_hypothesis_result(h2_result, 2)
    
    # 가설 3: 영어권 거주 경험
    with tab3:
        st.header("가설 3: 영어권 거주 경험이 있을수록 점수가 높을 것이다")
        
        # API에서 분석 결과 가져오기
        h3_result = api_request("/analysis/hypothesis3", "POST", filters)
        
        col1, col2 = st.columns(2)
        
        with col1:
            # 영어권 거주 경험별 박스플롯
            exp_scores = chart_data['experience_comparison']['exp_scores']
            no_exp_scores = chart_data['experience_comparison']['no_exp_scores']
            
            df_exp = pd.DataFrame({
                'experience': ['경험 있음'] * len(exp_scores) + ['경험 없음'] * len(no_exp_scores),
                'score': exp_scores + no_exp_scores
            })
            
            fig5 = px.box(
                df_exp, 
                x='experience', 
                y='score',
                title="영어권 거주 경험별 영어 실력 비교",
                labels={'score': '영어 실력 점수', 'experience': '영어권 거주 경험'}
            )
            st.plotly_chart(fig5, use_container_width=True)
        
        with col2:
            # 영어권 거주 경험별 레벨 분포 파이차트
            exp_ratio = summary['experience_ratio']
            no_exp_ratio = 1 - exp_ratio
            
            fig6 = px.pie(
                values=[exp_ratio, no_exp_ratio],
                names=['경험 있음', '경험 없음'],
                title="영어권 거주 경험별 참가자 비율"
            )
            st.plotly_chart(fig6, use_container_width=True)
        
        # 통계 분석 결과 표시
        display_hypothesis_result(h3_result, 3)
    
    # 전체 데이터 개요
    with tab4:
        st.header("📊 전체 데이터 개요")
        
        col1, col2 = st.columns(2)
        
        with col1:
            # 영어 레벨 분포
            level_dist = chart_data['level_distribution']
            fig7 = px.pie(
                values=list(level_dist.values()),
                names=[f"{level} ({LEVEL_NAMES.get(level, level)})" for level in level_dist.keys()],
                title="영어 레벨 분포"
            )
            st.plotly_chart(fig7, use_container_width=True)
        
        with col2:
            # 연령 분포
            ages = chart_data['age_vs_score']['ages']
            fig8 = px.histogram(
                x=ages,
                nbins=20,
                title="연령 분포"
            )
            fig8.update_layout(xaxis_title="연령", yaxis_title="빈도")
            st.plotly_chart(fig8, use_container_width=True)
        
        # 지역별 상세 통계
        st.subheader("지역별 상세 통계")
        
        location_stats = chart_data['location_stats']
        if location_stats.get('mean'):
            location_df = pd.DataFrame({
                '지역': list(location_stats['mean'].keys()),
                '참가자 수': [location_stats['count'].get(loc, 0) for loc in location_stats['mean'].keys()],
                '평균 점수': [round(score, 3) for score in location_stats['mean'].values()]
            })
            
            location_df = location_df.sort_values('평균 점수').reset_index(drop=True)
            st.dataframe(location_df, use_container_width=True)
        
        # 주요 발견사항
        st.subheader("💡 주요 발견사항")
        st.info("""
        **모든 가설이 기각되어 일반적인 직관과 반대되는 결과:**
        - **연령**: 나이가 많을수록 영어 실력이 더 좋음
        - **지역**: 비수도권이 수도권보다 영어 실력이 더 좋음  
        - **경험**: 영어권 거주 경험이 없는 사람들의 영어 실력이 더 좋음
        
        이러한 결과는 데이터의 특성이나 샘플링 방법에 따른 것일 수 있으며, 
        추가적인 연구와 분석이 필요합니다.
        """)

if __name__ == "__main__":
    main()