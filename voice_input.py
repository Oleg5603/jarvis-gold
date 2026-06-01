import whisper
import sounddevice as sd
import numpy as np
import pyperclip
import keyboard
import time

SAMPLE_RATE = 16000

print("Загрузка модели Whisper tiny...")
model = whisper.load_model("small")
print("Готово!")
print("=" * 40)
print("F9 = начать запись")
print("F10 = остановить и распознать")
print("F12 = выход")
print("=" * 40)

recording = False
audio_data = []

def audio_callback(indata, frames, time_info, status):
    if recording:
        audio_data.append(indata.copy())

with sd.InputStream(samplerate=SAMPLE_RATE, channels=1, callback=audio_callback):
    while True:
        if keyboard.is_pressed("F12"):
            print("Выход.")
            break

        if keyboard.is_pressed("F9") and not recording:
            recording = True
            audio_data = []
            print(">>> Запись...")
            time.sleep(0.3)

        if keyboard.is_pressed("F10") and recording:
            recording = False
            print(">>> Распознаю...")

            if audio_data:
                audio = np.concatenate(audio_data, axis=0).flatten().astype(np.float32)
                result = model.transcribe(audio, language="ru", fp16=False)
                text = result["text"].strip()

                if text:
                    print(f">>> {text}")
                    pyperclip.copy(text)
                    keyboard.send("ctrl+v")
                else:
                    print(">>> Не распознано")
            else:
                print(">>> Нет аудио")
            time.sleep(0.3)

        time.sleep(0.05)
