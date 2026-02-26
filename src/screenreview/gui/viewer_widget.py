# -*- coding: utf-8 -*-
"""Widget for showing the current screenshot with optional drawing annotations."""

from __future__ import annotations

from pathlib import Path
from PyQt6.QtCore import Qt, pyqtSignal, QPoint, QSize
from PyQt6.QtGui import QPixmap, QImage, QPainter, QPen, QColor, QMouseEvent
from PyQt6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
    QPushButton,
)


class DrawingLabel(QLabel):
    """A label that supports drawing yellow annotations on an internal buffer."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._drawing_enabled = False
        # Semi-transparent yellow for "highlighter" look
        self._pen_color = QColor(255, 255, 0, 80) # Increased transparency (alpha 120 -> 80)
        self._pen_width = 20  # Wider default for highlighter
        self._last_point = QPoint()
        
        # Buffer for the original resolution drawing
        self._original_buffer = QImage()
        # Undo history (list of QImages)
        self._undo_stack: list[QImage] = []
        self._max_undo = 3
        # Pixmap of the screenshot
        self._screenshot_pixmap = QPixmap()
        # Current scale factor (display size / original size)
        self._scale_factor = 1.0

    def set_drawing_enabled(self, enabled: bool) -> None:
        self._drawing_enabled = enabled
        if enabled:
            self.setCursor(Qt.CursorShape.CrossCursor)
        else:
            self.setCursor(Qt.CursorShape.ArrowCursor)

    def set_pen_width(self, width: int) -> None:
        self._pen_width = width

    def set_screenshot(self, pixmap: QPixmap, scale_factor: float) -> None:
        """Update the background screenshot and the expected buffer size."""
        self._screenshot_pixmap = pixmap
        self._scale_factor = scale_factor
        
        # Initialize or resize drawing buffer if needed
        if not pixmap.isNull():
            orig_size = QSize(int(pixmap.width() / scale_factor), int(pixmap.height() / scale_factor))
            if self._original_buffer.isNull() or self._original_buffer.size() != orig_size:
                # Create a new transparent buffer
                new_buffer = QImage(orig_size, QImage.Format.Format_ARGB32)
                new_buffer.fill(Qt.GlobalColor.transparent)
                
                # Copy old drawing if sizes match (optional, but good for persistence during resize)
                if not self._original_buffer.isNull() and self._original_buffer.size() == orig_size:
                    painter = QPainter(new_buffer)
                    painter.drawImage(0, 0, self._original_buffer)
                    painter.end()
                
                self._original_buffer = new_buffer
        
        self._update_display()

    def clear_drawing(self) -> None:
        if not self._original_buffer.isNull():
            self._undo_stack.append(self._original_buffer.copy())
            if len(self._undo_stack) > self._max_undo:
                self._undo_stack.pop(0)
            self._original_buffer.fill(Qt.GlobalColor.transparent)
            self._update_display()

    def get_drawing_buffer(self) -> QImage:
        return self._original_buffer

    def undo(self) -> None:
        if not self._undo_stack:
            return
        self._original_buffer = self._undo_stack.pop()
        self._update_display()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if self._drawing_enabled and event.button() == Qt.MouseButton.LeftButton:
            # Save state for undo BEFORE drawing starts
            if not self._original_buffer.isNull():
                self._undo_stack.append(self._original_buffer.copy())
                if len(self._undo_stack) > self._max_undo:
                    self._undo_stack.pop(0)
            self._last_point = event.pos()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._drawing_enabled and (event.buttons() & Qt.MouseButton.LeftButton):
            self._draw_line(self._last_point, event.pos())
            self._last_point = event.pos()

    def _draw_line(self, start_pos: QPoint, end_pos: QPoint) -> None:
        if self._original_buffer.isNull():
            return

        # Translate coordinates to original buffer scale
        start_orig = QPoint(int(start_pos.x() / self._scale_factor), int(start_pos.y() / self._scale_factor))
        end_orig = QPoint(int(end_pos.x() / self._scale_factor), int(end_pos.y() / self._scale_factor))

        painter = QPainter(self._original_buffer)
        pen = QPen(self._pen_color, self._pen_width, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        painter.drawLine(start_orig, end_orig)
        painter.end()
        
        self._update_display()

    def _update_display(self) -> None:
        if self._screenshot_pixmap.isNull():
            return

        # Composite the buffer onto the screenshot
        display_pixmap = self._screenshot_pixmap.copy()
        
        if not self._original_buffer.isNull():
            # Scale the buffer to display size
            scaled_buffer = self._original_buffer.scaled(
                self._screenshot_pixmap.size(), 
                Qt.AspectRatioMode.IgnoreAspectRatio, 
                Qt.TransformationMode.SmoothTransformation
            )
            
            painter = QPainter(display_pixmap)
            painter.drawImage(0, 0, scaled_buffer)
            painter.end()
            
        self.setPixmap(display_pixmap)


class ViewerWidget(QWidget):
    """Display a screenshot image with a framed placeholder and drawing tools."""

    viewport_changed = pyqtSignal(str)
    brush_active_changed = pyqtSignal(bool)

    MIN_DISPLAY_WIDTH = 0

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._image_path: Path | None = None
        self._scale_percent = 100
        self._original_pixmap = QPixmap()

        self.title_label = QLabel("Screenshot")
        self.title_label.setObjectName("sectionTitle")
        
        # Drawing Controls
        self.brush_button = QPushButton("✏️ Brush")
        self.brush_button.setCheckable(True)
        self.brush_button.setFixedWidth(80)
        self.brush_button.toggled.connect(self._on_brush_toggled)
        
        self.undo_button = QPushButton("↩️")
        self.undo_button.setToolTip("Undo last brush stroke")
        self.undo_button.setFixedWidth(30)
        self.undo_button.clicked.connect(self._on_undo_clicked)

        self.brush_size_combo = QComboBox()
        self.brush_size_combo.addItems(["1px", "3px", "5px", "10px", "20px", "50px"])
        self.brush_size_combo.setCurrentText("5px")
        self.brush_size_combo.setFixedWidth(60)
        self.brush_size_combo.currentTextChanged.connect(self._on_brush_size_changed)
        self.brush_size_combo.activated.connect(lambda: self.setFocus())
        
        self.clear_button = QPushButton("🗑️")
        self.clear_button.setToolTip("Clear annotations")
        self.clear_button.setFixedWidth(30)
        self.clear_button.clicked.connect(self._on_clear_clicked)

        self.scale_combo = QComboBox()
        self.scale_combo.addItems(["10%", "20%", "30%", "40%", "50%", "60%", "70%", "80%", "90%", "100%"])
        self.scale_combo.setCurrentText("50%")
        self.scale_combo.setToolTip("Scale screenshot width relative to the viewer area.")
        self.scale_combo.currentTextChanged.connect(self._on_scale_changed)
        self.scale_combo.activated.connect(lambda: self.setFocus())
        
        self.scale_label = QLabel("Scale")
        self.scale_label.setObjectName("mutedText")
        
        self.viewport_combo = QComboBox()
        self.viewport_combo.addItems(["mobile", "desktop"])
        self.viewport_combo.setCurrentText("mobile")
        self.viewport_combo.setToolTip("Switch between mobile and desktop viewport.")
        self.viewport_combo.currentTextChanged.connect(self._on_viewport_changed)
        self.viewport_combo.activated.connect(lambda: self.setFocus())
        
        self.viewport_label = QLabel("Viewport")
        self.viewport_label.setObjectName("mutedText")
        
        self.image_label = DrawingLabel()
        self.image_label.setObjectName("viewerSurface")
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setMinimumSize(120, 120)
        self.image_label.setScaledContents(False)
        self.image_label.setContentsMargins(8, 8, 8, 8)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(False)
        self.scroll_area.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.scroll_area.setMinimumWidth(240)
        self.scroll_area.setMinimumHeight(260)
        self.scroll_area.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.scroll_area.setWidget(self.image_label)

        title_row = QHBoxLayout()
        title_row.setContentsMargins(0, 0, 0, 0)
        title_row.setSpacing(8)
        title_row.addWidget(self.title_label)
        title_row.addStretch(1)
        
        # Tools layout
        title_row.addWidget(self.brush_button)
        title_row.addWidget(self.undo_button)
        title_row.addWidget(self.brush_size_combo)
        title_row.addWidget(self.clear_button)
        title_row.addSpacing(10)
        
        title_row.addWidget(self.viewport_label)
        title_row.addWidget(self.viewport_combo)
        title_row.addWidget(self.scale_label)
        title_row.addWidget(self.scale_combo)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.addLayout(title_row)
        layout.addWidget(self.scroll_area, 1)

    def load_drawing(self, input_path: Path) -> bool:
        """Load a transparent drawing buffer into the current view."""
        if not input_path.exists():
            self.image_label.clear_drawing()
            return False
            
        img = QImage(str(input_path))
        if img.isNull():
            return False
            
        # Initialize buffer if needed by ensuring set_image was called
        # If set_image was called, _original_buffer should have the size of the screenshot
        target_buffer = self.image_label.get_drawing_buffer()
        if target_buffer.isNull():
            return False
            
        # Draw loaded image onto buffer
        painter = QPainter(target_buffer)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Source)
        painter.drawImage(0, 0, img)
        painter.end()
        self.image_label._update_display()
        return True

    def set_image(self, path: Path | None) -> None:
        """Load and display an image from disk."""
        self._image_path = path
        if path is None or not path.exists():
            self._original_pixmap = QPixmap()
            self.image_label.set_screenshot(QPixmap(), 1.0)
            self.image_label.setText("No screenshot loaded")
            self.image_label.adjustSize()
            return

        pixmap = QPixmap(str(path))
        if pixmap.isNull():
            self._original_pixmap = QPixmap()
            self.image_label.set_screenshot(QPixmap(), 1.0)
            self.image_label.setText("Failed to load screenshot")
            self.image_label.adjustSize()
            return

        self._original_pixmap = pixmap
        self._refresh_display()

    def save_drawing(self, output_path: Path) -> bool:
        """Save the current drawing buffer as a transparent PNG."""
        buffer = self.image_label.get_drawing_buffer()
        if buffer.isNull():
            return False
        return buffer.save(str(output_path), "PNG")

    def clear_drawing(self) -> None:
        self.image_label.clear_drawing()

    def resizeEvent(self, event) -> None:  # type: ignore[override]
        super().resizeEvent(event)
        self._refresh_display()

    def _on_scale_changed(self, text: str) -> None:
        raw = text.strip().rstrip("%")
        try:
            value = int(raw)
        except ValueError:
            value = 100
        self._scale_percent = max(10, min(100, value))
        self._refresh_display()

    def _on_viewport_changed(self, text: str) -> None:
        self.viewport_changed.emit(text)

    def _on_brush_toggled(self, checked: bool) -> None:
        self.image_label.set_drawing_enabled(checked)
        self.brush_active_changed.emit(checked)

    def _on_brush_size_changed(self, text: str) -> None:
        try:
            width = int(text.replace("px", ""))
            self.image_label.set_pen_width(width)
        except ValueError:
            pass

    def _on_undo_clicked(self) -> None:
        self.image_label.undo()

    def _on_clear_clicked(self) -> None:
        self.image_label.clear_drawing()

    def _refresh_display(self) -> None:
        if self._original_pixmap.isNull():
            return

        target_size = self.scroll_area.viewport().size()
        target_width = max(1, target_size.width() - 16)
        scaled_target_width = int(target_width * (self._scale_percent / 100.0))
        display_width = max(self.MIN_DISPLAY_WIDTH, scaled_target_width)

        if display_width > 0:
            scaled = self._original_pixmap.scaledToWidth(display_width, Qt.TransformationMode.SmoothTransformation)
        else:
            scaled = self._original_pixmap.scaled(
                max(1, self.MIN_DISPLAY_WIDTH),
                max(1, target_size.height() - 16),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        
        scale_factor = scaled.width() / self._original_pixmap.width()
        self.image_label.set_screenshot(scaled, scale_factor)
        self.image_label.resize(scaled.size())
        self.image_label.setText("")
