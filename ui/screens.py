from __future__ import annotations

import re
from datetime import date
from decimal import Decimal

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QPainter
from PyQt6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from models import (
    Cart,
    Company,
    Exhibition,
    Order,
    OrderItem,
    OrganizerService,
    ModerationService,
    Product,
    Role,
    Ticket,
    User,
)
from state_machine import InterfaceState, InterfaceStateMachine
from ui.header import TopNavBar

EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def is_valid_email(value: str) -> bool:
    return bool(EMAIL_PATTERN.match(value.strip()))


def make_placeholder_box(height: int = 120) -> QFrame:
    box = QFrame()
    box.setFixedHeight(height)
    box.setStyleSheet("background-color: #B9DCFA; border: none;")
    return box


def make_card(padding: int = 18) -> tuple[QFrame, QVBoxLayout]:
    card = QFrame()
    card.setObjectName("CardBox")
    layout = QVBoxLayout(card)
    layout.setContentsMargins(padding, padding, padding, padding)
    layout.setSpacing(10)
    return card, layout


class QrPlaceholderWidget(QWidget):
    """Условное графическое отображение QR-кода для экрана билета."""

    def __init__(self, size: int = 160, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedSize(size, size)

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#FFFFFF"))
        cells = 15
        cell_w = self.width() / cells
        cell_h = self.height() / cells
        dark = QColor("#0B0F17")

        for r in range(cells):
            for c in range(cells):
                in_top_left = r < 5 and c < 5
                in_top_right = r < 5 and c >= cells - 5
                in_bottom_left = r >= cells - 5 and c < 5
                pattern = (r * 3 + c * 5) % 4 == 0
                if in_top_left or in_top_right or in_bottom_left or pattern:
                    painter.fillRect(
                        int(c * cell_w),
                        int(r * cell_h),
                        int(cell_w) + 1,
                        int(cell_h) + 1,
                        dark,
                    )
        painter.end()


# 1. Вход / регистрация с проверкой email и выбором роли
class LoginScreen(QWidget):
    login_submitted = pyqtSignal(str, str, str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(70, 50, 70, 50)

        left_box = QVBoxLayout()
        left_box.addStretch()
        brand = QLabel("ExpoOnline")
        brand.setStyleSheet("color: #1570D8; font-size: 16px; font-weight: 700;")
        hero = QLabel("Выставки и ярмарки\nонлайн и вживую")
        hero.setStyleSheet("color: #0B0F17; font-size: 42px; font-weight: 800;")
        left_box.addWidget(brand)
        left_box.addWidget(hero)
        left_box.addStretch()

        card, card_layout = make_card(28)
        card.setFixedWidth(380)
        title = QLabel("Вход и выбор роли")
        title.setStyleSheet("font-size: 24px; font-weight: 800;")

        self.email_input = QLineEdit()
        self.email_input.setPlaceholderText("Email (например, abcdgf@gmail.com)")

        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("Пароль (необязательно)")
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)

        role_label = QLabel("Роль:")
        role_label.setObjectName("MutedText")

        self.role_combo = QComboBox()
        self.role_combo.addItems([
            "Посетитель",
            "Организатор",
            "Компания-участник",
            "Модератор / Поддержка",
        ])

        self.error_lbl = QLabel("")
        self.error_lbl.setStyleSheet("color: #C62828; font-weight: 600;")
        self.error_lbl.setWordWrap(True)
        self.error_lbl.hide()

        submit_btn = QPushButton("Войти")
        submit_btn.setObjectName("PrimaryBtn")
        submit_btn.clicked.connect(self._on_submit)

        card_layout.addWidget(title)
        card_layout.addWidget(self.email_input)
        card_layout.addWidget(self.password_input)
        card_layout.addWidget(role_label)
        card_layout.addWidget(self.role_combo)
        card_layout.addWidget(self.error_lbl)
        card_layout.addWidget(submit_btn)

        layout.addLayout(left_box, stretch=1)
        layout.addWidget(card, alignment=Qt.AlignmentFlag.AlignVCenter)

    def _on_submit(self) -> None:
        email = self.email_input.text().strip()
        if not is_valid_email(email):
            self.error_lbl.setText(
                "Ошибка проверки данных: введите корректный email вида name@domain.com."
            )
            self.error_lbl.show()
            return
        self.error_lbl.hide()
        self.login_submitted.emit(email, self.password_input.text(), self.role_combo.currentText())


class ExhibitionsListScreen(QWidget):
    open_exhibition = pyqtSignal(Exhibition)

    def __init__(self, exhibitions: list[Exhibition], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.exhibitions = exhibitions
        self.current_filter = "Все"

        root = QVBoxLayout(self)
        root.setContentsMargins(36, 26, 36, 26)
        root.setSpacing(16)

        title = QLabel("Список выставок")
        title.setObjectName("ScreenTitle")
        root.addWidget(title)

        filter_row = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Поиск выставки или компании")
        self.search_input.textChanged.connect(self.refresh_exhibitions)
        filter_row.addWidget(self.search_input, stretch=1)

        self.filter_group = QButtonGroup(self)
        for label in ("Все", "Живые", "Онлайн"):
            btn = QPushButton(label)
            btn.setObjectName("FilterChip")
            btn.setCheckable(True)
            if label == "Все":
                btn.setChecked(True)
            self.filter_group.addButton(btn)
            btn.clicked.connect(lambda _, f=label: self._set_filter(f))
            filter_row.addWidget(btn)

        root.addLayout(filter_row)

        self.cards_layout = QHBoxLayout()
        self.cards_layout.setSpacing(20)
        root.addLayout(self.cards_layout)
        root.addStretch()

        self.refresh_exhibitions()

    def _set_filter(self, filter_name: str) -> None:
        self.current_filter = filter_name
        self.refresh_exhibitions()

    def refresh_exhibitions(self) -> None:
        while self.cards_layout.count():
            item = self.cards_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        query = self.search_input.text().strip().lower()
        for ex in self.exhibitions:
            matches_query = not query or query in ex.name.lower() or any(
                query in c.name.lower() for c in ex.companies
            )
            matches_filter = (
                self.current_filter == "Все"
                or (self.current_filter == "Живые" and "Живая" in ex.format_label)
                or (self.current_filter == "Онлайн" and "онлайн" in ex.format_label.lower())
            )
            if not (matches_query and matches_filter):
                continue

            card, c_layout = make_card(16)
            c_layout.addWidget(make_placeholder_box(130))

            name_lbl = QLabel(ex.name)
            name_lbl.setObjectName("CardTitle")
            meta_lbl = QLabel(f"{ex.start_date} · {ex.venue}")
            meta_lbl.setObjectName("MutedText")

            badge = QLabel(ex.format_label)
            badge.setObjectName("StatusBadge")
            badge.setFixedWidth(150)

            open_btn = QPushButton("Открыть")
            open_btn.setObjectName("PrimaryBtn")
            open_btn.clicked.connect(lambda _, e=ex: self.open_exhibition.emit(e))

            c_layout.addWidget(name_lbl)
            c_layout.addWidget(meta_lbl)
            c_layout.addWidget(badge)
            c_layout.addWidget(open_btn)
            self.cards_layout.addWidget(card)


class ExhibitionDetailScreen(QWidget):
    open_company = pyqtSignal(Company)
    buy_ticket_clicked = pyqtSignal(Exhibition)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.exhibition: Exhibition | None = None

        root = QHBoxLayout(self)
        root.setContentsMargins(36, 26, 36, 26)
        root.setSpacing(24)

        left_card, left_layout = make_card(20)
        left_layout.addWidget(make_placeholder_box(190))

        self.title_lbl = QLabel("Выставка")
        self.title_lbl.setObjectName("ScreenTitle")
        self.desc_lbl = QLabel("Описание выставки.")
        self.desc_lbl.setObjectName("MutedText")
        self.desc_lbl.setWordWrap(True)

        comp_header = QLabel("Компании-участники")
        comp_header.setObjectName("CardTitle")

        self.companies_row = QHBoxLayout()
        self.companies_row.setSpacing(12)

        left_layout.addWidget(self.title_lbl)
        left_layout.addWidget(self.desc_lbl)
        left_layout.addWidget(comp_header)
        left_layout.addLayout(self.companies_row)
        left_layout.addStretch()

        right_card, right_layout = make_card(20)
        right_card.setFixedWidth(340)
        live_title = QLabel("Живая выставка")
        live_title.setObjectName("CardTitle")
        live_hint = QLabel("Купите билет и получите QR-код для прохода и карту зала.")
        live_hint.setObjectName("MutedText")
        live_hint.setWordWrap(True)

        self.sales_status_lbl = QLabel("Продажа билетов: открыта")
        self.sales_status_lbl.setObjectName("StatusBadge")

        self.buy_btn = QPushButton("Купить билет")
        self.buy_btn.setObjectName("PrimaryBtn")
        self.buy_btn.clicked.connect(
            lambda: self.buy_ticket_clicked.emit(self.exhibition) if self.exhibition else None
        )

        right_layout.addWidget(live_title)
        right_layout.addWidget(live_hint)
        right_layout.addWidget(self.sales_status_lbl)
        right_layout.addWidget(self.buy_btn)
        right_layout.addStretch()

        root.addWidget(left_card, stretch=2)
        root.addWidget(right_card, stretch=1)

    def set_exhibition(self, exhibition: Exhibition) -> None:
        self.exhibition = exhibition
        self.title_lbl.setText(exhibition.name)
        self.desc_lbl.setText(exhibition.description)
        sales_open = getattr(exhibition, "ticket_sales_open", True)
        self.sales_status_lbl.setText(
            "Продажа билетов: открыта" if sales_open else "Продажа билетов: закрыта"
        )
        self.buy_btn.setEnabled(sales_open)

        while self.companies_row.count():
            item = self.companies_row.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        for comp in exhibition.companies:
            btn = QPushButton(comp.name)
            btn.setObjectName("PrimaryBtn")
            btn.clicked.connect(lambda _, c=comp: self.open_company.emit(c))
            self.companies_row.addWidget(btn)
        self.companies_row.addStretch()


class CompanyShowcaseScreen(QWidget):
    add_to_cart_clicked = pyqtSignal(Product)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.company: Company | None = None

        root = QVBoxLayout(self)
        root.setContentsMargins(36, 26, 36, 26)
        root.setSpacing(18)

        header_row = QHBoxLayout()
        logo = QFrame()
        logo.setFixedSize(48, 48)
        logo.setStyleSheet("background-color: #B9DCFA;")
        header_row.addWidget(logo)

        title_col = QVBoxLayout()
        self.company_title = QLabel("Компания")
        self.company_title.setObjectName("ScreenTitle")
        self.company_sub = QLabel("Онлайн-витрина · Каталог товаров")
        self.company_sub.setObjectName("MutedText")
        title_col.addWidget(self.company_title)
        title_col.addWidget(self.company_sub)
        header_row.addLayout(title_col)
        header_row.addStretch()
        root.addLayout(header_row)

        self.grid = QGridLayout()
        self.grid.setSpacing(16)
        root.addLayout(self.grid)
        root.addStretch()

    def set_company(self, company: Company) -> None:
        self.company = company
        self.company_title.setText(company.name)
        self.company_sub.setText(f"Онлайн-витрина · {company.description}")

        while self.grid.count():
            item = self.grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        for idx, prod in enumerate(company.products):
            card, c_layout = make_card(14)
            c_layout.addWidget(make_placeholder_box(110))
            p_name = QLabel(prod.name)
            p_name.setObjectName("CardTitle")
            p_price = QLabel(f"{prod.price} BYN")
            p_price.setObjectName("MutedText")

            add_btn = QPushButton("В корзину")
            add_btn.setObjectName("PrimaryBtn")
            add_btn.clicked.connect(lambda _, p=prod: self.add_to_cart_clicked.emit(p))

            c_layout.addWidget(p_name)
            c_layout.addWidget(p_price)
            c_layout.addWidget(add_btn)
            self.grid.addWidget(card, idx // 4, idx % 4)


class CartCheckoutScreen(QWidget):
    pay_clicked = pyqtSignal(str)

    def __init__(self, cart: Cart, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.cart = cart

        root = QHBoxLayout(self)
        root.setContentsMargins(36, 26, 36, 26)
        root.setSpacing(24)

        left_card, self.left_layout = make_card(22)
        cart_title = QLabel("Корзина")
        cart_title.setObjectName("ScreenTitle")
        self.left_layout.addWidget(cart_title)
        self.items_container = QVBoxLayout()
        self.left_layout.addLayout(self.items_container)
        self.left_layout.addStretch()

        right_card, right_layout = make_card(22)
        right_card.setFixedWidth(360)
        checkout_title = QLabel("Оформление")
        checkout_title.setObjectName("ScreenTitle")
        self.address_input = QLineEdit()
        self.address_input.setPlaceholderText("Адрес доставки")

        self.delivery_lbl = QLabel("Доставка: 10 BYN")
        self.total_lbl = QLabel("Итого: 0 BYN")
        self.total_lbl.setObjectName("CardTitle")

        pay_btn = QPushButton("Оплатить")
        pay_btn.setObjectName("PrimaryBtn")
        pay_btn.clicked.connect(lambda: self.pay_clicked.emit(self.address_input.text()))

        hint = QLabel("После оплаты вы получите трек-номер.")
        hint.setObjectName("MutedText")

        right_layout.addWidget(checkout_title)
        right_layout.addWidget(self.address_input)
        right_layout.addWidget(self.delivery_lbl)
        right_layout.addWidget(self.total_lbl)
        right_layout.addWidget(pay_btn)
        right_layout.addWidget(hint)
        right_layout.addStretch()

        root.addWidget(left_card, stretch=2)
        root.addWidget(right_card, stretch=1)
        self.refresh_cart()

    def refresh_cart(self) -> None:
        while self.items_container.count():
            item = self.items_container.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        subtotal = Decimal("0.00")
        for order_item in self.cart.items:
            row = QHBoxLayout()
            thumb = QFrame()
            thumb.setFixedSize(46, 46)
            thumb.setStyleSheet("background-color: #B9DCFA;")

            info = QVBoxLayout()
            name = order_item.product.name if order_item.product else "Товар"
            title = QLabel(name)
            title.setObjectName("CardTitle")
            qty = QLabel(f"Количество: {order_item.quantity}")
            qty.setObjectName("MutedText")
            info.addWidget(title)
            info.addWidget(qty)

            line_sum = order_item.price * order_item.quantity
            subtotal += line_sum
            price_lbl = QLabel(f"{line_sum} BYN")
            price_lbl.setObjectName("CardTitle")

            row_widget = QWidget()
            row_widget.setLayout(row)
            row.addWidget(thumb)
            row.addLayout(info, stretch=1)
            row.addWidget(price_lbl)
            self.items_container.addWidget(row_widget)

        delivery = Decimal("10.00") if self.cart.items else Decimal("0.00")
        self.delivery_lbl.setText(f"Доставка: {delivery} BYN")
        self.total_lbl.setText(f"Итого: {subtotal + delivery} BYN")


class CabinetScreen(QWidget):
    open_tickets = pyqtSignal()
    open_orders = pyqtSignal()
    open_cart = pyqtSignal()
    open_role_panel = pyqtSignal()
    role_changed = pyqtSignal(str)
    logout_clicked = pyqtSignal()

    def __init__(self, user: User, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.user = user
        root = QHBoxLayout(self)
        root.setContentsMargins(36, 26, 36, 26)
        root.setSpacing(24)

        profile_card, p_layout = make_card(22)
        profile_card.setFixedWidth(340)
        avatar = QFrame()
        avatar.setFixedSize(86, 86)
        avatar.setStyleSheet("background-color: #B9DCFA;")

        self.name_lbl = QLabel(user.full_name)
        self.name_lbl.setStyleSheet("font-size: 20px; font-weight: 800;")
        self.role_lbl = QLabel(user.role.name if user.role else "Посетитель")
        self.role_lbl.setObjectName("StatusBadge")
        self.email_lbl = QLabel(user.email)
        self.email_lbl.setObjectName("MutedText")
        self.phone_lbl = QLabel(user.phone)
        self.phone_lbl.setObjectName("MutedText")

        switch_lbl = QLabel("Сменить роль:")
        switch_lbl.setObjectName("MutedText")
        self.role_switch = QComboBox()
        self.role_switch.addItems([
            "Посетитель",
            "Организатор",
            "Компания-участник",
            "Модератор / Поддержка",
        ])
        self.role_switch.currentTextChanged.connect(self.role_changed.emit)

        logout_btn = QPushButton("Сменить пользователя (Выйти)")
        logout_btn.setObjectName("PrimaryBtn")
        logout_btn.clicked.connect(self.logout_clicked.emit)

        p_layout.addWidget(avatar)
        p_layout.addWidget(self.name_lbl)
        p_layout.addWidget(self.role_lbl)
        p_layout.addWidget(self.email_lbl)
        p_layout.addWidget(self.phone_lbl)
        p_layout.addWidget(switch_lbl)
        p_layout.addWidget(self.role_switch)
        p_layout.addWidget(logout_btn)
        p_layout.addStretch()

        right_col = QVBoxLayout()
        right_col.setSpacing(16)

        r_card, r_layout = make_card(18)
        r_layout.addWidget(QLabel("Панель возможностей роли", objectName="CardTitle"))
        r_layout.addWidget(QLabel("Сценарии Use Case для выбранной роли.", objectName="MutedText"))
        btn_r = QPushButton("Открыть панель роли", objectName="PrimaryBtn")
        btn_r.clicked.connect(self.open_role_panel.emit)
        r_layout.addWidget(btn_r)

        t_card, t_layout = make_card(18)
        t_layout.addWidget(QLabel("Мои билеты", objectName="CardTitle"))
        t_layout.addWidget(QLabel("Билеты на живые выставки и QR-коды для входа.", objectName="MutedText"))
        btn_t = QPushButton("Открыть", objectName="PrimaryBtn")
        btn_t.clicked.connect(self.open_tickets.emit)
        t_layout.addWidget(btn_t)

        o_card, o_layout = make_card(18)
        o_layout.addWidget(QLabel("Мои заказы", objectName="CardTitle"))
        o_layout.addWidget(QLabel("История покупок, статусы и трек-номера.", objectName="MutedText"))
        btn_o = QPushButton("Открыть", objectName="PrimaryBtn")
        btn_o.clicked.connect(self.open_orders.emit)
        o_layout.addWidget(btn_o)

        c_card, c_layout = make_card(18)
        btn_c = QPushButton("Корзина", objectName="PrimaryBtn")
        btn_c.clicked.connect(self.open_cart.emit)
        c_layout.addWidget(btn_c)

        right_col.addWidget(r_card)
        right_col.addWidget(t_card)
        right_col.addWidget(o_card)
        right_col.addWidget(c_card)
        right_col.addStretch()

        root.addWidget(profile_card)
        root.addLayout(right_col, stretch=1)

    def set_user(self, user: User) -> None:
        self.user = user
        role_name = user.role.name if user.role else "Посетитель"
        self.name_lbl.setText(user.full_name)
        self.role_lbl.setText(role_name)
        self.email_lbl.setText(user.email)
        self.phone_lbl.setText(user.phone)
        self.role_switch.blockSignals(True)
        self.role_switch.setCurrentText(role_name)
        self.role_switch.blockSignals(False)


class MyTicketsScreen(QWidget):
    show_qr_clicked = pyqtSignal(Ticket)

    def __init__(self, tickets: list[Ticket], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.tickets = tickets
        self.filter_mode = "Все"

        root = QVBoxLayout(self)
        root.setContentsMargins(36, 26, 36, 26)
        root.setSpacing(14)

        root.addWidget(QLabel("Мои билеты", objectName="ScreenTitle"))

        chips = QHBoxLayout()
        for mode in ("Все", "Активные", "Использованные"):
            btn = QPushButton(mode)
            btn.setObjectName("FilterChip")
            btn.setCheckable(True)
            if mode == "Все":
                btn.setChecked(True)
            btn.clicked.connect(lambda _, m=mode: self._set_mode(m))
            chips.addWidget(btn)
        chips.addStretch()
        root.addLayout(chips)

        self.list_layout = QVBoxLayout()
        self.list_layout.setSpacing(12)
        root.addLayout(self.list_layout)
        root.addStretch()
        self.refresh_tickets()

    def _set_mode(self, mode: str) -> None:
        self.filter_mode = mode
        self.refresh_tickets()

    def refresh_tickets(self) -> None:
        while self.list_layout.count():
            item = self.list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        for ticket in self.tickets:
            if self.filter_mode == "Активные" and ticket.status != "Активен":
                continue
            if self.filter_mode == "Использованные" and ticket.status == "Активен":
                continue

            card, c_layout = make_card(14)
            row = QHBoxLayout()
            bar = QFrame()
            bar.setFixedSize(5, 42)
            bar.setStyleSheet("background-color: #0B0F17;")

            info = QVBoxLayout()
            t_title = QLabel("Выставка «11111»")
            t_title.setObjectName("CardTitle")
            t_sub = QLabel(f"Билет №{ticket.id} · {ticket.visit_date} · Время")
            t_sub.setObjectName("MutedText")
            info.addWidget(t_title)
            info.addWidget(t_sub)

            status_badge = QLabel(ticket.status)
            status_badge.setObjectName("StatusBadge")

            qr_btn = QPushButton("Показать QR")
            qr_btn.setObjectName("PrimaryBtn")
            qr_btn.clicked.connect(lambda _, t=ticket: self.show_qr_clicked.emit(t))

            row.addWidget(bar)
            row.addLayout(info, stretch=1)
            row.addWidget(status_badge)
            row.addWidget(qr_btn)
            c_layout.addLayout(row)
            self.list_layout.addWidget(card)


class TicketDetailScreen(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        root = QVBoxLayout(self)
        root.setContentsMargins(60, 40, 60, 40)

        card, c_layout = make_card(28)
        row = QHBoxLayout()
        row.setSpacing(24)

        left = QVBoxLayout()
        self.title_lbl = QLabel("Выставка «11111»")
        self.title_lbl.setStyleSheet("font-size: 26px; font-weight: 800;")
        self.meta_lbl = QLabel("Дата · Время · Место проведения")
        self.meta_lbl.setObjectName("MutedText")
        self.note_lbl = QLabel(
            "Покажите QR-код на входе. Карта зала и маршрут до стенда доступны в панели посетителя."
        )
        self.note_lbl.setObjectName("MutedText")
        self.note_lbl.setWordWrap(True)

        left.addWidget(self.title_lbl)
        left.addWidget(self.meta_lbl)
        left.addWidget(self.note_lbl)
        left.addStretch()

        self.qr_widget = QrPlaceholderWidget(170)

        row.addLayout(left, stretch=1)
        row.addWidget(self.qr_widget, alignment=Qt.AlignmentFlag.AlignCenter)
        c_layout.addLayout(row)

        root.addWidget(card, alignment=Qt.AlignmentFlag.AlignCenter)

    def set_ticket(self, ticket: Ticket) -> None:
        self.title_lbl.setText("Выставка «11111»")
        self.meta_lbl.setText(f"{ticket.visit_date} · Время · Код: {ticket.qr_code}")


class MyOrdersScreen(QWidget):
    def __init__(self, orders: list[Order], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.orders = orders
        self.status_filter = "Все"

        root = QVBoxLayout(self)
        root.setContentsMargins(36, 26, 36, 26)
        root.setSpacing(14)

        root.addWidget(QLabel("Мои заказы", objectName="ScreenTitle"))

        chips = QHBoxLayout()
        for status in ("Все", "Оплачен", "В пути", "Доставлен"):
            btn = QPushButton(status)
            btn.setObjectName("FilterChip")
            btn.setCheckable(True)
            if status == "Все":
                btn.setChecked(True)
            btn.clicked.connect(lambda _, s=status: self._set_status_filter(s))
            chips.addWidget(btn)
        chips.addStretch()
        root.addLayout(chips)

        self.orders_layout = QVBoxLayout()
        self.orders_layout.setSpacing(12)
        root.addLayout(self.orders_layout)
        root.addStretch()
        self.refresh_orders()

    def _set_status_filter(self, status: str) -> None:
        self.status_filter = status
        self.refresh_orders()

    def refresh_orders(self) -> None:
        while self.orders_layout.count():
            item = self.orders_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        for order in self.orders:
            if self.status_filter != "Все" and order.status != self.status_filter:
                continue

            card, c_layout = make_card(16)
            row = QHBoxLayout()

            info = QVBoxLayout()
            o_title = QLabel(f"Заказ №{order.id}")
            o_title.setObjectName("CardTitle")
            o_sub = QLabel(f"{order.order_date} · Трек-номер: {order.tracking_number}")
            o_sub.setObjectName("MutedText")
            info.addWidget(o_title)
            info.addWidget(o_sub)

            badge = QLabel(order.status)
            badge.setObjectName("StatusBadge")

            amount_lbl = QLabel(f"{order.total_amount} BYN")
            amount_lbl.setObjectName("CardTitle")

            row.addLayout(info, stretch=1)
            row.addWidget(badge)
            row.addWidget(amount_lbl)
            c_layout.addLayout(row)
            self.orders_layout.addWidget(card)


class RoleWorkspaceScreen(QWidget):
    """Рабочее пространство роли с конкретными сценариями Use Case."""

    exhibition_created = pyqtSignal(Exhibition)
    company_media_updated = pyqtSignal(Company)

    def __init__(
        self,
        user: User,
        exhibitions: list[Exhibition],
        companies: list[Company],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.user = user
        self.exhibitions = exhibitions
        self.companies = companies
        self.organizer_service = OrganizerService()
        self.moderation_service = ModerationService()

        root = QVBoxLayout(self)
        root.setContentsMargins(36, 26, 36, 26)
        root.setSpacing(16)

        header_row = QHBoxLayout()
        self.title_lbl = QLabel("Панель роли")
        self.title_lbl.setObjectName("ScreenTitle")
        self.role_badge = QLabel(user.role.name if user.role else "Посетитель")
        self.role_badge.setObjectName("StatusBadge")
        header_row.addWidget(self.title_lbl)
        header_row.addWidget(self.role_badge)
        header_row.addStretch()
        root.addLayout(header_row)

        self.feedback_lbl = QLabel("Выберите действие для выбранной роли.")
        self.feedback_lbl.setObjectName("MutedText")
        self.feedback_lbl.setWordWrap(True)
        root.addWidget(self.feedback_lbl)

        self.panel_stack = QStackedWidget()
        self.visitor_panel = self._build_visitor_panel()
        self.organizer_panel = self._build_organizer_panel()
        self.company_panel = self._build_company_panel()
        self.moderator_panel = self._build_moderator_panel()

        self.panel_stack.addWidget(self.visitor_panel)
        self.panel_stack.addWidget(self.organizer_panel)
        self.panel_stack.addWidget(self.company_panel)
        self.panel_stack.addWidget(self.moderator_panel)
        root.addWidget(self.panel_stack)
        root.addStretch()

        self.refresh_role(user)

    def _build_visitor_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setSpacing(14)

        card, c_layout = make_card(18)
        c_layout.addWidget(QLabel("Запросить карту зала и построить маршрут до стенда", objectName="CardTitle"))
        c_layout.addWidget(
            QLabel("Выберите нужный стенд и нажмите «Запросить карту» или «Построить маршрут».", objectName="MutedText")
        )

        row = QHBoxLayout()
        self.booth_combo = QComboBox()
        for comp in self.companies:
            booth = getattr(comp, "booth_code", None) or f"СТ-{comp.id:03d}"
            self.booth_combo.addItem(f"{comp.name} (Стенд {booth})", comp)

        map_btn = QPushButton("Запросить карту зала")
        map_btn.setObjectName("PrimaryBtn")
        map_btn.clicked.connect(self._on_request_hall_map)

        route_btn = QPushButton("Построить маршрут до стенда")
        route_btn.setObjectName("PrimaryBtn")
        route_btn.clicked.connect(self._on_build_booth_route)

        row.addWidget(self.booth_combo, stretch=1)
        row.addWidget(map_btn)
        row.addWidget(route_btn)
        c_layout.addLayout(row)

        self.map_box = QLabel("Схема зала: [Вход] ── Зона A ── [Стенд 00000] ── [Стенд 00001] ── [Стенд 00002]")
        self.map_box.setStyleSheet("background-color: #B9DCFA; padding: 14px; font-weight: 700;")
        self.map_box.setWordWrap(True)
        c_layout.addWidget(self.map_box)

        self.route_result_lbl = QLabel("Маршрут ещё не построен.")
        self.route_result_lbl.setObjectName("MutedText")
        self.route_result_lbl.setWordWrap(True)
        c_layout.addWidget(self.route_result_lbl)

        layout.addWidget(card)
        return panel

    def _on_request_hall_map(self) -> None:
        self.map_box.setText(
            "Карта зала загружена: Вход → Главный проход → Сектор выставок (Стенды 00000, 00001, 00002) → Выход."
        )
        self.feedback_lbl.setText("Карта зала получена.")

    def _on_build_booth_route(self) -> None:
        comp: Company | None = self.booth_combo.currentData()
        if not comp:
            return
        booth = getattr(comp, "booth_code", None) or f"СТ-{comp.id:03d}"
        self.route_result_lbl.setText(
            f"Маршрут до «{comp.name}» (стенд {booth}): от главного входа пройдите прямо по галерее 40 м, "
            f"поверните налево в сектор экспонентов — стенд {booth} будет справа."
        )
        self.feedback_lbl.setText(f"Построен маршрут до стенда {booth}.")

    def _build_organizer_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setSpacing(14)

        create_card, cr_layout = make_card(18)
        cr_layout.addWidget(QLabel("Создать мероприятие", objectName="CardTitle"))

        form_row = QHBoxLayout()
        self.event_name_input = QLineEdit()
        self.event_name_input.setPlaceholderText("Название выставки или ярмарки")
        self.event_venue_input = QLineEdit()
        self.event_venue_input.setPlaceholderText("Площадка / формат")
        self.event_format_combo = QComboBox()
        self.event_format_combo.addItems(["Живая и онлайн", "Живая", "Онлайн"])
        create_btn = QPushButton("Создать мероприятие")
        create_btn.setObjectName("PrimaryBtn")
        create_btn.clicked.connect(self._on_create_event)

        form_row.addWidget(self.event_name_input, stretch=1)
        form_row.addWidget(self.event_venue_input, stretch=1)
        form_row.addWidget(self.event_format_combo)
        form_row.addWidget(create_btn)
        cr_layout.addLayout(form_row)
        layout.addWidget(create_card)

        info_card, inf_layout = make_card(18)
        inf_layout.addWidget(QLabel("Добавить информацию и настроить продажу билетов", objectName="CardTitle"))

        self.org_event_combo = QComboBox()
        self._reload_organizer_events()

        self.event_info_input = QTextEdit()
        self.event_info_input.setPlaceholderText("Описание программы, расписание, правила участия...")
        self.event_info_input.setFixedHeight(75)

        add_info_btn = QPushButton("Добавить информацию")
        add_info_btn.setObjectName("PrimaryBtn")
        add_info_btn.clicked.connect(self._on_add_event_info)

        self.ticket_sales_chk = QCheckBox("Открыть продажу билетов на мероприятие")
        self.ticket_sales_chk.setChecked(True)
        save_tickets_btn = QPushButton("Настроить продажу билетов")
        save_tickets_btn.setObjectName("PrimaryBtn")
        save_tickets_btn.clicked.connect(self._on_configure_ticket_sales)

        inf_layout.addWidget(self.org_event_combo)
        inf_layout.addWidget(self.event_info_input)
        inf_layout.addWidget(add_info_btn)

        t_row = QHBoxLayout()
        t_row.addWidget(self.ticket_sales_chk)
        t_row.addWidget(save_tickets_btn)
        inf_layout.addLayout(t_row)

        layout.addWidget(info_card)
        return panel

    def _reload_organizer_events(self) -> None:
        current = self.org_event_combo.currentIndex()
        self.org_event_combo.clear()
        for ex in self.exhibitions:
            self.org_event_combo.addItem(ex.name, ex)
        if self.org_event_combo.count() > 0:
            self.org_event_combo.setCurrentIndex(max(0, min(current, self.org_event_combo.count() - 1)))

    def _on_create_event(self) -> None:
        title = self.event_name_input.text().strip() or "Новое мероприятие"
        venue = self.event_venue_input.text().strip() or "Выставочный зал"
        fmt = self.event_format_combo.currentText()
        new_ex = self.organizer_service.create_event(title, venue, fmt)
        if self.companies:
            new_ex.companies.append(self.companies[0])
        self.exhibitions.append(new_ex)
        self._reload_organizer_events()
        self.org_event_combo.setCurrentIndex(self.org_event_combo.count() - 1)
        self.event_name_input.clear()
        self.event_venue_input.clear()
        self.exhibition_created.emit(new_ex)
        self.feedback_lbl.setText(f"Создано мероприятие «{new_ex.name}» ({new_ex.format_label}).")

    def _on_add_event_info(self) -> None:
        ex: Exhibition | None = self.org_event_combo.currentData()
        text = self.event_info_input.toPlainText().strip()
        if not ex:
            return
        self.organizer_service.add_event_info(ex, text or f"Обновлённая программа мероприятия «{ex.name}».")
        self.event_info_input.clear()
        self.exhibition_created.emit(ex)
        self.feedback_lbl.setText(f"Информация для «{ex.name}» обновлена.")

    def _on_configure_ticket_sales(self) -> None:
        ex: Exhibition | None = self.org_event_combo.currentData()
        if not ex:
            return
        enabled = self.ticket_sales_chk.isChecked()
        ex.ticket_sales_open = enabled
        msg = self.organizer_service.configure_ticket_sales(ex, enabled)
        self.feedback_lbl.setText(msg)

    def _build_company_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setSpacing(14)

        card, c_layout = make_card(18)
        c_layout.addWidget(QLabel("Загрузить каталоги и фото / Зарегистрироваться на выставке", objectName="CardTitle"))

        self.comp_select_combo = QComboBox()
        for comp in self.companies:
            self.comp_select_combo.addItem(comp.name, comp)

        self.comp_ex_combo = QComboBox()
        for ex in self.exhibitions:
            self.comp_ex_combo.addItem(ex.name, ex)

        reg_btn = QPushButton("Зарегистрироваться на выставке")
        reg_btn.setObjectName("PrimaryBtn")
        reg_btn.clicked.connect(self._on_company_register)

        self.photo_name_input = QLineEdit()
        self.photo_name_input.setPlaceholderText("Название фото или каталога (например, catalog_2026.pdf / photo_stand.jpg)")

        upload_btn = QPushButton("Загрузить каталоги и фото")
        upload_btn.setObjectName("PrimaryBtn")
        upload_btn.clicked.connect(self._on_upload_catalog_photo)

        notif_btn = QPushButton("Проверить подтверждение и уведомления о продажах")
        notif_btn.setObjectName("PrimaryBtn")
        notif_btn.clicked.connect(self._on_company_notifications)

        c_layout.addWidget(QLabel("Компания:", objectName="MutedText"))
        c_layout.addWidget(self.comp_select_combo)
        c_layout.addWidget(QLabel("Выставка:", objectName="MutedText"))
        c_layout.addWidget(self.comp_ex_combo)
        c_layout.addWidget(reg_btn)
        c_layout.addWidget(self.photo_name_input)
        c_layout.addWidget(upload_btn)
        c_layout.addWidget(notif_btn)

        layout.addWidget(card)
        return panel

    def _on_company_register(self) -> None:
        comp: Company | None = self.comp_select_combo.currentData()
        ex: Exhibition | None = self.comp_ex_combo.currentData()
        if not comp or not ex:
            return
        if comp not in ex.companies:
            ex.companies.append(comp)
            self.exhibition_created.emit(ex)
        self.feedback_lbl.setText(
            f"Подтверждение регистрации: «{comp.name}» зарегистрирована на «{ex.name}»."
        )

    def _on_upload_catalog_photo(self) -> None:
        comp: Company | None = self.comp_select_combo.currentData()
        if not comp:
            return
        label = self.photo_name_input.text().strip() or "Фото стенда и каталог"
        new_prod = Product(
            id=len(comp.products) + 100,
            name=label,
            description="Загружено компанией-участником",
            price=Decimal("50.00"),
            stock=10,
        )
        comp.products.append(new_prod)
        self.photo_name_input.clear()
        self.company_media_updated.emit(comp)
        self.feedback_lbl.setText(f"Материал «{label}» загружен в витрину «{comp.name}».")

    def _on_company_notifications(self) -> None:
        comp: Company | None = self.comp_select_combo.currentData()
        name = comp.name if comp else "Компания"
        self.feedback_lbl.setText(
            f"[{name}] Регистрация подтверждена. Новое уведомление о продаже: оформлен заказ на 120 BYN."
        )

    def _build_moderator_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setSpacing(14)

        card, c_layout = make_card(18)
        c_layout.addWidget(QLabel("Модерация контента и помощь при сбоях", objectName="CardTitle"))

        self.mod_item_input = QLineEdit()
        self.mod_item_input.setPlaceholderText("Карточка выставки, каталог или фото на проверку")

        mod_btn = QPushButton("Модерировать контент")
        mod_btn.setObjectName("PrimaryBtn")
        mod_btn.clicked.connect(self._on_moderate)

        self.issue_input = QLineEdit()
        self.issue_input.setPlaceholderText("Описание сбоя или обращения пользователя")

        support_btn = QPushButton("Помогать при сбоях пользователям")
        support_btn.setObjectName("PrimaryBtn")
        support_btn.clicked.connect(self._on_assist)

        c_layout.addWidget(self.mod_item_input)
        c_layout.addWidget(mod_btn)
        c_layout.addWidget(self.issue_input)
        c_layout.addWidget(support_btn)

        layout.addWidget(card)
        return panel

    def _on_moderate(self) -> None:
        item = self.mod_item_input.text().strip() or "Витрина участника"
        self.feedback_lbl.setText(self.moderation_service.moderate_content(item))
        self.mod_item_input.clear()

    def _on_assist(self) -> None:
        issue = self.issue_input.text().strip() or "Ошибка отображения страницы"
        self.feedback_lbl.setText(self.moderation_service.assist_user(self.user.email, issue))
        self.issue_input.clear()

    def refresh_role(self, user: User) -> None:
        self.user = user
        role_name = user.role.name if user.role else "Посетитель"
        self.role_badge.setText(role_name)
        self.title_lbl.setText(f"Панель роли — {role_name}")
        self._reload_organizer_events()

        if role_name == "Организатор":
            self.panel_stack.setCurrentWidget(self.organizer_panel)
        elif role_name == "Компания-участник":
            self.panel_stack.setCurrentWidget(self.company_panel)
        elif role_name == "Модератор / Поддержка":
            self.panel_stack.setCurrentWidget(self.moderator_panel)
        else:
            self.panel_stack.setCurrentWidget(self.visitor_panel)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("ExpoOnline — Платформа для виртуальных выставок и ярмарок")
        self.resize(1180, 740)

        self.state_machine = InterfaceStateMachine(InterfaceState.LOGIN)

        self.user = User(
            id=1,
            full_name="ФИО пользователя",
            email="email@example.com",
            phone="+000 00 000-00-00",
            role=Role(id=1, name="Посетитель"),
        )
        self.cart = Cart(id=1)

        comp_0 = Company(
            id=1,
            name="Компания «00000»",
            description="Каталог товаров · Стенд 00000",
            booth_code="00000",
            products=[
                Product(1, "Товар 1", "Описание товара 1", Decimal("120.00"), 10),
                Product(2, "Товар 2", "Описание товара 2", Decimal("250.00"), 5),
                Product(3, "Товар 3", "Описание товара 3", Decimal("85.00"), 8),
                Product(4, "Товар 4", "Описание товара 4", Decimal("310.00"), 3),
            ],
        )
        comp_1 = Company(id=2, name="Компания «00001»", description="Каталог товаров", booth_code="00001")
        comp_2 = Company(id=3, name="Компания «00002»", description="Каталог товаров", booth_code="00002")
        self.companies = [comp_0, comp_1, comp_2]

        self.exhibitions = [
            Exhibition(
                id=11111,
                name="Выставка «11111»",
                description="Описание выставки, программа мероприятия, дата и место проведения.",
                start_date=date(2026, 12, 10),
                end_date=date(2026, 12, 12),
                venue="Место проведения",
                format_label="Живая",
                companies=[comp_0, comp_1, comp_2],
            ),
            Exhibition(
                id=22222,
                name="Выставка «22222»",
                description="Онлайн-выставка экспонентов.",
                start_date=date(2026, 12, 15),
                end_date=date(2026, 12, 20),
                venue="Онлайн",
                format_label="Онлайн",
                companies=[comp_0],
            ),
            Exhibition(
                id=33333,
                name="Ярмарка «33333»",
                description="Живая и онлайн ярмарка.",
                start_date=date(2026, 12, 22),
                end_date=date(2026, 12, 25),
                venue="Место проведения",
                format_label="Живая и онлайн",
                companies=[comp_1, comp_2],
            ),
        ]

        self.tickets = [
            Ticket(1, Decimal("25.00"), "Билет №1", date(2026, 12, 10), "QR-11111-1", "Активен", 11111, 1),
            Ticket(2, Decimal("25.00"), "Билет №2", date(2026, 12, 11), "QR-11111-2", "Активен", 11111, 1),
            Ticket(3, Decimal("25.00"), "Билет №3", date(2026, 12, 12), "QR-11111-3", "Использован", 11111, 1),
        ]

        self.orders = [
            Order(1, date(2026, 11, 20), "Оплачен", "Минск", "—", Decimal("120.00"), [], 1),
            Order(2, date(2026, 11, 21), "В пути", "Минск", "000000", Decimal("250.00"), [], 1),
            Order(3, date(2026, 11, 22), "Доставлен", "Минск", "000000", Decimal("310.00"), [], 1),
        ]

        central = QWidget()
        central.setObjectName("CentralRoot")
        self.setCentralWidget(central)

        root_layout = QVBoxLayout(central)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        self.nav_bar = TopNavBar()
        self.nav_bar.navigate_requested.connect(self.navigate_to)
        root_layout.addWidget(self.nav_bar)

        self.stack = QStackedWidget()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidget(self.stack)
        root_layout.addWidget(scroll)

        self.login_screen = LoginScreen()
        self.exhibitions_screen = ExhibitionsListScreen(self.exhibitions)
        self.exhibition_detail_screen = ExhibitionDetailScreen()
        self.showcase_screen = CompanyShowcaseScreen()
        self.cart_screen = CartCheckoutScreen(self.cart)
        self.cabinet_screen = CabinetScreen(self.user)
        self.tickets_screen = MyTicketsScreen(self.tickets)
        self.ticket_detail_screen = TicketDetailScreen()
        self.orders_screen = MyOrdersScreen(self.orders)
        self.role_workspace_screen = RoleWorkspaceScreen(self.user, self.exhibitions, self.companies)

        self._state_to_widget: dict[InterfaceState, QWidget] = {
            InterfaceState.LOGIN: self.login_screen,
            InterfaceState.EXHIBITIONS_LIST: self.exhibitions_screen,
            InterfaceState.EXHIBITION_PAGE: self.exhibition_detail_screen,
            InterfaceState.COMPANY_SHOWCASE: self.showcase_screen,
            InterfaceState.CART_CHECKOUT: self.cart_screen,
            InterfaceState.CABINET: self.cabinet_screen,
            InterfaceState.MY_TICKETS: self.tickets_screen,
            InterfaceState.TICKET_QR: self.ticket_detail_screen,
            InterfaceState.MY_ORDERS: self.orders_screen,
            InterfaceState.ROLE_WORKSPACE: self.role_workspace_screen,
        }

        for widget in self._state_to_widget.values():
            self.stack.addWidget(widget)

        self._wire_signals()
        self.navigate_to(InterfaceState.LOGIN)

    def _wire_signals(self) -> None:
        self.login_screen.login_submitted.connect(
            lambda email, _, role_name: self._on_login(email, role_name)
        )
        self.exhibitions_screen.open_exhibition.connect(self._on_open_exhibition)
        self.exhibition_detail_screen.open_company.connect(self._on_open_company)
        self.exhibition_detail_screen.buy_ticket_clicked.connect(self._on_buy_ticket)
        self.showcase_screen.add_to_cart_clicked.connect(self._on_add_to_cart)
        self.cart_screen.pay_clicked.connect(self._on_pay_order)

        self.cabinet_screen.open_role_panel.connect(
            lambda: self.navigate_to(InterfaceState.ROLE_WORKSPACE)
        )
        self.cabinet_screen.open_tickets.connect(
            lambda: self.navigate_to(InterfaceState.MY_TICKETS)
        )
        self.cabinet_screen.open_orders.connect(
            lambda: self.navigate_to(InterfaceState.MY_ORDERS)
        )
        self.cabinet_screen.open_cart.connect(
            lambda: self.navigate_to(InterfaceState.CART_CHECKOUT)
        )
        self.cabinet_screen.role_changed.connect(self._on_role_changed)
        self.cabinet_screen.logout_clicked.connect(
            lambda: self.navigate_to(InterfaceState.LOGIN)
        )
        self.tickets_screen.show_qr_clicked.connect(self._on_show_qr)

        self.role_workspace_screen.exhibition_created.connect(
            lambda _: self.exhibitions_screen.refresh_exhibitions()
        )
        self.role_workspace_screen.company_media_updated.connect(self._on_company_media_updated)

    def _on_company_media_updated(self, comp: Company) -> None:
        if self.showcase_screen.company is comp:
            self.showcase_screen.set_company(comp)

    def _apply_role(self, role_name: str) -> None:
        role_ids = {
            "Посетитель": 1,
            "Организатор": 2,
            "Компания-участник": 3,
            "Модератор / Поддержка": 4,
        }
        self.user.role = Role(id=role_ids.get(role_name, 1), name=role_name)
        self.cabinet_screen.set_user(self.user)
        self.role_workspace_screen.refresh_role(self.user)

    def _on_role_changed(self, role_name: str) -> None:
        self._apply_role(role_name)

    def _on_login(self, email: str, role_name: str = "Посетитель") -> None:
        if email.strip():
            self.user.email = email.strip()
        self._apply_role(role_name)
        if role_name == "Посетитель":
            self.navigate_to(InterfaceState.EXHIBITIONS_LIST)
        else:
            self.navigate_to(InterfaceState.ROLE_WORKSPACE)

    def navigate_to(self, target: InterfaceState) -> None:
        if target == InterfaceState.EXIT:
            self.close()
            return
        widget = self._state_to_widget.get(target)
        if widget is not None:
            if target == InterfaceState.ROLE_WORKSPACE:
                self.role_workspace_screen.refresh_role(self.user)
            self.state_machine.transition(target)
            self.nav_bar.setVisible(target != InterfaceState.LOGIN)
            self.stack.setCurrentWidget(widget)

    def _on_open_exhibition(self, exhibition: Exhibition) -> None:
        self.exhibition_detail_screen.set_exhibition(exhibition)
        self.navigate_to(InterfaceState.EXHIBITION_PAGE)

    def _on_open_company(self, company: Company) -> None:
        self.showcase_screen.set_company(company)
        self.navigate_to(InterfaceState.COMPANY_SHOWCASE)

    def _on_buy_ticket(self, exhibition: Exhibition) -> None:
        new_ticket = Ticket(
            id=len(self.tickets) + 1,
            price=Decimal("25.00"),
            description=f"Билет на {exhibition.name}",
            visit_date=exhibition.start_date,
            qr_code=f"QR-{exhibition.id}-{len(self.tickets) + 1}",
            status="Активен",
            exhibition_id=exhibition.id,
            user_id=self.user.id,
        )
        self.tickets.append(new_ticket)
        self.tickets_screen.refresh_tickets()
        self.ticket_detail_screen.set_ticket(new_ticket)
        self.navigate_to(InterfaceState.TICKET_QR)

    def _on_add_to_cart(self, product: Product) -> None:
        self.cart.add_product(product, quantity=1)
        self.cart_screen.refresh_cart()
        self.navigate_to(InterfaceState.CART_CHECKOUT)

    def _on_pay_order(self, address: str) -> None:
        subtotal = sum((i.price * i.quantity for i in self.cart.items), Decimal("0.00"))
        delivery = Decimal("10.00") if self.cart.items else Decimal("0.00")
        new_order = Order(
            id=len(self.orders) + 1,
            order_date=date.today(),
            status="Оплачен",
            delivery_address=address.strip() or "Адрес не указан",
            tracking_number=f"TRK-{100000 + len(self.orders) + 1}",
            total_amount=subtotal + delivery,
            items=[OrderItem(i.quantity, i.price, i.product) for i in self.cart.items],
            user_id=self.user.id,
        )
        self.orders.insert(0, new_order)
        self.cart.clear()
        self.cart_screen.refresh_cart()
        self.orders_screen.refresh_orders()
        self.navigate_to(InterfaceState.MY_ORDERS)

    def _on_show_qr(self, ticket: Ticket) -> None:
        self.ticket_detail_screen.set_ticket(ticket)
        self.navigate_to(InterfaceState.TICKET_QR)