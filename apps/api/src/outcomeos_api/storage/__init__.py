"""Tenant-safe object storage adapters."""

from outcomeos_api.storage.objects import ObjectHead, ObjectStorage, S3ObjectStorage

__all__ = ["ObjectHead", "ObjectStorage", "S3ObjectStorage"]
