#!/usr/bin/env python3
import sys
import os
import argparse
import datetime
from pathlib import Path
from core.config import OUTPUT_DIR
from core.db import db
from core.storage import storage
from core.llm import generate_script_with_gemini
from core.renderer import video_renderer
from core.youtube import youtube_uploader

def cmd_generate(topic: str, auto_approve: bool = False, dry_run: bool = False):
    """Generates an animated short from idea/topic end-to-end and uploads to Supabase Storage."""
    print(f"\n=======================================================")
    print(f"🎬 Generating Animated Short: '{topic}' (dry_run={dry_run})")
    print(f"=======================================================\n")

    # Step 1: Script & Metadata
    print("[1/4] Writing script & scene storyboard with Gemini...")
    script_data = generate_script_with_gemini(topic)
    title = script_data.get("title", f"The Truth About {topic}")
    desc = script_data.get("description", "")
    tags = script_data.get("tags", ["shorts", "animation", "comedy"])
    print(f"      Title: {title}")
    print(f"      Scenes: {len(script_data.get('scenes', []))}")

    # Step 2: Database Record (Initial)
    idea_id = db.add_idea(topic=topic, niche="storytime", status="processed")
    video_id = db.create_video_record(
        idea_id=idea_id,
        title=title,
        description=desc,
        tags=tags,
        script_data=script_data
    )

    # Step 3: Render Video & Thumbnail
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    output_filename = f"short_{video_id}_{timestamp}.mp4"
    output_filepath = str(OUTPUT_DIR / output_filename)
    output_thumbpath = str(OUTPUT_DIR / f"short_{video_id}_{timestamp}_thumb.jpg")

    print("\n[2/4] Rendering stick figure animation...")
    try:
        video_renderer.render_short(script_data, output_filepath)
        print(f"      Video rendered: {output_filepath}")

        print("\n[3/4] Generating video thumbnail...")
        video_renderer.generate_thumbnail(script_data, output_filepath, output_thumbpath)
        print(f"      Thumbnail rendered: {output_thumbpath}")

        # Step 4: Upload to Supabase Storage
        remote_video_path = f"videos/{video_id}/final.mp4"
        remote_thumb_path = f"videos/{video_id}/thumb.jpg"

        print("\n[4/4] Uploading assets to Supabase Storage bucket...")
        storage_video_key = storage.upload_file(
            local_path=output_filepath,
            remote_path=remote_video_path,
            content_type="video/mp4"
        )
        storage_thumb_key = storage.upload_file(
            local_path=output_thumbpath,
            remote_path=remote_thumb_path,
            content_type="image/jpeg"
        )
        print(f"      Storage video path: {storage_video_key}")
        print(f"      Storage thumb path: {storage_thumb_key}")

        # Step 5: Persist storage paths & status on the videos row.
        # update_video_status raises DatabaseUpdateError if the row is not updated.
        new_status = "approved_for_upload" if auto_approve else "ready_for_review"
        db.update_video_status(
            video_id=video_id,
            status=new_status,
            video_path=output_filepath,
            storage_path=storage_video_key,
            thumbnail_path=storage_thumb_key
        )
        print(f"      DB row #{video_id} updated: storage_path={storage_video_key}, thumbnail_path={storage_thumb_key}")

        print(f"\n✅ Video #{video_id} successfully processed!")
        print(f"   Status: '{new_status}'")
        print(f"   Storage Path: {storage_video_key}")
        print(f"   Thumbnail Path: {storage_thumb_key}\n")

        if not auto_approve:
            print(f"   Review the video in Vercel panel or run:")
            print(f"   python3 run_pipeline.py approve --approve {video_id}\n")

        return video_id, output_filepath, storage_video_key

    except Exception as e:
        print(f"❌ Error during generation/upload: {e}", file=sys.stderr)
        try:
            db.update_video_status(video_id=video_id, status="failed", error_log=str(e))
        except Exception as mark_err:
            print(f"❌ Also failed to mark video #{video_id} as failed: {mark_err}", file=sys.stderr)
        raise

def cmd_list_review_queue():
    """Lists videos awaiting review."""
    print("\n=======================================================")
    print("📋 Review Queue (Pending Approval)")
    print("=======================================================\n")

    job = db.get_next_job(status="ready_for_review")
    if not job:
        print("No videos currently waiting for review.")
        return

    print(f"Video ID:     {job['id']}")
    print(f"Title:        {job['title']}")
    print(f"Status:       {job.get('status')}")
    print(f"Storage Path: {job.get('storage_path')}")
    print(f"Local Path:   {job.get('video_path')}")
    print(f"Tags:         {job.get('tags')}")
    print("\nTo approve this video for scheduled upload, run:")
    print(f"python3 run_pipeline.py approve --approve {job['id']}\n")

