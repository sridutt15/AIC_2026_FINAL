"""Thin wrapper over Supabase Storage (Phase 16).

All raw uploaded files and canonical dataset CSVs live in a single private
bucket, organized per user: {user_id}/{source_id}/{filename}. The wrapper is
deliberately minimal — upload/download/delete — because the access decision
is always made by the database ownership check in the API layer BEFORE any
storage call (the service-role key can technically read any path, so the
user-prefixed layout is a safety net, never the gate).

Derived canonical CSVs are gzipped on upload (compress=True) because large
joins easily exceed Supabase's per-object upload cap; download transparently
decompresses any gzip payload (magic-byte check), so every caller sees the
original bytes either way.
"""

import functools
import gzip

from app.config import settings

# Supabase Storage simple-upload limit per object.
UPLOAD_LIMIT_BYTES = 50 * 1024 * 1024

_GZIP_MAGIC = b"\x1f\x8b"


class StorageTooLarge(ValueError):
    """Raised when an object exceeds Supabase Storage's upload cap."""


@functools.lru_cache(maxsize=1)
def _client():
    if not settings.SUPABASE_URL or not settings.SUPABASE_SERVICE_KEY:
        raise RuntimeError(
            "SUPABASE_URL / SUPABASE_SERVICE_KEY must be set in backend/.env "
            "(Project Settings -> API in the Supabase dashboard)."
        )
    from supabase import create_client

    return create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_KEY)


def upload_file(path: str, file_bytes: bytes, content_type: str, compress: bool = False) -> None:
    """Upload bytes to {bucket}/{path}, overwriting if the path exists.

    compress=True gzips the payload first (for server-derived artifacts that
    can exceed the upload cap); download_file reverses this transparently.
    """
    if compress:
        file_bytes = gzip.compress(file_bytes)
        content_type = "application/gzip"
    if len(file_bytes) > UPLOAD_LIMIT_BYTES:
        raise StorageTooLarge(
            f"Storage object is {len(file_bytes) / 1e6:.1f} MB; Supabase Storage "
            f"allows at most 50 MB per object. Reduce the dataset size and retry."
        )
    _client().storage.from_(settings.SUPABASE_STORAGE_BUCKET).upload(
        path=path,
        file=file_bytes,
        file_options={"content-type": content_type, "upsert": "true"},
    )


def download_file(path: str) -> bytes:
    """Fetch the file's bytes; gzip payloads are decompressed transparently."""
    data = _client().storage.from_(settings.SUPABASE_STORAGE_BUCKET).download(path)
    if data[:2] == _GZIP_MAGIC:
        data = gzip.decompress(data)
    return data


def delete_file(path: str) -> None:
    """Remove the file (best-effort: missing files are fine)."""
    _client().storage.from_(settings.SUPABASE_STORAGE_BUCKET).remove([path])
