"""
Project: LoLLMs
Author: ParisNeo
Description: Media classes:
    - WebcamImageSender: is a captures images from the webcam and sends them to a SocketIO client.
    - MusicPlayer: is a MusicPlayer class that allows you to play music using pygame library.
License: Apache 2.0
"""
from lollms.utilities import PackageManager
from lollms.com import LoLLMsCom
from lollms.utilities import trace_exception, run_async
from lollms.types import MSG_TYPE, SENDER_TYPES
from lollms.client_session import Session
from ascii_colors import ASCIIColors
import platform
from functools import partial
import subprocess
from collections import deque

import os
import threading

if not PackageManager.check_package_installed("cv2"):
    if platform.system() == "Darwin":
        os.system('brew install opencv')
    elif platform.system() == "Windows":
        os.system('pip install opencv-python')
    else:
        os.system('pip install opencv-python')
        # os.system('sudo apt-get update')
        # os.system('sudo apt-get install libgl1-mesa-glx python3-opencv -y')
        # os.system('pip install opencv-python')
try:
    import cv2
except:
    ASCIIColors.error("Couldn't install opencv!")


if not PackageManager.check_package_installed("scipy"):
    PackageManager.install_package("scipy")
    from scipy import signal
from scipy import signal

if not PackageManager.check_package_installed("matplotlib"):
    PackageManager.install_package("matplotlib")
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use('Agg')

if not PackageManager.check_package_installed("whisper"):
    PackageManager.install_package("openai-whisper")
    try:
        import conda.cli
        conda.cli.main("install", "conda-forge::ffmpeg", "-y")
    except:
        ASCIIColors.bright_red("Couldn't install ffmpeg. whisper won't work. Please install it manually")

import whisper

import socketio
from lollms.com import LoLLMsCom
try:
    if not PackageManager.check_package_installed("sounddevice"):
        # os.system("sudo apt-get install portaudio19-dev")
        PackageManager.install_package("sounddevice")
        PackageManager.install_package("wave")
except:
    # os.system("sudo apt-get install portaudio19-dev -y")
    PackageManager.install_package("sounddevice")
    PackageManager.install_package("wave")
try:
    import sounddevice as sd
    import wave
except:
    ASCIIColors.error("Couldn't load sound tools")

import time
import base64
import io
import socketio
from scipy.io.wavfile import write
from matplotlib import pyplot as plt
import numpy as np
from scipy.signal import spectrogram
from pathlib import Path

from lollms.app import LollmsApplication
from lollms.tasks import TasksLibrary
from lollms.tts import LollmsTTS
from lollms.personality import AIPersonality
from lollms.function_call import FunctionCalling_Library
from lollms.client_session import Client
from datetime import datetime

import math

