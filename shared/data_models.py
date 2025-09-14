"""
한영 데이터 분석 시스템의 공통 데이터 모델
"""

from typing import Dict, List, Optional, Any, Union
from pydantic import BaseModel, Field
from enum import Enum


class EnglishLevel(str, Enum):
    """영어 레벨 열거형"""
    IG = "IG"
    TL = "TL"
    TM = "TM"
    TH = "TH"
    NA = "NA"


class Gender(str, Enum):
    """성별 열거형"""
    MALE = "male"
    FEMALE = "female"


class ParticipantData(BaseModel):
    """참가자 기본 데이터"""
    participant_id: str
    age: int
    gender: Gender
    location: str
    english_level: EnglishLevel
    english_level_numeric: int
    self_grade: str
    age_group: str
    is_metropolitan: bool
    english_speaking_experience: bool
    combo_scores: Dict[str, float] = Field(default_factory=dict)
    interview: Dict[str, Any] = Field(default_factory=dict)
    file_date: str
    year: str


class StatisticalResult(BaseModel):
    """통계 분석 결과"""
    test_name: str
    statistic: float
    p_value: float
    degrees_of_freedom: Optional[int] = None
    confidence_interval: Optional[List[float]] = None


class EffectSize(BaseModel):
    """효과 크기 결과"""
    value: float
    interpretation: str  # "작은 효과", "중간 효과", "큰 효과", "매우 큰 효과"


class HypothesisResult(BaseModel):
    """가설 검증 결과"""
    hypothesis_id: str
    title: str
    conclusion: str  # "채택", "기각", "판단불가"
    significance_level: float
    statistical_tests: List[StatisticalResult]
    effect_size: Optional[EffectSize] = None
    sample_size: int
    description: str
    visualization_data: Dict[str, Any] = Field(default_factory=dict)


class CorrelationAnalysis(BaseModel):
    """상관관계 분석 결과"""
    pearson_r: float
    pearson_p: float
    spearman_r: float
    spearman_p: float
    sample_size: int


class GroupComparisonAnalysis(BaseModel):
    """그룹 비교 분석 결과"""
    group1_name: str
    group1_mean: float
    group1_std: float
    group1_size: int
    group2_name: str
    group2_mean: float
    group2_std: float
    group2_size: int
    mean_difference: float


class DataSummary(BaseModel):
    """데이터 요약 통계"""
    total_participants: int
    age_range: Dict[str, int]  # {"min": 20, "max": 45}
    gender_distribution: Dict[str, int]
    location_distribution: Dict[str, int]
    level_distribution: Dict[str, int]
    metropolitan_ratio: float
    english_experience_ratio: float


class AnalysisRequest(BaseModel):
    """분석 요청"""
    hypothesis_id: Optional[str] = None
    filters: Optional[Dict[str, Any]] = Field(default_factory=dict)
    include_visualization: bool = True


class AnalysisResponse(BaseModel):
    """분석 응답"""
    success: bool
    message: str
    data: Optional[Union[HypothesisResult, DataSummary, Dict[str, Any]]] = None
    error: Optional[str] = None


class VisualizationData(BaseModel):
    """시각화 데이터"""
    chart_type: str  # "box", "scatter", "bar", "histogram", "heatmap"
    data: Dict[str, Any]
    layout: Dict[str, Any] = Field(default_factory=dict)
    config: Dict[str, Any] = Field(default_factory=dict)