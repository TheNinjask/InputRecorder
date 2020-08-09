import re, time, sched, json, uuid, argparse, jsonpickle, pydirectinput
from tqdm import tqdm
from threading import Lock, Thread, Event
from sys import argv, exit
from typing import List, Tuple, Callable
from pynput import mouse
from pynput import keyboard
from pynput.mouse import Controller as MouseController
from pynput.keyboard import Controller as KeyboardController
from pprint import pprint

def save(data: dict, filename='config', extension='json'):
    if extension == None:
        extension = ''
    with open(f'{filename}{"" if extension == None else "."}{extension}', 'w') as outfile:
        json.dump(data, outfile)

def load(filename='config', extension='json') -> dict:
    data = {}
    if extension == None:
        extension = ''
    try:
        with open(f'{filename}{"" if extension == None else "."}{extension}') as infile:
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
stop_listen_button = data.get('stop_listen_button')
emergency_button = data.get('emergency_button', keyboard.Key.esc)

listen_mouse = True
listen_key = True
use_pydirect_input = data.get('use_pydirect_input', False)

class DrBoom(Exception):
    pass

def keyTrans(key: keyboard.KeyCode) -> str:
    key_map = {
        '+': 'add',
        '-': 'subtract',
        '*': 'multiply',
        '/': 'divide',
        'shiftr': 'shift',
        'ctrll': 'ctrl',
        'ctrlr': 'ctrlright',
        'altl': 'alt',
        'altr': 'altright'
        #'cmd': 'win'
    }
    str_key = re.sub(r"('|Key\.|\[|\]|_)", '', str(key))
    #print(key_map.get(str_key, str_key))
    return key_map.get(str_key, str_key)

def ignoreKey(key: str, exclude: List = [start_record_button, start_replay_button, stop_record_button, pause_record_button, unpause_record_button, emergency_button]) -> bool:
    if key in exclude:
        return True
    return False

big_red_button = None

def waitForKey(given: str, suppress=False):
    global big_red_button
    big_red_button = None
    keyboard_halt = None
    mouse_halt = None
    def on_release(key):
        global big_red_button
        str_key = keyTrans(key)
        if str_key == emergency_button:
            big_red_button = DrBoom()
            mouse_halt.stop()
            return False
        if str_key == given:
            mouse_halt.stop()
            return False
    def on_click(x, y, button, pressed):
        global big_red_button
        if not pressed and str(button) == emergency_button:
            big_red_button = DrBoom()
            keyboard_halt.stop()
            return False
        if not pressed and str(button) == given:
            keyboard_halt.stop()
            return False
    
    keyboard_halt = keyboard.Listener(on_release=on_release, suppress=suppress)
    mouse_halt = mouse.Listener(on_click=on_click, suppress=suppress)
    
    keyboard_halt.start()
    mouse_halt.start()
    
    keyboard_halt.join()
    mouse_halt.join()
    if isinstance(big_red_button, DrBoom):
        print(f'The emergency button {emergency_button} was pressed! Stopping.')
        exit(1)

def waitForAnyKey() -> str:
    global big_red_button
    global chosen
    big_red_button = None
    keyboard_halt = None
    mouse_halt = None
    chosen = None
    def on_release(key):
        global big_red_button
        global chosen
        str_key = keyTrans(key)
        if str_key == emergency_button:
            big_red_button = DrBoom()
            mouse_halt.stop()
            return False
        if chosen == None:
            chosen = str_key
        if not mouse_halt == None:
            mouse_halt.stop()
        return False
    def on_click(x, y, button, pressed):
        global big_red_button
        global chosen
        if not pressed and str(button) == emergency_button:
            big_red_button = DrBoom()
            keyboard_halt.stop()
            return False
        if chosen == None:
            chosen = str(button)
        if not keyboard_halt == None:
            keyboard_halt.stop()
        return False
    
    if listen_key:
        keyboard_halt = keyboard.Listener(on_release=on_release, suppress=True)
        keyboard_halt.start()
    if listen_mouse:
        mouse_halt = mouse.Listener(on_click=on_click, suppress=True)
        mouse_halt.start()
    
    if listen_key:
        keyboard_halt.join()
    if listen_mouse:
        mouse_halt.join()
    
    if isinstance(big_red_button, DrBoom):
        print(f'The emergency button {emergency_button} was pressed! Stopping.')
        exit(1)
    return chosen

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
    if listen_mouse:
        mice = mouse_listener()
    if listen_key:
        rainbow = keyboard_listener()
    print(f'Press {stop_record_button} key to stop recording!')
    str_pause = f'Press {pause_record_button} key to pause recording!'
    lenght = len(str_pause)
    print(str_pause, end='\r')
    tuple_listener = pause_recording_listener()
    waitForKey(stop_record_button)
    if listen_mouse:
        mice.stop()
    if listen_key:
        rainbow.stop()
    tuple_listener[0].stop()
    tuple_listener[1].stop()
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
def keyboard_pynput(instr:dict):
    keyboard_c.touch(
        jsonpickle.decode(
            instr.get('key')
        ),
        instr.get('press')
    )

