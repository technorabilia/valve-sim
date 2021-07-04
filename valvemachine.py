import time

from statemachine import State, StateMachine


class ValveMachine(StateMachine):
    opened = State("Valve open")
    closed = State("Valve closed", initial=True)
    faulty = State("Valve faulty")

    open = closed.to(opened)

    close = opened.to(closed)
    fault = opened.to(faulty) | closed.to(faulty)
    reset = faulty.to(closed)
    cycle = open | close

    def on_enter_faulty(self):
        time.sleep(10)
        self.reset()
