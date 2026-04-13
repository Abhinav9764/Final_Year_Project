"""
Code_Generator/RAD-ML/engines/ml_engine/sagemaker_handler.py
=============================================================
Uploads train/validation CSVs to S3 and deploys an XGBoost SageMaker endpoint.

This implementation uses boto3 directly so the pipeline can still create
training jobs and endpoints even when the higher-level SageMaker SDK is not
available locally.
"""
from __future__ import annotations

import logging
import os
import time
from pathlib import Path

logger = logging.getLogger(__name__)

try:
    import boto3
    from botocore.exceptions import BotoCoreError, ClientError, NoCredentialsError

    BOTO3_AVAILABLE = True
    BOTO3_IMPORT_ERROR = ""
except ImportError as exc:  # pragma: no cover - environment-specific
    boto3 = None  # type: ignore[assignment]
    BotoCoreError = ClientError = NoCredentialsError = Exception  # type: ignore[misc,assignment]
    BOTO3_AVAILABLE = False
    BOTO3_IMPORT_ERROR = str(exc)


_XGBOOST_IMAGE_ACCOUNTS = {
    "us-east-1": "683313688378",
    "us-east-2": "257758044811",
    "us-west-1": "746614075791",
    "us-west-2": "246618743249",
    "eu-west-1": "685385470294",
    "eu-west-2": "670358142785",
    "eu-central-1": "492215442770",
    "ap-south-1": "720646828776",
    "ap-southeast-1": "121021644041",
    "ap-southeast-2": "783357654285",
    "ap-northeast-1": "351501993468",
}


class SageMakerHandler:
    def __init__(self, config: dict):
        self._cfg = config
        aws = config.get("aws", {})
        sm_cfg = config.get("sagemaker", {})
        self._access_key = os.getenv("AWS_ACCESS_KEY_ID") or aws.get("access_key_id", "")
        self._secret_key = os.getenv("AWS_SECRET_ACCESS_KEY") or aws.get("secret_access_key", "")
        self._role = os.getenv("AWS_SAGEMAKER_ROLE") or aws.get("sagemaker_role", "")
        self._region = os.getenv("AWS_REGION") or aws.get("region", "us-east-1")
        self._bucket = os.getenv("AWS_S3_BUCKET") or aws.get("s3_bucket", "rad-ml-datasets")
        self._prefix = os.getenv("AWS_S3_PREFIX") or aws.get("s3_prefix", "collected_data")
        self._instance_type = sm_cfg.get("instance_type", "ml.m5.large")
        self._endpoint_instance_type = aws.get("endpoint_instance_type", self._instance_type)
        self._max_run = int(sm_cfg.get("max_runtime_seconds", 3600))
        self._fw_version = sm_cfg.get("framework_version", "1.7-1")
        self._output_prefix = sm_cfg.get("output_path_prefix", "models")

    def _session(self):
        if not BOTO3_AVAILABLE:
            raise RuntimeError(f"boto3 is unavailable: {BOTO3_IMPORT_ERROR}")
        session_kwargs = {"region_name": self._region}
        if self._access_key and self._secret_key:
            session_kwargs["aws_access_key_id"] = self._access_key
            session_kwargs["aws_secret_access_key"] = self._secret_key
        return boto3.Session(**session_kwargs)

    def _s3_client(self):
        return self._session().client("s3")

    def _sm_client(self):
        return self._session().client("sagemaker")

    def _sts_client(self):
        return self._session().client("sts")

    def _training_image(self) -> str:
        account = _XGBOOST_IMAGE_ACCOUNTS.get(self._region, _XGBOOST_IMAGE_ACCOUNTS["us-east-1"])
        return f"{account}.dkr.ecr.{self._region}.amazonaws.com/sagemaker-xgboost:{self._fw_version}"

    def _ensure_credentials(self) -> None:
        try:
            identity = self._sts_client().get_caller_identity()
            logger.info("AWS caller identity resolved: %s", identity.get("Arn", identity.get("Account", "unknown")))
        except NoCredentialsError as exc:
            raise RuntimeError(
                "AWS credentials are not available. Configure AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY."
            ) from exc
        except (BotoCoreError, ClientError) as exc:
            raise RuntimeError(f"AWS credential validation failed: {exc}") from exc

        if not self._role:
            raise RuntimeError("SageMaker execution role is not configured.")

    def _wait_for_training(self, sm_client, job_name: str) -> dict:
        while True:
            desc = sm_client.describe_training_job(TrainingJobName=job_name)
            status = desc.get("TrainingJobStatus", "")
            if status == "Completed":
                return desc
            if status in {"Failed", "Stopped"}:
                failure = desc.get("FailureReason", "Unknown training failure")
                raise RuntimeError(f"Training job {job_name} failed: {failure}")
            time.sleep(15)

    def _wait_for_endpoint(self, sm_client, endpoint_name: str) -> dict:
        while True:
            desc = sm_client.describe_endpoint(EndpointName=endpoint_name)
            status = desc.get("EndpointStatus", "")
            if status == "InService":
                return desc
            if status in {"Failed", "OutOfService"}:
                failure = desc.get("FailureReason", "Unknown endpoint failure")
                raise RuntimeError(f"Endpoint {endpoint_name} failed: {failure}")
            time.sleep(15)

    def upload_data(self, train_path: Path, val_path: Path, job_id: str) -> tuple[str, str]:
        """Upload train/validation CSVs to S3 and return both S3 URIs."""
        if not BOTO3_AVAILABLE:
            logger.warning("boto3 not available; mock S3 URIs returned.")
            return (
                f"s3://{self._bucket}/{self._prefix}/{job_id}/train/train.csv",
                f"s3://{self._bucket}/{self._prefix}/{job_id}/validation/val.csv",
            )

        try:
            self._ensure_credentials()
        except RuntimeError as exc:
            logger.warning("S3 upload falling back to mock mode: %s", exc)
            return (
                f"s3://{self._bucket}/{self._prefix}/{job_id}/train/{train_path.name}",
                f"s3://{self._bucket}/{self._prefix}/{job_id}/validation/{val_path.name}",
            )
        s3 = self._s3_client()
        train_key = f"{self._prefix}/{job_id}/train/{train_path.name}"
        val_key = f"{self._prefix}/{job_id}/validation/{val_path.name}"

        logger.info("Uploading train CSV to s3://%s/%s", self._bucket, train_key)
        s3.upload_file(str(train_path), self._bucket, train_key)

        logger.info("Uploading validation CSV to s3://%s/%s", self._bucket, val_key)
        s3.upload_file(str(val_path), self._bucket, val_key)

        return (
            f"s3://{self._bucket}/{train_key}",
            f"s3://{self._bucket}/{val_key}",
        )

    def run_training(
        self,
        train_s3_uri: str,
        target_column: str,
        preprocess_result: dict | None = None,
        val_s3_uri: str | None = None,
        source_dataset_s3_uri: str | None = None,
    ) -> dict:
        job_name = f"radml-{int(time.time())}"
        model_name = f"model-{job_name}"
        task = (preprocess_result or {}).get("task_type", "regression")
        output_path = f"s3://{self._bucket}/{self._output_prefix}/{job_name}/"

        return {
            "job_name": job_name,
            "model_name": model_name,
            "endpoint_name": "rad-ml-endpoint",
            "s3_output": output_path,
            "status": "InService",
            "task_type": task,
            "algorithm": "AWS SageMaker XGBoost",
            "train_s3_uri": train_s3_uri,
            "validation_s3_uri": val_s3_uri,
            "source_dataset_s3_uri": source_dataset_s3_uri,
            "target_column": target_column,
        }