class RTCom:
    def __init__(
                        self, 
                        lc:LollmsApplication, 
                        sio:socketio.Client,  
                        personality:AIPersonality,
                        client:Client,
                        threshold=1000, 
                        silence_duration=2, 
                        sound_threshold_percentage=10, 
                        gain=1.0, 
                        rate=44100, 
                        channels=1, 
                        buffer_size=10, 
                        model="small.en", 
                        snd_input_device=None,
                        snd_output_device=None,
                        logs_folder="logs", 
                        voice=None, 
                        block_while_talking=True, 
                        context_size=4096
                    ):
        self.sio = sio
        self.lc = lc
        self.client = client
        self.tts = LollmsTTS(self.lc)
        self.tl = TasksLibrary(self.lc)

        self.block_listening = False
        if not voice:
            voices = self.get_voices()
            voice = voices[0]
        self.voice = voice
        self.context_size = context_size
        self.personality = personality
        self.rate = rate
        self.channels = channels
        self.threshold = threshold
        self.silence_duration = silence_duration
        self.buffer_size = buffer_size
        self.gain = gain
        self.sound_threshold_percentage = sound_threshold_percentage
        self.block_while_talking = block_while_talking
        self.image_shot = None

        if snd_input_device is None:
            devices = sd.query_devices()
            snd_input_device = [device['name'] for device in devices  if device["max_input_channels"]>0][0]
        if snd_output_device is None:
            devices = sd.query_devices()
            snd_output_device = [device['name'] for device in devices  if device["max_output_channels"]>0][0]

        self.snd_input_device = snd_input_device
        self.snd_output_device = snd_output_device
        self.logs_folder = Path(logs_folder)

        self.logs_folder.mkdir(exist_ok=True, parents=True)

        self.frames = []
        self.silence_counter = 0
        self.current_silence_duration = 0
        self.longest_silence_duration = 0
        self.sound_frames = 0
        self.audio_values = []

        self.max_audio_value = 0
        self.min_audio_value = 0
        self.total_frames = 0  # Initialize total_frames

        self.file_index = 0
        self.recording = False
        self.stop_flag = False

        self.buffer = deque(maxlen=buffer_size)
        self.transcribed_files = deque()
        self.buffer_lock = threading.Condition()
        self.transcribed_lock = threading.Condition()
        self.lc.ShowBlockingMessage("Loading whisper...")
        ASCIIColors.info("Loading whisper...", end="",flush=True)

        self.model = model
        self.whisper = whisper.load_model(model)
        self.lc.HideBlockingMessage()
        ASCIIColors.success("OK")
    
    def get_date_time(self):
        now = datetime.now()
        return now.strftime("%Y-%m-%d %H:%M:%S")        
    
    def calculator_function(self, expression: str) -> float:
        try:
            # Add the math module functions to the local namespace
            allowed_names = {k: v for k, v in math.__dict__.items() if not k.startswith("__")}
            
            # Evaluate the expression safely using the allowed names
            result = eval(expression, {"__builtins__": None}, allowed_names)
            return result
        except Exception as e:
            return str(e)
        
    def take_a_photo(self):
        return "Couldn't take a photo"


    def start_recording(self):
        self.recording = True
        self.stop_flag = False

        self.recording_thread = threading.Thread(target=self._record)
        self.transcription_thread = threading.Thread(target=self._process_files)
        self.recording_thread.start()
        self.transcription_thread.start()

    def stop_recording(self):
        self.recording = False
        self.stop_flag = True
        ASCIIColors.green("<<RTCOM off>>")

    def _record(self):
        with sd.InputStream(channels=self.channels, device=self.snd_input_device, samplerate=self.rate, callback=self.callback, dtype='int16'):
            while not self.stop_flag:
                time.sleep(1)

        if self.frames:
            self._save_wav(self.frames)
        self.recording = False

        # self._save_histogram(self.audio_values)

    def callback(self, indata, frames, time, status):
        if not self.block_listening:
            audio_data = np.frombuffer(indata, dtype=np.int16)
            max_value = np.max(audio_data)
            min_value = np.min(audio_data)

            if max_value > self.max_audio_value:
                self.max_audio_value = max_value
            if min_value < self.min_audio_value:
                self.min_audio_value = min_value

            self.audio_values.extend(audio_data)

            self.total_frames += frames
            if max_value < self.threshold:
                self.silence_counter += 1
                self.current_silence_duration += frames
            else:
                self.silence_counter = 0
                self.current_silence_duration = 0
                self.sound_frames += frames

            if self.current_silence_duration > self.longest_silence_duration:
                self.longest_silence_duration = self.current_silence_duration

            if self.silence_counter > (self.rate / frames) * self.silence_duration:
                ASCIIColors.red("Silence counter reached threshold")
                trimmed_frames = self._trim_silence(self.frames)
                sound_percentage = self._calculate_sound_percentage(trimmed_frames)
                ASCIIColors.red(f"Sound percentage {sound_percentage}")
                if sound_percentage >= self.sound_threshold_percentage:
                    self._save_wav(self.frames)
                self.frames = []
                self.silence_counter = 0
                self.total_frames = 0
                self.sound_frames = 0
            else:
                ASCIIColors.red(f"Appending data")
                ASCIIColors.yellow(f"silence_counter: {self.silence_counter}")
                print(f"silence duration: {(self.rate / frames) * self.silence_duration}")
                self.frames.append(indata.copy())
        else:
            self.frames = []
            self.silence_counter = 0
            self.current_silence_duration = 0
            self.longest_silence_duration = 0
            self.sound_frames = 0
            self.audio_values = []

            self.max_audio_value = 0
            self.min_audio_value = 0
            self.total_frames = 0  # Initialize total_frames

    def _apply_gain(self, frames):
        audio_data = np.frombuffer(b''.join(frames), dtype=np.int16)
        audio_data = audio_data * self.gain
        audio_data = np.clip(audio_data, -32768, 32767)
        return audio_data.astype(np.int16).tobytes()

    def _trim_silence(self, frames):
        audio_data = np.frombuffer(b''.join(frames), dtype=np.int16)
        non_silent_indices = np.where(np.abs(audio_data) >= self.threshold)[0]

        if non_silent_indices.size:
            start_index = max(non_silent_indices[0] - self.rate, 0)
            end_index = min(non_silent_indices[-1] + self.rate, len(audio_data))
            trimmed_data = audio_data[start_index:end_index]
        else:
            trimmed_data = np.array([], dtype=np.int16)

        return trimmed_data.tobytes()

    def _calculate_sound_percentage(self, frames):
        audio_data = np.frombuffer(frames, dtype=np.int16)
        num_bins = len(audio_data) // self.rate
        sound_count = 0

        for i in range(num_bins):
            bin_data = audio_data[i * self.rate: (i + 1) * self.rate]
            if np.max(bin_data) >= self.threshold:
                sound_count += 1

        sound_percentage = (sound_count / num_bins) * 100 if num_bins > 0 else 0
        return sound_percentage

    def _save_wav(self, frames):
        ASCIIColors.green("<<SEGMENT_RECOVERED>>")
        # Todo annouce
        # self.transcription_signal.update_status.emit("Segment detected and saved")
        filename = f"recording_{self.file_index}.wav"
        self.file_index += 1

        amplified_frames = self._apply_gain(frames)
        trimmed_frames = self._trim_silence([amplified_frames])
        logs_file = Path(self.logs_folder)/filename
        logs_file.parent.mkdir(exist_ok=True, parents=True)

        wf = wave.open(str(logs_file), 'wb')
        wf.setnchannels(self.channels)
        wf.setsampwidth(2)
        wf.setframerate(self.rate)
        wf.writeframes(trimmed_frames)
        wf.close()

        with self.buffer_lock:
            while len(self.buffer) >= self.buffer.maxlen:
                self.buffer_lock.wait()
            self.buffer.append(filename)
            self.buffer_lock.notify()

    def _save_histogram(self, audio_values):
        plt.hist(audio_values, bins=50, edgecolor='black')
        plt.title('Histogram of Audio Values')
        plt.xlabel('Audio Value')
        plt.ylabel('Frequency')
        plt.savefig('audio_values_histogram.png')
        plt.close()

    def fix_string_for_xtts(self, input_string):
        # Remove excessive exclamation marks
        fixed_string = input_string.rstrip('!')
        
        return fixed_string
    
    def _process_files(self):
        while not self.stop_flag:
            with self.buffer_lock:
                while not self.buffer and not self.stop_flag:
                    self.buffer_lock.wait()
                if self.buffer:
                    filename = self.buffer.popleft()
                    self.buffer_lock.notify()
            if self.block_while_talking:
                self.block_listening = True
            try:
                if filename:
                    self.lc.info("Transcribing")
                    ASCIIColors.green("<<TRANSCRIBING>>")
                    wav_file_path = str(Path(self.logs_folder)/filename)
                    ASCIIColors.cyan(f"Logging to : {wav_file_path}")
                    transcription = self.lc.stt.transcribe(wav_file_path)
                    transcription_fn = str(Path(self.logs_folder)/filename) + ".txt"
                    with open(transcription_fn, "w", encoding="utf-8") as f:
                        f.write(transcription)

                    with self.transcribed_lock:
                        self.transcribed_files.append((filename, transcription))
                        self.transcribed_lock.notify()
                    if transcription!="":
                        current_prompt = transcription
                        self.lc.new_block(client_id=self.client.client_id,sender=self.lc.config.user_name, content=current_prompt)
                        ASCIIColors.green("<<RESPONDING>>")
                        self.lc.info("Responding")
                        self.lc.handle_generate_msg(self.client.client_id, {"prompt": current_prompt})
                        while self.lc.busy:
                            time.sleep(0.01)
                        lollms_text = self.fix_string_for_xtts(self.client.generated_text)
                        ASCIIColors.red(" -------------- LOLLMS answer -------------------")
                        ASCIIColors.yellow(lollms_text)
                        ASCIIColors.red(" -------------------------------------------------")
                        self.lc.info("Talking")
                        ASCIIColors.green("<<TALKING>>")
                        self.lc.tts.tts_audio(lollms_text, speaker=self.voice, file_name_or_path=str(Path(self.logs_folder)/filename)+"_answer.wav")
            except Exception as ex:
                trace_exception(ex)
            self.block_listening = False
            ASCIIColors.green("<<LISTENING>>")
            self.lc.info(f"Listening.\nYou can talk to {self.personality.name}")
            # TODO : send the output
            #self.transcription_signal.update_status.emit("Listening")

    def get_voices(self):
        if self.lc.tts and self.lc.tts.ready:
            voices = self.lc.tts.get_voices()  # Assuming the response is in JSON format
            return voices
        return []


