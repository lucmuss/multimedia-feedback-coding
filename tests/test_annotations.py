# -*- coding: utf-8 -*-
"""Tests for screenshot annotation (drawing) feature."""

from __future__ import annotations

import json
from pathlib import Path
from PyQt6.QtCore import Qt, QPoint, QEvent, QPointF
from PyQt6.QtGui import QImage, QMouseEvent
from screenreview.gui.viewer_widget import ViewerWidget
from screenreview.models.screen_item import ScreenItem

def test_viewer_widget_drawing_and_saving(tmp_path: Path, qt_app) -> None:
    viewer = ViewerWidget()
    viewer.resize(800, 600)
    
    # Create a dummy image to draw on
    img = QImage(800, 600, QImage.Format.Format_RGB32)
    img.fill(Qt.GlobalColor.white)
    img_path = tmp_path / "base.png"
    img.save(str(img_path))
    
    viewer.set_image(img_path)
    qt_app.processEvents()
    
    # Simulate a drawing action on the label
    label = viewer.image_label
    label.set_drawing_enabled(True)
    
    press = QMouseEvent(QEvent.Type.MouseButtonPress, QPointF(100, 100), Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
    move = QMouseEvent(QEvent.Type.MouseMove, QPointF(200, 200), Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
    release = QMouseEvent(QEvent.Type.MouseButtonRelease, QPointF(200, 200), Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
    
    label.mousePressEvent(press)
    label.mouseMoveEvent(move)
    label.mouseReleaseEvent(release)
    
    save_path = tmp_path / "drawing.png"
    viewer.save_drawing(save_path)
    
    assert save_path.exists()
    assert save_path.stat().st_size > 0
    
    # Load it back
    viewer.clear_drawing()
    viewer.load_drawing(save_path)

def test_main_window_saves_annotations_on_navigation(tmp_path: Path, qt_app, default_config) -> None:
    from screenreview.gui.main_window import MainWindow
    
    # Setup VALID project structure for folder_scanner
    project_dir = tmp_path / "project"
    routes_dir = project_dir / "routes"
    routes_dir.mkdir(parents=True)
    
    for slug in ["login", "dashboard"]:
        slug_dir = routes_dir / slug / "mobile"
        slug_dir.mkdir(parents=True)
        (slug_dir / "meta.json").write_text(json.dumps({"route": f"/{slug}", "viewport": "mobile"}), encoding="utf-8")
        img = QImage(100, 100, QImage.Format.Format_RGB32)
        img.fill(Qt.GlobalColor.white)
        img.save(str(slug_dir / "screenshot.png"))
    
    window = MainWindow(default_config)
    window.show()
    window.load_project(project_dir, show_file_report=False)
    qt_app.processEvents()
    
    assert window.controller.navigator is not None
    assert len(window.controller.screens) == 2
    
    screen = window.controller.navigator.current()
    assert screen.name == "dashboard"
    
    # Ensure buffer is initialized by drawing something
    label = window.viewer_widget.image_label
    label.set_drawing_enabled(True)
    
    press = QMouseEvent(QEvent.Type.MouseButtonPress, QPointF(10, 10), Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
    move = QMouseEvent(QEvent.Type.MouseMove, QPointF(20, 20), Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
    label.mousePressEvent(press)
    label.mouseMoveEvent(move)
    qt_app.processEvents()
    
    # Manually trigger save
    window._save_drawing(screen)
    qt_app.processEvents()
    
    overlay_path = screen.extraction_dir / "annotation_overlay.png"
    assert overlay_path.exists()
    
    # Navigate should call save_drawing_callback
    window.controller.go_next(save_drawing_callback=window._save_drawing)
    assert window.controller.navigator.current().name == "login"
    
    window.close()
