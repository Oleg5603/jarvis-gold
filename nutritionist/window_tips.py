from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QListWidget, QListWidgetItem,
    QFontComboBox, QSlider, QFrame
)
from PyQt6.QtCore import Qt, pyqtSlot
from PyQt6.QtGui import QFont


class TipsWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Суфлёр — Рекомендации")
        self.setGeometry(500, 100, 460, 520)
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.WindowStaysOnTopHint)
        self._build_ui()

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setSpacing(8)
        layout.setContentsMargins(12, 12, 12, 12)

        # --- Шрифт + размер ---
        font_row = QHBoxLayout()
        self.font_combo = QFontComboBox()
        self.font_combo.setCurrentFont(QFont("Arial"))
        self.font_combo.currentFontChanged.connect(self._apply_font)
        font_row.addWidget(QLabel("Шрифт:"))
        font_row.addWidget(self.font_combo)

        self.font_size = QSlider(Qt.Orientation.Horizontal)
        self.font_size.setRange(10, 28)
        self.font_size.setValue(14)
        self.font_size.setFixedWidth(90)
        self.font_size.valueChanged.connect(self._apply_font)
        font_row.addWidget(QLabel("Размер:"))
        font_row.addWidget(self.font_size)
        layout.addLayout(font_row)

        # --- Тема ---
        self.topic_label = QLabel("Тема: ожидаю речь...")
        self.topic_label.setStyleSheet("font-weight: bold; font-size: 15px; color: #5a2c82;")
        layout.addWidget(self.topic_label)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(sep)

        # --- Список рекомендаций ---
        rec_label = QLabel("Рекомендации по Малаховой:")
        rec_label.setStyleSheet("font-weight: bold;")
        layout.addWidget(rec_label)

        self.tips_list = QListWidget()
        self.tips_list.setWordWrap(True)
        self.tips_list.setSpacing(4)
        self.tips_list.setStyleSheet("""
            QListWidget { background: #fff8f0; border: 1px solid #ffc107; border-radius: 6px; }
            QListWidget::item { padding: 8px 10px; border-bottom: 1px solid #ffe082; }
            QListWidget::item:selected { background: #fff3cd; color: #856404; }
        """)
        layout.addWidget(self.tips_list, stretch=1)

        self._apply_font()

    def _apply_font(self):
        font = self.font_combo.currentFont()
        font.setPointSize(self.font_size.value())
        self.tips_list.setFont(font)

    @pyqtSlot(str, list)
    def update_content(self, topic: str, recommendations: list):
        self.topic_label.setText(f"Тема: {topic.upper()}")
        self.tips_list.clear()
        for i, rec in enumerate(recommendations, 1):
            item = QListWidgetItem(f"✓ {rec}")
            self.tips_list.addItem(item)
