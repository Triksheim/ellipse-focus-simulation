"""Optional Windows sound effects, played away from the animation thread."""

import io
import math
import struct
import sys
import threading
import wave

def make_effect(wall=False, focus=False):
    """Create an Arcade PCM effect (or a mix of both event types)."""
    rate = 22050
    wall_duration, focus_duration = 0.045, 0.075
    duration = focus_duration if focus else wall_duration
    frames = bytearray()
    for index in range(int(rate*duration)):
        t = index/rate
        sample = 0.0
        if wall and t < wall_duration:
            envelope = min(1, t/0.001)*max(0, 1-t/wall_duration)**2
            sample += 0.16*envelope*math.tanh(2.5*math.sin(2*math.pi*(1400*t-7000*t*t)))
        if focus:
            note = min(2, int(t/0.025))
            local = t-note*0.025
            envelope = min(1, local/0.002)*max(0, 1-local/0.025)
            sample += 0.18*envelope*math.tanh(2*math.sin(2*math.pi*(523.25, 659.25, 783.99)[note]*local))
        frames.extend(struct.pack('<h', round(max(-1, min(1, sample))*32767)))
    output = io.BytesIO()
    with wave.open(output, 'wb') as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(rate)
        wav.writeframes(frames)
    return output.getvalue()


class SoundPlayer:
    """A bounded event mixer: simultaneous hits share a sound, never a backlog."""

    def __init__(self, play=None):
        if play is None and sys.platform == 'win32':
            try:
                import winsound
                play = lambda data: winsound.PlaySound(data, winsound.SND_MEMORY | winsound.SND_NODEFAULT)
            except ImportError:
                play = None
        self._play = play
        self.available = play is not None
        self.enabled = False
        self._condition = threading.Condition()
        self._pending_wall = self._pending_focus = False
        self._closed = False
        self._worker = None
        self._effects = {(wall, focus): make_effect(wall, focus)
                         for wall, focus in ((True, False), (False, True), (True, True))}

    def _ensure_worker(self):
        if self._worker is None:
            self._worker = threading.Thread(target=self._run, daemon=True, name='ellipse-audio')
            self._worker.start()

    def set_enabled(self, enabled):
        with self._condition:
            self.enabled = bool(enabled and self.available and not self._closed)
            if not self.enabled:
                self._pending_wall = self._pending_focus = False
            else:
                self._ensure_worker()

    def emit(self, wall=0, focus=0):
        if not self.enabled or not (wall or focus):
            return
        with self._condition:
            if not self.enabled:
                return
            self._pending_wall |= bool(wall)
            self._pending_focus |= bool(focus)
            self._condition.notify()

    def _run(self):
        while True:
            with self._condition:
                self._condition.wait_for(lambda: self._closed or
                                         (self.enabled and (self._pending_wall or self._pending_focus)))
                if self._closed:
                    return
                key = (self._pending_wall, self._pending_focus)
                self._pending_wall = self._pending_focus = False
            try:
                self._play(self._effects[key])
            except (OSError, RuntimeError):
                self.set_enabled(False)

    def close(self):
        with self._condition:
            self.enabled = False
            self._closed = True
            self._pending_wall = self._pending_focus = False
            self._condition.notify()
