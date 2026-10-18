import sys
import time

sys.path.insert(0, r"D:\FunnyThing\ToDoList\client")
from pynput import keyboard

count = 0


def on_press(key):
    global count
    count += 1


listener = keyboard.Listener(on_press=on_press)
listener.start()
print("listener alive:", listener.is_alive(), flush=True)
for i in range(12):
    time.sleep(1)
    print("count:", count, flush=True)