def keyboard_pydirectinput(instr:dict):
    func = pydirectinput.keyDown if instr.get('press') else pydirectinput.keyUp 
    func(
            keyTrans(
                str(
                    jsonpickle.decode(
                        instr.get('key')
                    )
                )
            )
        )
        
handler = {
    'mouse': mouse_input,
    'keyboard': keyboard_pynput if not use_pydirect_input else keyboard_pydirectinput
}

def raw_replay(trigger: str, script: List[dict]):
    waitForKey(start_replay_button)  
    s = sched.scheduler(time.time, time.sleep)
    key_wait = Thread(target= waitForKey, args=[emergency_button])
    key_wait.start()
    for elem in arr:
        # Rework line below?
        s.enter(elem.get('time'), 0, handler.get(elem.get('controller')), [elem])
        s.run(False)
        if not key_wait.is_alive():
            exit(1)
    while not s.empty():
        s.run(False)
        if not key_wait.is_alive():
            exit(1)

replay_ender_flag = Event()
class replay_ender(Thread):
    def __init__(self, func: Callable):
        Thread.__init__(self)
        self.func = func
    def run(self):
        func()
        replay_ender_flag.set()


def replay(args: List[str] = [], file: str = None, f_error: Callable[[str], None] = None, **kwargs: dict):
    file = kwargs.get('kwargs').get('file') if file == None else file
    if file == None:
        f_error("Missing -f / --file parameter!")
    arr:List[dict] = load(file,extension=None)
    
    print(f'Press {start_replay_button} key to start replay!')
    waitForKey(start_replay_button)
    
    s = sched.scheduler(time.time, time.sleep)
    key_wait = Thread(target= waitForKey, args=[emergency_button])
    key_wait.start()
    for elem in tqdm(arr, 'Loading & Replaying...'):
        # Rework line below?
        s.enter(elem.get('time'), 0, handler.get(elem.get('controller')), [elem])
        s.run(False)
        if not key_wait.is_alive():
            exit(1)
    print('Only Replaying...')
    replay_ender(s.run).run()
    replay_ender(key_wait.join).run()
    replay_ender_flag.wait()

def listen(args: List[str] = [], f_error: Callable[[str], None] = None, **kwargs: dict):
        
    start_time = time.time()
    def mouse_listener():
        def on_move(x, y):
            at_time = time.time() - start_time
            print(f'Mouse in ({x},{y}) at {at_time}')

        def on_click(x, y, button: mouse.Button, pressed):
            at_time = time.time() - start_time
            str_pressed = 'Pressed' if pressed else 'Released'
            print(f'{str_pressed} {button} button in ({x},{y}) at {at_time}')    
        mouse_listen = mouse.Listener(on_move=on_move, on_click=on_click)
        mouse_listen.start()
    def keyboard_listener():
        def on_press(key: keyboard.KeyCode):
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
        
        if listen_mouse:
            mouse_listener()
        if listen_key:
            keyboard_listener()

    waitForKey(stop_listen_button)

wait_for_all = Event()
class multiple_replay(Thread):
    def __init__(self, trigger: str, script: List[dict]):
        Thread.__init__(self)
    def run(self):
        wait_for_all.wait()
        while True:
            raw_replay(trigger, script)

def keybind_listen(keybind_sett: dict) -> dict:
    arr = keybind_sett.get('keybinds')
    if arr == None or len(arr) == 0:
        print('Nothing to listen to :|')
    for elem in tqdm(arr.items(), 'Loading Scripts...'):
        script = load(elem[1], None)
        multiple_replay(elem[0], script).run()
    wait_for_all.set()
    print(f'All scripts loaded. Press {stop_listen_button} to exit.')
    waitForKey(stop_listen_button)

def set_script_keybind(keybind_sett: dict) -> dict:
    print(f'Press {start_record_button} to listen for trigger')
    waitForKey(start_record_button, suppress=True)
    print('Listening...')
    trigger = waitForAnyKey()
    while trigger in keybind_sett.get('keybinds').keys():
        print(f'The trigger {trigger} is already in use!')
        print(f'Press {start_record_button} to listen for trigger')
        waitForKey(start_record_button)
        print('Listening...')
        trigger = waitForAnyKey()
    file = str(input('Insert file to script: '))
    keybind_sett.get('keybinds')[trigger] = file
    return keybind_sett

