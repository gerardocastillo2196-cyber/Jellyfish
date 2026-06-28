from prompt_toolkit import Application
from prompt_toolkit.layout import Layout, Window, HSplit
from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.key_binding import KeyBindings

lines = []
for i in range(100):
    lines.append(f"Line {i} " * 10)  # Very long line to test wrapping
text = "\n".join(lines)

scroll_pos = 0

def get_scroll():
    return scroll_pos

window = Window(
    content=FormattedTextControl(text),
    wrap_lines=True,
    get_vertical_scroll=get_scroll
)

layout = Layout(HSplit([window]))

kb = KeyBindings()

@kb.add("c-c")
def exit_(event):
    event.app.exit()

@kb.add("down")
def scroll_down(event):
    global scroll_pos
    scroll_pos += 1
    with open("scroll_log.txt", "a") as f:
        f.write(f"scroll_pos: {scroll_pos}\n")
    event.app.invalidate()

@kb.add("up")
def scroll_up(event):
    global scroll_pos
    scroll_pos = max(0, scroll_pos - 1)
    event.app.invalidate()

app = Application(layout=layout, key_bindings=kb, full_screen=True)
