import os
import asyncio
from pathlib import Path
from typing import List, Dict, Any, Tuple
from core.config import DEFAULT_VOICE, OUTPUT_DIR

class TextToSpeech:
    def __init__(self, voice: str = DEFAULT_VOICE):
        self.voice = voice

    async def _synthesize_edge_tts(self, text: str, output_audio_path: str) -> List[Dict[str, Any]]:
        """Synthesize audio with word-level boundary timestamps using edge-tts."""
        import edge_tts
        communicate = edge_tts.Communicate(text, self.voice)
        submaker = edge_tts.SubMaker()
        
        with open(output_audio_path, "wb") as f:
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    f.write(chunk["data"])
                elif chunk["type"] == "WordBoundary":
                    submaker.feed(chunk)
                    
        # Extract word boundaries: offset is in 100ns units
        word_timings = []
        for offset, duration, text_word in submaker.offset_and_duration:
            start_s = offset / 10_000_000.0
            end_s = (offset + duration) / 10_000_000.0
            word_timings.append({
                "word": text_word,
                "start": start_s,
                "end": end_s
            })
        return word_timings

    def synthesize(self, text: str, output_audio_path: str) -> List[Dict[str, Any]]:
        """Main synthesis entrypoint with fallback support."""
        output_path = Path(output_audio_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            return asyncio.run(self._synthesize_edge_tts(text, str(output_path)))
        except Exception as e:
            print(f"[TTS] edge-tts error: {e}. Attempting system fallback.")
            return self._fallback_synthesize(text, str(output_path))

    def _fallback_synthesize(self, text: str, output_audio_path: str) -> List[Dict[str, Any]]:
        """Fallback for offline testing or system TTS."""
        # On macOS, check if 'say' can be used:
        aiff_path = output_audio_path.replace(".mp3", ".aiff")
        try:
            os.system(f'say -v "Alex" "{text}" -o "{aiff_path}"')
            if os.path.exists(aiff_path):
                # Convert to mp3 or keep aiff
                os.system(f'ffmpeg -y -i "{aiff_path}" "{output_audio_path}" >/dev/null 2>&1')
                if os.path.exists(output_audio_path):
                    os.remove(aiff_path)
        except Exception:
            pass

        # Estimate word timestamps if no boundary data
        words = text.split()
        total_estimate_duration = max(len(words) * 0.35, 1.0)
        word_duration = total_estimate_duration / max(len(words), 1)
        
        timings = []
        cur = 0.0
        for w in words:
            timings.append({
                "word": w,
                "start": round(cur, 2),
                "end": round(cur + word_duration, 2)
            })
            cur += word_duration
        return timings

tts = TextToSpeech()
