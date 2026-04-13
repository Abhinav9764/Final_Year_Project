"""
backend/chat_history_db.py
===========================
DynamoDB-backed chat history store with an in-memory fallback.

Each job record is keyed by:
- user_id (partition key)
- job_id  (sort key)

This keeps the backend on a single AWS-friendly NoSQL stack instead of
depending on a separate MongoDB service.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

logger = logging.getLogger(__name__)

try:
    import boto3
    from boto3.dynamodb.conditions import Key
    from botocore.config import Config as BotoConfig
    from botocore.exceptions import BotoCoreError, ClientError, NoCredentialsError

    _BOTO3_AVAILABLE = True
except ImportError:  # pragma: no cover - environment-specific
    boto3 = None  # type: ignore[assignment]
    Key = None  # type: ignore[assignment]
    BotoConfig = None  # type: ignore[assignment]
    BotoCoreError = ClientError = NoCredentialsError = Exception  # type: ignore[misc,assignment]
    _BOTO3_AVAILABLE = False


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _iso_now() -> str:
    return _utcnow().isoformat()


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: _json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(v) for v in value]
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Decimal):
        return int(value) if value == int(value) else float(value)
    return value


class _MemoryStore:
    """Simple in-memory fallback when DynamoDB is unavailable."""

    def __init__(self):
        self._docs: dict[tuple[str, str], dict[str, Any]] = {}

    def upsert_job(self, user_id: int, job_id: str, **fields) -> None:
        key = (str(user_id), job_id)
        doc = self._docs.get(
            key,
            {
                "user_id": str(user_id),
                "job_id": job_id,
                "created_at": _iso_now(),
                "updated_at_epoch": 0,
            },
        )
        doc.update(_json_safe(fields))
        doc["updated_at"] = _iso_now()
        doc["updated_at_epoch"] = int(_utcnow().timestamp())
        self._docs[key] = doc

    def get_history(self, user_id: int, limit: int = 50) -> list[dict[str, Any]]:
        docs = [d for d in self._docs.values() if d["user_id"] == str(user_id)]
        docs.sort(key=lambda d: d.get("updated_at_epoch", 0), reverse=True)
        return [dict(d) for d in docs[:limit]]

    def get_job(self, user_id: int, job_id: str) -> dict[str, Any] | None:
        doc = self._docs.get((str(user_id), job_id))
        return dict(doc) if doc else None

    def delete_job(self, user_id: int, job_id: str) -> bool:
        return self._docs.pop((str(user_id), job_id), None) is not None

    def delete_all(self, user_id: int) -> int:
        keys = [key for key in self._docs if key[0] == str(user_id)]
        for key in keys:
            del self._docs[key]
        return len(keys)


class ChatHistoryDB:
    """DynamoDB-backed chat history with automatic in-memory fallback."""

    def __init__(self, config: dict):
        nosql_cfg = config.get("nosql", {})
        aws_cfg = config.get("aws", {})
        self._provider = str(nosql_cfg.get("provider", "dynamodb")).lower()
        self._region = nosql_cfg.get("region") or aws_cfg.get("region", "us-east-1")
        self._table_name = nosql_cfg.get("table_name", "radml-chat-history")
        self._endpoint_url = nosql_cfg.get("endpoint_url") or None
        self._auto_create = bool(nosql_cfg.get("auto_create_table", True))
        self._access_key = aws_cfg.get("access_key_id", "")
        self._secret_key = aws_cfg.get("secret_access_key", "")
        self._table = None
        self._fallback = _MemoryStore()
        self._use_nosql = False
        self._connect()

    def _resource(self):
        if not _BOTO3_AVAILABLE:
            raise RuntimeError("boto3 is not installed")
        # Avoid slow EC2 metadata probing on local machines when AWS creds are absent.
        os.environ.setdefault("AWS_EC2_METADATA_DISABLED", "true")
        kwargs: dict[str, Any] = {"region_name": self._region}
        if self._endpoint_url:
            kwargs["endpoint_url"] = self._endpoint_url
        if self._access_key and self._secret_key:
            kwargs["aws_access_key_id"] = self._access_key
            kwargs["aws_secret_access_key"] = self._secret_key
        if BotoConfig is not None:
            kwargs["config"] = BotoConfig(
                connect_timeout=2,
                read_timeout=2,
                retries={"max_attempts": 1, "mode": "standard"},
            )
        return boto3.resource("dynamodb", **kwargs)

    def _connect(self) -> None:
        if self._provider != "dynamodb":
            logger.warning(
                "Unsupported nosql.provider '%s' - using in-memory history store.",
                self._provider,
            )
            return
        if not _BOTO3_AVAILABLE:
            logger.warning("boto3 not installed - using in-memory history store.")
            return
        if not (self._access_key and self._secret_key) and not self._endpoint_url:
            logger.warning(
                "AWS credentials not configured for DynamoDB - using in-memory history store."
            )
            return

        try:
            resource = self._resource()
            table = resource.Table(self._table_name)
            table.load()
            self._table = table
            self._use_nosql = True
            logger.info("DynamoDB connected: table=%s region=%s", self._table_name, self._region)
        except ClientError as exc:
            error_code = exc.response.get("Error", {}).get("Code", "")
            if error_code == "ResourceNotFoundException" and self._auto_create:
                self._create_table()
                return
            logger.warning("DynamoDB unavailable (%s) - using in-memory history store.", exc)
        except Exception as exc:
            logger.warning("NoSQL history unavailable (%s) - using in-memory history store.", exc)

    def _create_table(self) -> None:
        try:
            resource = self._resource()
            table = resource.create_table(
                TableName=self._table_name,
                KeySchema=[
                    {"AttributeName": "user_id", "KeyType": "HASH"},
                    {"AttributeName": "job_id", "KeyType": "RANGE"},
                ],
                AttributeDefinitions=[
                    {"AttributeName": "user_id", "AttributeType": "S"},
                    {"AttributeName": "job_id", "AttributeType": "S"},
                ],
                BillingMode="PAY_PER_REQUEST",
            )
            table.wait_until_exists()
            self._table = resource.Table(self._table_name)
            self._use_nosql = True
            logger.info("Created DynamoDB table: %s", self._table_name)
        except Exception as exc:
            logger.warning("Failed to create DynamoDB table (%s) - using in-memory history store.", exc)

    def upsert_job(self, user_id: int, job_id: str, **fields) -> None:
        payload = _json_safe(fields)
        if not self._use_nosql:
            self._fallback.upsert_job(user_id, job_id, **payload)
            return

        existing = self.get_job(user_id, job_id) or {}
        item = {
            **existing,
            **payload,
            "user_id": str(user_id),
            "job_id": job_id,
            "created_at": existing.get("created_at", _iso_now()),
            "updated_at": _iso_now(),
            "updated_at_epoch": int(_utcnow().timestamp()),
        }
        self._table.put_item(Item=item)

    def get_history(self, user_id: int, limit: int = 50) -> list[dict[str, Any]]:
        if not self._use_nosql:
            return self._fallback.get_history(user_id, limit)

        try:
            response = self._table.query(
                KeyConditionExpression=Key("user_id").eq(str(user_id)),
            )
            items = response.get("Items", [])
            items = [_json_safe({k: v for k, v in item.items() if k != "logs"}) for item in items]
            items.sort(key=lambda item: item.get("updated_at_epoch", 0), reverse=True)
            return items[:limit]
        except Exception as exc:
            logger.warning("DynamoDB history query failed (%s) - falling back to memory.", exc)
            return self._fallback.get_history(user_id, limit)

    def get_job(self, user_id: int, job_id: str) -> dict[str, Any] | None:
        if not self._use_nosql:
            return self._fallback.get_job(user_id, job_id)

        try:
            response = self._table.get_item(Key={"user_id": str(user_id), "job_id": job_id})
            item = response.get("Item")
            return _json_safe(item) if item else None
        except Exception as exc:
            logger.warning("DynamoDB get_job failed (%s) - falling back to memory.", exc)
            return self._fallback.get_job(user_id, job_id)

    def delete_job(self, user_id: int, job_id: str) -> bool:
        if not self._use_nosql:
            return self._fallback.delete_job(user_id, job_id)

        try:
            self._table.delete_item(Key={"user_id": str(user_id), "job_id": job_id})
            return True
        except Exception as exc:
            logger.warning("DynamoDB delete_job failed (%s) - falling back to memory.", exc)
            return self._fallback.delete_job(user_id, job_id)

    def delete_all(self, user_id: int) -> int:
        if not self._use_nosql:
            return self._fallback.delete_all(user_id)

        try:
            items = self.get_history(user_id, limit=1000)
            if not items:
                return 0
            with self._table.batch_writer() as batch:
                for item in items:
                    batch.delete_item(Key={"user_id": str(user_id), "job_id": item["job_id"]})
            return len(items)
        except Exception as exc:
            logger.warning("DynamoDB delete_all failed (%s) - falling back to memory.", exc)
            return self._fallback.delete_all(user_id)
