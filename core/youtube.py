import os
import json
import base64
from typing import Dict, Any, List, Optional
from core.config import YOUTUBE_CLIENT_SECRETS_FILE, YOUTUBE_TOKEN_FILE, YOUTUBE_TOKEN_BASE64, YOUTUBE_DEFAULT_PRIVACY

SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube"
]

class YouTubeUploader:
    def __init__(self):
        self.client_secrets_file = YOUTUBE_CLIENT_SECRETS_FILE
        self.token_file = YOUTUBE_TOKEN_FILE

    def get_authenticated_service(self):
        """Authenticates with YouTube API using saved credentials or env var."""
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from google.auth.transport.requests import Request
        from googleapiclient.discovery import build

        creds = None

        # Check if token provided via environment variable (useful for GitHub Actions secrets)
        if YOUTUBE_TOKEN_BASE64:
            try:
                decoded = base64.b64decode(YOUTUBE_TOKEN_BASE64).decode("utf-8")
                token_data = json.loads(decoded)
                creds = Credentials.from_authorized_user_info(token_data, SCOPES)
            except Exception as e:
                print(f"[YouTube] Could not load credentials from YOUTUBE_TOKEN_BASE64: {e}")

        # Check local token.json
        if not creds and os.path.exists(self.token_file):
            creds = Credentials.from_authorized_user_file(self.token_file, SCOPES)

        # Refresh or prompt login if local
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                except Exception as e:
                    raise RuntimeError(
                        f"[YouTube] Token refresh failed ({type(e).__name__}). If the OAuth app is in "
                        "Testing mode the refresh token expires after 7 days: re-run the local sign-in "
                        "and update the YOUTUBE_TOKEN_BASE64 secret."
                    ) from e
                with open(self.token_file, "w") as token:
                    token.write(creds.to_json())
            elif os.getenv("CI"):
                # No browser on a CI runner: run_local_server would hang until the job timeout.
                raise RuntimeError(
                    "[YouTube] No valid credentials in CI. Set the YOUTUBE_TOKEN_BASE64 secret "
                    "(base64 of a token.json that has a refresh_token)."
                )
            else:
                if not os.path.exists(self.client_secrets_file):
                    raise FileNotFoundError(
                        f"Client secret file '{self.client_secrets_file}' not found. "
                        "Download it from Google Cloud Console > APIs & Services > Credentials."
                    )
                flow = InstalledAppFlow.from_client_secrets_file(self.client_secrets_file, SCOPES)
                creds = flow.run_local_server(port=0)
                with open(self.token_file, "w") as token:
                    token.write(creds.to_json())

        return build("youtube", "v3", credentials=creds)

    def upload_short(
        self,
        video_file_path: str,
        title: str,
        description: str,
        tags: List[str],
        publish_at: Optional[str] = None,
        privacy_status: Optional[str] = None,
        dry_run: bool = False
    ) -> Dict[str, Any]:
        """Uploads a vertical video to YouTube as a Short."""
        # Unscheduled uploads previously defaulted to "private", so videos the
        # cron "published" never became visible. Default now comes from env.
        privacy_status = privacy_status or YOUTUBE_DEFAULT_PRIVACY
        if dry_run:
            if not os.path.exists(video_file_path):
                raise FileNotFoundError(f"Video file not found at {video_file_path}")
            print(
                f"[YouTube DRY-RUN] Would upload {video_file_path} ({os.path.getsize(video_file_path)} bytes): "
                f"title={title!r}, tags={tags}, publishAt={publish_at}, "
                f"privacy={'private (scheduled)' if publish_at else privacy_status}"
            )
            return {
                "id": "dry_run_simulated_id",
                "url": "https://youtube.com/shorts/dry_run_simulated_id",
                "response": {"id": "dry_run_simulated_id"}
            }

        from googleapiclient.http import MediaFileUpload

        if not os.path.exists(video_file_path):
            raise FileNotFoundError(f"Video file not found at {video_file_path}")

        youtube = self.get_authenticated_service()

        # YouTube rules: if scheduled (publishAt set), privacyStatus must be 'private'
        status_body: Dict[str, Any] = {
            "selfDeclaredMadeForKids": False
        }
        if publish_at:
            status_body["publishAt"] = publish_at
            status_body["privacyStatus"] = "private"
        else:
            status_body["privacyStatus"] = privacy_status

        body = {
            "snippet": {
                "title": title[:100],
                "description": description if "#shorts" in description.lower() else description + "\n\n#Shorts",
                "tags": tags,
                "categoryId": "23" # Comedy category
            },
            "status": status_body
        }

        media = MediaFileUpload(
            video_file_path,
            chunksize=-1,
            resumable=True,
            mimetype="video/mp4"
        )

        print(f"[YouTube] Uploading {video_file_path} to YouTube...")
        request = youtube.videos().insert(
            part="snippet,status",
            body=body,
            media_body=media
        )

        response = None
        while response is None:
            status, response = request.next_chunk()
            if status:
                print(f"[YouTube] Upload progress: {int(status.progress() * 100)}%")

        video_id = response.get("id")
        short_url = f"https://youtube.com/shorts/{video_id}"
        print(f"[YouTube] Upload complete! Video URL: {short_url}")

        return {
            "id": video_id,
            "url": short_url,
            "response": response
        }

youtube_uploader = YouTubeUploader()
