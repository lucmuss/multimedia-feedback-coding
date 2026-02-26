# -*- coding: utf-8 -*-
"""
Autonomous GUI Self-Test / Stress Test.
This script launches the application and simulates user clicks to verify stability.
"""

import sys
import os
import time
import logging
from pathlib import Path
from PyQt6.QtWidgets import QApplication, QPushButton, QTabBar
from PyQt6.QtTest import QTest
from PyQt6.QtCore import Qt, QTimer

# Add src to path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from screenreview.main import main
from screenreview.gui.main_window import MainWindow
from screenreview.gui.settings_dialog import SettingsDialog
from screenreview.config import load_config

logging.basicConfig(level=logging.DEBUG, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("GUI-SelfTest")

def run_stress_test():
    app = QApplication.instance() or QApplication(sys.argv)
    settings = load_config()
    window = MainWindow(settings=settings)
    window.show()
    
    logger.info("=== Starting Autonomous GUI Stress Test ===")

    def step_1_open_settings():
        logger.info("Step 1: Opening Settings Dialog...")
        window._open_settings_dialog()
        # Find the active settings dialog
        dialog = window.findChild(SettingsDialog)
        if not dialog:
            logger.error("Failed to find SettingsDialog!")
            app.quit()
            return

        QTimer.singleShot(1000, lambda: step_2_iterate_tabs(dialog))

    def step_2_iterate_tabs(dialog: SettingsDialog):
        logger.info("Step 2: Iterating through all settings tabs...")
        tab_widget = dialog.tab_widget
        for i in range(tab_widget.count()):
            tab_name = tab_widget.tabText(i)
            logger.info(f"  Switching to tab: {tab_name}")
            tab_widget.setCurrentIndex(i)
            QTest.qWait(500)
        
        QTimer.singleShot(1000, lambda: step_3_close_settings(dialog))

    def step_3_close_settings(dialog: SettingsDialog):
        logger.info("Step 3: Closing Settings (Accepted)...")
        dialog.accept()
        QTimer.singleShot(1000, step_4_navigation)

    def step_4_navigation():
        logger.info("Step 4: Testing Navigation Controls...")
        # Since we might not have a project loaded, we just check buttons exist
        controls = window.controls_widget
        logger.info("  Clicking 'Next' (if enabled)...")
        if controls.next_button.isEnabled():
            QTest.mouseClick(controls.next_button, Qt.MouseButton.LeftButton)
        
        QTest.qWait(500)
        
        logger.info("  Clicking 'Skip' (if enabled)...")
        if controls.skip_button.isEnabled():
            QTest.mouseClick(controls.skip_button, Qt.MouseButton.LeftButton)

        QTimer.singleShot(1000, step_5_recording)

    def step_5_recording():
        logger.info("Step 5: Testing Recording Toggle...")
        controls = window.controls_widget
        logger.info("  Starting Recording...")
        QTest.mouseClick(controls.record_button, Qt.MouseButton.LeftButton)
        
        QTest.qWait(2000) # Wait 2 seconds of "recording"
        
        logger.info("  Stopping Recording...")
        QTest.mouseClick(controls.record_button, Qt.MouseButton.LeftButton)
        
        QTimer.singleShot(2000, step_6_finalize)

    def step_6_finalize():
        logger.info("=== Stress Test Completed Successfully ===")
        window.close()
        app.quit()

    # Start the sequence
    QTimer.singleShot(2000, step_1_open_settings)
    
    logger.info("Application loop starting...")
    sys.exit(app.exec())

if __name__ == "__main__":
    # Ensure we run offscreen if in CI, but here we want to see it if possible
    # os.environ["QT_QPA_PLATFORM"] = "xcb" 
    run_stress_test()
