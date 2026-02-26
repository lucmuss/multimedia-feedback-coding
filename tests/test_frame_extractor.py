# -*- coding: utf-8 -*-
"""Tests for frame extraction."""

from __future__ import annotations
from pathlib import Path
from unittest.mock import Mock, patch
import pytest
from screenreview.pipeline.frame_extractor import FrameExtractor

class TestFrameExtractor:
    def test_init(self):
        extractor = FrameExtractor(fps=2.0)
        assert extractor.fps == 2.0

    @patch("subprocess.run")
    def test_extract_frames_calls_ffmpeg(self, mock_run, tmp_path):
        mock_run.return_value = Mock(returncode=0, stdout="", stderr="")
        
        # Create a dummy video file (> 1KB to pass size check)
        video_path = tmp_path / "test_video.mp4"
        video_path.write_bytes(b"0" * 2048)
        
        output_dir = tmp_path / "frames"
        
        extractor = FrameExtractor(fps=1.0)
        # We also need to mock the glob result since ffmpeg didn't actually run
        with patch.object(Path, "glob") as mock_glob:
            mock_glob.return_value = [output_dir / "frame_0001.png"]
            frames = extractor.extract_frames(video_path, output_dir)
            
            assert mock_run.called
            assert "ffmpeg" in mock_run.call_args[0][0]
            assert len(frames) == 1

    def test_extract_frames_skips_small_files(self, tmp_path):
        video_path = tmp_path / "tiny.mp4"
        video_path.write_bytes(b"too small")
        
        extractor = FrameExtractor()
        frames = extractor.extract_frames(video_path, tmp_path / "out")
        assert frames == []

    @patch("subprocess.run")
    def test_get_video_info(self, mock_run, tmp_path):
        # Mock ffprobe output
        mock_run.return_value = Mock(
            returncode=0, 
            stdout='{"format": {"duration": "10.5"}, "streams": [{"codec_type": "video", "width": 1920, "height": 1080, "r_frame_rate": "30/1"}]}',
            stderr=""
        )
        
        video_path = tmp_path / "info_test.mp4"
        video_path.write_text("dummy")
        
        extractor = FrameExtractor()
        info = extractor.get_video_info(video_path)
        
        assert info["duration"] == 10.5
        assert info["width"] == 1920
        assert info["height"] == 1080
        assert info["fps"] == 30.0

    def test_smart_select_frames(self):
        extractor = FrameExtractor()
        frames = [Path(f"frame_{i}.png") for i in range(10)]
        
        # Select first, last, and every 3rd
        selected = extractor.smart_select_frames(frames)
        # 0, 3, 6, 9 (and last is 9) -> [0, 3, 6, 9]
        assert Path("frame_0.png") in selected
        assert Path("frame_9.png") in selected
        assert len(selected) == 4

