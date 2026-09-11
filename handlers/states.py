from aiogram.fsm.state import State, StatesGroup


class AdvisorStates(StatesGroup):
    """AI maslahatchi rejimi — hujjat kutilmoqda yoki savol-javob davom etmoqda."""

    chatting = State()
