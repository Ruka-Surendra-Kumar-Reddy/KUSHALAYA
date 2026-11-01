import uuid
from abc import ABC, abstractmethod
from pathlib import Path

from app.core.config import settings


class StorageBackend(ABC):

    @abstractmethod
    def save(
        self,
        tenant_id: int,
        entity_type: str,
        entity_id: int,
        file_name: str,
        content: bytes,
        content_type: str,
    ) -> tuple[str, str]:
        """Returns (storage_key, storage_url)."""

    @abstractmethod
    def read(self, storage_key: str) -> tuple[bytes, str]:
        """Returns (content, content_type)."""

    @abstractmethod
    def delete(self, storage_key: str) -> None:
        pass

    def put(
        self,
        storage_key: str,
        content: bytes,
        content_type: str,
    ) -> tuple[str, str]:
        """Write bytes at an explicit key (e.g. global catalog images). Returns (key, url)."""
        raise NotImplementedError


def catalog_product_image_key(product_id: str, file_name: str) -> str:
    safe_product = "".join(c if c.isalnum() or c in "-_" else "_" for c in product_id)[:80]
    safe_name = Path(file_name).name.replace(" ", "_")
    return f"catalog/products/{safe_product}/{uuid.uuid4().hex}_{safe_name}"


def _object_key(
    tenant_id: int,
    entity_type: str,
    entity_id: int,
    file_name: str,
) -> str:
    safe_name = Path(file_name).name.replace(" ", "_")
    return f"{tenant_id}/{entity_type}/{entity_id}/{uuid.uuid4().hex}_{safe_name}"


