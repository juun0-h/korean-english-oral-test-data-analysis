#!/usr/bin/env python3
"""
FastAPI 백엔드 - 데이터 분석 API 서버
da2.ipynb의 분석 로직을 API 엔드포인트로 제공
"""

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict, List, Optional, Any
import pandas as pd
import numpy as np
from scipy.stats import pearsonr, spearmanr, ttest_ind, f_oneway, mannwhitneyu, chi2_contingency
import os
import json
import boto3
from dotenv import load_dotenv
from botocore.exceptions import NoCredentialsError, PartialCredentialsError, ClientError
import logging
from datetime import datetime

# 환경변수 로드
load_dotenv()

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="한국인 영어 실력 분석 API",
    description="3가지 가설 검증을 위한 데이터 분석 API",
    version="1.0.0"
)

# CORS 설정 (Streamlit에서 접근 허용)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8501", "http://localhost:8504", "http://localhost:8506"],  # Streamlit 기본 포트들 + 커스텀 포트
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 전역 변수로 데이터 캐싱
df_master: Optional[pd.DataFrame] = None

# S3 설정 (환경변수)
AWS_REGION = os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION") or "ap-northeast-2"
S3_BUCKET_NAME = os.getenv("S3_BUCKET_NAME")
S3_RAW_PREFIX = os.getenv("S3_RAW_PREFIX", "")

# S3 클라이언트 초기화
try:
    s3_client = boto3.client("s3", region_name=AWS_REGION)
except Exception as e:
    logger.warning(f"S3 클라이언트 초기화 실패: {e}")
    s3_client = None

# Pydantic 모델들
class DataSummary(BaseModel):
    total_participants: int
    age_range: Dict[str, int]
    average_age: float
    location_distribution: Dict[str, int]
    level_distribution: Dict[str, int]
    metropolitan_ratio: float
    experience_ratio: float

class HypothesisResult(BaseModel):
    hypothesis: str
    result: str
    p_value: float
    effect_size: Optional[float] = None
    correlation: Optional[float] = None
    statistics: Dict[str, Any]
    conclusion: str

class FilterRequest(BaseModel):
    age_min: Optional[int] = None
    age_max: Optional[int] = None
    locations: Optional[List[str]] = None
    levels: Optional[List[str]] = None

# 분석 함수들
def calculate_effect_size(group1: np.ndarray, group2: np.ndarray) -> float:
    """Cohen's d 효과 크기 계산"""
    n1, n2 = len(group1), len(group2)
    pooled_std = np.sqrt(((n1-1)*group1.var() + (n2-1)*group2.var()) / (n1+n2-2))
    return (group1.mean() - group2.mean()) / pooled_std

def interpret_effect_size(d: float) -> str:
    """효과 크기 해석"""
    abs_d = abs(d)
    if abs_d < 0.2:
        return "작은 효과"
    elif abs_d < 0.5:
        return "중간 효과"
    elif abs_d < 0.8:
        return "큰 효과"
    else:
        return "매우 큰 효과"

# ===== 데이터 전처리 및 S3 적재 유틸 ===== #

# 레벨 매핑 (숫자가 낮을수록 높은 레벨)
LEVEL_MAPPING = {
    'IG': 1,  # Intermediate General
    'TL': 2,  # Talented Low
    'TM': 3,  # Talented Middle
    'TH': 4,  # Talented High
    'NA': 5   # Native-like
}

def create_age_groups(age: int) -> str:
    if pd.isna(age):
        return "미상"
    age_int = int(age)
    if age_int < 25:
        return '20대 초반'
    elif age_int < 30:
        return '20대 후반'
    elif age_int < 35:
        return '30대 초반'
    elif age_int < 40:
        return '30대 후반'
    else:
        return '40대 이상'

def classify_metropolitan(location: str) -> bool:
    if not isinstance(location, str):
        return False
    metro_areas = ['서울', '경기']
    return any(area in location for area in metro_areas)

def extract_english_experience(interview_data: Dict) -> bool:
    if not isinstance(interview_data, dict):
        return False
    return interview_data.get('영어권_거주_여부', '') == '있음'