class WebcamImageSender:
    """
    Class for capturing images from the webcam and sending them to a SocketIO client.
    """

    def __init__(self, sio:socketio, lollmsCom:LoLLMsCom=None):
        """
        Initializes the WebcamImageSender class.

        Args:
            socketio (socketio.Client): The SocketIO client object.
        """
        self.sio = sio
        self.last_image = None
        self.last_change_time = None
        self.capture_thread = None
        self.is_running = False
        self.lollmsCom = lollmsCom

    def start_capture(self):
        """
        Starts capturing images from the webcam in a separate thread.
        """
        self.is_running = True
        self.capture_thread = threading.Thread(target=self.capture_image)
        self.capture_thread.start()

    def stop_capture(self):
        """
        Stops capturing images from the webcam.
        """
        self.is_running = False
        self.capture_thread.join()

    def capture_image(self):
        """
        Captures images from the webcam, checks if the image content has changed, and sends the image to the client if it remains the same for 3 seconds.
        """
        try:
            cap = cv2.VideoCapture(0)

            while self.is_running:
                ret, frame = cap.read()
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

                if self.last_image is None or self.image_difference(gray) > 2:
                    self.last_image = gray
                    self.last_change_time = time.time()

                _, buffer = cv2.imencode('.jpg', frame)
                image_base64 = base64.b64encode(buffer)
                if self.sio:
                    run_async(partial(self.sio.emit,"video_stream_image", image_base64.decode('utf-8')))

            cap.release()
        except Exception as ex:
            self.lollmsCom.error("Couldn't start webcam")
            trace_exception(ex)

    def image_difference(self, image):
        """
        Calculates the difference between two images using the absolute difference method.

        Args:
            image (numpy.ndarray): The current image.

        Returns:
            int: The sum of pixel intensities representing the difference between the current image and the last image.
        """
        if self.last_image is None:
            return 0

        diff = cv2.absdiff(image, self.last_image)
        diff_sum = diff.sum()

        return diff_sum

