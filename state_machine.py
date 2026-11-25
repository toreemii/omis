from __future__ import annotations

from enum import Enum


class InterfaceState(str, Enum):
    LOGIN = "Вход пользователя"
    EXHIBITIONS_LIST = "Список выставок"
    EXHIBITION_PAGE = "Страница выставки"
    COMPANY_SHOWCASE = "Онлайн-витрина компании"
    CART_CHECKOUT = "Корзина и оформление"
    CABINET = "Личный кабинет"
    MY_TICKETS = "Мои билеты"
    TICKET_QR = "Билет (QR-код)"
    MY_ORDERS = "Мои заказы"
    EXIT = "Выход из программы"


TOP_MENU_STATES: tuple[InterfaceState, ...] = (
    InterfaceState.EXHIBITIONS_LIST,
    InterfaceState.MY_ORDERS,
    InterfaceState.MY_TICKETS,
    InterfaceState.CABINET,
)


ALLOWED_TRANSITIONS: dict[InterfaceState, set[InterfaceState]] = {
    InterfaceState.LOGIN: {InterfaceState.EXHIBITIONS_LIST, InterfaceState.EXIT},
    InterfaceState.EXHIBITIONS_LIST: {
        InterfaceState.EXHIBITION_PAGE,
        InterfaceState.CART_CHECKOUT,
        InterfaceState.EXIT,
        *TOP_MENU_STATES,
    },
    InterfaceState.EXHIBITION_PAGE: {
        InterfaceState.COMPANY_SHOWCASE,
        InterfaceState.TICKET_QR,
        InterfaceState.CART_CHECKOUT,
        InterfaceState.EXIT,
        *TOP_MENU_STATES,
    },
    InterfaceState.COMPANY_SHOWCASE: {
        InterfaceState.CART_CHECKOUT,
        InterfaceState.EXIT,
        *TOP_MENU_STATES,
    },
    InterfaceState.CART_CHECKOUT: {
        InterfaceState.MY_ORDERS,
        InterfaceState.EXIT,
        *TOP_MENU_STATES,
    },
    InterfaceState.CABINET: {
        InterfaceState.MY_TICKETS,
        InterfaceState.MY_ORDERS,
        InterfaceState.CART_CHECKOUT,
        InterfaceState.EXIT,
        *TOP_MENU_STATES,
    },
    InterfaceState.MY_TICKETS: {
        InterfaceState.TICKET_QR,
        InterfaceState.CART_CHECKOUT,
        InterfaceState.EXIT,
        *TOP_MENU_STATES,
    },
    InterfaceState.TICKET_QR: {
        InterfaceState.CART_CHECKOUT,
        InterfaceState.EXIT,
        *TOP_MENU_STATES,
    },
    InterfaceState.MY_ORDERS: {
        InterfaceState.CART_CHECKOUT,
        InterfaceState.EXIT,
        *TOP_MENU_STATES,
    },
    InterfaceState.EXIT: set(),
}


class InterfaceStateMachine:
    def __init__(self, initial_state: InterfaceState = InterfaceState.LOGIN) -> None:
        self.current_state: InterfaceState = initial_state

    def can_transition(self, target: InterfaceState) -> bool:
        return target in ALLOWED_TRANSITIONS.get(self.current_state, set())

    def transition(self, target: InterfaceState) -> InterfaceState:
        if self.can_transition(target):
            self.current_state = target
        return self.current_state