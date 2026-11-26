from __future__ import annotations

from datetime import date
from decimal import Decimal

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QPainter
from PyQt6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from models import (
    Cart,
    Company,
    Exhibition,
    Order,
    OrderItem,
    Product,
    Role,
    Ticket,
    User,
)
from state_machine import InterfaceState, InterfaceStateMachine
from ui.header import TopNavBar


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


class LoginScreen(QWidget):
    login_submitted = pyqtSignal(str, str)

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
        card.setFixedWidth(360)
        title = QLabel("Вход")
        title.setStyleSheet("font-size: 24px; font-weight: 800;")
        self.email_input = QLineEdit()
        self.email_input.setPlaceholderText("Email")
        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("Пароль")
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)

        submit_btn = QPushButton("Войти")
        submit_btn.setObjectName("PrimaryBtn")
        submit_btn.clicked.connect(
            lambda: self.login_submitted.emit(self.email_input.text(), self.password_input.text())
        )

        card_layout.addWidget(title)
        card_layout.addWidget(self.email_input)
        card_layout.addWidget(self.password_input)
        card_layout.addWidget(submit_btn)

        layout.addLayout(left_box, stretch=1)
        layout.addWidget(card, alignment=Qt.AlignmentFlag.AlignVCenter)


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
        self.search_input.textChanged.connect(self._rebuild_cards)
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

        self._rebuild_cards()

    def _set_filter(self, filter_name: str) -> None:
        self.current_filter = filter_name
        self._rebuild_cards()

    def _rebuild_cards(self) -> None:
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
            meta_lbl = QLabel(f"Дата · {ex.venue}")
            meta_lbl.setObjectName("MutedText")

            badge = QLabel(ex.format_label)
            badge.setObjectName("StatusBadge")
            badge.setFixedWidth(130)

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

        self.title_lbl = QLabel("Выставка «11111»")
        self.title_lbl.setObjectName("ScreenTitle")
        self.desc_lbl = QLabel("Описание выставки, программа мероприятия, дата и место проведения.")
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

        buy_btn = QPushButton("Купить билет")
        buy_btn.setObjectName("PrimaryBtn")
        buy_btn.clicked.connect(
            lambda: self.buy_ticket_clicked.emit(self.exhibition) if self.exhibition else None
        )

        right_layout.addWidget(live_title)
        right_layout.addWidget(live_hint)
        right_layout.addWidget(buy_btn)
        right_layout.addStretch()

        root.addWidget(left_card, stretch=2)
        root.addWidget(right_card, stretch=1)

    def set_exhibition(self, exhibition: Exhibition) -> None:
        self.exhibition = exhibition
        self.title_lbl.setText(exhibition.name)
        self.desc_lbl.setText(exhibition.description)

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
        self.company_title = QLabel("Компания «00000»")
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

        p_layout.addWidget(avatar)
        p_layout.addWidget(self.name_lbl)
        p_layout.addWidget(self.role_lbl)
        p_layout.addWidget(self.email_lbl)
        p_layout.addWidget(self.phone_lbl)
        p_layout.addStretch()

        right_col = QVBoxLayout()
        right_col.setSpacing(16)

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

        right_col.addWidget(t_card)
        right_col.addWidget(o_card)
        right_col.addWidget(c_card)
        right_col.addStretch()

        root.addWidget(profile_card)
        root.addLayout(right_col, stretch=1)

    def set_user(self, user: User) -> None:
        self.user = user
        self.name_lbl.setText(user.full_name)
        self.email_lbl.setText(user.email)
        self.phone_lbl.setText(user.phone)


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
            "Покажите QR-код на входе. Карта зала и маршрут до стенда «00000» доступны в билете."
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


from PyQt6.QtWidgets import QComboBox


ROLE_USE_CASES: dict[str, list[tuple[str, str]]] = {
    "Посетитель": [
        ("Найти выставку в каталоге", "Переход к каталогу выставок и поиску"),
        ("Купить входной билет и получить QR-код", "Оформление билета и просмотр QR-кода"),
        ("Запросить карту зала и маршрут до стенда", "Построение маршрута до стенда компании"),
        ("Просмотреть витрину и оформить заказ", "Добавление товаров в корзину и оплата"),
    ],
    "Организатор": [
        ("Создать мероприятие", "Заглушка создания страницы выставки/ярмарки"),
        ("Добавить информацию", "Заглушка заполнения описания, даты и программы"),
        ("Настроить продажу билетов", "Заглушка открытия и параметров продажи билетов"),
    ],
    "Компания-участник": [
        ("Зарегистрироваться на выставке", "Заглушка подачи заявки на участие в выставке"),
        ("Загрузить каталоги и фото", "Заглушка загрузки товаров, фото и PDF-каталогов"),
        ("Получить подтверждение регистрации", "Заглушка статуса подтверждения участия"),
        ("Получить уведомление о новой продаже", "Заглушка оповещения о заказе от посетителя"),
    ],
    "Модератор / Поддержка": [
        ("Модерировать контент", "Заглушка проверки материалов выставок и компаний"),
        ("Помогать при сбоях пользователям", "Заглушка обработки обращений и инцидентов"),
    ],
}