def cmd_approve(video_id: int, publish_at: str = None):
    """Approves a video for upload."""
    db.update_video_status(video_id=video_id, status="approved_for_upload")
    print(f"✅ Video #{video_id} approved for upload!")

def cmd_publish(dry_run: bool = False):
    """
    Uploads the next approved video to YouTube.
    If local file is missing, downloads from Supabase Storage first.
    """
    job = db.get_next_job(status="approved_for_upload")
    if not job:
        print("[Upload] No approved videos ready for publishing.")
        return None

    video_id = job["id"]
    title = job["title"]
    desc = job.get("description", "")
    tags = job.get("tags", "").split(",") if job.get("tags") else []
    publish_at = job.get("scheduled_publish_at")

    print(f"\n[Upload] Preparing Video #{video_id}: '{title}'...")

    video_path = job.get("video_path")

    # If local file is missing, download from Supabase Storage
    if not video_path or not os.path.exists(video_path):
        remote_path = job.get("storage_path")
        if not remote_path or remote_path.startswith("/") or not remote_path.startswith("videos/"):
            # Fallback to standard storage key pattern
            remote_path = f"videos/{video_id}/final.mp4"

        local_download_path = str(OUTPUT_DIR / f"downloaded_video_{video_id}.mp4")
        print(f"[Upload] Local video file missing. Downloading from Supabase Storage ({remote_path})...")
        try:
            video_path = storage.download_file(remote_path, local_download_path)
            print(f"[Upload] Successfully downloaded to {video_path}")
        except Exception as e:
            err = f"Failed to download video #{video_id} from storage: {e}"
            print(f"[Upload] Error: {err}")
            db.update_video_status(video_id, status="failed", error_log=err)
            raise e

    print(f"[Upload] Publishing Video #{video_id} to YouTube (dry_run={dry_run})...")

    try:
        res = youtube_uploader.upload_short(
            video_file_path=video_path,
            title=title,
            description=desc,
            tags=tags,
            publish_at=publish_at,
            dry_run=dry_run
        )
        db.update_video_status(
            video_id=video_id,
            status="published",
            youtube_id=res["id"]
        )
        print(f"🎉 Successfully published to YouTube! Video ID: {res['id']}, URL: {res['url']}\n")
        return res
    except Exception as e:
        print(f"❌ YouTube upload failed: {e}")
        db.update_video_status(video_id=video_id, status="failed", error_log=str(e))
        raise e

# Alias for compatibility with prompt's naming
cmd_publish_next = cmd_publish

def main():
    parser = argparse.ArgumentParser(description="Automated Stick Figure Shorts Generator & Publisher")
    # Support both positional argument or --mode flag
    parser.add_argument(
        "action",
        nargs="?",
        choices=["generate", "review", "approve", "publish", "batch"],
        help="Pipeline action to run"
    )
    parser.add_argument(
        "--mode",
        choices=["generate", "review", "approve", "publish", "batch"],
        help="Alternative flag syntax for action"
    )
    parser.add_argument("--topic", type=str, default="Trying to wake up at 5 AM", help="Topic for the short")
    parser.add_argument("--auto-approve", action="store_true", help="Skip review queue and approve immediately")
    parser.add_argument("--approve", type=int, help="Approve a specific video ID")
    parser.add_argument("--publish-time", type=str, help="ISO timestamp for scheduled publishing (e.g. 2026-11-16T14:00:00Z)")
    parser.add_argument("--dry-run", action="store_true", help="Dry run mode (skips live YouTube upload)")

    args = parser.parse_args()

    # Determine action (positional takes precedence, then --mode, default to generate)
    action = args.action or args.mode

    if args.approve:
        cmd_approve(args.approve, args.publish_time)
        return

    if action == "generate" or not action:
        cmd_generate(args.topic, auto_approve=args.auto_approve, dry_run=args.dry_run)
    elif action == "review":
        cmd_list_review_queue()
    elif action == "publish":
        cmd_publish(dry_run=args.dry_run)
    elif action == "approve":
        if args.approve:
            cmd_approve(args.approve, args.publish_time)
        else:
            print("Error: Specify video ID with --approve <id>")
    elif action == "batch":
        topics = [
            "Going to the gym on January 1st",
            "When someone says 'we need to talk'",
            "Trying to sleep before an early flight"
        ]
        for t in topics:
            cmd_generate(t, auto_approve=args.auto_approve, dry_run=args.dry_run)

if __name__ == "__main__":
    main()
