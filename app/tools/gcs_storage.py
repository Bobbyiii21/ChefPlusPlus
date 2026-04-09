"""
Upload (and list / delete) files in a Google Cloud Storage bucket.

The target bucket is read from the ``GCS_BUCKET`` environment variable
(via :mod:`tools.env_config`).

Usage::

    from tools.gcs_storage import upload_file, list_files, delete_file

    url = upload_file("/tmp/menu.pdf")
    for blob in list_files(prefix="uploads/"):
        print(blob)
    delete_file("uploads/menu.pdf")
"""

from __future__ import annotations

import logging
import os
from typing import Optional, Sequence

from google.cloud import storage

from tools.env_config import gcs_bucket, google_cloud_project

logger = logging.getLogger(__name__)

_client: Optional[storage.Client] = None


def _get_client() -> storage.Client:
    global _client
    if _client is None:
        _client = storage.Client(project=google_cloud_project())
    return _client


def _get_bucket() -> storage.Bucket:
    return _get_client().bucket(gcs_bucket())


def upload_file(
    local_path: str,
    *,
    destination_name: Optional[str] = None,
    content_type: Optional[str] = None,
) -> str:
    """
    Upload a local file to the GCS bucket.

    Parameters
    ----------
    local_path:
        Path to the file on the local filesystem.
    destination_name:
        Object name inside the bucket.  Defaults to the basename of
        *local_path*.
    content_type:
        MIME type (e.g. ``"application/pdf"``).  GCS will auto-detect
        if omitted.

    Returns
    -------
    str
        The ``gs://`` URI of the uploaded object.
    """
    if not local_path or not os.path.isfile(local_path):
        raise FileNotFoundError(f"Local file not found: {local_path}")

    blob_name = destination_name or os.path.basename(local_path)
    bucket = _get_bucket()
    blob = bucket.blob(blob_name)

    kwargs = {}
    if content_type:
        kwargs["content_type"] = content_type

    blob.upload_from_filename(local_path, **kwargs)
    uri = f"gs://{bucket.name}/{blob_name}"
    logger.info("Uploaded %s → %s", local_path, uri)
    return uri


def upload_from_string(
    data: bytes | str,
    destination_name: str,
    *,
    content_type: str = "application/octet-stream",
) -> str:
    """
    Upload raw bytes or a string directly to the GCS bucket.

    Returns the ``gs://`` URI of the uploaded object.
    """
    if not destination_name or not destination_name.strip():
        raise ValueError("destination_name is required.")

    bucket = _get_bucket()
    blob = bucket.blob(destination_name.strip())
    blob.upload_from_string(data, content_type=content_type)
    uri = f"gs://{bucket.name}/{destination_name.strip()}"
    logger.info("Uploaded string/bytes → %s", uri)
    return uri


def list_files(prefix: Optional[str] = None) -> list[str]:
    """
    List object names in the bucket, optionally filtered by *prefix*.

    Returns a list of blob name strings.
    """
    bucket = _get_bucket()
    blobs = bucket.list_blobs(prefix=prefix)
    return [b.name for b in blobs]


def delete_file(blob_name: str) -> None:
    """Delete a single object from the bucket by name."""
    if not blob_name or not blob_name.strip():
        raise ValueError("blob_name is required.")

    bucket = _get_bucket()
    bucket.blob(blob_name.strip()).delete()
    logger.info("Deleted gs://%s/%s", bucket.name, blob_name.strip())
