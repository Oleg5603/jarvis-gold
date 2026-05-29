import sys
import time
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QThread, pyqtSignal
import speech_recognition as sr

from window_questions import QuestionsWindow
from window_tips import TipsWindow
from knowledge_base import find_topics, get_content


class SpeechThread(QThread):
    words_detected = pyqtSignal(str)
    status_changed = pyqtSignal(str)   # "init" | "ready" | "listening" | "error:<msg>"
    listening_toggle = pyqtSignal(bool)

    def __init__(self):
        super().__init__()
        self.running = True
        self.active = False
        self.recognizer = sr.Recognizer()
        self.recognizer.energy_threshold = 300
        self.recognizer.dynamic_energy_threshold = True

    def set_active(self, value: bool):
        self.active = value
        if not value:
            self.status_changed.emit("paused")

    def run(self):
        self.status_changed.emit("init")
        try:
            mic = sr.Microphone()
        except Exception as e:
            self.status_changed.emit(f"error:Микрофон не найден: {e}")
            return

        try:
            with mic as source:
                self.status_changed.emit("init")
                self.recognizer.adjust_for_ambient_noise(source, duration=1)
                self.status_changed.emit("ready")
                while self.running:
                    if not self.active:
                        time.sleep(0.3)
                        continue
                    try:
                        self.status_changed.emit("listening")
                        audio = self.recognizer.listen(source, timeout=3, phrase_time_limit=8)
                        self.status_changed.emit("recognizing")
                        text = self.recognizer.recognize_google(audio, language="ru-RU")
                        self.words_detected.emit(text.lower())
                        self.status_changed.emit("listening")
                    except sr.WaitTimeoutError:
                        self.status_changed.emit("listening")
                    except sr.UnknownValueError:
                        self.status_changed.emit("listening")
                    except sr.RequestError as e:
                        self.status_changed.emit(f"error:Нет интернета или ошибка Google: {e}")
                        time.sleep(3)
                        self.status_changed.emit("listening")
                    except Exception as e:
                        self.status_changed.emit(f"error:{e}")
                        time.sleep(1)
                        self.status_changed.emit("listening")
        except Exception as e:
            self.status_changed.emit(f"error:Ошибка микрофона: {e}")

    def stop(self):
        self.running = False
        self.active = False


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    questions_win = QuestionsWindow()
    tips_win = TipsWindow()

    questions_win.show()
    tips_win.show()

    speech_thread = SpeechThread()

    def on_words(text: str):
        questions_win.log_recognized(text)
        tips_win.log_recognized(text)
        topics = find_topics(text)
        if not topics:
            return
        content = get_content(topics)
        topic_display = ", ".join(topics)
        questions_win.update_content(topic_display, content["questions"])
        tips_win.update_content(topic_display, content["recommendations"])

    def on_status(status: str):
        questions_win.set_mic_status(status)
        tips_win.set_mic_status(status)

    speech_thread.words_detected.connect(on_words)
    speech_thread.status_changed.connect(on_status)

    # Start/stop listening controlled by questions window button
    questions_win.mic_toggled.connect(speech_thread.set_active)

    speech_thread.start()

    ret = app.exec()
    speech_thread.stop()
    speech_thread.wait()
    sys.exit(ret)


if __name__ == "__main__":
    main()