class LocalStorageBackend(StorageBackend):

    def __init__(self):
        self.root = Path(settings.UPLOAD_DIR)
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, storage_key: str) -> Path:
        return self.root / storage_key

    def save(
        self,
        tenant_id: int,
        entity_type: str,
        entity_id: int,
        file_name: str,
        content: bytes,
        content_type: str,
    ) -> tuple[str, str]:
        storage_key = _object_key(tenant_id, entity_type, entity_id, file_name)
        path = self._path(storage_key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        storage_url = f"local://{storage_key}"
        return storage_key, storage_url

    def read(self, storage_key: str) -> tuple[bytes, str]:
        path = self._path(storage_key)
        if not path.exists():
            from app.core.responses import raise_not_found
            raise_not_found("File not found on disk")
        suffix = path.suffix.lower()
        mime = {
            ".pdf": "application/pdf",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".png": "image/png",
            ".webp": "image/webp",
        }.get(suffix, "application/octet-stream")
        return path.read_bytes(), mime

    def delete(self, storage_key: str) -> None:
        path = self._path(storage_key)
        if path.exists():
            path.unlink()

    def put(
        self,
        storage_key: str,
        content: bytes,
        content_type: str,
    ) -> tuple[str, str]:
        path = self._path(storage_key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        return storage_key, f"local://{storage_key}"


class AzureBlobStorageBackend(StorageBackend):
    """Azure Blob Storage — enable with STORAGE_BACKEND=azure and connection string."""

    def __init__(self):
        conn = settings.AZURE_STORAGE_CONNECTION_STRING
        if not conn:
            raise RuntimeError(
                "AZURE_STORAGE_CONNECTION_STRING is required for azure backend"
            )
        try:
            from azure.storage.blob import BlobServiceClient
        except ImportError as exc:
            raise RuntimeError(
                "Install azure-storage-blob for Azure storage backend"
            ) from exc

        self.client = BlobServiceClient.from_connection_string(conn)
        self.container = settings.AZURE_STORAGE_CONTAINER
        self._ensure_container()

    def _ensure_container(self):
        container = self.client.get_container_client(self.container)
        if not container.exists():
            container.create_container()

    def save(
        self,
        tenant_id: int,
        entity_type: str,
        entity_id: int,
        file_name: str,
        content: bytes,
        content_type: str,
    ) -> tuple[str, str]:
        storage_key = _object_key(tenant_id, entity_type, entity_id, file_name)
        blob = self.client.get_blob_client(self.container, storage_key)
        blob.upload_blob(content, overwrite=True, content_type=content_type)
        storage_url = blob.url
        return storage_key, storage_url

    def read(self, storage_key: str) -> tuple[bytes, str]:
        blob = self.client.get_blob_client(self.container, storage_key)
        props = blob.get_blob_properties()
        content_type = props.content_settings.content_type or "application/octet-stream"
        return blob.download_blob().readall(), content_type

    def delete(self, storage_key: str) -> None:
        blob = self.client.get_blob_client(self.container, storage_key)
        blob.delete_blob()

    def put(
        self,
        storage_key: str,
        content: bytes,
        content_type: str,
    ) -> tuple[str, str]:
        blob = self.client.get_blob_client(self.container, storage_key)
        blob.upload_blob(content, overwrite=True, content_type=content_type)
        return storage_key, blob.url


class S3CompatibleStorageBackend(StorageBackend):
    """S3-compatible storage for Cloudflare R2, Backblaze B2, or AWS S3.

    Enable with STORAGE_BACKEND=s3 or STORAGE_BACKEND=r2 and set:
      S3_ENDPOINT_URL, S3_BUCKET, S3_ACCESS_KEY_ID, S3_SECRET_ACCESS_KEY
    Buckets should stay private; the app serves images through authenticated routes.
    """

    def __init__(self):
        endpoint = (settings.S3_ENDPOINT_URL or "").strip()
        bucket = (settings.S3_BUCKET or "").strip()
        access_key = (settings.S3_ACCESS_KEY_ID or "").strip()
        secret_key = (settings.S3_SECRET_ACCESS_KEY or "").strip()
        if not endpoint or not bucket or not access_key or not secret_key:
            raise RuntimeError(
                "S3_ENDPOINT_URL, S3_BUCKET, S3_ACCESS_KEY_ID, and "
                "S3_SECRET_ACCESS_KEY are required for s3/r2 storage"
            )
        try:
            import boto3
            from botocore.client import Config
        except ImportError as exc:
            raise RuntimeError(
                "Install boto3 for S3/R2 storage backend (pip install boto3)"
            ) from exc

        self.bucket = bucket
        self.public_base = (settings.S3_PUBLIC_BASE_URL or "").strip().rstrip("/")
        region = (settings.S3_REGION or "auto").strip() or "auto"
        self.client = boto3.client(
            "s3",
            endpoint_url=endpoint,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name=region,
            config=Config(signature_version="s3v4"),
        )
        self._ensure_bucket()

    def _ensure_bucket(self) -> None:
        try:
            self.client.head_bucket(Bucket=self.bucket)
        except Exception:
            # R2 often creates buckets in the dashboard; create is best-effort.
            try:
                self.client.create_bucket(Bucket=self.bucket)
            except Exception:
                pass

    def save(
        self,
        tenant_id: int,
        entity_type: str,
        entity_id: int,
        file_name: str,
        content: bytes,
        content_type: str,
    ) -> tuple[str, str]:
        storage_key = _object_key(tenant_id, entity_type, entity_id, file_name)
        self.client.put_object(
            Bucket=self.bucket,
            Key=storage_key,
            Body=content,
            ContentType=content_type or "application/octet-stream",
        )
        if self.public_base:
            storage_url = f"{self.public_base}/{storage_key}"
        else:
            storage_url = f"s3://{self.bucket}/{storage_key}"
        return storage_key, storage_url

    def read(self, storage_key: str) -> tuple[bytes, str]:
        try:
            obj = self.client.get_object(Bucket=self.bucket, Key=storage_key)
        except Exception:
            from app.core.responses import raise_not_found
            raise_not_found("File not found in object storage")
        body = obj["Body"].read()
        content_type = obj.get("ContentType") or "application/octet-stream"
        return body, content_type

    def delete(self, storage_key: str) -> None:
        try:
            self.client.delete_object(Bucket=self.bucket, Key=storage_key)
        except Exception:
            pass

    def put(
        self,
        storage_key: str,
        content: bytes,
        content_type: str,
    ) -> tuple[str, str]:
        self.client.put_object(
            Bucket=self.bucket,
            Key=storage_key,
            Body=content,
            ContentType=content_type or "application/octet-stream",
        )
        if self.public_base:
            storage_url = f"{self.public_base}/{storage_key}"
        else:
            storage_url = f"s3://{self.bucket}/{storage_key}"
        return storage_key, storage_url


def get_storage() -> StorageBackend:
    backend = (settings.STORAGE_BACKEND or "local").strip().lower()
    if backend == "azure":
        return AzureBlobStorageBackend()
    if backend in ("s3", "r2", "b2"):
        return S3CompatibleStorageBackend()
    return LocalStorageBackend()
