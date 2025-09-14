"""
데이터베이스 연결 설정
"""

import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# 환경변수에서 데이터베이스 URL 가져오기
DATABASE_URL = os.getenv(
    'DATABASE_URL', 
    'postgresql://airflow:airflow@localhost:5432/airflow'
)

# SQLAlchemy 엔진 생성
engine = create_engine(DATABASE_URL)

# 세션 팩토리 생성
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    """데이터베이스 세션 가져오기"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()