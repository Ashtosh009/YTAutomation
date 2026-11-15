import os
from pathlib import Path
from typing import Optional
from core.config import SUPABASE_URL, SUPABASE_KEY, SUPABASE_BUCKET

class StorageManager:
    def __init__(self, bucket: str = SUPABASE_BUCKET):
        self.bucket = bucket
        self.supabase = None
        if SUPABASE_URL and SUPABASE_KEY:
            try:
                from supabase import create_client
                self.supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
            except Exception as e:
                print(f"[Storage] Warning: Failed to initialize Supabase client: {e}")

    def upload_file(self, local_path: str, remote_path: str, content_type: Optional[str] = None) -> str:
        """
        Uploads a local file to Supabase Storage with upsert enabled.
        Raises an error if upload fails or if Supabase is not configured.
        Returns the remote_path.
        """
        if not os.path.exists(local_path):
            raise FileNotFoundError(f"[Storage] Local file not found: {local_path}")

        if not self.supabase:
            raise RuntimeError(
                "[Storage] Cannot upload file: Supabase client is not configured. "
                "Ensure SUPABASE_URL and SUPABASE_KEY are set in environment."
            )

        # Normalize remote path
        clean_remote_path = remote_path.lstrip("/")

        # Infer content type if not provided
        if not content_type:
            if local_path.endswith(".mp4"):
                content_type = "video/mp4"
            elif local_path.endswith(".jpg") or local_path.endswith(".jpeg"):
                content_type = "image/jpeg"
            elif local_path.endswith(".png"):
                content_type = "image/png"
            else:
                content_type = "application/octet-stream"

        file_options = {
            "content-type": content_type,
            "upsert": "true"
        }

        with open(local_path, "rb") as f:
            file_bytes = f.read()

        try:
            res = self.supabase.storage.from_(self.bucket).upload(
                path=clean_remote_path,
                file=file_bytes,
                file_options=file_options
            )
            print(f"[Storage] Uploaded {local_path} -> {self.bucket}/{clean_remote_path}")
            return clean_remote_path
        except Exception as e:
            raise RuntimeError(
                f"[Storage] Failed to upload '{local_path}' to '{self.bucket}/{clean_remote_path}': {e}"
            ) from e

    def download_file(self, remote_path: str, local_path: str) -> str:
        """
        Downloads a file from Supabase Storage bucket to local_path.
        Creates parent directories if necessary.
        Raises an error if download fails or if Supabase is not configured.
        Returns the local_path.
        """
        if not self.supabase:
            raise RuntimeError(
                "[Storage] Cannot download file: Supabase client is not configured. "
                "Ensure SUPABASE_URL and SUPABASE_KEY are set in environment."
            )

        clean_remote_path = remote_path.lstrip("/")

        # If remote_path is a full URL, extract the path after bucket
        if clean_remote_path.startswith("http://") or clean_remote_path.startswith("https://"):
            pattern = f"/{self.bucket}/"
            if pattern in clean_remote_path:
                clean_remote_path = clean_remote_path.split(pattern, 1)[1].split("?")[0]

        target_path = Path(local_path)
        target_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            file_bytes = self.supabase.storage.from_(self.bucket).download(clean_remote_path)
            with open(target_path, "wb") as f:
                f.write(file_bytes)
            print(f"[Storage] Downloaded {self.bucket}/{clean_remote_path} -> {local_path} ({len(file_bytes)} bytes)")
            return str(target_path)
        except Exception as e:
            raise RuntimeError(
                f"[Storage] Failed to download '{self.bucket}/{clean_remote_path}' to '{local_path}': {e}"
            ) from e

storage = StorageManager()
