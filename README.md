# 한영 데이터 분석 시스템 - ELT 파이프라인

Apache Airflow, FastAPI, Streamlit을 활용한 종합 데이터 분석 시스템입니다.

## 📋 시스템 구성

- **Apache Airflow 2.9.3**: 배치 처리 및 워크플로 관리
- **FastAPI**: 실시간 데이터 분석 API 서버
- **Streamlit**: 데이터 시각화 대시보드
- **PostgreSQL**: Airflow 메타데이터 저장소
- **AWS S3**: 데이터 저장소 (날짜별 파티셔닝)

## 🚀 빠른 시작

### 1. 환경 설정

```bash
# 프로젝트 디렉토리로 이동
cd /path/to/kor_eng_data_analy

# 패키지 설치 (uv 사용)
uv sync

# 환경 변수 설정
cp .env.example .env  # 필요시 생성하여 AWS 키 등 설정
```

### 2. 로컬 개발 환경 실행 (권장)

```bash
# 통합 실행 스크립트 사용
./run_system.sh

# 또는 개별 실행
uv run python api_server.py &        # FastAPI 서버 (포트 8002)
uv run streamlit run frontend_app.py # Streamlit 대시보드 (포트 8507)
```

### 3. Docker 환경 실행 (선택사항)

```bash
# Docker 컨테이너 빌드 및 실행
docker-compose up -d

# Airflow 데이터베이스 초기화 (최초 1회만)
docker-compose run --rm airflow-webserver airflow db init

# Airflow 관리자 계정 생성 (최초 1회만)
docker-compose run --rm airflow-webserver airflow users create \
  --username admin \
  --firstname Admin \
  --lastname User \
  --role Admin \
  --email admin@example.com \
  --password admin
```

### 4. 서비스 접속

| 서비스 | 로컬 환경 URL | Docker 환경 URL | 계정 정보 |
|--------|-------------|----------------|----------|
| FastAPI API | http://localhost:8002 | http://localhost:8000 | - |
| FastAPI 문서 | http://localhost:8002/docs | http://localhost:8000/docs | - |
| Streamlit 대시보드 | http://localhost:8507 | http://localhost:8502 | - |
| Airflow 웹 UI | - | http://localhost:8080 | admin/admin |
| PostgreSQL | - | localhost:5433 | airflow/airflow |

## 📋 현재 구현 상태

### ✅ 구현 완료된 기능

#### 1. FastAPI 백엔드 서버 (`api_server.py`)
- **포트**: 8002
- **주요 기능**:
  - 한영 데이터셋 자동 로드 및 캐싱
  - AWS S3 연결 및 대표 파일 수집
  - 실시간 데이터 분석 API
  - 통계 조회 및 시각화 데이터 제공

#### 2. Streamlit 프론트엔드 (`frontend_app.py`)
- **포트**: 8507
- **주요 기능**:
  - 실시간 데이터 대시보드
  - API 연동 상태 모니터링
  - 인터랙티브 차트 및 그래프
  - 다국어 지원 (한국어/영어)

#### 3. 시스템 통합
- **통합 실행 스크립트**: `run_system.sh`
- 서버 상태 자동 확인 및 헬스체크
- 백그라운드 프로세스 관리
- 우아한 종료 처리

#### 4. 프로젝트 구조
```
kor_eng_data_analy/
├── api_server.py              # FastAPI 메인 서버
├── frontend_app.py            # Streamlit 대시보드
├── run_system.sh              # 통합 실행 스크립트
├── config/                    # 설정 파일들
├── shared/                    # 공통 모듈
├── dataset/                   # 로컬 데이터 파일
└── docker-compose.yml         # Docker 환경 설정
```

### 5. DAG 실행 (Docker 환경)

1. **Airflow UI 접속**: http://localhost:8080 (admin/admin)
2. **DAG 목록에서 활성화**:
   - `simple_test_dag`: S3 연결 및 데이터셋 테스트
   - `daily_data_pipeline`: 실제 ELT 파이프라인
3. **수동 실행**: DAG 우측의 "Trigger DAG" 버튼 클릭

## 📊 데이터 파이프라인 구조

### ELT 파이프라인 플로우

```
JSON 파일 (34,428개)
    ↓
[Extract] 날짜별 필터링 (metadata.date)
    ↓  
[Load] S3 업로드 (년/월/일/레벨별 파티셔닝)
    ↓
[Transform] S3 기반 FastAPI 실시간 분석
    ↓
[저장] 분석 결과를 Parquet으로 S3 processed/ 저장
    ↓
Streamlit 대시보드 시각화
```

### S3 파티셔닝 구조

