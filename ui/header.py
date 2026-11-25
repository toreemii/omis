from __future__ import annotations

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QWidget

from state_machine import InterfaceState


class TopNavBar(QWidget):
    navigate_requested = pyqtSignal(InterfaceState)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("TopNavBar")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(28, 0, 28, 0)
        layout.setSpacing(14)

        brand = QLabel("ExpoOnline")
        brand.setObjectName("BrandLabel")
        layout.addWidget(brand)
        layout.addStretch()

        nav_items: list[tuple[str, InterfaceState]] = [
            ("Выставки", InterfaceState.EXHIBITIONS_LIST),
            ("Заказы", InterfaceState.MY_ORDERS),
            ("Билеты", InterfaceState.MY_TICKETS),
            ("Личный кабинет", InterfaceState.CABINET),
        ]
        for title, target_state in nav_items:
            btn = QPushButton(title)
            btn.setObjectName("NavLinkBtn")
            btn.clicked.connect(lambda _, s=target_state: self.navigate_requested.emit(s))
            layout.addWidget(btn)