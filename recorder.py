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
            shutil.move(temp_wav, filename)
            print(f"Файл {filename} успешно создан.")
        else:
            # Формируем команду для ffmpeg
            command = []
            if self.compression == "mp3":
                # Проверяем, доступен ли кодек libmp3lame
                result = subprocess.run(
                    ["ffmpeg", "-codecs"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True
                )
                if "libmp3lame" not in result.stdout:
                    raise RuntimeError("Кодек libmp3lame не найден. Установите ffmpeg с поддержкой MP3.")

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