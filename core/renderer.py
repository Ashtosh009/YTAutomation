import os
import subprocess
from pathlib import Path
from typing import List, Dict, Any, Optional
from PIL import Image
from core.config import VIDEO_WIDTH, VIDEO_HEIGHT, FPS, OUTPUT_DIR, ASSETS_DIR
from core.stick_engine import renderer_engine
from core.captions import captions_drawer
from core.tts import tts

def get_ffmpeg_binary() -> str:
    """Finds FFmpeg from PATH or imageio-ffmpeg."""
    import shutil
    ffmpeg_path = shutil.which("ffmpeg")
    if ffmpeg_path:
        return ffmpeg_path
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return "ffmpeg"

class VideoRenderer:
    def __init__(self, width: int = VIDEO_WIDTH, height: int = VIDEO_HEIGHT, fps: int = FPS):
        self.width = width
        self.height = height
        self.fps = fps
        self.ffmpeg_bin = get_ffmpeg_binary()

    def get_audio_duration(self, audio_file: str) -> float:
        """Determines duration in seconds of an audio file using ffprobe/ffmpeg."""
        try:
            cmd = [
                self.ffmpeg_bin, "-i", audio_file,
                "-f", "null", "-"
            ]
            res = subprocess.run(cmd, stderr=subprocess.PIPE, stdout=subprocess.DEVNULL, text=True)
            # Parse Duration: 00:00:05.12
            for line in res.stderr.splitlines():
                if "Duration:" in line:
                    parts = line.split("Duration:")[1].split(",")[0].strip().split(":")
                    hours = float(parts[0])
                    mins = float(parts[1])
                    secs = float(parts[2])
                    return hours * 3600 + mins * 60 + secs
        except Exception:
            pass
        return 5.0 # fallback estimate

    def render_short(self, script_data: Dict[str, Any], output_path: str) -> str:
        """Renders end-to-end 9:16 vertical short from script JSON."""
        scenes = script_data.get("scenes", [])
        if not scenes:
            raise ValueError("Script contains no scenes.")

        temp_dir = OUTPUT_DIR / "temp"
        temp_dir.mkdir(parents=True, exist_ok=True)

        scene_media = []
        total_duration = 0.0

        # Step 1: Synthesize audio for each scene
        print("[Renderer] Synthesizing speech audio for scenes...")
        for idx, scene in enumerate(scenes):
            scene_audio_path = str(temp_dir / f"scene_{idx}.mp3")
            text = scene.get("text", "")
            timings = tts.synthesize(text, scene_audio_path)
            duration = self.get_audio_duration(scene_audio_path)
            # Add small 0.2s pause between scenes for natural pacing
            duration = max(duration, 1.5)
            scene_media.append({
                "scene": scene,
                "audio_path": scene_audio_path,
                "timings": timings,
                "duration": duration,
                "start_time": total_duration
            })
            total_duration += duration

        # Step 2: Combine scene audio files into one narration track
        combined_audio_path = str(temp_dir / "narration.mp3")
        concat_list_file = str(temp_dir / "concat_audio.txt")
        with open(concat_list_file, "w") as f:
            for item in scene_media:
                f.write(f"file '{os.path.abspath(item['audio_path'])}'\n")

        concat = subprocess.run([
            self.ffmpeg_bin, "-y", "-f", "concat", "-safe", "0",
            "-i", concat_list_file, "-c", "copy", combined_audio_path
        ], stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
        if concat.returncode != 0:
            raise RuntimeError(f"[Renderer] FFmpeg audio concat failed: {concat.stderr[-800:]}")

        # Step 3: Stream rendered frames directly to FFmpeg via STDIN pipe
        print(f"[Renderer] Rendering {total_duration:.1f}s animation ({int(total_duration * self.fps)} frames) at {self.fps} FPS...")
        ffmpeg_cmd = [
            self.ffmpeg_bin,
            "-y",
            "-f", "rawvideo",
            "-vcodec", "rawvideo",
            "-s", f"{self.width}x{self.height}",
            "-pix_fmt", "rgb24",
            "-r", str(self.fps),
            "-i", "-",  # Video input from pipe
            "-i", combined_audio_path, # Audio input
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            "-preset", "veryfast",
            "-c:a", "aac",
            "-b:a", "192k",
            "-shortest",
            "-movflags", "+faststart",  # moov atom first so the panel can stream before full download
            output_path
        ]

        ffmpeg_log = open(temp_dir / "ffmpeg_render.log", "w")
        pipe = subprocess.Popen(ffmpeg_cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=ffmpeg_log)

        total_frames = int(total_duration * self.fps)
        cur_scene_idx = 0

        for frame_num in range(total_frames):
            current_time = frame_num / self.fps

            # Find active scene
            while cur_scene_idx < len(scene_media) - 1 and current_time >= scene_media[cur_scene_idx + 1]["start_time"]:
                cur_scene_idx += 1

            cur_item = scene_media[cur_scene_idx]
            scene_local_time = current_time - cur_item["start_time"]
            scene_progress = min(max(scene_local_time / cur_item["duration"], 0.0), 1.0)

            # Generate base frame
            frame_img = renderer_engine.render_frame(cur_item["scene"], scene_progress)

            # Find active words for karaoke captioning (group into 3-4 word phrases)
            timings = cur_item["timings"]
            words = [t["word"] for t in timings]
            active_word_idx = -1

            # Hold the most recently started word through inter-word gaps so the
            # caption chunk does not flash back to the first words of the scene.
            for w_idx, t in enumerate(timings):
                if t["start"] <= scene_local_time:
                    active_word_idx = w_idx
                else:
                    break

            if words:
                # Group words into chunks of 3 for punchy display
                chunk_size = 3
                if active_word_idx >= 0:
                    chunk_start = (active_word_idx // chunk_size) * chunk_size
                else:
                    chunk_start = 0
                chunk = words[chunk_start:chunk_start + chunk_size]
                local_active = active_word_idx - chunk_start if active_word_idx >= 0 else -1
                captions_drawer.draw_karaoke_captions(frame_img, chunk, local_active)

            # Write raw bytes to FFmpeg stdin
            try:
                pipe.stdin.write(frame_img.tobytes())
            except Exception as e:
                print(f"[Renderer] Error writing frame to pipe: {e}")
                break

        pipe.stdin.close()
        rc = pipe.wait()
        ffmpeg_log.close()
        if rc != 0 or not os.path.exists(output_path) or os.path.getsize(output_path) == 0:
            tail = (temp_dir / "ffmpeg_render.log").read_text()[-800:]
            raise RuntimeError(f"[Renderer] FFmpeg encode failed (exit {rc}): {tail}")
        print(f"[Renderer] Render complete: {output_path}")
        return output_path

    def generate_thumbnail(self, script_data: Dict[str, Any], video_path: str, output_thumbnail_path: str) -> str:
        """Generates a 9:16 thumbnail image from script scene or extracts frame from video."""
        target_path = Path(output_thumbnail_path)
        target_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            scenes = script_data.get("scenes", [])
            peak_scene = scenes[0] if scenes else {}
            img = renderer_engine.render_frame(peak_scene, progress=0.5)
            img.save(str(target_path), "JPEG", quality=90)
            return str(target_path)
        except Exception as e:
            print(f"[Renderer] Could not render frame for thumbnail: {e}. Trying FFmpeg extract.")

        # Fallback: extract frame using ffmpeg
        if os.path.exists(video_path):
            subprocess.run([
                self.ffmpeg_bin, "-y", "-ss", "00:00:01",
                "-i", video_path, "-vframes", "1",
                "-q:v", "2", str(target_path)
            ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        return str(target_path)

video_renderer = VideoRenderer()
