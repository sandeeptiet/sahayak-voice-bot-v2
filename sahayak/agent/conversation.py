"""Bounded in-process conversation; not AgentCore Memory or ticket authority."""
from copy import deepcopy
from uuid import uuid4
from .workflow import LANGUAGES


class Conversation:
    def __init__(self, workflow, language, max_turns=6):
        if language not in LANGUAGES or not 1 <= max_turns <= 6:
            raise ValueError("Invalid conversation language or turn limit")
        self.workflow, self.language, self.max_turns = workflow, language, max_turns
        self.session_id = str(uuid4())
        self._history = []
        self._pending = None
        self.turns = 0
        self.closed = False

    def respond(self, question):
        if self.closed or self.turns >= self.max_turns or self._pending is not None:
            raise ValueError("Session ended or previous reply delivery is incomplete")
        state = self.workflow.invoke({"question": question, "language": self.language,
                                      "history": deepcopy(self._history)})
        if state["status"] == "generated_unreviewed":
            self._pending = (question, state["spoken_text"])
        else:
            self.closed = True
        return {**state, "session_id": self.session_id, "turn_number": self.turns + 1}

    def delivered(self):
        # Called only after local playback completes, not after generation or TTS.
        # Playback completion is NOT evidence the employee heard/accepted a fix.
        if self._pending is None or self.closed:
            raise ValueError("No pending response")
        question, answer = self._pending
        self._history.extend([{"role": "user", "content": question},
                              {"role": "assistant", "content": answer}])
        self._pending = None
        self.turns += 1

    def close(self):
        self.closed = True
        self._history.clear()
        self._pending = None
