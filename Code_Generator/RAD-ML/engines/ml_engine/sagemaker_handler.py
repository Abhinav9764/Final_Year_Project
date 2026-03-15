"""
engines/ml_engine/sagemaker_handler.py - Single SageMaker training orchestration
===============================================================================
Runs one explicit SageMaker training job (no Autopilot candidate fan-out),
creates/reuses one model, and deploys/reuses one endpoint.

Dependencies: pip install boto3
"""

from __future__ import annotations

import logging
import re
import time
from typing import Dict, Optional

log = logging.getLogger(__name__)

# boto3 (optional - graceful degradation)
try:
    import boto3  # type: ignore
    from botocore.exceptions import ClientError  # type: ignore

    BOTO3_AVAILABLE = True
except ImportError:
    ClientError = Exception  # type: ignore[misc, assignment]
    BOTO3_AVAILABLE = False
    log.warning("boto3 not installed - SageMakerHandler will use mock mode.")


class SageMakerHandler:
    """
    Orchestrates one SageMaker training job and endpoint deployment.

    Args:
        cfg: Full config dict (reads [aws] section).
    """

    POLL_INTERVAL = 30
    MAX_WAIT_MINUTES = 120
    ENDPOINT_INSTANCE_FALLBACK_ORDER = (
        "ml.m5.large",
        "ml.m5.xlarge",
        "ml.c5.xlarge",
        "ml.c6i.large",
        "ml.m6i.large",
    )

    def __init__(self, cfg: dict):
        aws = cfg.get("aws", {})
        cost_control = cfg.get("cost_control", {})

        self.region = aws.get("region", "us-east-1")
        self.role = aws.get("sagemaker_role", "")
        self.s3_bucket = aws.get("s3_bucket", "rad-ml-datasets")
        self.training_instance = aws.get("training_instance_type", "ml.m5.large")
        self.endpoint_instance = aws.get(
            "endpoint_instance_type",
            cost_control.get("preferred_instance", "ml.m5.large"),
        )
        self.training_image_uri = aws.get(
            "training_image_uri",
            f"683313688378.dkr.ecr.{self.region}.amazonaws.com/sagemaker-xgboost:1.7-1",
        )
        self.max_runtime_secs = int(aws.get("training_max_runtime_secs", 3600))
        self.training_job_base_name = aws.get("sagemaker_training_job_name", "rad-ml-train-once")
        self.model_base_name = aws.get("sagemaker_model_name", "rad-ml-model")
        self.endpoint_base_name = aws.get("sagemaker_endpoint_name", "rad-ml-endpoint")

        self._sm = None
        self._rt = None
        self._latest_endpoint_cfg_name: Optional[str] = None

    def run_training(
        self,
        s3_input_uri: str,
        target_column: str,
        job_name: Optional[str] = None,
    ) -> Dict[str, str]:
        """
        Run or reuse one SageMaker training job and one deployed endpoint.

        Args:
            s3_input_uri: S3 URI of the cleaned training CSV.
            target_column: Name of the target/label column.
            job_name: Optional custom training job name.

        Returns:
            {
              "endpoint_name": str,
              "endpoint_console_url": str,
              "job_name": str,
              "model_name": str,
              "model_artifact_uri": str
            }
        """
        if not BOTO3_AVAILABLE or not self.role or "arn:aws:iam::ACCOUNT" in self.role:
            return self._mock_run(s3_input_uri, target_column)

        sm = self._get_sm_client()
        job_name = job_name or self.training_job_base_name
        model_name = self.model_base_name
        endpoint_name = self.endpoint_base_name
        endpoint_cfg_name = f"{endpoint_name}-cfg"

        training_desc = self._describe_training_job(sm, job_name)
        if training_desc is None:
            self._create_training_job(
                sm=sm,
                job_name=job_name,
                s3_input_uri=s3_input_uri,
                output_s3_uri=f"s3://{self.s3_bucket}/training-output/{job_name}/",
            )
        else:
            status = training_desc.get("TrainingJobStatus", "Unknown")
            log.info("Reusing existing training job %s with status=%s", job_name, status)
            if status in ("Failed", "Stopped"):
                prev_reason = training_desc.get("FailureReason", "Unknown")
                timestamp = str(int(time.time()))
                base = job_name[: max(1, 63 - len(timestamp) - 1)]
                job_name = f"{base}-{timestamp}"
                log.warning(
                    "Existing training job is %s and cannot be reused; creating fresh job %s. "
                    "Previous FailureReason: %s",
                    status,
                    job_name,
                    prev_reason,
                )
                self._create_training_job(
                    sm=sm,
                    job_name=job_name,
                    s3_input_uri=s3_input_uri,
                    output_s3_uri=f"s3://{self.s3_bucket}/training-output/{job_name}/",
                )

        self._wait_for_training_job(sm, job_name)
        training_desc = self._describe_training_job(sm, job_name)
        if not training_desc:
            raise RuntimeError(f"Unable to describe training job {job_name} after completion.")

        model_artifact_uri = (
            training_desc.get("ModelArtifacts", {}).get("S3ModelArtifacts", "")
        )
        if not model_artifact_uri:
            raise RuntimeError(
                f"Training job {job_name} completed without model artifacts."
            )

        model_name = self._ensure_model(
            sm=sm,
            model_name=model_name,
            model_artifact_uri=model_artifact_uri,
        )
        self._ensure_endpoint_config(
            sm=sm,
            endpoint_cfg_name=endpoint_cfg_name,
            model_name=model_name,
        )
        self._ensure_endpoint(
            sm=sm,
            endpoint_name=endpoint_name,
            endpoint_cfg_name=endpoint_cfg_name,
        )

        endpoint_console_url = (
            "https://console.aws.amazon.com/sagemaker/home"
            f"?region={self.region}#/endpoints/{endpoint_name}"
        )
        log.info("SAGEMAKER_ENDPOINT_URL: %s", endpoint_console_url)
        log.info("SageMaker endpoint ready -> %s", endpoint_name)

        return {
            "endpoint_name": endpoint_name,
            "endpoint_console_url": endpoint_console_url,
            "job_name": job_name,
            "model_name": model_name,
            "model_artifact_uri": model_artifact_uri,
        }

    def run_autopilot(
        self,
        s3_input_uri: str,
        target_column: str,
        job_name: Optional[str] = None,
    ) -> Dict[str, str]:
        """
        Backward-compatible alias.

        Historically this method used Autopilot. It now routes to single-job
        training to avoid multiple SageMaker training jobs.
        """
        return self.run_training(
            s3_input_uri=s3_input_uri,
            target_column=target_column,
            job_name=job_name,
        )

    def predict(self, endpoint_name: str, payload: str) -> str:
        """
        Invoke a deployed SageMaker endpoint.

        Args:
            endpoint_name: Name of the real-time endpoint.
            payload: CSV row string of input features.

        Returns:
            Raw prediction string from the endpoint.
        """
        if not BOTO3_AVAILABLE:
            return "0.72"

        rt = self._get_rt_client()
        response = rt.invoke_endpoint(
            EndpointName=endpoint_name,
            ContentType="text/csv",
            Body=payload,
        )
        return response["Body"].read().decode("utf-8").strip()

    def delete_endpoint(self, endpoint_name: str) -> None:
        """Clean up a deployed endpoint to avoid AWS charges."""
        if not BOTO3_AVAILABLE:
            return
        self._get_sm_client().delete_endpoint(EndpointName=endpoint_name)
        log.info("Deleted SageMaker endpoint: %s", endpoint_name)

    def _get_sm_client(self):
        if self._sm is None:
            self._sm = boto3.client("sagemaker", region_name=self.region)
        return self._sm

    def _get_rt_client(self):
        if self._rt is None:
            self._rt = boto3.client("sagemaker-runtime", region_name=self.region)
        return self._rt

    def _describe_training_job(self, sm, job_name: str) -> Optional[dict]:
        try:
            return sm.describe_training_job(TrainingJobName=job_name)
        except ClientError as exc:  # type: ignore[misc]
            if self._is_not_found(exc):
                return None
            raise

    def _create_training_job(
        self,
        sm,
        job_name: str,
        s3_input_uri: str,
        output_s3_uri: str,
    ) -> None:
        log.info("Creating single SageMaker training job: %s", job_name)
        sm.create_training_job(
            TrainingJobName=job_name,
            RoleArn=self.role,
            AlgorithmSpecification={
                "TrainingImage": self.training_image_uri,
                "TrainingInputMode": "File",
            },
            InputDataConfig=[
                {
                    "ChannelName": "train",
                    "DataSource": {
                        "S3DataSource": {
                            "S3DataType": "S3Prefix",
                            "S3Uri": s3_input_uri,
                            "S3DataDistributionType": "FullyReplicated",
                        }
                    },
                    "ContentType": "text/csv",
                    "InputMode": "File",
                }
            ],
            OutputDataConfig={"S3OutputPath": output_s3_uri},
            ResourceConfig={
                "InstanceType": self.training_instance,
                "InstanceCount": 1,
                "VolumeSizeInGB": 30,
            },
            StoppingCondition={"MaxRuntimeInSeconds": self.max_runtime_secs},
            HyperParameters={
                "objective": "reg:squarederror",
                "num_round": "150",
                "max_depth": "6",
                "eta": "0.2",
                "subsample": "0.8",
            },
        )

    def _wait_for_training_job(self, sm, job_name: str) -> None:
        elapsed = 0
        max_seconds = self.MAX_WAIT_MINUTES * 60

        while elapsed < max_seconds:
            resp = sm.describe_training_job(TrainingJobName=job_name)
            status = resp.get("TrainingJobStatus", "Unknown")
            secondary = resp.get("SecondaryStatus", "")
            log.info("Training job %s - status: %s (%s)", job_name, status, secondary)

            if status in ("Completed", "Failed", "Stopped"):
                if status != "Completed":
                    reason = resp.get("FailureReason", "Unknown")
                    raise RuntimeError(
                        f"Training job {job_name} ended with status={status}. Reason: {reason}"
                    )
                return

            time.sleep(self.POLL_INTERVAL)
            elapsed += self.POLL_INTERVAL

        raise TimeoutError(
            f"Training job {job_name} did not complete in {self.MAX_WAIT_MINUTES} min."
        )

    def _ensure_model(self, sm, model_name: str, model_artifact_uri: str) -> str:
        try:
            desc = sm.describe_model(ModelName=model_name)
            primary = desc.get("PrimaryContainer", {})
            existing_artifact_uri = str(primary.get("ModelDataUrl", ""))
            existing_image = str(primary.get("Image", ""))

            if (
                existing_artifact_uri == model_artifact_uri
                and existing_image == self.training_image_uri
            ):
                log.info("Reusing existing SageMaker model: %s", model_name)
                return model_name

            timestamp = str(int(time.time()))
            base = model_name[: max(1, 63 - len(timestamp) - 1)]
            versioned_model_name = f"{base}-{timestamp}"
            sm.create_model(
                ModelName=versioned_model_name,
                ExecutionRoleArn=self.role,
                PrimaryContainer={
                    "Image": self.training_image_uri,
                    "ModelDataUrl": model_artifact_uri,
                },
            )
            log.info(
                "Created new versioned SageMaker model: %s (base model already existed)",
                versioned_model_name,
            )
            return versioned_model_name
        except ClientError as exc:  # type: ignore[misc]
            if not self._is_not_found(exc):
                raise

        sm.create_model(
            ModelName=model_name,
            ExecutionRoleArn=self.role,
            PrimaryContainer={
                "Image": self.training_image_uri,
                "ModelDataUrl": model_artifact_uri,
            },
        )
        log.info("Created SageMaker model: %s", model_name)
        return model_name

    def _ensure_endpoint_config(self, sm, endpoint_cfg_name: str, model_name: str) -> None:
        current_model = None
        try:
            cfg = sm.describe_endpoint_config(EndpointConfigName=endpoint_cfg_name)
            variants = cfg.get("ProductionVariants", [])
            if variants:
                current_model = variants[0].get("ModelName")
        except ClientError as exc:  # type: ignore[misc]
            if not self._is_not_found(exc):
                raise

        if current_model == model_name:
            self._latest_endpoint_cfg_name = endpoint_cfg_name
            log.info(
                "Reusing existing endpoint config %s for model %s",
                endpoint_cfg_name,
                model_name,
            )
            return

        create_name = endpoint_cfg_name
        if current_model and current_model != model_name:
            create_name = f"{endpoint_cfg_name}-{int(time.time())}"

        try:
            sm.create_endpoint_config(
                EndpointConfigName=create_name,
                ProductionVariants=[
                    {
                        "VariantName": "AllTraffic",
                        "ModelName": model_name,
                        "InstanceType": self.endpoint_instance,
                        "InitialInstanceCount": 1,
                        "InitialVariantWeight": 1.0,
                    }
                ],
            )
        except ClientError as exc:  # type: ignore[misc]
            if not self._is_invalid_instance_type_error(exc):
                raise

            fallback = self._select_endpoint_instance_fallback(exc, self.endpoint_instance)
            if not fallback or fallback == self.endpoint_instance:
                raise

            log.warning(
                "Endpoint instance type '%s' is not supported for this model container. "
                "Retrying with '%s'.",
                self.endpoint_instance,
                fallback,
            )
            self.endpoint_instance = fallback
            sm.create_endpoint_config(
                EndpointConfigName=create_name,
                ProductionVariants=[
                    {
                        "VariantName": "AllTraffic",
                        "ModelName": model_name,
                        "InstanceType": self.endpoint_instance,
                        "InitialInstanceCount": 1,
                        "InitialVariantWeight": 1.0,
                    }
                ],
            )
        self._latest_endpoint_cfg_name = create_name
        log.info("Created endpoint config: %s", create_name)

    def _ensure_endpoint(self, sm, endpoint_name: str, endpoint_cfg_name: str) -> None:
        effective_cfg_name = self._latest_endpoint_cfg_name or endpoint_cfg_name
        endpoint_desc = None

        try:
            endpoint_desc = sm.describe_endpoint(EndpointName=endpoint_name)
        except ClientError as exc:  # type: ignore[misc]
            if not self._is_not_found(exc):
                raise

        if endpoint_desc is None:
            sm.create_endpoint(
                EndpointName=endpoint_name,
                EndpointConfigName=effective_cfg_name,
            )
            log.info("Created endpoint: %s", endpoint_name)
        else:
            status = endpoint_desc.get("EndpointStatus", "Unknown")
            current_cfg = endpoint_desc.get("EndpointConfigName", "")

            if status == "InService" and current_cfg == effective_cfg_name:
                log.info("Reusing in-service endpoint %s", endpoint_name)
                return

            if current_cfg != effective_cfg_name:
                sm.update_endpoint(
                    EndpointName=endpoint_name,
                    EndpointConfigName=effective_cfg_name,
                )
                log.info("Updating endpoint %s with config %s", endpoint_name, effective_cfg_name)

        waiter = sm.get_waiter("endpoint_in_service")
        waiter.wait(EndpointName=endpoint_name, WaiterConfig={"Delay": 30, "MaxAttempts": 60})

    @staticmethod
    def _is_not_found(exc: Exception) -> bool:
        if not hasattr(exc, "response"):
            return False
        err = getattr(exc, "response", {}).get("Error", {})
        code = str(err.get("Code", "")).strip()
        message = str(err.get("Message", "")).lower()

        if code in {"ResourceNotFound", "ResourceNotFoundException"}:
            return True
        if code == "ValidationException" and "not found" in message:
            return True
        if code == "ValidationException" and "could not find" in message:
            return True
        return False

    @staticmethod
    def _is_invalid_instance_type_error(exc: Exception) -> bool:
        if not hasattr(exc, "response"):
            return False
        err = getattr(exc, "response", {}).get("Error", {})
        code = str(err.get("Code", "")).strip()
        message = str(err.get("Message", "")).lower()
        return (
            code == "ValidationException"
            and "instancetype" in message
            and "enum value set" in message
        )

    @classmethod
    def _select_endpoint_instance_fallback(cls, exc: Exception, current: str) -> str:
        err = getattr(exc, "response", {}).get("Error", {})
        message = str(err.get("Message", ""))
        allowed = set(re.findall(r"\bml\.[a-z0-9]+\.[a-z0-9]+\b", message.lower()))

        for candidate in cls.ENDPOINT_INSTANCE_FALLBACK_ORDER:
            if candidate == current:
                continue
            if not allowed or candidate in allowed:
                return candidate

        if allowed:
            for candidate in sorted(allowed):
                if candidate != current:
                    return candidate
        return current

    @staticmethod
    def _mock_run(s3_input_uri: str, target_column: str) -> Dict[str, str]:
        ep_name = "mock-endpoint-rad-ml"
        model_name = "mock-model-rad-ml"
        job_name = "mock-train-rad-ml-once"

        log.warning("SageMaker mock mode - returning fake endpoint.")
        log.info("SAGEMAKER_ENDPOINT_URL: http://localhost:5000")
        log.info("SageMaker endpoint ready -> %s", ep_name)
        return {
            "endpoint_name": ep_name,
            "endpoint_console_url": "http://localhost:5000",
            "job_name": job_name,
            "model_name": model_name,
            "model_artifact_uri": "s3://mock-bucket/mock-model.tar.gz",
        }
