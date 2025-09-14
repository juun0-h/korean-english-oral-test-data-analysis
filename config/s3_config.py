"""
S3 설정 및 유틸리티 함수
"""

import os
import boto3
from botocore.exceptions import ClientError


class S3Manager:
    """S3 파일 업로드/다운로드 관리자"""
    
    def __init__(self):
        self.s3_client = boto3.client(
            's3',
            aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
            aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
            region_name=os.getenv('AWS_REGION', 'ap-northeast-2')
        )
        self.bucket_name = os.getenv('S3_BUCKET_NAME')
        
    def upload_file(self, file_path: str, s3_key: str) -> bool:
        """파일을 S3에 업로드"""
        try:
            self.s3_client.upload_file(file_path, self.bucket_name, s3_key)
            print(f"업로드 성공: {s3_key}")
            return True
        except ClientError as e:
            print(f"업로드 실패: {e}")
            return False
    
    def download_file(self, s3_key: str, local_path: str) -> bool:
        """S3에서 파일 다운로드"""
        try:
            self.s3_client.download_file(self.bucket_name, s3_key, local_path)
            print(f"다운로드 성공: {s3_key}")
            return True
        except ClientError as e:
            print(f"다운로드 실패: {e}")
            return False
    
    def list_files(self, prefix: str = "") -> list:
        """S3 버킷의 파일 목록 조회"""
        try:
            response = self.s3_client.list_objects_v2(
                Bucket=self.bucket_name,
                Prefix=prefix
            )
            return [obj['Key'] for obj in response.get('Contents', [])]
        except ClientError as e:
            print(f"파일 목록 조회 실패: {e}")
            return []
    
    def delete_file(self, s3_key: str) -> bool:
        """S3에서 파일 삭제"""
        try:
            self.s3_client.delete_object(Bucket=self.bucket_name, Key=s3_key)
            print(f"삭제 성공: {s3_key}")
            return True
        except ClientError as e:
            print(f"삭제 실패: {e}")
            return False


def get_s3_manager():
    """S3 매니저 인스턴스 반환"""
    return S3Manager()