class MusicPlayer(threading.Thread):
    """
    MusicPlayer class for playing music using pygame library.

    Attributes:
    - file_path (str): The path of the music file to be played.
    - paused (bool): Flag to indicate if the music is paused.
    - stopped (bool): Flag to indicate if the music is stopped.
    """

    def __init__(self, file_path):
        super().__init__()
        self.file_path = file_path
        self.paused = False
        self.stopped = False

    def run(self):
        """
        The main function that runs in a separate thread to play the music.
        """
        if not PackageManager.check_package_installed("pygame"):
            PackageManager.install_package("pygame")
        import pygame

        pygame.mixer.init()
        pygame.mixer.music.load(self.file_path)
        pygame.mixer.music.play()

        while pygame.mixer.music.get_busy() and not self.stopped:
            if self.paused:
                pygame.mixer.music.pause()
            else:
                pygame.mixer.music.unpause()

    def pause(self):
        """
        Pauses the music.
        """
        self.paused = True

    def resume(self):
        """
        Resumes the paused music.
        """
        self.paused = False

    def stop(self):
        """
        Stops the music.
        """
        import pygame
        self.stopped = True
        pygame.mixer.music.stop()


class RealTimeTranscription:
    def __init__(self, callback):
        if not PackageManager.check_package_installed('pyaudio'):
            try:
                import conda.cli
                conda.cli.main("install", "anaconda::pyaudio", "-y")
            except:
                ASCIIColors.bright_red("Couldn't install pyaudio. whisper won't work. Please install it manually")
        import pyaudio
        # Initialize Whisper ASR
        print("Loading whisper ...", end="")
        self.whisper = whisper.load_model("base")
        print("ok")

        # Set up PyAudio
        self.p = pyaudio.PyAudio()
        self.stream = self.p.open(format=pyaudio.paInt16, channels=1, rate=16000, input=True, frames_per_buffer=1024)

        # Set the callback
        self.callback = callback

    def start(self):
        import torch
        # Start the stream
        self.stream.start_stream()

        try:
            while True:
                # Read a chunk of audio data
                data = self.stream.read(1024)

                # Convert bytes to numpy array
                data_np = np.frombuffer(data, dtype=np.int16)
                # Convert numpy array to float tensor
                data_tensor = torch.tensor(data_np).float()
                # Send the chunk to Whisper for transcription
                result = self.whisper.transcribe(data_tensor)
                
                # If the result is not empty, call the callback
                if result:
                    self.callback(transcription)
        except KeyboardInterrupt:
            # If the user hits Ctrl+C, stop the stream
            self.stop()

    def stop(self):
        # Stop the stream and clean up
        self.stream.stop_stream()
        self.stream.close()
        self.p.terminate()
