import sys
from blessed import Terminal

from intuno.tune import Tuner, Note

def show_note_selection(term, note):
    ''' Renders the menu bar to select notes.

    Parameters:
      note (int): the currently selected note number
    '''
    prior = '  '.join([Note(n).name() for n in range(0, note)])
    post = '  '.join([Note(n).name() for n in range(note + 1, Note.MAX)])
    current = f' {Note(note).name()} '
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
    tuner = Tuner(term, sys.argv[1] if len(sys.argv) > 1 else 48)
    with term.fullscreen(), term.cbreak(), term.hidden_cursor():
        tuner.start()
        while True:
            print(term.home + term.clear)
            note = Note(tuner.get_note())
            label = f'Tuning: ({note.num+1}) ({note.freq():.02f} Hz)'
            label += f' | sample freq: {note.sample_rate()}'
            label += f' | buffer: {tuner.secs:.03f} sec'
            label += f' | volume: {tuner.volume}'
            with term.location(y=0):
                print(term.black_on_darkkhaki(term.center(label)))
                show_note_selection(term, note.num)
                print(term.darkkhaki_on_darkkhaki('='*term.width))

            inp = term.inkey()
            if inp.name == 'KEY_LEFT':
                tuner.next(-1)
            elif inp.name == 'KEY_RIGHT':
                tuner.next(1)
            elif inp.name == 'KEY_UP':
                tuner.volume_adj(1.5)
            elif inp.name == 'KEY_DOWN':
                tuner.volume_adj(1/1.5)
            elif inp.name == 'KEY_ESCAPE' or inp == 'q':
                break
    tuner.stop().join()

if __name__ == '__main__':
    main()
