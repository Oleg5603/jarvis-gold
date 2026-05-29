import sys
import time
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QThread, pyqtSignal
import speech_recognition as sr

from window_questions import QuestionsWindow
from window_tips import TipsWindow
from knowledge_base import KNOWLEDGE_BASE, find_topics, get_content


class SpeechThread(QThread):
    words_detected = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.running = True
        self.recognizer = sr.Recognizer()
        self.recognizer.energy_threshold = 300
        self.recognizer.dynamic_energy_threshold = True

    def run(self):
        with sr.Microphone() as source:
            self.recognizer.adjust_for_ambient_noise(source, duration=1)
            while self.running:
                try:
                    audio = self.recognizer.listen(source, timeout=3, phrase_time_limit=8)
                    text = self.recognizer.recognize_google(audio, language="ru-RU")
                    self.words_detected.emit(text.lower())
                except sr.WaitTimeoutError:
                    pass
                except sr.UnknownValueError:
                    pass
                except Exception:
                    time.sleep(1)

    def stop(self):
        self.running = False


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    questions_win = QuestionsWindow()
    tips_win = TipsWindow()

    questions_win.show()
    tips_win.show()

    speech_thread = SpeechThread()

    def on_words(text: str):
        topics = find_topics(text)
        if not topics:
            return
        content = get_content(topics)
        topic_display = ", ".join(topics)
        questions_win.update_content(topic_display, content["questions"])
        tips_win.update_content(topic_display, content["recommendations"])

    speech_thread.words_detected.connect(on_words)
    speech_thread.start()

    ret = app.exec()
    speech_thread.stop()
    speech_thread.wait()
    sys.exit(ret)


if __name__ == "__main__":
    main()
