#!/bin/bash

# FastAPI 백엔드와 Streamlit 프론트엔드를 동시에 실행하는 스크립트

echo "🚀 한국인 영어 실력 분석 시스템 시작"
echo "=================================="

# 백그라운드에서 FastAPI 서버 시작
echo "📡 FastAPI 백엔드 서버 시작 중..."
uv run python api_server.py &
API_PID=$!

# 서버가 시작될 때까지 대기 (최대 30초)
echo "🔍 API 서버 상태 확인 중..."
for i in {1..30}; do
    if curl -s http://localhost:8002/health > /dev/null; then
        break
    fi
    if [ $i -eq 30 ]; then
        echo "❌ FastAPI 서버 시작 실패 (시간 초과)"
        kill $API_PID
        exit 1
    fi
    sleep 1
done

if curl -s http://localhost:8002/health > /dev/null; then
    echo "✅ FastAPI 서버가 성공적으로 시작되었습니다 (PID: $API_PID)"
    echo "   URL: http://localhost:8002"
    echo "   API 문서: http://localhost:8002/docs"
else
    echo "❌ FastAPI 서버 시작 실패"
    kill $API_PID
    exit 1
fi

# Streamlit 프론트엔드 시작
echo ""
echo "🎨 Streamlit 프론트엔드 시작 중..."
echo "   URL: http://localhost:8501"
echo ""
echo "💡 종료하려면 Ctrl+C를 누르세요"

# 종료 시그널 핸들러
cleanup() {
    echo ""
    echo "🛑 시스템 종료 중..."
    echo "📡 FastAPI 서버 종료 (PID: $API_PID)"
    kill $API_PID
    echo "✅ 모든 서비스가 종료되었습니다"
    exit 0
}

# 시그널 핸들러 등록
trap cleanup SIGINT SIGTERM

# Streamlit 실행
uv run streamlit run frontend_app.py --server.port=8507

# 만약 Streamlit이 종료되면 API 서버도 종료
cleanup