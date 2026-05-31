"""VPN Switcher — entry point."""
import sys
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt

from vpn_window import VPNWindow


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setApplicationName("VPN Switcher")

    # Dark palette for Fusion style
    from PyQt6.QtGui import QPalette, QColor
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window,          QColor(26, 26, 26))
    palette.setColor(QPalette.ColorRole.WindowText,      QColor(220, 220, 220))
    palette.setColor(QPalette.ColorRole.Base,            QColor(18, 18, 18))
    palette.setColor(QPalette.ColorRole.AlternateBase,   QColor(30, 30, 30))
    palette.setColor(QPalette.ColorRole.ToolTipBase,     QColor(50, 50, 50))
    palette.setColor(QPalette.ColorRole.ToolTipText,     QColor(220, 220, 220))
    palette.setColor(QPalette.ColorRole.Text,            QColor(220, 220, 220))
    palette.setColor(QPalette.ColorRole.Button,          QColor(40, 40, 40))
    palette.setColor(QPalette.ColorRole.ButtonText,      QColor(220, 220, 220))
    palette.setColor(QPalette.ColorRole.BrightText,      QColor(255, 100, 100))
    palette.setColor(QPalette.ColorRole.Link,            QColor(42, 130, 218))
    palette.setColor(QPalette.ColorRole.Highlight,       QColor(42, 130, 218))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor(0, 0, 0))
    app.setPalette(palette)

    win = VPNWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
