import sys
import time

import queue
import threading

from multiprocessing import Lock

import pyaudio
import plotille

import numpy as np
from math import log2
from scipy.signal import firwin

from struct import unpack

from blessed import Terminal


def estimate_freq(arr, rate, consistency=3, show_dist=False):
    ''' Estimate frequency by counting number of axis crossings.

    Parameters:
      arr (array): the filtered audio buffer
      rate (int): sampling rate
      consistency (int): the maximum number of axis crossing differences
        for an estimate to be considered accurate
      show_dist (bool): display the distribution of distances between
        axis crossings

    Returns:
      an estimate of the signal's frequency or numpy.nan if it could not be
      measured accurately.
    '''
    diffs = np.diff(np.where(np.diff(np.signbit(arr))))
    uniq, counts = np.unique(diffs, return_counts=True)

    if len(uniq) > consistency:
        return np.nan

    if show_dist:
        dd = {x: str(n) for (x, n) in zip(uniq, counts)}
        dds = ','.join(['_' if x not in dd else dd[x] for x in range(40)])
        print(f'{rate / np.mean(diffs) / 2:.03f}', dds, Terminal().clear_eol)
    return rate / np.mean(diffs) / 2


class Note:
    MAX = 88 # The number of notes on modern piano

    def __init__(self, val):
        ''' Initializes from note index [0, Max) or name e.g. 'a4' '''
        self.note_names = self.gen_names()
        self.num = val if isinstance(val, int) else self.num_from_name(val)

    def gen_names(self):
        ''' Initializes the array of note names. '''
        names = 'A A# B C C# D D# E F F# G G#'.split()
        return [f'{names[n % 12]}{(12 + n - 3) // 12}' for n in range(Note.MAX)]

    def num_from_name(self, name):
        ''' Returns the note index from `name` e.g. 'c#4' '''
        if name.upper() not in self.note_names:
            raise ValueError(f'Invalid note name: {name}')
        return self.note_names.index(name.upper())

    def name(self):
        ''' Returns a string representation of the note. '''
        nname = self.note_names[self.num]
        note = nname[:-1]
        octave = int(nname[-1])
        pre = f'[Octave {octave}] ' if note == 'C' else ''
        return pre + note

    def freq(self):
        ''' Returns the note's frequency in Hz '''
        return 27.5 * 2**(self.num / 12)

    def sample_rate(self, minr=1000, maxr=44100):
        ''' Returns the appropriate sampling rate for this note.

        Parameters:
           minr (int): minimum sampling rate to consider
           maxr (int): maximum sampling rate to consider
        '''
        return min(minr * 2**(self.num // 12), maxr)

    def fir_filter(self, note_width=3, size=250):
        ''' Creates a Finite Impulse Response (FIR) filter for the note.

        Parameters:
          note_width (int): how many adjacent notes to permit in passband
          size (int): the size of the filter
        '''
        scale = 2**(note_width / 12)
        passband = (self.freq() / scale, self.freq() * scale)

        return firwin(size, passband, fs=self.sample_rate(),
                      pass_zero=False, scale=False)


class Tuner(threading.Thread):
    def __init__(self, term, initial_note=36):
        ''' Creates a Tuning thread.

        Parameters:
          term (Terminal object): terminal object for visualizations
          initial_note (int): which note to tune
        '''
        super(Tuner, self).__init__()
        self.stream = None
        self.term = term
        self.volume = 1
        self.q = queue.Queue()
        self.lock = Lock()
        self.set_note(initial_note)

    def get_note(self):
        ''' Returns the currently tuned note. '''
        with self.lock:
            return self.note.num

    def next(self, inc):
        ''' Switches to tuning the adjacent note.

        Parameters:
          inc (int): note increment (positive or negative)
        '''
        with self.lock:
            newnote = max(min(self.note.num + inc, Note.MAX - 1), 0)
        self.set_note(newnote)

    def volume_adj(self, scale):
        with self.lock:
            self.volume *= scale
            with self.term.location(y=0):
                print(f'Volume: {self.volume:.2f}')
                time.sleep(.15)

    def set_note(self, note):
        ''' Changes the currently tuned note to `note`. '''
        with self.lock:
            if self.stream:
                self.stream.close()
            self.estimates = []
            self.note = Note(note)
            self.secs = max(int(self.note.freq() * 0.2), 20) / self.note.freq()
            self.open_stream(self.note.sample_rate(), self.secs)
            self.fir = self.note.fir_filter()

    def open_stream(self, rate, seconds=0.2):
        ''' Open a non-blocking audio stream.

        Parameters:
          rate (int): sampling rate
          seconds (float): length of time of each collected buffer
        '''
        p = pyaudio.PyAudio()
        self.stream = p.open(format=pyaudio.paInt16, channels=1, rate=rate,
                             input=True, frames_per_buffer=int(rate*seconds),
                             stream_callback=self.audio_callback)

    def audio_callback(self, data, frame_count, time_info, status):
        ''' Called by PyAudio after a buffer is filled. '''
        if status:
            print(status, file=sys.stderr)

        self.q.put(np.array(unpack(f'{frame_count}h', data)))

        return None, pyaudio.paContinue

    def stop(self):
        ''' Stops the tuning thread. '''
        with self.lock:
            self.stream.close()
        self.q.put(None)
        return self

    def add_estimate(self, arr, min_estimates=5, min_volume=50):
        ''' Adds a frequency estimate from the filtered data to the pool.

        Parameters:
          arr (nd.array): the filtered samples
          min_estimates (int): how many recent frequency estimates to keep
          min_volume (int): the mean amplitude required for an estimate

        Returns:
          True iff an accurate estimate is possible
        '''
        rate = self.note.sample_rate()
        if np.mean(np.abs(arr)) < min_volume:
            return False
        self.estimates.insert(0, estimate_freq(arr, rate))
        if len(self.estimates) > min_estimates:
            self.estimates.pop()
            frange = np.max(self.estimates) - np.min(self.estimates)
            return frange / self.estimates[-1] < 0.05
        return False

    def show_dist_to_next_note(self, freq, detected):
        ''' Shows a bar representing how far off estimate is from target.

        Parameters:
          freq (float): target note frequency
          detected (float): frequency estimate
        '''
        w = self.term.width // 2
        lin_dist_to_adj = min(abs(log2(detected) - log2(freq)), 1/12)
        barlen = int(lin_dist_to_adj * w * 12)
        space = w - barlen
        bar = self.term.white_on_white('='*barlen)

        print(' '*(space if detected < freq else w) + bar + self.term.clear_eol)

    def show_freq_estimate(self, accurate, tolerance=0.1):
        ''' Shows the estimated frequency or '--' if not `accurate`.

        Parameters:
          tolerance (float): the fraction from the adjacent note's frequency
                             for the estimate to be considered OK (green)
        '''
        if not accurate:
            print(self.term.center('--'))
            print(self.term.clear_eol)
            return

        freq = self.note.freq()
        detected = np.mean(self.estimates)

        diff = detected - freq
        if abs(log2(detected) - log2(freq)) * 12 < tolerance:
            diff_s = self.term.bold_black_on_green(f' {diff:.03f} OK ')
        else:
            diff_s = self.term.bold_white_on_red(f' {diff:.03f} ')
        print(self.term.center(f'{detected:.03f}' + diff_s) + self.term.clear_eol)
        self.show_dist_to_next_note(freq, detected)

    def show_signal(self, arr, periods=5, height=8, x_margin=20, y_max=2000):
        ''' Visualizes the collected samples in the given array.

        Parameters:
          arr (nd.array): the buffer of samples
          periods (int): how many cycles to show from the target frequency
          height (int): the height of the graph
          x_margin (int): margin width around the width of the terminal
          y_max (float): the amplitude extent of the graph
        '''
        freq = self.note.freq()
        rate = self.note.sample_rate()

        samples = min(round(periods * rate / freq), len(arr))
        plot_text = plotille.plot(range(samples), arr[:samples], origin=False,
                                  height=height, width=self.term.width - x_margin,
                                  y_max=y_max, y_min=-y_max, x_min=0)

        # Since the plotille module does not offer any functionality to hide
        # the axes, just trim them using text processing
        rc = {ord(c):' ' for c in '0123456789.-|(XY^>)'}
        print('\n'.join(plot_text.translate(rc).split('\n')[:-3]))


    def visualize(self, arr):
        ''' Renders the input data (`arr`) and frequency estimates.'''

        with self.lock:
            arr = arr * self.volume
            farr = np.convolve(arr, self.fir, mode='valid')
            plot_margin = 5
            plot_height = (self.term.height) // 2 - plot_margin
            with self.term.location(y=3):
                self.show_freq_estimate(self.add_estimate(farr))
            with self.term.location(y=5):
                self.show_signal(arr, height=plot_height)
            with self.term.location(y=3 + plot_height + plot_margin):
                self.show_signal(farr, height=plot_height)

    def run(self):
        ''' Thread main method. '''
        while self.is_alive():
            arr = self.q.get()
            if arr is None:
                return
            self.visualize(arr)


