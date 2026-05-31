from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QListWidget, QListWidgetItem,
    QSpinBox, QFontComboBox, QSlider, QFrame, QTextEdit
)
from PyQt6.QtCore import Qt, QTimer, pyqtSlot, pyqtSignal
from PyQt6.QtGui import QFont


class QuestionsWindow(QMainWindow):
    mic_toggled = pyqtSignal(bool)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Суфлёр — Вопросы")
        self.setGeometry(50, 80, 430, 660)
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.WindowStaysOnTopHint)

        self.duration_seconds = 30 * 60
        self.remaining_seconds = self.duration_seconds
        self.timer_running = False
        self._mic_on = False

        self.timer = QTimer()
        self.timer.setInterval(1000)
        self.timer.timeout.connect(self._tick)

        self._build_ui()

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setSpacing(6)
        layout.setContentsMargins(12, 10, 12, 10)

        # --- Статус микрофона ---
        self.status_label = QLabel("🎙 Статус: инициализация...")
        self.status_label.setStyleSheet(
            "background:#e9ecef; border-radius:6px; padding:4px 8px; font-size:12px; color:#495057;"
        )
        layout.addWidget(self.status_label)

        # --- Кнопка микрофона ---
        self.btn_mic = QPushButton("🎙 Включить микрофон")
        self.btn_mic.setCheckable(True)
        self.btn_mic.setStyleSheet(
            "background:#6c757d; color:white; border-radius:6px; padding:7px 14px; font-size:13px;"
        )
        self.btn_mic.clicked.connect(self._toggle_mic)
        layout.addWidget(self.btn_mic)

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
        self.topic_label.setStyleSheet("font-weight: bold; font-size: 15px; color: #2a6496;")
        layout.addWidget(self.topic_label)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(sep)

        # --- Список вопросов ---
        list_label = QLabel("Что спросить:")
        list_label.setStyleSheet("font-weight: bold;")
        layout.addWidget(list_label)

        self.questions_list = QListWidget()
        self.questions_list.setWordWrap(True)
        self.questions_list.setSpacing(4)
        self.questions_list.setStyleSheet("""
            QListWidget { background: #f8f9fa; border: 1px solid #dee2e6; border-radius: 6px; }
            QListWidget::item { padding: 6px 8px; border-bottom: 1px solid #e9ecef; }
            QListWidget::item:selected { background: #d1ecf1; color: #0c5460; }
        """)
        layout.addWidget(self.questions_list, stretch=1)

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

        sep2 = QFrame()
        sep2.setFrameShape(QFrame.Shape.HLine)
        sep2.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(sep2)

        # --- Таймер ---
        timer_label = QLabel("Таймер консультации:")
        timer_label.setStyleSheet("font-weight: bold;")
        layout.addWidget(timer_label)

        timer_row = QHBoxLayout()
        self.duration_spin = QSpinBox()
        self.duration_spin.setRange(5, 120)
        self.duration_spin.setValue(30)
        self.duration_spin.setSuffix(" мин")
        self.duration_spin.setFixedWidth(90)
        self.duration_spin.valueChanged.connect(self._set_duration)
        timer_row.addWidget(QLabel("Длительность:"))
        timer_row.addWidget(self.duration_spin)
        timer_row.addStretch()
        layout.addLayout(timer_row)

        self.timer_display = QLabel("30:00")
        self.timer_display.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.timer_display.setStyleSheet(
            "font-size: 36px; font-weight: bold; color: #28a745; letter-spacing: 2px;"
        )
        layout.addWidget(self.timer_display)

        btn_row = QHBoxLayout()
        self.btn_start = QPushButton("▶ Старт")
        self.btn_start.setStyleSheet("background:#28a745; color:white; border-radius:6px; padding:6px 14px;")
        self.btn_start.clicked.connect(self._start_timer)

        self.btn_pause = QPushButton("⏸ Пауза")
        self.btn_pause.setStyleSheet("background:#ffc107; color:#333; border-radius:6px; padding:6px 14px;")
        self.btn_pause.clicked.connect(self._pause_timer)

        self.btn_reset = QPushButton("↺ Сброс")
        self.btn_reset.setStyleSheet("background:#6c757d; color:white; border-radius:6px; padding:6px 14px;")
        self.btn_reset.clicked.connect(self._reset_timer)

        self.btn_add10 = QPushButton("+10 мин")
        self.btn_add10.setStyleSheet("background:#17a2b8; color:white; border-radius:6px; padding:6px 14px;")
        self.btn_add10.clicked.connect(self._add_10min)

        for btn in (self.btn_start, self.btn_pause, self.btn_reset, self.btn_add10):
            btn_row.addWidget(btn)
        layout.addLayout(btn_row)

        self._apply_font()

    def _toggle_mic(self, checked: bool):
        self._mic_on = checked
        if checked:
            self.btn_mic.setText("🔴 Микрофон включён — нажми чтобы выключить")
            self.btn_mic.setStyleSheet(
                "background:#dc3545; color:white; border-radius:6px; padding:7px 14px; font-size:13px;"
            )
        else:
            self.btn_mic.setText("🎙 Включить микрофон")
            self.btn_mic.setStyleSheet(
                "background:#6c757d; color:white; border-radius:6px; padding:7px 14px; font-size:13px;"
            )
        self.mic_toggled.emit(checked)

    @pyqtSlot(str)
    def set_mic_status(self, status: str):
        styles = {
            "init":        ("⏳ Инициализация микрофона...", "#fff3cd", "#856404"),
            "ready":       ("✅ Микрофон готов. Нажми «Включить микрофон»", "#d4edda", "#155724"),
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

    @pyqtSlot()
    def _tick(self):
        if self.remaining_seconds > 0:
            self.remaining_seconds -= 1
            self._refresh_timer_display()
        else:
            self.timer.stop()
            self.timer_running = False
            self.timer_display.setText("00:00")
            self.timer_display.setStyleSheet(
                "font-size: 36px; font-weight: bold; color: #dc3545; letter-spacing: 2px;"
            )

    def _refresh_timer_display(self):
        m, s = divmod(self.remaining_seconds, 60)
        self.timer_display.setText(f"{m:02d}:{s:02d}")
        if self.remaining_seconds <= 300:
            color = "#dc3545"
        elif self.remaining_seconds <= 600:
            color = "#fd7e14"
        else:
            color = "#28a745"
        self.timer_display.setStyleSheet(
            f"font-size: 36px; font-weight: bold; color: {color}; letter-spacing: 2px;"
        )

    def _start_timer(self):
        if not self.timer_running:
            self.timer_running = True
            self.timer.start()

    def _pause_timer(self):
        self.timer.stop()
        self.timer_running = False

    def _reset_timer(self):
        self.timer.stop()
        self.timer_running = False
        self.remaining_seconds = self.duration_seconds
        self._refresh_timer_display()

    def _add_10min(self):
        self.remaining_seconds += 600
        self._refresh_timer_display()

    def _set_duration(self, minutes: int):
        self.duration_seconds = minutes * 60
        self.remaining_seconds = self.duration_seconds
        self._refresh_timer_display()

    def _apply_font(self):
        font = self.font_combo.currentFont()
        font.setPointSize(self.font_size.value())
        self.questions_list.setFont(font)

    @pyqtSlot(str, list)
    def update_content(self, topic: str, questions: list):
        self.topic_label.setText(f"Тема: {topic.upper()}")
        self.questions_list.clear()
        for i, q in enumerate(questions, 1):
            item = QListWidgetItem(f"{i}. {q}")
            self.questions_list.addItem(item)
