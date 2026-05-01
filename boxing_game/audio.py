import shutil
import subprocess
import threading
import time
from pathlib import Path


class AudioManager:
    def __init__(self, root=None):
        self.root = Path(root or Path(__file__).resolve().parent / "assets" / "audio")
        self.afplay = shutil.which("afplay")
        self.loop_process = None
        self.loop_stop = threading.Event()
        self.loop_thread = None
        self.last_played = {}

    def is_available(self):
        return self.afplay is not None and self.root.exists()

    def resolve(self, *parts):
        path = self.root.joinpath(*parts)
        return path if path.exists() else None

    def play_sfx(self, relative_path, throttle=0.0):
        if not self.is_available():
            return
        now = time.time()
        last = self.last_played.get(relative_path, 0.0)
        if throttle and now - last < throttle:
            return
        self.last_played[relative_path] = now
        path = self.resolve(*relative_path.split("/"))
        if path is None:
            return
        subprocess.Popen(
            [self.afplay, str(path)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    def start_loop(self, relative_path):
        if not self.is_available():
            return
        path = self.resolve(*relative_path.split("/"))
        if path is None:
            return
        self.stop_loop()
        self.loop_stop.clear()

        def runner():
            while not self.loop_stop.is_set():
                proc = subprocess.Popen(
                    [self.afplay, str(path)],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                self.loop_process = proc
                while proc.poll() is None:
                    if self.loop_stop.is_set():
                        proc.terminate()
                        break
                    time.sleep(0.1)
                time.sleep(0.05)

        self.loop_thread = threading.Thread(target=runner, daemon=True)
        self.loop_thread.start()

    def stop_loop(self):
        self.loop_stop.set()
        if self.loop_process is not None and self.loop_process.poll() is None:
            self.loop_process.terminate()
        self.loop_process = None

    def stop_all(self):
        self.stop_loop()

