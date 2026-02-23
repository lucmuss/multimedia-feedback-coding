# -*- coding: utf-8 -*-
"""Audio recording with PyAudio and transcription."""

from __future__ import annotations

import json
import logging
import threading
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class AudioRecorder:
    """Record audio from microphone with level monitoring and transcription."""

    def __init__(self, sample_rate: int = 16000, channels: int = 1) -> None:
        self.sample_rate = sample_rate
        self.channels = channels
        self._recording = False
        self._stream = None
        self._audio_interface = None
        self._frames = []
        self._level = 0.0
        self._level_lock = threading.Lock()
        self._output_path = None
        self._init_pyaudio()

    def _init_pyaudio(self) -> None:
        """Initialize PyAudio."""
        try:
            import pyaudio
            self._audio_interface = pyaudio.PyAudio()
            logger.info("PyAudio initialized successfully")
        except ImportError:
            logger.warning("PyAudio not available. Install with: pip install pyaudio")
            self._audio_interface = None

    def start_recording(self, output_path: Path) -> None:
        """Start recording audio to file."""
        if self._audio_interface is None:
            raise RuntimeError("PyAudio not available")

        if self._recording:
            raise RuntimeError("Already recording")

        self._frames = []
        self._recording = True
        self._output_path = output_path

        # Start recording in background thread
        self._recording_thread = threading.Thread(target=self._record_loop)
        self._recording_thread.daemon = True
        self._recording_thread.start()

        logger.info(f"Started audio recording to: {output_path}")

    def _record_loop(self) -> None:
        """Main recording loop."""
        try:
            import pyaudio
            import numpy as np

            chunk_size = 1024
            format = pyaudio.paInt16

            self._stream = self._audio_interface.open(
                format=format,
                channels=self.channels,
                rate=self.sample_rate,
                input=True,
                frames_per_buffer=chunk_size
            )

            logger.info("Audio recording loop started")

            while self._recording:
                data = self._stream.read(chunk_size, exception_on_overflow=False)
                self._frames.append(data)

                # Calculate audio level
                audio_data = np.frombuffer(data, dtype=np.int16)
                level = np.sqrt(np.mean(audio_data.astype(np.float32) ** 2)) / 32768.0
                with self._level_lock:
                    self._level = float(level)

        except Exception as e:
            logger.error(f"Recording error: {e}")
        finally:
            if self._stream:
                self._stream.stop_stream()
                self._stream.close()
                self._stream = None

    def stop_recording(self) -> float:
        """Stop recording and save to file."""
        if not self._recording:
            return 0.0

        self._recording = False

        if self._recording_thread:
            self._recording_thread.join(timeout=2.0)

        if self._frames and self._output_path:
            try:
                import wave
                # Save as WAV file
                with wave.open(str(self._output_path), 'wb') as wf:
                    wf.setnchannels(self.channels)
                    wf.setsampwidth(2)  # 16-bit
                    wf.setframerate(self.sample_rate)
                    wf.writeframes(b''.join(self._frames))

                duration = len(self._frames) * 1024 / self.sample_rate
                logger.info(f"Saved {duration:.1f}s audio to: {self._output_path}")
                return duration

            except Exception as e:
                logger.error(f"Failed to save audio: {e}")

        return 0.0

    def get_level(self) -> float:
        """Get current audio level (0.0-1.0)."""
        with self._level_lock:
            return self._level

    def is_recording(self) -> bool:
        """Check if currently recording."""
        return self._recording

    def transcribe_audio(self, audio_path: Path, api_key: str) -> dict[str, Any]:
        """Transcribe audio using OpenAI Whisper."""
        if not audio_path.exists():
            raise FileNotFoundError(audio_path)

        try:
            from openai import OpenAI
            client = OpenAI(api_key=api_key)

            with open(audio_path, "rb") as audio_file:
                transcript = client.audio.transcriptions.create(
                    file=audio_file,
                    model="whisper-1",
                    response_format="verbose_json",
                    timestamp_granularities=["segment"]
                )

            # Convert to our format
            segments = []
            for segment in transcript.segments:
                segments.append({
                    "start": segment.get("start", 0),
                    "end": segment.get("end", 0),
                    "text": segment.get("text", "").strip()
                })

            result = {
                "text": transcript.text,
                "language": transcript.language,
                "duration": transcript.duration,
                "segments": segments
            }

            logger.info(f"Transcribed {transcript.duration:.1f}s audio")
            return result

        except Exception as e:
            logger.error(f"Transcription failed: {e}")
            return {
                "text": "",
                "language": "unknown",
                "duration": 0.0,
                "segments": []
            }