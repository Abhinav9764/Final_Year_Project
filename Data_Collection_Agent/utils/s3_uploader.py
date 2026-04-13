"""
utils/s3_uploader.py
=====================
Uploads collected datasets and metadata to S3.
Gracefully disables itself when boto3 or credentials are unavailable.
"""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)
_SMALL_UPLOAD_BYTES = 16 * 1024 * 1024

try:
    import boto3
    from botocore.config import Config as BotoConfig
    from boto3.s3.transfer import TransferConfig

    _BOTO3 = True
except ImportError:  # pragma: no cover - environment-specific
    _BOTO3 = False
    BotoConfig = None  # type: ignore[assignment]
    TransferConfig = None  # type: ignore[assignment]


class S3Uploader:
    def __init__(self, config: dict):
        aws = config.get("aws", {})
        self._bucket = os.getenv("AWS_S3_BUCKET") or aws.get("s3_bucket", "rad-ml-datasets")
        self._prefix = os.getenv("AWS_S3_PREFIX") or aws.get("s3_prefix", "collected_data")
        self._region = os.getenv("AWS_REGION") or aws.get("region", "us-east-1")
        self._endpoint_url = os.getenv("AWS_S3_ENDPOINT_URL") or aws.get("s3_endpoint_url") or None
        self._access_key = os.getenv("AWS_ACCESS_KEY_ID") or aws.get("access_key_id") or ""
        self._secret_key = os.getenv("AWS_SECRET_ACCESS_KEY") or aws.get("secret_access_key") or ""
        self._client = None
        self._transfer_config = None
        self._enabled = _BOTO3

        if self._enabled and not self._endpoint_url and not (self._access_key and self._secret_key):
            logger.warning("AWS credentials not configured for S3 - uploads disabled.")
            self._enabled = False

        if self._enabled:
            try:
                os.environ.setdefault("AWS_EC2_METADATA_DISABLED", "true")
                kwargs: dict = {"region_name": self._region}
                if self._endpoint_url:
                    kwargs["endpoint_url"] = self._endpoint_url
                if self._access_key and self._secret_key:
                    kwargs["aws_access_key_id"] = self._access_key
                    kwargs["aws_secret_access_key"] = self._secret_key
                if BotoConfig is not None:
                    kwargs["config"] = BotoConfig(
                        connect_timeout=2,
                        read_timeout=15,
                        max_pool_connections=16,
                        retries={"max_attempts": 2, "mode": "standard"},
                    )
                self._client = boto3.client("s3", **kwargs)
                if TransferConfig is not None:
                    self._transfer_config = TransferConfig(
                        multipart_threshold=_SMALL_UPLOAD_BYTES,
                        max_concurrency=8,
                        multipart_chunksize=8 * 1024 * 1024,
                        use_threads=True,
                    )
                logger.info("S3Uploader ready - bucket=%s prefix=%s", self._bucket, self._prefix)
            except Exception as exc:
                logger.warning("S3 init failed (%s) - uploads disabled.", exc)
                self._enabled = False

    def upload_dataset(self, local_path: Path, job_id: str) -> str | None:
        """Upload the collected dataset CSV and return its s3:// URI."""
        if not self._enabled:
            logger.info("S3 disabled - dataset not uploaded.")
            return None
        key = f"{self._prefix}/datasets/{job_id}/{local_path.name}"
        return self._upload(local_path, key)

    def upload_results_json(self, payload: dict, job_id: str) -> str | None:
        if not self._enabled:
            return None
        key = f"{self._prefix}/{job_id}/db_results.json"
        try:
            self._client.put_object(
                Bucket=self._bucket,
                Key=key,
                Body=json.dumps(payload, indent=2, default=str).encode("utf-8"),
                ContentType="application/json",
            )
            uri = f"s3://{self._bucket}/{key}"
            logger.info("Uploaded results JSON -> %s", uri)
            return uri
        except Exception as exc:
            logger.error("JSON upload failed: %s", exc)
            return None

    def _upload(self, path: Path, key: str) -> str | None:
        try:
            file_size = path.stat().st_size
            if file_size <= _SMALL_UPLOAD_BYTES:
                logger.info("Uploading %s to S3 with put_object (%d bytes)", path.name, file_size)
                with open(path, "rb") as handle:
                    self._client.put_object(
                        Bucket=self._bucket,
                        Key=key,
                        Body=handle.read(),
                        ContentType="text/csv",
                    )
            else:
                logger.info("Uploading %s to S3 with multipart transfer (%d bytes)", path.name, file_size)
                extra_args = {"ContentType": "text/csv"}
                if self._transfer_config is not None:
                    self._client.upload_file(
                        str(path),
                        self._bucket,
                        key,
                        ExtraArgs=extra_args,
                        Config=self._transfer_config,
                    )
                else:
                    self._client.upload_file(str(path), self._bucket, key, ExtraArgs=extra_args)
            uri = f"s3://{self._bucket}/{key}"
            logger.info("Uploaded %s -> %s", path.name, uri)
            return uri
        except Exception as exc:
            logger.error("Upload failed for %s: %s", path, exc)
            return None
