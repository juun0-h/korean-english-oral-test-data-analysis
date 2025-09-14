#!/bin/bash

# 한영 데이터 분석 시스템 종료 스크립트

echo "🛑 한영 데이터 분석 시스템 종료 중..."

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

# 1. Docker 컨테이너 종료
log_info "Docker 컨테이너 종료 중..."

docker-compose down

if [ $? -eq 0 ]; then
    log_success "모든 컨테이너가 정상적으로 종료되었습니다."
else
    log_error "컨테이너 종료 중 오류가 발생했습니다."
fi

# 2. 볼륨 삭제 옵션 (선택사항)
echo ""
read -p "데이터베이스 볼륨도 삭제하시겠습니까? (y/N): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    log_warning "데이터베이스 볼륨 삭제 중..."
    docker-compose down -v
    log_success "볼륨이 삭제되었습니다. 다음 시작 시 Airflow 초기화가 다시 필요합니다."
fi

# 3. 이미지 삭제 옵션 (선택사항)
echo ""
read -p "빌드된 Docker 이미지도 삭제하시겠습니까? (y/N): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    log_warning "Docker 이미지 삭제 중..."
    docker-compose down --rmi all
    log_success "이미지가 삭제되었습니다. 다음 시작 시 이미지 빌드가 다시 필요합니다."
fi

# 4. 최종 상태 확인
log_info "최종 상태 확인 중..."

CONTAINERS=$(docker-compose ps -q)
if [ -z "$CONTAINERS" ]; then
    log_success "모든 서비스가 정상적으로 종료되었습니다."
else
    log_warning "일부 컨테이너가 아직 실행 중입니다:"
    docker-compose ps
fi

echo ""
echo "✅ 시스템 종료 완료!"
echo ""
echo "💡 다시 시작하려면:"
echo "   ./start_system.sh"
echo ""