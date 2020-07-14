import time, sched, json
from pynput import mouse
from pynput import keyboard
from typing import List
from sys import argv, exit
import argparse

def save(data, filename='config'):
    with open(f'{filename}.json', 'w') as outfile:
        json.dump(data, outfile)

def load(filename='config') -> dict:
    data = {}
    try:
        with open(f'{filename}.json') as infile:
            data = json.load(infile)
    except Exception as eff:
        pass
    return data


parser = argparse.ArgumentParser(description='Input Recorder/Replayer and a good listener!')
parser.add_argument('-m', '--mode', choices=['main', 'listen'], help='Mode for execution (Default: main)')
args = parser.parse_known_args()

data = load()
start_record_button = data.get('start_record_button')
stop_record_button = data.get('stop_record_button')
emergency_button = data.get('emergency_button', keyboard.Key.esc)

def keyTrans(key: keyboard.KeyCode) -> str:
    return str(key).replace("'",'')

def main(args: List[str]):
    print(args)

def listen(args: List[str]):
    start_time = time.time()
    def mouse_listener():
        def on_move(x, y):
            at_time = time.time() - start_time
            print(f'Mouse in ({x},{y}) at {at_time}')

        def on_click(x, y, button, pressed):
            at_time = time.time() - start_time
            str_pressed = 'Pressed' if pressed else 'Released'
            print(f'{str_pressed} {button} button in ({x},{y}) at {at_time}')    
        mouse_listen = mouse.Listener(on_move=on_move, on_click=on_click)
        mouse_listen.start()
    def keyboard_listener():
        def on_press(key):
            at_time = time.time() - start_time
            try:
                if key.char == None:
                    raise AttributeError
                print(f'alphanumeric key {keyTrans(key)} pressed at {at_time}')
            except AttributeError:
                print(f'special key {keyTrans(key)} pressed at {at_time}')
        def on_release(key):
            at_time = time.time() - start_time
            print(f'{keyTrans(key)} released at {at_time}')
        keyboard_listen = keyboard.Listener(on_press=on_press, on_release=on_release)
        keyboard_listen.start()
    mouse_listener()
    keyboard_listener()
    #
    keyboard_halt = None
    mouse_halt = None
    def on_release(key):
        str_key = keyTrans(key)
        if str_key == str(emergency_button):
            mouse_halt.stop()
            return False
    def on_click(x, y, button, pressed):
        if not pressed and str(button) == str(emergency_button):
            keyboard_halt.stop()
            return False
    keyboard_halt = keyboard.Listener(on_release=on_release)
    mouse_halt = mouse.Listener(on_click=on_click)
    
    keyboard_halt.start()
    mouse_halt.start()
    
    keyboard_halt.join()
    mouse_halt.join()

modes = {
    'listen': listen,
    'main': main
}


"""
# Set up scheduler
s = sched.scheduler(time.time, time.sleep)
# Schedule when you want the action to occur
s.enter(10, 0, print, argument=['hi'])
#s.enterabs(time.time()+10, 0, print, 'hi')
# Block until the action has been run
start_time = time.time()
time.sleep(5)
s.run()
print(time.time() - start_time)
exit(1)
"""

funct = modes.get(vars(args[0]).get('mode'), main)

funct(args[1])

#if len(argv)>1 and '-' in argv[1]:
#    exec = modes.get(argv[1], None)
#    if exec == None:
#        print(f'Mode {argv[1]} does not exist!')
#        exit(1)
#    exec(argv[2:])
#else:
#    print('Defaulting to main mode...')
#    main(argv[1:])
