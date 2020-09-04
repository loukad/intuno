import sys

import queue
import threading
from multiprocessing import Lock

import pyaudio
import plotille

import numpy as np
from scipy import signal
from scipy.signal import find_peaks

from struct import unpack

from blessed import Terminal

class Note:
    def __init__(self, num):
        self.num = num

    def name(self):
        names = 'A,A#,B,C,C#,D,D#,E,F,F#,G,G#'.split(',')
        pre = f'[Octave {self.num // 12}] ' if self.num % 12 == 0 else ''
        return pre + names[self.num % 12]

    def freq(self):
        return 27.5 * 2**(self.num / 12)

    def sample_rate(self, minr=1000, maxr=44100):
        return min(minr * 2**(self.num // 12), maxr)

    def fir_filter(self, note_width=3, size=250):
        scale = 2**(note_width / 12)
        passband = (self.freq() / scale, self.freq() * scale)

        return signal.firwin(size, passband, fs=self.sample_rate(),
                             pass_zero=False, scale=False)

class Tuner(threading.Thread):
    def __init__(self, term, initial_note=36):
        super(Tuner, self).__init__()
        self.stream = None
        self.term = term
        self.q = queue.Queue()
        self.lock = Lock()
        self.set_note(initial_note)

    def get_note(self):
        with self.lock:
            return self.note.num

    def next(self, inc):
        with self.lock:
            newnote = max(min(self.note.num + inc, 87), 0)
        self.set_note(newnote)

    def set_note(self, note):
        with self.lock:
            if self.stream:
                self.stream.close()
            self.note = Note(note)
            secs = max(min(100/self.note.freq(), 0.45), 0.1)
            self.open_stream(self.note.sample_rate(), secs)
            self.fir = self.note.fir_filter()

    def open_stream(self, rate, seconds=0.2):
        p = pyaudio.PyAudio()
        self.stream = p.open(format=pyaudio.paInt16, channels=1, rate=rate,
                             input=True, frames_per_buffer=int(rate*seconds),
                             stream_callback=self.audio_callback)

    def audio_callback(self, data, frame_count, time_info, status):
        if status:
            print(status, file=sys.stderr)

        self.q.put(np.array(unpack(f'{frame_count}h', data)))

        return None, pyaudio.paContinue

    def stop(self):
        with self.lock:
            self.stream.close()
        self.q.put(None)
        return self

    def show_signal(self, arr, y, height=8, ymax=2000):
        with self.lock:
            freq = self.note.freq()
            rate = self.note.sample_rate()

        with self.term.location(y=y-1):
            peaks, _ = find_peaks(arr, height=400)
            if len(peaks) > 4:
                detected = rate / np.mean(np.diff(peaks))
                diff = detected - freq
                if abs(diff) < (freq * 2**(1/12) - freq) * .1:
                    diff_s = self.term.bold_black_on_green(f' {diff:.03f} OK ')
                else:
                    diff_s = self.term.bold_white_on_red(f' {diff:.03f} ')
                print(f'{detected:.03f}', diff_s, self.term.clear_eol)
            else:
                print('--', self.term.clear_eol)

        with self.term.location(y=y):
            samples = int(3 * rate / freq)
            print(plotille.plot(range(samples), arr[:samples], origin=False,
                                height=height, width=self.term.width - 20,
                                y_max=ymax, y_min=-ymax, x_min=0))


    def run(self):
        while self.is_alive():
            arr = self.q.get()
            if arr is None:
                return
            self.show_signal(arr, y=5)

            with self.lock:
                farr = np.convolve(arr, self.fir, mode='valid')
                firlen = len(self.fir)
            self.show_signal(farr, y=18)


def show_note_selection(term, note, maxnote=88):
    prior = '  '.join([Note(n).name() for n in range(0, note)])
    post = '  '.join([Note(n).name() for n in range(note + 1, 88)])
    current = f' {Note(note).name()} '
    with term.location(y=1):
        width = term.width - len(current)
        maxleft = maxright = width // 2 - 1
        if len(prior) < maxright:
            maxright = width - len(prior)
        if len(post) < maxleft:
            maxleft = width - len(post)

        left = prior[len(prior) - min(maxleft, len(prior)):]
        right = post[:min(maxright, len(post))] + term.clear_eol
        print(left + term.bold_black_on_darkkhaki(current) + right)

def main():
    term = Terminal()
    tuner = Tuner(term, int(sys.argv[1])-1 if len(sys.argv) > 0 else 36)
    with term.fullscreen(), term.cbreak(), term.hidden_cursor():
        tuner.start()
        while True:
            print(term.home + term.clear)
            note = Note(tuner.get_note())
            show_note_selection(term, note.num)
            label = f'Tuning: ({note.num+1}) ({note.freq():.02f} Hz)'
            label += f' sample freq: {note.sample_rate()}'
            with term.location(y=0):
                print(term.black_on_darkkhaki(term.center(label)))

            inp = term.inkey()
            if inp.name == 'KEY_LEFT':
                tuner.next(-1)
            elif inp.name == 'KEY_RIGHT':
                tuner.next(1)
            elif inp.name == 'KEY_ESCAPE' or inp == 'q':
                break
    tuner.stop().join()

if __name__ == '__main__':
    main()
