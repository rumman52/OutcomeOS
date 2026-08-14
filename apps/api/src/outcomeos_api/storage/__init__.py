"""Tenant-safe object storage adapters."""

from outcomeos_api.storage.objects import (
    ObjectHead,
    ObjectPage,
    ObjectStorage,
    PaginatedObjectStorage,
    S3ObjectStorage,
)

__all__ = [
    "ObjectHead",
    "ObjectPage",
    "ObjectStorage",
    "PaginatedObjectStorage",
    "S3ObjectStorage",
]
