import pyaudio
import wave
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import threading
import time
from datetime import datetime
import struct
from queue import Queue
import subprocess
import os
import shutil  # Для перемещения файлов между дисками

class AudioRecorder:
    def __init__(self):
        self.is_recording = False
        self.is_paused = False
        self.stream = None
        self.audio = None
        self.frames = []  # Буфер для хранения всех аудиоданных
        self.start_time = None
        self.microphone_level = 0
        self.save_queue = Queue(maxsize=10)
        self.save_thread = threading.Thread(target=self.process_save_queue, daemon=True)
        self.save_thread.start()

        # Настройки по умолчанию
        self.sample_rate = 44100  # Частота дискретизации
        self.bit_depth = pyaudio.paInt16  # Битрейт
        self.compression = "wav"  # Формат сжатия (wav, mp3, aac, opus, g726)
        self.quality = "128k"  # Качество по умолчанию
        self.save_interval = 1  # Интервал записи в минутах

    def save_audio_file(self, filename, frames, channels):
        """Сохраняет аудиофайл в выбранном формате."""
        temp_wav = "temp.wav"
        try:
            # Сначала сохраняем в WAV
            with wave.open(temp_wav, 'wb') as wf:
                wf.setnchannels(channels)
                wf.setsampwidth(self.audio.get_sample_size(self.bit_depth))
                wf.setframerate(self.sample_rate)
                wf.writeframes(b''.join(frames))

            if self.compression == "wav":
                # Используем shutil.move для перемещения файла
                shutil.move(temp_wav, filename)
                print(f"Файл {filename} успешно создан.")
            else:
                # Конвертируем в нужный формат с помощью ffmpeg
                if self.compression == "mp3":
                    command = [
                        "ffmpeg", "-y", "-i", temp_wav,
                        "-acodec", "libmp3lame", "-b:a", self.quality, filename
                    ]
                elif self.compression == "aac":
                    command = [
                        "ffmpeg", "-y", "-i", temp_wav,
                        "-acodec", "aac", "-b:a", self.quality, filename
                    ]
                elif self.compression == "opus":
                    command = [
                        "ffmpeg", "-y", "-i", temp_wav,
                        "-acodec", "libopus", "-b:a", self.quality, filename
                    ]
                elif self.compression == "g726":
                    command = [
                        "ffmpeg", "-y", "-i", temp_wav,
                        "-ar", "8000", "-acodec", "g726", "-b:a", self.quality, "-f", "wav", filename
                    ]
                else:
                    raise ValueError(f"Неизвестный формат сжатия: {self.compression}")

                # Выполняем команду
                print(f"Выполняется команда: {' '.join(command)}")
                result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                if result.returncode != 0:
                    print(f"Ошибка при выполнении команды: {result.stderr.decode()}")
                else:
                    print(f"Файл {filename} успешно создан.")
        except Exception as e:
            print(f"Ошибка при сохранении файла: {e}")
        finally:
            if os.path.exists(temp_wav):
                os.remove(temp_wav)

    def process_save_queue(self):
        """Обрабатывает очередь сохранения файлов."""
        while True:
            if not self.save_queue.empty():
                filename, frames, channels = self.save_queue.get()
                self.save_audio_file(filename, frames, channels)
                self.save_queue.task_done()
            time.sleep(0.1)

    def check_microphone_available(self):
        """Проверяет, доступен ли микрофон."""
        try:
            audio = pyaudio.PyAudio()
            stream = audio.open(format=self.bit_depth, channels=1, rate=self.sample_rate, input=True, frames_per_buffer=1024)
            stream.close()
            audio.terminate()
            return True
        except Exception as e:
            print(f"Микрофон недоступен: {e}")
            return False

    def record_audio(self, output_folder, chunk_size=1024):
        """Записывает аудио с микрофона и сохраняет его в файлы."""
        try:
            self.audio = pyaudio.PyAudio()
            format = self.bit_depth
            channels = 1

            self.stream = self.audio.open(format=format,
                                         channels=channels,
                                         rate=self.sample_rate,
                                         input=True,
                                         frames_per_buffer=chunk_size,
                                         start=False)

            self.stream.start_stream()

            self.frames.clear()  # Очищаем буфер перед началом записи
            print("Запись началась...")
            part_number = 1
            self.start_time = datetime.now()

            while self.is_recording:
                if self.is_paused:
                    time.sleep(0.1)
                    continue

                part_start_time = datetime.now()
                part_frames = []
                while (datetime.now() - part_start_time).total_seconds() < self.save_interval * 60:
                    if not self.is_recording or self.is_paused:
                        break
                    try:
                        data = self.stream.read(chunk_size, exception_on_overflow=False)
                        part_frames.append(data)
                        self.frames.append(data)  # Добавляем данные в общий буфер

                        # Обновление уровня микрофона
                        audio_data = struct.unpack(f"{chunk_size}h", data)
                        self.microphone_level = max(abs(sample) for sample in audio_data) / 32768

                    except Exception as e:
                        print(f"Ошибка при чтении данных: {e}")
                        break

                if self.is_recording and part_frames and not self.is_paused:
                    part_end_time = datetime.now()
                    duration = int((part_end_time - part_start_time).total_seconds())
                    part_filename = f"{output_folder}/recorded_audio_part{part_number}_{self.start_time.strftime('%Y-%m-%d_%H-%M-%S')}_to_{part_end_time.strftime('%H-%M-%S')}_{duration}s.{self.compression}"
                    print(f"Создан файл: {part_filename}")
                    self.save_queue.put((part_filename, part_frames.copy(), channels))
                    part_number += 1

        except Exception as e:
            print(f"Ошибка при записи аудио: {e}")
        finally:
            if self.stream:
                self.stream.stop_stream()
                self.stream.close()
            if self.audio:
                self.audio.terminate()

            # Сохраняем последний файл, если запись была остановлена
            if not self.is_recording and self.frames:
                end_time = datetime.now()
                duration = int((end_time - self.start_time).total_seconds())
                output_filename = f"{output_folder}/recorded_audio_final_{self.start_time.strftime('%Y-%m-%d_%H-%M-%S')}_to_{end_time.strftime('%H-%M-%S')}_{duration}s.{self.compression}"
                print(f"Создан финальный файл: {output_filename}")
                self.save_queue.put((output_filename, self.frames.copy(), channels))

