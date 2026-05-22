"""
S3 storage module for Hebrew Shorts Generator.

Two-bucket design:
  PRIVATE_BUCKET  — generated clips (presigned URLs for playback)
  PUBLIC_BUCKET   — gallery videos, actor images (public CDN URLs)

All functions are no-ops (return None/[]) when AWS_ACCESS_KEY_ID is not set,
allowing fully local development without S3 credentials.
"""

import os
import json
import logging
import time as time_module
from typing import Optional

logger = logging.getLogger(__name__)

CACHE_TTL = 300  # 5 minutes
_gallery_cache: dict = {"data": None, "ts": 0}


def _s3_client():
    """Return an authenticated boto3 S3 client, or None if credentials absent."""
    access_key = os.environ.get("AWS_ACCESS_KEY_ID")
    secret_key = os.environ.get("AWS_SECRET_ACCESS_KEY")
    if not access_key or not secret_key:
        return None
    import boto3
    from botocore.config import Config
    return boto3.client(
        "s3",
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        region_name=os.environ.get("AWS_REGION", "us-east-1"),
        config=Config(signature_version="s3v4"),
    )


def _private_bucket() -> str:
    return os.environ.get("AWS_S3_PRIVATE_BUCKET", "hebrew-shorts-private")


def _public_bucket() -> str:
    return os.environ.get("AWS_S3_PUBLIC_BUCKET", "hebrew-shorts-public")


def _cdn_url(bucket: str, key: str) -> str:
    region = os.environ.get("AWS_REGION", "us-east-1")
    return f"https://{bucket}.s3.{region}.amazonaws.com/{key}"


# ── Public API ────────────────────────────────────────────────────────


def upload_clip(job_id: str, file_path: str) -> Optional[str]:
    """
    Upload a generated clip to the private bucket.
    Returns a 2-hour presigned URL, or None if S3 unavailable.
    """
    client = _s3_client()
    if not client:
        return None

    filename = os.path.basename(file_path)
    s3_key = f"{job_id}/{filename}"
    bucket = _private_bucket()

    try:
        client.upload_file(file_path, bucket, s3_key, ExtraArgs={"ContentType": "video/mp4"})
        url = client.generate_presigned_url(
            "get_object", Params={"Bucket": bucket, "Key": s3_key}, ExpiresIn=7200
        )
        logger.info(f"Uploaded clip: {s3_key}")
        return url
    except Exception as e:
        logger.error(f"upload_clip failed: {e}")
        return None


def upload_to_gallery(video_path: str, meta: dict, video_id: str = None) -> Optional[dict]:
    """
    Upload a UGC video + metadata to the public gallery bucket.
    Returns {"video_url", "video_id", "metadata_url"} CDN URLs, or None.
    meta should contain: product_name, title, description, actor_image_path (optional).
    """
    client = _s3_client()
    if not client:
        return None

    import uuid
    import datetime

    if not video_id:
        video_id = str(uuid.uuid4())[:8]

    bucket = _public_bucket()
    results = {"video_id": video_id}

    try:
        # Upload video
        if os.path.exists(video_path):
            key = f"videos/{video_id}/video.mp4"
            client.upload_file(video_path, bucket, key, ExtraArgs={"ContentType": "video/mp4"})
            results["video_url"] = _cdn_url(bucket, key)

        # Upload actor thumbnail if provided
        actor_path = meta.pop("actor_image_path", None)
        if actor_path and os.path.exists(actor_path):
            key = f"videos/{video_id}/actor.png"
            client.upload_file(actor_path, bucket, key, ExtraArgs={"ContentType": "image/png"})
            results["actor_url"] = _cdn_url(bucket, key)
            meta["actor_url"] = results["actor_url"]

        # Write metadata JSON
        meta.update({
            "video_id": video_id,
            "video_url": results.get("video_url", ""),
            "created_at": datetime.datetime.utcnow().isoformat() + "Z",
        })
        meta_key = f"videos/{video_id}/metadata.json"
        client.put_object(
            Bucket=bucket, Key=meta_key,
            Body=json.dumps(meta, ensure_ascii=False, indent=2).encode("utf-8"),
            ContentType="application/json",
        )
        results["metadata_url"] = _cdn_url(bucket, meta_key)

        # Invalidate gallery listing cache
        _gallery_cache["data"] = None

        logger.info(f"Uploaded to gallery: {video_id}")
        return results

    except Exception as e:
        logger.error(f"upload_to_gallery failed: {e}")
        return None


def upload_actor(image_path: str, description: str = "") -> Optional[str]:
    """
    Upload an actor portrait image to the public avatars gallery.
    Returns the public CDN URL, or None if S3 unavailable.
    """
    client = _s3_client()
    if not client:
        return None

    import uuid
    import datetime

    bucket = _public_bucket()
    name, ext = os.path.splitext(os.path.basename(image_path))
    s3_key = f"avatars/{name}_{str(uuid.uuid4())[:8]}{ext}"

    try:
        if os.path.getsize(image_path) < 1000:
            return None

        client.upload_file(image_path, bucket, s3_key, ExtraArgs={"ContentType": "image/png"})
        public_url = _cdn_url(bucket, s3_key)

        if description:
            meta_key = s3_key.rsplit(".", 1)[0] + ".json"
            client.put_object(
                Bucket=bucket, Key=meta_key,
                Body=json.dumps({
                    "description": description,
                    "url": public_url,
                    "created_at": datetime.datetime.utcnow().isoformat() + "Z",
                }, ensure_ascii=False).encode("utf-8"),
                ContentType="application/json",
            )

        logger.info(f"Uploaded actor: {public_url}")
        return public_url

    except Exception as e:
        logger.error(f"upload_actor failed: {e}")
        return None


def list_gallery(limit: int = 50, force_refresh: bool = False) -> list:
    """
    List videos from the public gallery bucket, newest first.
    Cached for 5 minutes. Returns [] if S3 unavailable.
    """
    global _gallery_cache

    now = time_module.time()
    if not force_refresh and _gallery_cache["data"] is not None:
        if now - _gallery_cache["ts"] < CACHE_TTL:
            return _gallery_cache["data"][:limit]

    client = _s3_client()
    if not client:
        return []

    bucket = _public_bucket()
    videos = []

    try:
        paginator = client.get_paginator("list_objects_v2")
        meta_files = []
        for page in paginator.paginate(Bucket=bucket, Prefix="videos/"):
            for obj in page.get("Contents", []):
                if obj["Key"].endswith("/metadata.json"):
                    meta_files.append(obj)

        meta_files.sort(key=lambda x: x["LastModified"], reverse=True)

        for obj in meta_files:
            try:
                resp = client.get_object(Bucket=bucket, Key=obj["Key"])
                data = json.loads(resp["Body"].read().decode("utf-8"))
                videos.append(data)
                if limit and len(videos) >= limit:
                    break
            except Exception as e:
                logger.error(f"Error reading metadata {obj['Key']}: {e}")

    except Exception as e:
        logger.error(f"list_gallery failed: {e}")

    _gallery_cache["data"] = videos
    _gallery_cache["ts"] = now
    return videos[:limit]