def extract_analysis_data(data: Dict) -> Optional[Dict]:
    """단일 JSON에서 분석 필드 추출"""
    try:
        speaker = data.get('speaker', {})
        extracted = {
            'participant_id': speaker.get('id', ''),
            'age': speaker.get('age'),
            'gender': speaker.get('gender', ''),
            'location': speaker.get('location', ''),
            'english_level': speaker.get('level', {}).get('final', ''),
            'self_grade': speaker.get('self_grade', ''),
            'combo_scores': {
                k: float(v) for k, v in speaker.get('level', {}).items()
                if isinstance(k, str) and k.startswith('Combo') and v != ''
            },
            'interview': speaker.get('interview', {}),
            'file_date': data.get('metadata', {}).get('date', ''),
            'year': data.get('metadata', {}).get('year', '')
        }
        # 필수값 유효성
        if not extracted['age'] or not extracted['location'] or not extracted['english_level']:
            return None
        return extracted
    except Exception as e:
        logger.warning(f"데이터 추출 실패: {e}")
        return None

def get_participant_representative_files(bucket_name: str, prefix: str = "") -> Dict[str, str]:
    """참가자별 대표 JSON 파일 하나 선택 (비용 절감)"""
    if s3_client is None:
        raise HTTPException(status_code=500, detail="S3 클라이언트가 초기화되지 않았습니다.")
    paginator = s3_client.get_paginator('list_objects_v2')
    pages = paginator.paginate(Bucket=bucket_name, Prefix=prefix)
    participant_files: Dict[str, List[str]] = {}
    for page in pages:
        for obj in page.get('Contents', []):
            key = obj['Key']
            if not key.endswith('.json'):
                continue
            parts = key.split('/')
            # 기대 구조: raw/year=YYYY/month=MM/day=DD/level=XX/ESPEAK_XXXX_..._json/...
            # 6번째 토큰(인덱스 5)이 참가자 디렉토리로 가정
            if len(parts) >= 6:
                participant_dir = parts[5]
                participant_id = participant_dir.replace('_json', '')
                participant_files.setdefault(participant_id, []).append(key)
    # 각 참가자 첫 파일 선택
    representative: Dict[str, str] = {pid: files[0] for pid, files in participant_files.items() if files}
    logger.info(f"S3 대표 파일 수집 완료 - 참가자 {len(representative)}명")
    return representative

def load_participant_data(bucket_name: str, file_key: str) -> Optional[Dict]:
    try:
        obj = s3_client.get_object(Bucket=bucket_name, Key=file_key)
        content = obj['Body'].read().decode('utf-8')
        return json.loads(content)
    except Exception as e:
        logger.warning(f"파일 로드 실패 {file_key}: {e}")
        return None

def preprocess_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    logger.info("데이터 전처리 시작")
    df = df.copy()
    # 타입/파생 컬럼
    df['age'] = pd.to_numeric(df['age'], errors='coerce')
    df['english_level_numeric'] = df['english_level'].map(LEVEL_MAPPING)
    df['age_group'] = df['age'].apply(create_age_groups)
    df['is_metropolitan'] = df['location'].apply(classify_metropolitan)
    df['english_speaking_experience'] = df['interview'].apply(extract_english_experience)
    # 핵심 결측 제거
    before = len(df)
    df = df.dropna(subset=['age', 'english_level_numeric', 'location'])
    after = len(df)
    logger.info(f"전처리 완료: {before} -> {after} (제거 {before-after})")
    return df

def load_all_participant_data() -> pd.DataFrame:
    """S3에서 모든 참가자 대표 JSON을 읽어 DataFrame 생성"""
    if not S3_BUCKET_NAME or not S3_RAW_PREFIX:
        logger.error("S3 설정이 누락되었습니다. (.env 확인)")
        raise HTTPException(status_code=500, detail="S3 설정이 누락되었습니다.")
    # 접근 확인 (선택적)
    try:
        s3_client.head_bucket(Bucket=S3_BUCKET_NAME)
    except (NoCredentialsError, PartialCredentialsError):
        logger.error("AWS 자격 증명이 설정되지 않았습니다.")
        raise HTTPException(status_code=500, detail="AWS 자격 증명 오류")
    except ClientError as e:
        logger.warning(f"버킷 접근 확인 경고: {e}")

    rep_files = get_participant_representative_files(S3_BUCKET_NAME, S3_RAW_PREFIX)
    all_rows: List[Dict] = []
    failed = 0
    for i, (pid, key) in enumerate(rep_files.items(), start=1):
        if i % 200 == 0:
            logger.info(f"진행률: {i}/{len(rep_files)} ({i/len(rep_files)*100:.1f}%)")
        data = load_participant_data(S3_BUCKET_NAME, key)
        if not data:
            failed += 1
            continue
        row = extract_analysis_data(data)
        if row:
            all_rows.append(row)
        else:
            failed += 1
    logger.info(f"S3 데이터 적재 완료 - 성공 {len(all_rows)}, 실패 {failed}")
    df = pd.DataFrame(all_rows)
    df = preprocess_dataframe(df)
    logger.info(f"영어 레벨 분포: {df['english_level'].value_counts().to_dict()}")
    return df

