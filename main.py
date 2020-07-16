import time, sched, json, uuid, argparse, jsonpickle
from tqdm import tqdm
from threading import Lock
from sys import argv, exit
from typing import List, Tuple, Callable
from pynput import mouse
from pynput import keyboard
from pynput.mouse import Controller as MouseController
from pynput.keyboard import Controller as KeyboardController

def save(data: dict, filename='config', extension='.json'):
    if extension == None:
        extension = ''
    with open(f'{filename}{extension}', 'w') as outfile:
        json.dump(data, outfile)

def load(filename='config', extension='.json') -> dict:
    data = {}
    if extension == None:
        extension = ''
    try:
        with open(f'{filename}{extension}') as infile:
            data = json.load(infile)
    except Exception as eff:
        print(eff)
        pass
    return data

data = load()
start_record_button = data.get('start_record_button')
start_replay_button = data.get('start_replay_button')
stop_record_button = data.get('stop_record_button')
pause_record_button = data.get('pause_record_button')
unpause_record_button = data.get('unpause_record_button')
emergency_button = data.get('emergency_button', keyboard.Key.esc)

def keyTrans(key: keyboard.KeyCode) -> str:
    return str(key).replace("'",'')

def ignoreKey(key: str) -> bool:
    if key in [start_record_button, stop_record_button, pause_record_button, unpause_record_button, emergency_button]:
        return True
    return False

def waitForKey(given: str):
    keyboard_halt = None
    mouse_halt = None
    def on_release(key):
        str_key = keyTrans(key)
        if str_key == given:
            mouse_halt.stop()
            return False
    def on_click(x, y, button, pressed):
        if not pressed and str(button) == given:
            keyboard_halt.stop()
            return False
    keyboard_halt = keyboard.Listener(on_release=on_release)
    mouse_halt = mouse.Listener(on_click=on_click)
    
    keyboard_halt.start()
    mouse_halt.start()
    
    keyboard_halt.join()
    mouse_halt.join()

isPaused = False
lenght = -1

def pause_recording_listener() -> Tuple[keyboard.Listener, mouse.Listener]:
    keyboard_halt = None
    mouse_halt = None

    def pause():
        global isPaused
        global lenght
        isPaused = True
        new_str = f'Press {unpause_record_button} key to resume recording!'
        print(' '*lenght, end='\r')
        print(new_str, end='\r')
        lenght = len(new_str)

    def unpause():
        global isPaused
        global lenght
        isPaused = False
        new_str = f'Press {pause_record_button} key to pause recording!'
        print(' '*lenght, end='\r')
        print(new_str, end='\r')
        lenght = len(new_str)

    switch = {
        (pause_record_button, False): pause,
        (unpause_record_button, True): unpause
    }

    def on_release(key):
        str_key = keyTrans(key)
        if str_key in [pause_record_button, unpause_record_button]:
            switch.get((str_key, isPaused))()

    def on_click(x, y, button, pressed):
        if not pressed and str(button) in [pause_record_button, unpause_record_button]:
            switch.get((str(button), isPaused))()
    keyboard_halt = keyboard.Listener(on_release=on_release)
    mouse_halt = mouse.Listener(on_click=on_click)
    
    keyboard_halt.start()
    mouse_halt.start()
    return (keyboard_halt, mouse_halt)


