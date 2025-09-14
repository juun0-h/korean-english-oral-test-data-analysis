"""
한영 데이터 분석 시스템의 공통 상수 정의
"""

# 영어 레벨 매핑 (숫자가 낮을수록 높은 레벨)
LEVEL_MAPPING = {
    'IG': 1,  # Intermediate General (가장 낮은 레벨)
    'TL': 2,  # Talented Low
    'TM': 3,  # Talented Middle
    'TH': 4,  # Talented High
    'NA': 5   # Native-like (가장 높은 레벨)
}

LEVEL_NAMES = {
    'IG': 'Intermediate General',
    'TL': 'Talented Low',
    'TM': 'Talented Middle',
    'TH': 'Talented High',
    'NA': 'Native-like'
}

# 역매핑 (숫자 -> 레벨)
LEVEL_REVERSE_MAPPING = {v: k for k, v in LEVEL_MAPPING.items()}

# 가설 정의
HYPOTHESES = {
    'H1': {
        'title': '연령대가 낮을수록 점수가 높을 것이다',
        'independent_var': 'age',
        'dependent_var': 'english_level_numeric',
        'type': 'correlation',
        'direction': 'negative',  # 나이 ↑, 점수 ↓ (점수가 낮을수록 높은 등급)
        'tests': ['pearson_correlation', 'spearman_correlation', 'anova', 'post_hoc']
    },
    'H2': {
        'title': '수도권(서울/경기)일수록 점수가 높을 것이다',
        'independent_var': 'is_metropolitan',
        'dependent_var': 'english_level_numeric',
        'type': 'group_comparison',
        'direction': 'metropolitan_higher',
        'tests': ['t_test', 'mann_whitney', 'chi_square']
    },
    'H3': {
        'title': '영어권 거주 경험이 있을수록 점수가 높을 것이다',
        'independent_var': 'english_speaking_experience',
        'dependent_var': 'english_level_numeric',
        'type': 'group_comparison',
        'direction': 'experience_higher',
        'tests': ['t_test', 'mann_whitney', 'anova']
    }
}

# 통계적 유의성 임계값
SIGNIFICANCE_LEVEL = 0.05

# 수도권 지역
METROPOLITAN_AREAS = ['서울', '경기']

# 연령대 구분
AGE_GROUPS = {
    '20대 초반': (0, 24),
    '20대 후반': (25, 29),
    '30대 초반': (30, 34),
    '30대 후반': (35, 39),
    '40대 이상': (40, 100)
}

# 효과 크기 해석 기준 (Cohen's d)
EFFECT_SIZE_THRESHOLDS = {
    'small': 0.2,
    'medium': 0.5,
    'large': 0.8
}

# API 응답 메시지
API_MESSAGES = {
    'data_loaded_success': '데이터가 성공적으로 로드되었습니다.',
    'analysis_completed': '분석이 완료되었습니다.',
    'hypothesis_accepted': '가설이 채택되었습니다.',
    'hypothesis_rejected': '가설이 기각되었습니다.',
    'hypothesis_inconclusive': '가설 판단이 불가합니다.',
    'insufficient_data': '분석에 충분한 데이터가 없습니다.',
    'server_error': '서버 오류가 발생했습니다.'
}