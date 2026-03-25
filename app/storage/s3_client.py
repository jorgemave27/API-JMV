from __future__ import annotations

import boto3
from botocore.client import Config
from app.core.config import settings

s3 = boto3.client(
    "s3",
    endpoint_url=settings.S3_ENDPOINT,
    aws_access_key_id=settings.S3_ACCESS_KEY,
    aws_secret_access_key=settings.S3_SECRET_KEY,
    region_name=settings.S3_REGION,
    config=Config(signature_version="s3v4"),
)


def create_bucket_if_not_exists():
    try:
        buckets = s3.list_buckets()["Buckets"]
        if not any(b["Name"] == settings.S3_BUCKET for b in buckets):
            s3.create_bucket(Bucket=settings.S3_BUCKET)
    except Exception as e:
        print("S3 init error:", e)


def upload_file(file_content: bytes, key: str, content_type: str):
    s3.put_object(
        Bucket=settings.S3_BUCKET,
        Key=key,
        Body=file_content,
        ContentType=content_type,
    )
    return key


def generate_presigned_url(key: str, expires_in: int = 3600):
    return s3.generate_presigned_url(
        "get_object",
        Params={"Bucket": settings.S3_BUCKET, "Key": key},
        ExpiresIn=expires_in,
    )


def delete_file(key: str):
    s3.delete_object(Bucket=settings.S3_BUCKET, Key=key)