def record(args: List[str] = [], file: str = None, f_error: Callable[[str], None] = None, **kwargs: dict):
    global lenght
    
    file = kwargs.get('kwargs').get('file') if file == None else file
    if file == None:
        file = f'record-{str(uuid.uuid1())}.scrpt'
     
    print(f'Recording on file name: {file}')
    if start_record_button == None:
        print('Please provide a start_record_button at config.json')
        return
    if stop_record_button == None:
        print('Please provide a stop_record_button at config.json')
        return
    arr = []
    print(f'Press {start_record_button} key to start recording!')
    waitForKey(start_record_button)
    start_time = time.time()
    lock = Lock()
    def mouse_listener() -> mouse.Listener:
        dict_isPressed = {}
        def on_move(x, y):
            at_time = time.time() - start_time
            lock.acquire()
            arr.append({
                'controller': 'mouse',
                'instruction': 'move',
                'x': x,
                'y': y,
                'time': at_time
            })
            lock.release()
        def on_click(x, y, button, pressed):
            at_time = time.time() - start_time
            if ignoreKey(str(button)):
                return
            was_pressed = dict_isPressed.get(button, False)
            if (pressed and not was_pressed) or (not pressed and was_pressed):
                lock.acquire()
                arr.append({
                    'controller': 'mouse',
                    'instruction': 'click',
                    'button': jsonpickle.encode(button),
                    'press': pressed,
                    'x': x,
                    'y': y,
                    'time': at_time
                })
                dict_isPressed[button] = pressed
                lock.release()
        mouse_listen = mouse.Listener(on_move=on_move, on_click=on_click)
        mouse_listen.start()
        return mouse_listen
    def keyboard_listener() -> keyboard.Listener:
        dict_isPressed = {}
        def on_press(key):
            at_time = time.time() - start_time
            if ignoreKey(keyTrans(key)):
                return
            was_pressed = dict_isPressed.get(key, False)
            if not was_pressed:
                lock.acquire()
                arr.append({
                    'controller': 'keyboard',
                    'key': jsonpickle.encode(key),
                    'press': True,
                    'time': at_time
                })
                dict_isPressed[key] = True
                lock.release()
                
        def on_release(key):
            at_time = time.time() - start_time
            if ignoreKey(keyTrans(key)):
                return
            was_pressed = dict_isPressed.get(key, False)
            if was_pressed:
                lock.acquire()
                arr.append({
                    'controller': 'keyboard',
                    'key': jsonpickle.encode(key),
                    'press': False,
                    'time': at_time
                })
                dict_isPressed[key] = False
                lock.release()
        keyboard_listen = keyboard.Listener(on_press=on_press, on_release=on_release)
        keyboard_listen.start()
        return keyboard_listen
    mice = mouse_listener()
    rainbow = keyboard_listener()
    print(f'Press {stop_record_button} key to stop recording!')
    str_pause = f'Press {pause_record_button} key to pause recording!'
    lenght = len(str_pause)
    print(str_pause, end='\r')
    tuple_listner = pause_recording_listener()
    waitForKey(stop_record_button)
    mice.stop()
    rainbow.stop()
    tuple_listner[0].stop()
    tuple_listner[1].stop()
    save(arr, file, None)

mouse_c = MouseController()
def mouse_input(instr:dict):
    def move(instr:dict):
        mouse_c.position = (int(instr.get('x')), int(instr.get('y')))
    def click(instr:dict):
        mouse_c.position = (int(instr.get('x')), int(instr.get('y')))
        if instr.get('press'):
            mouse_c.press(
                jsonpickle.decode(
                    instr.get('button')
                )
            )
        else:
            mouse_c.release(
                jsonpickle.decode(
                    instr.get('button')
                )
            )
    switch = {
        'move': move,
        'click': click
    }
    switch.get(instr.get('instruction'))(instr)

keyboard_c = KeyboardController()
def keyboard_input(instr:dict):
    if instr.get('press'):
        keyboard_c.press(
            jsonpickle.decode(
                instr.get('key')
            )
        )
    else:
        keyboard_c.release(
            jsonpickle.decode(
                instr.get('key')
            )
        )

handler = {
    'mouse': mouse_input,
    'keyboard': keyboard_input
}


def replay(args: List[str] = [], file: str = None, f_error: Callable[[str], None] = None, **kwargs: dict):
    
    file = kwargs.get('kwargs').get('file') if file == None else file
    if file == None:
        f_error("Missing -f / --file parameter!")
    arr:List[dict] = load(file,extension=None)
    
    print(f'Press {start_replay_button} key to start replay!')
    waitForKey(start_replay_button)
    
    s = sched.scheduler(time.time, time.sleep)
    for elem in tqdm(arr, 'Loading & Replaying...'):
        # Rework line below?
        s.enter(elem.get('time'), 0, handler.get(elem.get('controller')), [elem])
        s.run(False)
    print('Only Replaying...')
    s.run()


def listen(args: List[str] = [], f_error: Callable[[str], None] = None, **kwargs: dict):
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

    waitForKey(emergency_button)

modes = {
    'listen': listen,
    'replay': replay,
    'record': record
}

parser = argparse.ArgumentParser(description='Input Recorder/Replayer and a good listener!')
parser.add_argument('-m', '--mode', choices=modes.keys(), help='Mode for execution (Default: listen)')
parser.add_argument('-f', '--file', metavar="path/to/file", help='File\'s Path to write/read script (Needed for replay and Optional for record)')
args = parser.parse_known_args()
funct = modes.get(vars(args[0]).get('mode'), listen)
def raise_param_error(message='Unspecified!'):
    parser.error(message=message)

funct(args[1], f_error = raise_param_error, kwargs = vars(args[0]))

#if len(argv)>1 and '-' in argv[1]:
#    exec = modes.get(argv[1], None)
#    if exec == None:
#        print(f'Mode {argv[1]} does not exist!')
#        exit(1)
#    exec(argv[2:])
#else:
#    print('Defaulting to main mode...')
#    main(argv[1:])