class RoleWorkspaceScreen(QWidget):
    """Экран сценариев выбранной роли по диаграмме вариантов использования."""

    def __init__(self, user: User, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.user = user

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

        self.status_hint = QLabel("Выберите действие для проверки заглушки варианта использования.")
        self.status_hint.setObjectName("MutedText")
        root.addWidget(self.status_hint)

        self.cards_layout = QVBoxLayout()
        self.cards_layout.setSpacing(12)
        root.addLayout(self.cards_layout)
        root.addStretch()

        self.refresh_role(user)

    def refresh_role(self, user: User) -> None:
        self.user = user
        role_name = user.role.name if user.role else "Посетитель"
        self.role_badge.setText(role_name)
        self.title_lbl.setText(f"Панель роли — {role_name}")

        while self.cards_layout.count():
            item = self.cards_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        for action_title, action_desc in ROLE_USE_CASES.get(role_name, ROLE_USE_CASES["Посетитель"]):
            card, c_layout = make_card(14)
            row = QHBoxLayout()

            text_col = QVBoxLayout()
            t_lbl = QLabel(action_title)
            t_lbl.setObjectName("CardTitle")
            d_lbl = QLabel(action_desc)
            d_lbl.setObjectName("MutedText")
            text_col.addWidget(t_lbl)
            text_col.addWidget(d_lbl)

            run_btn = QPushButton("Выполнить")
            run_btn.setObjectName("PrimaryBtn")
            run_btn.clicked.connect(
                lambda _, name=action_title: self.status_hint.setText(
                    f"[{role_name}] Запущен сценарий «{name}» (заглушка)."
                )
            )

            row.addLayout(text_col, stretch=1)
            row.addWidget(run_btn)
            c_layout.addLayout(row)
            self.cards_layout.addWidget(card)

class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("ExpoOnline — Платформа для виртуальных выставок и ярмарок")
        self.resize(1180, 740)

        self.state_machine = InterfaceStateMachine(InterfaceState.LOGIN)

        # Демонстрационные данные по сценариям отчёта
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
        }

        for widget in self._state_to_widget.values():
            self.stack.addWidget(widget)

        self._wire_signals()
        self.navigate_to(InterfaceState.LOGIN)

    def _wire_signals(self) -> None:
        self.login_screen.login_submitted.connect(
            lambda email, _: self._on_login(email)
        )
        self.exhibitions_screen.open_exhibition.connect(self._on_open_exhibition)
        self.exhibition_detail_screen.open_company.connect(self._on_open_company)
        self.exhibition_detail_screen.buy_ticket_clicked.connect(self._on_buy_ticket)
        self.showcase_screen.add_to_cart_clicked.connect(self._on_add_to_cart)
        self.cart_screen.pay_clicked.connect(self._on_pay_order)

        self.cabinet_screen.open_tickets.connect(
            lambda: self.navigate_to(InterfaceState.MY_TICKETS)
        )
        self.cabinet_screen.open_orders.connect(
            lambda: self.navigate_to(InterfaceState.MY_ORDERS)
        )
        self.cabinet_screen.open_cart.connect(
            lambda: self.navigate_to(InterfaceState.CART_CHECKOUT)
        )
        self.tickets_screen.show_qr_clicked.connect(self._on_show_qr)

    def navigate_to(self, target: InterfaceState) -> None:
        if target == InterfaceState.EXIT:
            self.close()
            return
        widget = self._state_to_widget.get(target)
        if widget is not None:
            self.state_machine.transition(target)
            self.nav_bar.setVisible(target != InterfaceState.LOGIN)
            self.stack.setCurrentWidget(widget)

    def _on_login(self, email: str) -> None:
        if email.strip():
            self.user.email = email.strip()
            self.cabinet_screen.set_user(self.user)
        self.navigate_to(InterfaceState.EXHIBITIONS_LIST)

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