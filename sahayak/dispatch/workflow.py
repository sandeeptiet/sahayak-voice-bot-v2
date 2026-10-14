"""Deterministic entry graph, without model, network or telephony nodes.

Only operational preflight results are produced. A ready result is NOT a call
claim, answered event, troubleshooting outcome, or permission to dial.
"""
from datetime import datetime
from typing import TypedDict
from langgraph.graph import StateGraph, START, END

class Context(TypedDict):
    status: str
    assigned: bool
    is_test: bool
    contact_ready: bool
    event_generation: int
    current_generation: int
    available_at: datetime
    callback_at: datetime | None
    database_now: datetime
    result: str

def validate(state: Context):
    if state['is_test']: result='skipped_test'
    elif state['event_generation'] != state['current_generation']: result='skipped_generation'
    elif state['status'] != 'new': result='skipped_state'
    elif state['assigned']: result='skipped_assignment'
    elif max(state['available_at'],state['callback_at'] or state['available_at']) > state['database_now']: result='deferred'
    elif not state['contact_ready']: result='skipped_contact'
    else: result='ready_calls_disabled'
    return {'result': result}

builder=StateGraph(Context)
builder.add_node('validate_dispatch',validate)
builder.add_edge(START,'validate_dispatch')
builder.add_edge('validate_dispatch',END)
workflow=builder.compile()