```
s3://korea-english-dataset/
├── raw/                    # 원본 JSON 데이터
│   ├── year=2024/
│   │   ├── month=01/
│   │   │   ├── day=15/
│   │   │   │   ├── level=IG/
│   │   │   │   ├── level=NA/
│   │   │   │   └── level=TH/
├── processed/              # 1차 가공 데이터
│   └── cleaned_dataset.parquet
└── analytics/              # 분석 결과 캐시 (24시간)
    ├── age_performance/
    │   ├── analysis_result.json
    │   ├── processed_data.parquet
    │   └── metadata.json
    ├── regional_gap/
    │   ├── analysis_result.json  
    │   ├── processed_data.parquet
    │   └── metadata.json
    └── occupation_analysis/
        ├── analysis_result.json
        ├── processed_data.parquet
        └── metadata.json
```

## 🔧 주요 기능

### 1. Airflow DAGs

#### `daily_data_pipeline`
- **스케줄**: 매일 자동 실행 (`@daily`)
- **기능**: 날짜별 JSON 파일 필터링 → S3 업로드 → FastAPI 분석 트리거

#### `simple_test_dag`  
- **스케줄**: 수동 실행
- **기능**: S3 연결 테스트 및 데이터셋 파일 개수 확인

### 2. FastAPI 엔드포인트

#### 기본 API
```bash
# API 상태 확인
curl http://localhost:8000/health

# 일일 통계 조회
curl http://localhost:8000/stats/daily

# 레벨별 통계 조회  
curl http://localhost:8000/stats/levels

# 새 데이터 분석 트리거
curl -X POST http://localhost:8000/analyze/new-data
```

#### 가설 검증 분석 API
```bash
# 연령-성능 상관관계 분석
curl http://localhost:8000/analysis/age-performance

# 지역별 성능 격차 분석
curl http://localhost:8000/analysis/regional-gap

# 직업군별 성능 특성 분석
curl http://localhost:8000/analysis/occupation-analysis
```

### 3. Streamlit 대시보드

- **실시간 데이터 시각화**
- **일일/월별 통계**
- **레벨별 성능 분석**
- **API 연동 상태 모니터링**

## 🛠 개발 환경 설정

### 로컬 개발 실행

```bash
# FastAPI 서버 (포트 8000)
cd api
uv run python main.py

# Streamlit 대시보드 (포트 8501)  
cd dashboard
uv run streamlit run streamlit_app.py --server.port=8501
```

### 의존성 관리

이 프로젝트는 `uv` 패키지 매니저를 사용합니다.

```bash
# 의존성 설치
uv pip install -e .

# 개발 의존성 포함 설치
uv pip install -e ".[dev]"
```

## 📁 프로젝트 구조

```
kor_eng_data_analy/
├── airflow/
│   ├── dags/
│   │   ├── daily_data_pipeline.py    # 메인 ELT 파이프라인
│   │   └── simple_test_dag.py        # 테스트 DAG
│   ├── Dockerfile
│   ├── airflow.cfg                   # Airflow 설정
│   └── webserver_config.py           # 웹서버 설정
├── api/
│   ├── main.py                       # FastAPI 메인 애플리케이션
│   └── Dockerfile
├── dashboard/
│   ├── streamlit_app.py              # Streamlit 대시보드
│   └── Dockerfile  
├── dataset/                          # JSON 데이터 파일들
├── config/                           # 설정 파일들
├── docker-compose.yml                # 전체 서비스 정의
├── pyproject.toml                    # 의존성 및 프로젝트 설정
├── .env                              # 환경 변수
└── README.md                         # 이 파일
```

## 🎯 사용 사례

### 1. 일일 배치 처리
```bash
# 특정 날짜 데이터 처리
docker-compose exec airflow-scheduler airflow dags trigger daily_data_pipeline
```

### 2. 실시간 분석
```bash
# API를 통한 실시간 분석 요청
curl -X POST http://localhost:8000/analyze/new-data \
  -H "Content-Type: application/json" \
  -d '{"date": "2024-01-15"}'
```

### 3. 대시보드 모니터링
- http://localhost:8501 에서 실시간 통계 확인
- 레벨별 성능 트렌드 분석
- API 응답 시간 모니터링

## 🔍 모니터링

### 서비스 상태 확인

```bash
# 모든 컨테이너 상태 확인
docker-compose ps

# 특정 서비스 로그 확인
docker-compose logs -f airflow-webserver
docker-compose logs -f api
docker-compose logs -f dashboard
```

### 데이터 처리 현황

- **Airflow UI**: http://localhost:8080에서 DAG 실행 현황 확인
- **API 로그**: FastAPI 처리 로그 실시간 모니터링  
- **대시보드**: Streamlit에서 처리된 데이터 통계 확인

## 🔬 가설 검증 분석