def update_microphone_level():
    """Обновляет шкалу уровня микрофона."""
    if recorder.is_recording and not recorder.is_paused:
        level = int(recorder.microphone_level * 100)
        microphone_level_bar['value'] = level
        root.after(100, update_microphone_level)

def update_timer():
    """Обновляет таймер."""
    if recorder.is_recording and recorder.start_time and not recorder.is_paused:
        elapsed_time = datetime.now() - recorder.start_time
        days = elapsed_time.days
        hours, remainder = divmod(elapsed_time.seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        milliseconds = elapsed_time.microseconds // 1000
        timer_label.config(text=f"{days}:{hours:02}:{minutes:02}:{seconds:02}.{milliseconds:03}")
    if recorder.is_recording:
        root.after(50, update_timer)

def start_recording():
    """Начинает запись."""
    if not recorder.check_microphone_available():
        messagebox.showerror("Ошибка", "Микрофон недоступен!")
        return

    folder_path = filedialog.askdirectory()
    if not folder_path:
        messagebox.showerror("Ошибка", "Папка не выбрана!")
        return

    print(f"Выбранная папка: {folder_path}")
    recorder.is_recording = True
    recorder.is_paused = False
    recorder.frames.clear()  # Очищаем буфер перед началом записи
    recorder.start_time = datetime.now()
    threading.Thread(target=recorder.record_audio, args=(folder_path,), daemon=True).start()
    update_indicator()
    update_timer()
    update_microphone_level()

def pause_recording():
    """Ставит запись на паузу или возобновляет её."""
    if recorder.is_recording:
        if recorder.is_paused:
            recorder.is_paused = False
            pause_button.config(text="Пауза")
            print("Запись возобновлена.")
        else:
            recorder.is_paused = True
            pause_button.config(text="Продолжить")
            print("Запись на паузе.")
    update_indicator()

def stop_recording():
    """Останавливает запись."""
    recorder.is_recording = False
    recorder.is_paused = False
    print("Запись остановлена.")
    update_indicator()

def update_indicator():
    """Обновляет индикатор записи."""
    if recorder.is_recording:
        if recorder.is_paused:
            indicator_canvas.itemconfig(indicator, fill="#FFA500")  # Оранжевый кружок при паузе
        else:
            indicator_canvas.itemconfig(indicator, fill="#FF4444")  # Красный кружок при записи
    else:
        indicator_canvas.itemconfig(indicator, fill="#44FF44")  # Зеленый кружок при остановке

def update_quality_options(*args):
    """Обновляет доступные варианты качества в зависимости от выбранного кодека."""
    compression = compression_var.get()
    if compression == "wav":
        quality_menu.config(values=["16-bit", "24-bit"])
        quality_var.set("16-bit")
    elif compression == "mp3":
        quality_menu.config(values=["128k", "192k", "320k"])
        quality_var.set("128k")
    elif compression == "aac":
        quality_menu.config(values=["128k", "192k", "256k"])
        quality_var.set("128k")
    elif compression == "opus":
        quality_menu.config(values=["64k", "96k", "128k"])
        quality_var.set("96k")
    elif compression == "g726":
        quality_menu.config(values=["16k", "24k", "32k", "40k"])
        quality_var.set("32k")

def open_settings():
    """Открывает окно настроек."""
    global quality_menu, compression_var, quality_var

    settings_window = tk.Toplevel(root)
    settings_window.title("Настройки")
    settings_window.geometry("300x300")
    settings_window.configure(bg="#1E1E1E")

    # Выбор интервала записи
    interval_label = tk.Label(settings_window, text="Интервал записи (мин):", bg="#1E1E1E", fg="#FFFFFF")
    interval_label.pack(pady=5)
    interval_var = tk.IntVar(value=recorder.save_interval)
    interval_menu = ttk.Combobox(settings_window, textvariable=interval_var, values=[1, 3, 5, 15, 30], width=10)
    interval_menu.pack(pady=5)

    # Выбор качества записи
    quality_label = tk.Label(settings_window, text="Качество записи:", bg="#1E1E1E", fg="#FFFFFF")
    quality_label.pack(pady=5)
    quality_var = tk.StringVar(value=recorder.quality)
    quality_menu = ttk.Combobox(settings_window, textvariable=quality_var, width=10)
    quality_menu.pack(pady=5)

    # Выбор компрессии
    compression_label = tk.Label(settings_window, text="Формат сжатия:", bg="#1E1E1E", fg="#FFFFFF")
    compression_label.pack(pady=5)
    compression_var = tk.StringVar(value=recorder.compression)
    compression_menu = ttk.Combobox(settings_window, textvariable=compression_var, values=["wav", "mp3", "aac", "opus", "g726"], width=10)
    compression_menu.pack(pady=5)

    # Обновляем варианты качества при изменении кодека
    compression_var.trace("w", update_quality_options)
    update_quality_options()  # Инициализация начальных значений

    def save_settings():
        """Сохраняет настройки."""
        recorder.save_interval = interval_var.get()
        recorder.quality = quality_var.get()
        recorder.compression = compression_var.get()
        settings_window.destroy()
        print("Настройки сохранены.")

    save_button = tk.Button(settings_window, text="Сохранить", command=save_settings, bg="#333333", fg="#FFFFFF")
    save_button.pack(pady=10)

# Создание графического интерфейса
root = tk.Tk()
root.title("Запись звука")
root.geometry("550x250")  # Увеличили окно для кнопки настроек
root.configure(bg="#1E1E1E")

button_style = {
    "bg": "#333333",
    "fg": "#FFFFFF",
    "activebackground": "#555555",
    "activeforeground": "#FFFFFF",
    "borderwidth": 0,
    "font": ("Arial", 12),
    "width": 10,
}

button_frame = tk.Frame(root, bg="#1E1E1E")
button_frame.pack(pady=10)

record_button = tk.Button(button_frame, text="Начать", command=start_recording, **button_style)
record_button.pack(side="left", padx=10)

pause_button = tk.Button(button_frame, text="Пауза", command=pause_recording, **button_style)
pause_button.pack(side="left", padx=10)

stop_button = tk.Button(button_frame, text="Остановить", command=stop_recording, **button_style)
stop_button.pack(side="left", padx=10)

settings_button = tk.Button(button_frame, text="Настройки", command=open_settings, **button_style)
settings_button.pack(side="left", padx=10)

indicator_canvas = tk.Canvas(button_frame, width=30, height=30, bg="#1E1E1E", highlightthickness=0)
indicator_canvas.pack(side="left", padx=10)
indicator = indicator_canvas.create_oval(5, 5, 25, 25, fill="#44FF44")

microphone_level_label = tk.Label(root, text="Уровень микрофона:", bg="#1E1E1E", fg="#FFFFFF", font=("Arial", 12))
microphone_level_label.pack(pady=5)
microphone_level_bar = ttk.Progressbar(root, orient="horizontal", length=400, mode="determinate")
microphone_level_bar.pack(pady=5)

timer_label = tk.Label(root, text="0:00:00:00.000", bg="#1E1E1E", fg="#FFFFFF", font=("Arial", 16))
timer_label.pack(pady=10)

recorder = AudioRecorder()

root.mainloop()