def load_data_if_needed():
    """필요시 S3에서 데이터 로드 (캐싱)"""
    global df_master
    if df_master is None:
        df_master = load_all_participant_data()
        logger.info(f"데이터 로드 완료 (S3): {len(df_master)} 레코드")
    return df_master

def apply_filters(df: pd.DataFrame, filters: FilterRequest) -> pd.DataFrame:
    """필터 적용"""
    filtered_df = df.copy()
    
    if filters.age_min is not None:
        filtered_df = filtered_df[filtered_df['age'] >= filters.age_min]
    
    if filters.age_max is not None:
        filtered_df = filtered_df[filtered_df['age'] <= filters.age_max]
    
    if filters.locations:
        filtered_df = filtered_df[filtered_df['location'].isin(filters.locations)]
    
    if filters.levels:
        filtered_df = filtered_df[filtered_df['english_level'].isin(filters.levels)]
    
    return filtered_df

# API 엔드포인트들
@app.get("/")
async def root():
    """API 상태 확인"""
    return {
        "message": "한국인 영어 실력 분석 API",
        "status": "running",
        "timestamp": datetime.now().isoformat()
    }

@app.post("/reload")
async def reload_data():
    """S3에서 데이터를 다시 로드하여 캐시 갱신"""
    global df_master
    df_master = None
    df = load_data_if_needed()
    return {
        "status": "reloaded",
        "record_count": len(df),
        "timestamp": datetime.now().isoformat()
    }

@app.get("/health")
async def health_check():
    """헬스 체크"""
    try:
        df = load_data_if_needed()
        return {
            "status": "healthy",
            "data_loaded": True,
            "record_count": len(df),
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }

@app.post("/data/summary")
async def get_data_summary(filters: FilterRequest = FilterRequest()) -> DataSummary:
    """데이터 요약 정보"""
    df = load_data_if_needed()
    df_filtered = apply_filters(df, filters)
    
    if len(df_filtered) == 0:
        raise HTTPException(status_code=400, detail="필터 조건에 맞는 데이터가 없습니다.")
    
    return DataSummary(
        total_participants=len(df_filtered),
        age_range={"min": int(df_filtered['age'].min()), "max": int(df_filtered['age'].max())},
        average_age=float(df_filtered['age'].mean()),
        location_distribution=df_filtered['location'].value_counts().head().to_dict(),
        level_distribution=df_filtered['english_level'].value_counts().to_dict(),
        metropolitan_ratio=float(df_filtered['is_metropolitan'].mean()),
        experience_ratio=float(df_filtered['english_speaking_experience'].mean())
    )

@app.get("/data/locations")
async def get_locations() -> List[str]:
    """사용 가능한 지역 목록"""
    df = load_data_if_needed()
    # NaN 값 제거하고 정렬
    locations = df['location'].dropna().unique().tolist()
    # 문자열로 변환하고 정렬
    locations = sorted([str(location) for location in locations if location])
    return locations

@app.get("/data/levels") 
async def get_levels() -> List[str]:
    """사용 가능한 영어 레벨 목록"""
    df = load_data_if_needed()
    # NaN 값 제거하고 정렬
    levels = df['english_level'].dropna().unique().tolist()
    # 문자열로 변환하고 정렬
    levels = sorted([str(level) for level in levels if level])
    return levels