이 시스템은 한국인 영어 말하기 평가 데이터를 기반으로 3가지 핵심 가설을 검증할 수 있습니다.

### 가설 1: 연령-성능 상관관계
- **가설**: "나이가 많을수록 영어 말하기 성능이 낮아진다"
- **분석 내용**: 
  - 연령대별 평균 점수 (Task_Completion, Delivery, Accuracy, Appropriateness)
  - 연령과 총점의 피어슨 상관계수
  - 연령대별 점수 분포 비교
- **시각화**: 산점도 + 회귀선, 연령대별 박스플롯, 상관계수 히트맵

### 가설 2: 지역별 성능 격차  
- **가설**: "서울/수도권과 지방 간 영어 말하기 성능 격차가 존재한다"
- **분석 내용**:
  - 지역별 평균 점수 비교
  - 수도권 vs 비수도권 독립표본 t-검정
  - 지역별 고득점자(상위 25%) 비율 분석
- **시각화**: 지역별 평균 점수 지도, 수도권/비수도권 분포 비교, 지역별 순위 테이블

### 가설 3: 직업군별 성능 특성
- **가설**: "직업군에 따라 영어 말하기 성능과 특성이 다르게 나타난다"
- **분석 내용**:
  - 직업군별 평균 점수 및 표준편차 비교
  - 직업군별 강점 영역 분석 (4개 평가항목)
  - 직업과 성능의 일원분산분석(ANOVA)
- **시각화**: 직업군별 막대그래프, 4개 평가항목 히트맵, 점수 분포 박스플롯

### API 응답 구조
```json
{
  "hypothesis": "가설명",
  "statistical_test": "사용된 통계 검정",
  "p_value": 0.001,
  "conclusion": "가설 채택/기각",
  "effect_size": 0.25,
  "data": {
    "summary_stats": {...},
    "visualization_data": {...}
  }
}
```

## 🔧 앞으로 구현할 개선사항

### 🚧 1. Airflow 배치 파이프라인 완성
**우선순위: 높음**
- [ ] Airflow DAG 로직 완성 및 테스트
- [ ] 스케줄러 안정성 개선
- [ ] 데이터 품질 검증 단계 추가
- [ ] 실패 시 재시도 및 알림 기능

### 📊 2. 데이터 분석 기능 확장
**우선순위: 높음**
- [ ] 3가지 가설 검증 API 완전 구현
  - 연령-성능 상관관계 분석
  - 지역별 성능 격차 분석
  - 직업군별 성능 특성 분석
- [ ] 통계적 유의성 검정 강화
- [ ] 시각화 차트 다양성 확장

### 🎨 3. 프론트엔드 UI/UX 개선
**우선순위: 중간**
- [ ] 반응형 디자인 적용
- [ ] 실시간 데이터 업데이트 기능
- [ ] 사용자 인터페이스 개선
- [ ] 다크모드 지원
- [ ] 차트 인터랙션 개선

### ⚡ 4. 성능 최적화
**우선순위: 중간**
- [ ] Redis 캐싱 레이어 구축
- [ ] 데이터 로딩 성능 개선
- [ ] API 응답 시간 최적화
- [ ] 메모리 사용량 최적화

### 🔒 5. 보안 및 인증
**우선순위: 중간**
- [ ] API 키 인증 시스템
- [ ] HTTPS 적용
- [ ] 환경 변수 보안 강화
- [ ] 데이터 접근 권한 관리

### 🐳 6. DevOps 및 배포 개선
**우선순위: 낮음**
- [ ] GitHub Actions CI/CD 파이프라인
- [ ] 자동화된 테스트 스위트
- [ ] 모니터링 및 로깅 시스템
- [ ] Kubernetes 배포 설정

### 📈 7. 추가 분석 기능
**우선순위: 낮음**
- [ ] 머신러닝 모델 통합
- [ ] 예측 분석 기능
- [ ] 자연어 처리 파이프라인
- [ ] 추가 가설 검증 (성별, 교육수준 등)

### 🔧 8. 시스템 안정성
**우선순위: 높음**
- [ ] 에러 핸들링 개선
- [ ] 로그 시스템 구축
- [ ] 헬스 체크 고도화
- [ ] 장애 복구 메커니즘

---

## 📈 기존 확장 가능성

### 1. 추가 데이터 소스
- 새로운 데이터 형식 지원 (CSV, Parquet 등)
- 실시간 데이터 스트리밍 연동

### 2. 고급 분석
- 머신러닝 모델 통합
- 자연어 처리 파이프라인 추가
- 추가 가설 검증 (성별, 교육수준, 경험 등)

### 3. 인프라 확장
- Kubernetes 배포
- 다중 리전 S3 복제
- Redis 캐싱 레이어 추가