#!/bin/bash

# 한영 데이터 분석 시스템 시작 스크립트

echo "🚀 한영 데이터 분석 시스템 시작 중..."

# 색깔 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 로그 함수
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 1. 환경 확인
log_info "환경 확인 중..."

# Docker 설치 확인
if ! command -v docker &> /dev/null; then
    log_error "Docker가 설치되지 않았습니다. Docker를 먼저 설치해주세요."
    exit 1
fi

# Docker Compose 설치 확인
if ! command -v docker-compose &> /dev/null; then
    log_error "Docker Compose가 설치되지 않았습니다. Docker Compose를 먼저 설치해주세요."
    exit 1
fi

# .env 파일 확인
if [ ! -f ".env" ]; then
    log_error ".env 파일이 없습니다. .env 파일을 생성해주세요."
    exit 1
fi

log_success "환경 확인 완료"

# 2. 포트 충돌 확인
log_info "포트 사용 현황 확인 중..."

PORTS=(8080 8000 8501 5433)
for port in "${PORTS[@]}"; do
    if lsof -Pi :$port -sTCP:LISTEN -t >/dev/null ; then
        log_warning "포트 $port가 이미 사용 중입니다. 서비스를 종료하거나 다른 포트를 사용해주세요."
    else
        log_success "포트 $port 사용 가능"
    fi
done

# 3. Docker 컨테이너 시작
log_info "Docker 컨테이너 빌드 및 시작 중..."
docker-compose up -d

if [ $? -ne 0 ]; then
    log_error "Docker 컨테이너 시작 실패"
    exit 1
fi

log_success "Docker 컨테이너 시작 완료"

# 4. 서비스 상태 확인
log_info "서비스 상태 확인 중..."
sleep 10

docker-compose ps

# 5. Airflow 초기화 확인
log_info "Airflow 초기화 상태 확인 중..."

# 먼저 Airflow가 완전히 시작될 때까지 대기
log_info "Airflow 서비스 시작 대기 중..."
sleep 30

# DB 초기화 수행 (매번 실행하여 안전하게)
log_info "Airflow 데이터베이스 초기화 중..."
docker-compose run --rm airflow-webserver airflow db init

if [ $? -eq 0 ]; then
    log_success "Airflow 데이터베이스 초기화 완료"
else
    log_error "Airflow 데이터베이스 초기화 실패"
    # 실패해도 계속 진행 (이미 초기화된 경우일 수 있음)
    log_warning "초기화 실패했지만 계속 진행합니다"
fi

# 6. 관리자 계정 생성
log_info "Airflow 관리자 계정 생성 중..."

# 기존 계정 삭제 후 새로 생성 (중복 방지)
docker-compose run --rm airflow-webserver airflow users delete --username admin 2>/dev/null || true

# 새 관리자 계정 생성
docker-compose run --rm airflow-webserver airflow users create \
    --username admin \
    --firstname Admin \
    --lastname User \
    --role Admin \
    --email admin@example.com \
    --password admin

if [ $? -eq 0 ]; then
    log_success "Airflow 관리자 계정 생성 완료 (admin/admin)"
else
    log_warning "Airflow 관리자 계정 생성 실패 (이미 존재할 수 있음)"
fi

# 7. Airflow 서비스 확실히 시작
log_info "Airflow 서비스 재시작 중..."
docker-compose up -d airflow-webserver airflow-scheduler

log_info "Airflow 시작 완료 대기 중..."
sleep 15

# 8. 테스트 DAG 활성화
log_info "DAG 활성화 중..."

# docker-compose exec -T airflow-scheduler airflow dags unpause simple_test_dag 2>/dev/null
# if [ $? -eq 0 ]; then
#     log_success "테스트 DAG 활성화 완료"
# else
#     log_warning "테스트 DAG 활성화 실패 (수동으로 활성화하세요)"
# fi

docker-compose exec -T airflow-scheduler airflow dags unpause daily_data_pipeline 2>/dev/null
if [ $? -eq 0 ]; then
    log_success "메인 데이터 파이프라인 DAG 활성화 완료"
else
    log_warning "메인 DAG 활성화 실패 (수동으로 활성화하세요)"
fi

# 9. 최종 확인
log_info "서비스 최종 상태 확인 중..."
sleep 10

echo ""
echo "🎉 시스템 시작 완료!"
echo ""
echo "📋 서비스 접속 정보:"
echo "┌─────────────────────┬─────────────────────────┬─────────────────┐"
echo "│ 서비스              │ URL                     │ 계정 정보       │"
echo "├─────────────────────┼─────────────────────────┼─────────────────┤"
echo "│ Airflow 웹 UI       │ http://localhost:8080   │ admin/admin     │"
echo "│ FastAPI 문서        │ http://localhost:8000   │ -               │"
echo "│ Streamlit 대시보드  │ http://localhost:8501   │ -               │"
echo "└─────────────────────┴─────────────────────────┴─────────────────┘"
echo ""

# 서비스 응답 확인
log_info "서비스 응답 확인 중..."

# Airflow 확인 (여러 번 시도)
log_info "Airflow UI 응답 확인 중... (최대 3번 시도)"
AIRFLOW_OK=false
for i in {1..3}; do
    if curl -s -o /dev/null -w "%{http_code}" http://localhost:8080/ | grep -q "302\|200"; then
        log_success "Airflow 웹 UI 정상 응답 (시도 $i/3)"
        AIRFLOW_OK=true
        break
    else
        log_warning "Airflow UI 응답 없음 (시도 $i/3)"
        if [ $i -lt 3 ]; then
            sleep 10
        fi
    fi
done

if [ "$AIRFLOW_OK" = false ]; then
    log_error "Airflow UI가 응답하지 않습니다. 수동으로 확인해주세요."
    log_info "문제 해결 방법:"
    echo "  1. docker-compose logs airflow-webserver"
    echo "  2. docker-compose restart airflow-webserver"
    echo "  3. http://localhost:8080 직접 접속 시도"
fi

# FastAPI 확인
if curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/health | grep -q "200"; then
    log_success "FastAPI 서버 정상 응답"
else
    log_warning "FastAPI 서버 응답 없음 (잠시 후 다시 확인해주세요)"
fi

# Streamlit 확인
if curl -s -o /dev/null -w "%{http_code}" http://localhost:8501/ | grep -q "200"; then
    log_success "Streamlit 대시보드 정상 응답"
else
    log_warning "Streamlit 대시보드 응답 없음 (잠시 후 다시 확인해주세요)"
fi

echo ""
echo "🔥 다음 단계:"
echo "1. Airflow UI (http://localhost:8080)에 접속하여 DAG를 확인하세요"
echo "2. simple_test_dag를 실행하여 S3 연결을 테스트하세요"  
echo "3. daily_data_pipeline을 활성화하여 전체 파이프라인을 실행하세요"
echo ""
echo "❓ 문제가 발생하면 TROUBLESHOOTING.md 파일을 참고하세요"
echo ""