@app.post("/analysis/hypothesis1")
async def analyze_hypothesis1(filters: FilterRequest = FilterRequest()) -> HypothesisResult:
    """가설 1: 연령대가 낮을수록 점수가 높을 것이다"""
    df = load_data_if_needed()
    df_filtered = apply_filters(df, filters)
    
    if len(df_filtered) < 10:
        raise HTTPException(status_code=400, detail="분석에 충분한 데이터가 없습니다.")
    
    # 상관관계 분석
    corr_pearson, p_pearson = pearsonr(df_filtered['age'], df_filtered['english_level_numeric'])
    corr_spearman, p_spearman = spearmanr(df_filtered['age'], df_filtered['english_level_numeric'])
    
    # ANOVA 분석
    age_groups = df_filtered['age_group'].unique()
    if len(age_groups) > 1:
        groups_data = [df_filtered[df_filtered['age_group'] == group]['english_level_numeric'] for group in age_groups]
        f_stat, p_anova = f_oneway(*groups_data)
    else:
        f_stat, p_anova = 0, 1
    
    # 결론 도출
    if p_pearson < 0.05:
        if corr_pearson < 0:
            conclusion = "가설 기각: 연령대가 높을수록 영어 실력이 더 좋습니다."
        else:
            conclusion = "가설 채택: 연령대가 낮을수록 영어 실력이 더 좋습니다."
    else:
        conclusion = "가설 판단 불가: 연령과 영어 실력 간 유의한 관계가 없습니다."
    
    return HypothesisResult(
        hypothesis="연령대가 낮을수록 점수가 높을 것이다",
        result="기각" if (p_pearson < 0.05 and corr_pearson < 0) else "채택" if (p_pearson < 0.05 and corr_pearson > 0) else "판단불가",
        p_value=p_pearson,
        correlation=corr_pearson,
        statistics={
            "pearson_correlation": corr_pearson,
            "pearson_p_value": p_pearson,
            "spearman_correlation": corr_spearman,
            "spearman_p_value": p_spearman,
            "anova_f_stat": f_stat,
            "anova_p_value": p_anova,
            "age_group_stats": df_filtered.groupby('age_group')['english_level_numeric'].agg(['count', 'mean', 'std']).to_dict()
        },
        conclusion=conclusion
    )

@app.post("/analysis/hypothesis2")
async def analyze_hypothesis2(filters: FilterRequest = FilterRequest()) -> HypothesisResult:
    """가설 2: 수도권일수록 점수가 높을 것이다"""
    df = load_data_if_needed()
    df_filtered = apply_filters(df, filters)
    
    metro_scores = df_filtered[df_filtered['is_metropolitan'] == True]['english_level_numeric']
    non_metro_scores = df_filtered[df_filtered['is_metropolitan'] == False]['english_level_numeric']
    
    if len(metro_scores) < 5 or len(non_metro_scores) < 5:
        raise HTTPException(status_code=400, detail="각 그룹에 충분한 데이터가 없습니다.")
    
    # t-test
    t_stat, p_ttest = ttest_ind(metro_scores, non_metro_scores)
    effect_size = calculate_effect_size(metro_scores, non_metro_scores)
    
    # Mann-Whitney U test
    u_stat, p_mannwhitney = mannwhitneyu(metro_scores, non_metro_scores, alternative='two-sided')
    
    # 카이제곱 검정
    contingency_table = pd.crosstab(df_filtered['is_metropolitan'], df_filtered['english_level'])
    chi2, p_chi2, dof, expected = chi2_contingency(contingency_table)
    
    # 결론
    if p_ttest < 0.05:
        if metro_scores.mean() < non_metro_scores.mean():
            conclusion = "가설 채택: 수도권이 비수도권보다 영어 실력이 높습니다."
        else:
            conclusion = "가설 기각: 비수도권이 수도권보다 영어 실력이 높습니다."
    else:
        conclusion = "가설 판단 불가: 수도권과 비수도권 간 유의한 차이가 없습니다."
    
    return HypothesisResult(
        hypothesis="수도권일수록 점수가 높을 것이다",
        result="기각" if (p_ttest < 0.05 and metro_scores.mean() > non_metro_scores.mean()) else "채택" if (p_ttest < 0.05 and metro_scores.mean() < non_metro_scores.mean()) else "판단불가",
        p_value=p_ttest,
        effect_size=effect_size,
        statistics={
            "metro_mean": float(metro_scores.mean()),
            "non_metro_mean": float(non_metro_scores.mean()),
            "metro_count": len(metro_scores),
            "non_metro_count": len(non_metro_scores),
            "t_statistic": t_stat,
            "t_p_value": p_ttest,
            "effect_size": effect_size,
            "effect_interpretation": interpret_effect_size(effect_size),
            "mannwhitney_u": u_stat,
            "mannwhitney_p": p_mannwhitney,
            "chi_square": chi2,
            "chi_square_p": p_chi2
        },
        conclusion=conclusion
    )

