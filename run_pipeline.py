#!/usr/bin/env python3
import sys
import os
import argparse
import datetime
from pathlib import Path
from core.config import OUTPUT_DIR
from core.db import db
from core.llm import generate_script_with_gemini
from core.renderer import video_renderer
from core.youtube import youtube_uploader

def cmd_generate(topic: str, auto_approve: bool = False):
    """Generates an animated short from idea/topic end-to-end."""
    print(f"\n=======================================================")
    print(f"🎬 Generating Animated Short: '{topic}'")
    print(f"=======================================================\n")

    # Step 1: Script & Metadata
    print("[1/4] Writing script & scene storyboard with Gemini...")
    script_data = generate_script_with_gemini(topic)
    title = script_data.get("title", f"The Truth About {topic}")
    desc = script_data.get("description", "")
    tags = script_data.get("tags", ["shorts", "animation", "comedy"])
    print(f"      Title: {title}")
    print(f"      Scenes: {len(script_data.get('scenes', []))}")

    # Step 2: Database Record
    idea_id = db.add_idea(topic=topic, niche="storytime", status="processed")
    video_id = db.create_video_record(
        idea_id=idea_id,
        title=title,
        description=desc,
        tags=tags,
        script_data=script_data
    )

    # Step 3: Render Video
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    output_filename = f"short_{video_id}_{timestamp}.mp4"
    output_filepath = str(OUTPUT_DIR / output_filename)

    print("\n[2/4] Rendering stick figure animation & captions...")
    try:
        video_renderer.render_short(script_data, output_filepath)
        
        # Step 4: Status Update (Morning Review Queue)
        new_status = "approved_for_upload" if auto_approve else "ready_for_review"
        db.update_video_status(video_id=video_id, status=new_status, video_path=output_filepath)

        print(f"\n✅ Video successfully rendered: {output_filepath}")
        if not auto_approve:
            print(f"📋 Status set to 'ready_for_review' (Video ID: {video_id}).")
            print(f"   Review the video in output/ and run:")
            print(f"   python run_pipeline.py --approve {video_id}\n")
        else:
            print(f"🚀 Status set to 'approved_for_upload'.\n")

        return video_id, output_filepath

    except Exception as e:
        print(f"❌ Error during rendering: {e}")
        db.update_video_status(video_id=video_id, status="failed", error_log=str(e))
        raise e

def cmd_list_review_queue():
    """Lists videos awaiting morning review."""
    print("\n=======================================================")
    print("📋 Morning Review Queue (Pending Approval)")
    print("=======================================================\n")

    job = db.get_next_job(status="ready_for_review")
    if not job:
        print("No videos currently waiting for review.")
        return

    print(f"Video ID: {job['id']}")
    print(f"Title:    {job['title']}")
    print(f"File:     {job.get('video_path')}")
    print(f"Tags:     {job.get('tags')}")
    print("\nTo approve this video for scheduled upload, run:")
    print(f"python run_pipeline.py --approve {job['id']}\n")

def cmd_approve(video_id: int, publish_at: str = None):
    """Approves a video for upload."""
    db.update_video_status(video_id=video_id, status="approved_for_upload")
    print(f"✅ Video #{video_id} approved for upload!")

def cmd_publish():
    """Uploads the next approved video to YouTube."""
    job = db.get_next_job(status="approved_for_upload")
    if not job:
        print("[Upload] No approved videos ready for publishing.")
        return

    video_path = job.get("video_path")
    if not video_path or not os.path.exists(video_path):
        print(f"[Upload] Error: Video file not found at {video_path}")
        db.update_video_status(job["id"], status="failed", error_log="File missing")
        return

    tags = job.get("tags", "").split(",") if job.get("tags") else []
    print(f"\n[Upload] Publishing Video #{job['id']}: '{job['title']}'...")

    try:
        res = youtube_uploader.upload_short(
            video_file_path=video_path,
            title=job["title"],
            description=job["description"],
            tags=tags,
            publish_at=job.get("scheduled_publish_at")
        )
        db.update_video_status(
            video_id=job["id"],
            status="published",
            youtube_id=res["id"]
        )
        print(f"🎉 Successfully published to YouTube! URL: {res['url']}\n")
    except Exception as e:
        print(f"❌ YouTube upload failed: {e}")
        db.update_video_status(video_id=job["id"], status="failed", error_log=str(e))

def main():
    parser = argparse.ArgumentParser(description="Automated Stick Figure Shorts Generator")
    parser.add_argument("--mode", choices=["generate", "review", "approve", "publish", "batch"], default="generate")
    parser.add_argument("--topic", type=str, default="Trying to wake up at 5 AM", help="Topic for the short")
    parser.add_argument("--auto-approve", action="store_true", help="Skip review queue and approve immediately")
    parser.add_argument("--approve", type=int, help="Approve a specific video ID")
    parser.add_argument("--publish-time", type=str, help="ISO timestamp for scheduled publishing (e.g. 2026-11-16T14:00:00Z)")

    args = parser.parse_args()

    if args.approve:
        cmd_approve(args.approve, args.publish_time)
        return

    if args.mode == "generate":
        cmd_generate(args.topic, args.auto_approve)
    elif args.mode == "review":
        cmd_list_review_queue()
    elif args.mode == "publish":
        cmd_publish()
    elif args.mode == "batch":
        # Generate 3 videos for the day
        topics = [
            "Going to the gym on January 1st",
            "When someone says 'we need to talk'",
            "Trying to sleep before an early flight"
        ]
        for t in topics:
            cmd_generate(t, auto_approve=args.auto_approve)

if __name__ == "__main__":
    main()
