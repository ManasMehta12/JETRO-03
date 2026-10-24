"""Authorized source storage primitives; metadata scope is trusted server state."""
import os
from pathlib import Path, PurePosixPath
from typing import Optional
from .knowledge import Scope


def _authorize(owner_scope: Scope, requester_scope: Scope):
    if not isinstance(owner_scope, Scope) or owner_scope != requester_scope:
        raise PermissionError('Source is outside the authorized tenant/task/release')


def _key(value: str):
    if not isinstance(value, str) or not value or '\\' in value or '\0' in value:
        raise ValueError('Invalid source object key')
    path = PurePosixPath(value)
    if path.is_absolute() or any(part in ('.', '..', '') for part in value.split('/')):
        raise ValueError('Source keys must remain relative to their storage root')
    return value


class LocalStorage:
    def __init__(self, root: Path):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str):
        path = (self.root / _key(key)).resolve()
        try:
            path.relative_to(self.root)
        except ValueError as exc:
            raise ValueError('Source path escapes its storage root') from exc
        return path

    def read(self, key: str, *, owner_scope: Scope, requester_scope: Scope) -> bytes:
        _authorize(owner_scope, requester_scope)
        path = self._path(key)
        # Reject a final symlink even when another process replaces the path.
        descriptor = os.open(path, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0))
        with os.fdopen(descriptor, 'rb') as stream:
            return stream.read()

    def put(self, key: str, data: bytes, *, owner_scope: Scope, requester_scope: Scope):
        _authorize(owner_scope, requester_scope)
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        # Recheck after mkdir and prevent overwriting immutable source objects.
        path = self._path(key)
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, 'O_NOFOLLOW', 0), 0o600)
        with os.fdopen(descriptor, 'wb') as stream:
            stream.write(data)


class S3Storage:
    def __init__(self, bucket: str, *, endpoint_url: Optional[str] = None, client=None):
        if not bucket or '/' in bucket:
            raise ValueError('A private bucket name is required')
        self.bucket = bucket
        if client is None:
            try:
                import boto3
            except ImportError as exc:
                raise RuntimeError('S3 storage requires the optional boto3 dependency') from exc
            client = boto3.client('s3', endpoint_url=endpoint_url)
        self.client = client

    def signed_url(self, key: str, *, owner_scope: Scope, requester_scope: Scope, expires_in: int = 60):
        _authorize(owner_scope, requester_scope)
        key = _key(key)
        if not isinstance(expires_in, int) or not 1 <= expires_in <= 300:
            raise ValueError('Source URL expiry must be between 1 and 300 seconds')
        return self.client.generate_presigned_url('get_object', Params={'Bucket': self.bucket, 'Key': key}, ExpiresIn=expires_in)
