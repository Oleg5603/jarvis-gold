from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QListWidget, QListWidgetItem,
    QFontComboBox, QSlider, QFrame, QTextEdit
)
from PyQt6.QtCore import Qt, pyqtSlot
from PyQt6.QtGui import QFont


class TipsWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Суфлёр — Рекомендации")
        self.setGeometry(500, 80, 460, 580)
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.WindowStaysOnTopHint)
        self._build_ui()

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setSpacing(6)
        layout.setContentsMargins(12, 10, 12, 10)

        # --- Статус (зеркало из окна вопросов) ---
        self.status_label = QLabel("🎙 Статус: инициализация...")
        self.status_label.setStyleSheet(
            "background:#e9ecef; border-radius:6px; padding:4px 8px; font-size:12px; color:#495057;"
        )
        layout.addWidget(self.status_label)

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

        # --- Лог распознанного ---
        log_label = QLabel("Распознано:")
        log_label.setStyleSheet("font-weight: bold; font-size: 11px; color: #6c757d;")
        layout.addWidget(log_label)

        self.log_box = QTextEdit()
        self.log_box.setReadOnly(True)
        self.log_box.setMaximumHeight(55)
        self.log_box.setStyleSheet(
            "background:#f1f3f5; border:1px solid #ced4da; border-radius:4px; font-size:11px; color:#495057;"
        )
        layout.addWidget(self.log_box)

        self._apply_font()

    def _apply_font(self):
        font = self.font_combo.currentFont()
        font.setPointSize(self.font_size.value())
        self.tips_list.setFont(font)

    @pyqtSlot(str)
    def set_mic_status(self, status: str):
        styles = {
            "init":        ("⏳ Инициализация микрофона...", "#fff3cd", "#856404"),
            "ready":       ("✅ Микрофон готов", "#d4edda", "#155724"),
            "listening":   ("🎙 Слушаю...", "#cce5ff", "#004085"),
            "recognizing": ("🔄 Распознаю...", "#e2e3e5", "#383d41"),
            "paused":      ("⏸ Микрофон выключен", "#e9ecef", "#495057"),
        }
        if status.startswith("error:"):
            msg = status[6:]
            self.status_label.setText(f"❌ {msg}")
            self.status_label.setStyleSheet(
                "background:#f8d7da; border-radius:6px; padding:4px 8px; font-size:12px; color:#721c24;"
            )
            return
        text, bg, color = styles.get(status, ("...", "#e9ecef", "#495057"))
        self.status_label.setText(text)
        self.status_label.setStyleSheet(
            f"background:{bg}; border-radius:6px; padding:4px 8px; font-size:12px; color:{color};"
        )

    def log_recognized(self, text: str):
        self.log_box.append(f"► {text}")
        sb = self.log_box.verticalScrollBar()
        sb.setValue(sb.maximum())

    @pyqtSlot(str, list)
    def update_content(self, topic: str, recommendations: list):
        self.topic_label.setText(f"Тема: {topic.upper()}")
        self.tips_list.clear()
        for i, rec in enumerate(recommendations, 1):
            item = QListWidgetItem(f"✓ {rec}")
            self.tips_list.addItem(item)
