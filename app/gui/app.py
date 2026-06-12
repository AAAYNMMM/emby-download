"""
EmbyD GUI Application Entry Point.

Usage:
    python -m app.gui.app
"""

import sys
from typing import Optional

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt

from app.gui.main_window import MainWindow
from app.utils.logger import setup_logger


def main(config_path: Optional[str] = None):
    """Start the EmbyD GUI application."""
    # Initialize logger
    setup_logger(level="INFO")

    app = QApplication(sys.argv)
    app.setApplicationName("EmbyD")
    app.setOrganizationName("EmbyD")
    app.setStyle("Fusion")

    # Dark theme palette
    app.setStyleSheet("""
        QMainWindow, QWidget {
            background-color: #1e1e1e;
            color: #d4d4d4;
        }
        QGroupBox {
            border: 1px solid #333;
            border-radius: 4px;
            margin-top: 12px;
            padding-top: 16px;
            font-weight: bold;
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            left: 10px;
            padding: 0 4px;
        }
        QLineEdit, QSpinBox, QComboBox {
            background-color: #3c3c3c;
            color: #d4d4d4;
            border: 1px solid #555;
            border-radius: 3px;
            padding: 4px 8px;
        }
        QLineEdit:focus, QSpinBox:focus, QComboBox:focus {
            border-color: #007acc;
        }
        QPushButton {
            background-color: #0e639c;
            color: white;
            border: none;
            border-radius: 3px;
            padding: 6px 16px;
            min-width: 80px;
        }
        QPushButton:hover {
            background-color: #1177bb;
        }
        QPushButton:disabled {
            background-color: #333;
            color: #666;
        }
        QTableWidget {
            background-color: #252526;
            color: #d4d4d4;
            border: 1px solid #333;
            gridline-color: #333;
        }
        QTableWidget::item:selected {
            background-color: #094771;
        }
        QHeaderView::section {
            background-color: #333;
            color: #d4d4d4;
            border: 1px solid #444;
            padding: 4px;
        }
        QTabWidget::pane {
            border: 0;
        }
        QLabel {
            color: #d4d4d4;
        }
    """)

    window = MainWindow(config_path=config_path)
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()