def clear_keybind(keybind_sett: dict) -> dict:
    print(f'Press {start_record_button} to listen for trigger')
    waitForKey(start_record_button)
    print('Listening...')
    trigger = waitForAnyKey()
    if not trigger in keybind_sett.get('keybinds').keys():
        print(f'Trigger {trigger} not found!')
    else:
        del keybind_sett.get('keybinds')[trigger]
        print(f'Trigger {trigger} cleared!')
    return keybind_sett

def save_keybind_sett(keybind_sett: dict) -> dict:
    while keybind_sett.get('filename') == None or len(keybind_sett.get('filename')) == 0:
        keybind_sett['filename'] = str(input('Provide a name for these settings: '))
    file = keybind_sett.get('filename')
    del keybind_sett['filename']
    save(keybind_sett, file, None)
    keybind_sett['filename'] = file
    return keybind_sett

def keybind(args: List[str] = [], file: str = None, f_error: Callable[[str], None] = None, **kwargs: dict):
    file = kwargs.get('kwargs').get('file') if file == None else file
    keybind_sett = {}
    keybind_sett['keybinds'] = {}
    if not file == None:
        keybind_sett = load(filename=file)
        keybind_sett['filename'] = file
    menu = {
        '0': "#exit",
        '1': keybind_listen,
        '2': set_script_keybind,
        '3': clear_keybind,
        '4': save_keybind_sett
    }
    option = None
    def print_options():
        print('0 - Exit')
        print('1 - Keybind Listen Mode')
        print('2 - Keybind Script Mode')
        print('3 - Keybind Clear Mode')
        print('4 - Save Settings')
    print_options()
    while not option == '0':
        option = str(input('Insert option number: '))
        if not option == '0' and option in menu.keys():
            funct = menu.get(option)
            funct(keybind_sett)
        elif not option in menu.keys():
            print_options()
        pprint(keybind_sett)

def menu(args: List[str] = [], file: str = None, f_error: Callable[[str], None] = None, **kwargs: dict):
    selection = {
        '0': "#exit",
        '1': listen,
        '2': replay,
        '3': record,
        '4': keybind
    }
    option = None
    def print_options():
        print('0 - Exit')
        print('1 - Listen Mode')
        print('2 - Replay Mode')
        print('3 - Record Mode')
        print('4 - Keybind Mode')
        
    print_options()
    while not option == '0':
        option = str(input('Insert option number: '))
        file = None if not option == '2' else str(input('Provide path of file for replay: '))
        if not option == '0' and not option in selection.keys():
            funct = selection.get(option)
            funct([], file=file, f_error = f_error, kwargs = kwargs)
        elif not option in menu.keys():
            print_options()

modes = {
    'listen': listen,
    'replay': replay,
    'record': record,
    'keybind': keybind,
    'menu': menu
}

parser = argparse.ArgumentParser(description='Input Recorder/Replayer and a good listener!')
parser.add_argument('-m', '--mode', nargs=1, choices=modes.keys(), help='Mode for execution (Default: menu) (Priority n0)')
parser.add_argument('-f', '--file', metavar="path/to/file", help='File\'s Path to write/read script (Needed for replay and Optional for record)')
parser.add_argument('-nm', '--no_mouse', action='store_true', help='Disable mouse listener.')
parser.add_argument('-nk', '--no_keyboard', action='store_true', help='Disable keyboard listener.')
parser.add_argument('-l', '--listen', action='store_true', help='Skip imediatly to listen mode. (Priority n1)')
parser.add_argument('-rc', '--record', action='store_true', help='Skip imediatly to record mode. (Priority n2)')
parser.add_argument('-rp', '--replay', action='store_true', help='Skip imediatly to replay mode. (Priority n3)')
parser.add_argument('-k', '--keybind', action='store_true', help='Skip imediatly to keybind mode. (Priority n4)')
parser.add_argument('-pd', '--pydirectinput', action='store_true', help='Set pydirectinput\'s keyboard (Overrides the option in config.json & Priority n2)')
parser.add_argument('-pn', '--pynput', action='store_true', help='Set pynput\'s keyboard (Overrides the option in config.json & Priority n1)')
args = parser.parse_known_args()

funct = modes.get(vars(args[0]).get('mode'))

if funct == None:
    if vars(args[0]).get('listen'):
        funct = listen
    elif vars(args[0]).get('record'):
        funct = record
    elif vars(args[0]).get('replay'):
        funct = replay
    elif vars(args[0]).get('keybind'):
        funct = keybind
    else:
        funct = menu

if vars(args[0]).get('pynput'):
    handler['keyboard'] = keyboard_pynput
elif vars(args[0]).get('pydirectinput'):
    handler['keyboard'] = keyboard_pydirectinput

if vars(args[0]).get('no_mouse'):
    listen_mouse = False
if vars(args[0]).get('no_keyboard'):
    listen_key = False

def raise_param_error(message='Unspecified!'):
    parser.error(message=message)
if not listen_mouse and not listen_key:
    print("I'm not listening! Cya >:(")
    exit(1)
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
