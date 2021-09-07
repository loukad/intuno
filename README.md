# intuno
**intuno** is a terminal-based note tuning application for pianos and other instruments.  Written in Python, it is available for multiple platforms.

## Installation

The program depends on the `pyaudio` library, which in turn depends on `portaudio`, which on a Mac is installed most easily with Homebrew. After cloning this repository, run:

```
brew update
brew install portaudio
brew link --overwrite portaudio
```

On macs, the `pyaudio` installation can sometimes fail because it cannot find the portaudio header and lib files.  To fix, find out where in your Homebrew path the files are and point the installer to them:

```
pip3 install --global-option='build_ext' \
--global-option='-L/opt/homebrew/Cellar/portaudio/19.7.0/lib' \
--global-option='-I/opt/homebrew/Cellar/portaudio/19.7.0/include' pyaudio
```

Now you should be able to install with:

```
pip install intuno
```

## Tuning

Run **intuno** with:

```
intuno
```

This defaults to tuning A in Octave 5.  You can optionally specify a different starting note, for instance to start tuning at Middle C, use:

```
intuno c3
```

The interface shows the currently selected note in the top menu bar, which you can change with the left and right arrow keys.  The raw signal coming from the microphone is rendered with [`plotille`](https://github.com/tammoippen/plotille) and the filtered signal is shown below it.  For a correctly tuned note, you should see a nice, clean waveform with a green OK status next to its estimated frequency:

![OK](resources/screenshot-accurate.png)

If the note is out of tune, the bottom waveform will drift, and the frequency estimate will tell you how much you will have to tighten (if the frequency is too low) or loosen (if too high) the string:

![Off](resources/screenshot-off.png)

For lower- and higher frequency notes, you may need to adjust the volume of your microphone.  If your system's controls do not give the desired range, you can adjust the software volume with the up and down keys.

## Other

For more information on the how the program works, check out [this notebook](https://loukad.github.io/tuning.html).

