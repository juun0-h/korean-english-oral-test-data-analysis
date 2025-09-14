from datetime import datetime, timedelta
import os
import json
import glob
from typing import List, Dict

from airflow import DAG
from airflow.operators.python import PythonOperator
import boto3
import requests

# DAG 기본 설정
default_args = {
    'owner': 'data-team',
    'depends_on_past': False,
    'start_date': datetime(2025, 8, 1),
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

dag = DAG(
    'daily_data_pipeline',
    default_args=default_args,
    description='한국인 영어 말하기 평가 수준별 데이터 레이크 구축',
    schedule_interval='@daily',
    catchup=True,
    tags=['s3', 'upload', 'metadata']
)

# --------- 유틸 함수 ---------
def is_valid_yyyymmdd(date_str: str) -> bool:
    """YYYYMMDD 형식인지 검사"""
    try:
        datetime.strptime(date_str, "%Y%m%d")
        return True
    except Exception:
        return False


def find_files_by_date(target_date: str) -> List[Dict]:
    """
    특정 날짜(YYYYMMDD)의 JSON 파일 목록 반환
    """
    dataset_path = "/opt/airflow/dataset"
    matching_files = []

    for level in ['IG', 'NA', 'TH', 'TL', 'TM']:
        level_path = f"{dataset_path}/{level}"
        if not os.path.exists(level_path):
            continue

        for participant_dir in os.listdir(level_path):
            participant_path = f"{level_path}/{participant_dir}"
            if not os.path.isdir(participant_path):
                continue

            json_files = glob.glob(f"{participant_path}/*.json")
            for json_file in json_files:
                try:
                    with open(json_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        file_date = data.get('metadata', {}).get('date')
                        if file_date and file_date == target_date and is_valid_yyyymmdd(file_date):
                            matching_files.append({
                                'file_path': json_file,
                                'level': level,
                                'participant': participant_dir,
                                'date': file_date
                            })
                except Exception as e:
                    print(f"파일 읽기 오류 {json_file}: {e}")

    print(f"날짜 {target_date}에 해당하는 파일 {len(matching_files)}개 발견")
    print(f"응답자: {[f['participant'] for f in matching_files]}")
    return matching_files


def upload_to_s3(**context):
    """
    실행 날짜의 JSON 파일을 S3에 업로드
    """
    execution_date = context['ds']  # YYYY-MM-DD
    current_date = execution_date.replace('-', '')  # YYYYMMDD

    print(f"{current_date} 날짜 파일 업로드 시작")
    matching_files = find_files_by_date(current_date)

    if not matching_files:
        print("업로드할 파일이 없습니다.")
        return {"uploaded_files": 0}

    # S3 클라이언트
    s3_client = boto3.client(
        's3',
        aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
        aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
        region_name=os.getenv('AWS_REGION', 'ap-northeast-2')
    )

    bucket_name = os.getenv('S3_BUCKET_NAME')
    uploaded_count = 0

    for file_info in matching_files:
        file_date = file_info['date']
        if not is_valid_yyyymmdd(file_date):
            print(f"잘못된 날짜 형식: {file_date}, 파일 스킵")
            continue

        year, month, day = file_date[:4], file_date[4:6], file_date[6:8]
        file_name = os.path.basename(file_info['file_path'])
        s3_key = f"raw/year={year}/month={month}/day={day}/level={file_info['level']}/{file_info['participant']}/{file_name}"

        # 중복 업로드 회피 (S3 존재 확인)
        try:
            s3_client.head_object(Bucket=bucket_name, Key=s3_key)
            print(f"S3에 이미 존재, 스킵: {s3_key}")
            continue
        except s3_client.exceptions.ClientError:
            pass  # 존재하지 않으면 업로드 진행

        try:
            s3_client.upload_file(file_info['file_path'], bucket_name, s3_key)
            uploaded_count += 1
            print(f"업로드 완료: {s3_key}")
        except Exception as e:
            print(f"업로드 실패 {file_info['file_path']}: {e}")

    print(f"총 {uploaded_count}개 파일 업로드 완료")
    return {"uploaded_files": uploaded_count}


def trigger_analysis(**context):
    upload_result = context['ti'].xcom_pull(task_ids='upload_to_s3')
    if upload_result['uploaded_files'] > 0:
        print(f"{upload_result['uploaded_files']}개 파일이 업로드됨. 분석 API 호출 준비.")
        return upload_result
    else:
        print("새로운 파일이 없어 분석을 건너뜁니다.")
        return None


def call_analysis_api(**context):
    upload_result = context['ti'].xcom_pull(task_ids='upload_to_s3')
    if upload_result and upload_result['uploaded_files'] > 0:
        try:
            # 1. 기존 분석 API 호출
            response = requests.post(
                'http://api:8000/analyze/new-data',
                json={
                    "file_count": upload_result['uploaded_files'],
                    "message": f"{upload_result['uploaded_files']}개 파일이 S3에 업로드됨"
                },
                timeout=10
            )
            response.raise_for_status()
            print(f"분석 API 호출 성공: {response.json()}")
            
            # 2. ELT 변환 트리거 (/refresh API 호출)
            refresh_response = requests.post(
                'http://api:8000/refresh',
                json={
                    "trigger": "airflow_daily",
                    "uploaded_files": upload_result['uploaded_files'],
                    "execution_date": context['ds']
                },
                timeout=300  # 변환 작업은 시간이 걸릴 수 있음
            )
            refresh_response.raise_for_status()
            print(f"ELT 변환 트리거 성공: {refresh_response.json()}")
            
        except Exception as e:
            print(f"API 호출 중 오류: {e}")
    else:
        print("업로드된 파일이 없어 API 호출 건너뜀")

# 태스크 정의
upload_task = PythonOperator(
    task_id='upload_to_s3',
    python_callable=upload_to_s3,
    dag=dag,
)

analysis_trigger_task = PythonOperator(
    task_id='trigger_analysis',
    python_callable=trigger_analysis,
    dag=dag,
)

api_analysis_task = PythonOperator(
    task_id='call_analysis_api',
    python_callable=call_analysis_api,
    dag=dag,
)

upload_task >> analysis_trigger_task >> api_analysis_task