@app.post("/analysis/hypothesis3")
async def analyze_hypothesis3(filters: FilterRequest = FilterRequest()) -> HypothesisResult:
    """가설 3: 영어권 거주 경험이 있을수록 점수가 높을 것이다"""
    df = load_data_if_needed()
    df_filtered = apply_filters(df, filters)
    
    exp_scores = df_filtered[df_filtered['english_speaking_experience'] == True]['english_level_numeric']
    no_exp_scores = df_filtered[df_filtered['english_speaking_experience'] == False]['english_level_numeric']
    
    if len(exp_scores) < 5 or len(no_exp_scores) < 5:
        raise HTTPException(status_code=400, detail="각 그룹에 충분한 데이터가 없습니다.")
    
    # t-test
    t_stat, p_ttest = ttest_ind(exp_scores, no_exp_scores)
    effect_size = calculate_effect_size(exp_scores, no_exp_scores)
    
    # Mann-Whitney U test
    u_stat, p_mannwhitney = mannwhitneyu(exp_scores, no_exp_scores, alternative='two-sided')
    
    # 카이제곱 검정
    contingency_table = pd.crosstab(df_filtered['english_speaking_experience'], df_filtered['english_level'])
    chi2, p_chi2, dof, expected = chi2_contingency(contingency_table)
    
    # 결론
    if p_ttest < 0.05:
        if exp_scores.mean() < no_exp_scores.mean():
            conclusion = "가설 채택: 영어권 거주 경험이 있는 사람들의 영어 실력이 더 높습니다."
        else:
            conclusion = "가설 기각: 영어권 거주 경험이 없는 사람들의 영어 실력이 더 높습니다."
    else:
        conclusion = "가설 판단 불가: 영어권 거주 경험에 따른 유의한 차이가 없습니다."
    
    return HypothesisResult(
        hypothesis="영어권 거주 경험이 있을수록 점수가 높을 것이다",
        result="기각" if (p_ttest < 0.05 and exp_scores.mean() > no_exp_scores.mean()) else "채택" if (p_ttest < 0.05 and exp_scores.mean() < no_exp_scores.mean()) else "판단불가",
        p_value=p_ttest,
        effect_size=effect_size,
        statistics={
            "experience_mean": float(exp_scores.mean()),
            "no_experience_mean": float(no_exp_scores.mean()),
            "experience_count": len(exp_scores),
            "no_experience_count": len(no_exp_scores),
            "t_statistic": t_stat,
            "t_p_value": p_ttest,
            "effect_size": effect_size,
            "effect_interpretation": interpret_effect_size(effect_size),
            "mannwhitney_u": u_stat,
            "mannwhitney_p": p_mannwhitney,
            "chi_square": chi2,
            "chi_square_p": p_chi2
        },
        conclusion=conclusion
    )

@app.post("/data/chart_data")
async def get_chart_data(filters: FilterRequest = FilterRequest()) -> Dict[str, Any]:
    """차트 생성을 위한 데이터"""
    df = load_data_if_needed()
    df_filtered = apply_filters(df, filters)
    
    if len(df_filtered) == 0:
        raise HTTPException(status_code=400, detail="필터 조건에 맞는 데이터가 없습니다.")
    
    return {
        "age_vs_score": {
            "ages": df_filtered['age'].tolist(),
            "scores": df_filtered['english_level_numeric'].tolist(),
            "levels": df_filtered['english_level'].tolist()
        },
        "age_group_stats": df_filtered.groupby('age_group')['english_level_numeric'].agg(['count', 'mean', 'std']).to_dict(),
        "metro_comparison": {
            "metro_scores": df_filtered[df_filtered['is_metropolitan'] == True]['english_level_numeric'].tolist(),
            "non_metro_scores": df_filtered[df_filtered['is_metropolitan'] == False]['english_level_numeric'].tolist()
        },
        "experience_comparison": {
            "exp_scores": df_filtered[df_filtered['english_speaking_experience'] == True]['english_level_numeric'].tolist(),
            "no_exp_scores": df_filtered[df_filtered['english_speaking_experience'] == False]['english_level_numeric'].tolist()
        },
        "level_distribution": df_filtered['english_level'].value_counts().to_dict(),
        "location_stats": df_filtered.groupby('location')['english_level_numeric'].agg(['count', 'mean']).to_dict()
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002, log_level="info")