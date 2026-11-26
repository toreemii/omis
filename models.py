from __future__ import annotations
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Protocol


class StreamStatus(str, Enum):
    SCHEDULED = "ЗАПЛАНИРОВАНА"
    LIVE = "ИДЁТ"
    FINISHED = "ЗАВЕРШЕНА"


@dataclass
class Role:
    id: int
    name: str


@dataclass
class Language:
    code: str
    name: str


@dataclass
class AnalyticsEvent:
    event_type: str
    weight: float = 1.0
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class InterestProfile:
    id: int
    category_weights: dict[str, float] = field(default_factory=dict)
    updated_at: date = field(default_factory=date.today)

    def update(self, event: AnalyticsEvent) -> None:
        self.updated_at = date.today()

    def get_top_categories(self, n: int) -> list[str]:
        sorted_cats = sorted(
            self.category_weights.items(), key=lambda item: item[1], reverse=True
        )
        return [cat for cat, _ in sorted_cats[:n]]


@dataclass
class Recommendation:
    id: int
    score: float
    reason: str
    created_at: datetime = field(default_factory=datetime.now)
    viewed: bool = False
    company_id: int | None = None
    product_id: int | None = None

    def mark_as_viewed(self) -> None:
        self.viewed = True


@dataclass
class User:
    id: int
    full_name: str
    email: str
    phone: str
    role: Role | None = None
    interface_language: Language | None = None
    profile: InterestProfile | None = None
    watched_streams: list[Stream] = field(default_factory=list)

    def register(self) -> None:
        pass

    def login(self) -> bool:
        return bool(self.email.strip())

    def select_language(self, language: Language) -> None:
        self.interface_language = language

    def view_recommendations(self) -> list[Recommendation]:
        return []

    def join_stream(self, stream: Stream) -> None:
        if stream not in self.watched_streams:
            self.watched_streams.append(stream)


@dataclass
class Product:
    id: int
    name: str
    description: str
    price: Decimal
    stock: int
    format_tag: str = "Онлайн"
    category: str = ""
    tags: list[str] = field(default_factory=list)

    def check_availability(self) -> bool:
        return self.stock > 0

    def decrease_stock(self, qty: int) -> None:
        if qty > 0 and self.stock >= qty:
            self.stock -= qty

    def get_description(self, language: Language | None = None) -> str:
        return self.description


@dataclass
class Stream:
    id: int
    title: str
    start_time: datetime
    status: StreamStatus
    stream_url: str
    viewer_count: int = 0
    company_id: int | None = None
    exhibition_id: int | None = None
    product_id: int | None = None

    def start(self) -> None:
        self.status = StreamStatus.LIVE

    def finish(self) -> None:
        self.status = StreamStatus.FINISHED

    def add_viewer(self, user: User) -> None:
        self.viewer_count += 1

    def remove_viewer(self, user: User) -> None:
        if self.viewer_count > 0:
            self.viewer_count -= 1


@dataclass
class Company:
    id: int
    name: str
    description: str
    booth_code: str = "00000"
    products: list[Product] = field(default_factory=list)
    streams: list[Stream] = field(default_factory=list)
    categories: list[str] = field(default_factory=list)

    def add_product(self, product: Product) -> None:
        self.products.append(product)

    def upload_catalog(self) -> None:
        pass

    def schedule_stream(self, start_time: datetime) -> Stream | None:
        return None

    def get_description(self, language: Language | None = None) -> str:
        return self.description


@dataclass
class Exhibition:
    id: int
    name: str
    description: str
    start_date: date
    end_date: date
    venue: str = "Минск · Выставочный центр"
    format_label: str = "Живая и онлайн"
    companies: list[Company] = field(default_factory=list)

    def add_company(self, company: Company) -> None:
        self.companies.append(company)

    def open_ticket_sales(self) -> None:
        pass


@dataclass
class Ticket:
    id: int
    price: Decimal
    description: str
    visit_date: date
    qr_code: str
    status: str = "Активен"
    exhibition_id: int | None = None
    user_id: int | None = None

    def activate(self) -> None:
        self.status = "Активен"

    def cancel(self) -> None:
        self.status = "Отменён"


@dataclass
class OrderItem:
    quantity: int
    price: Decimal
    product: Product | None = None


@dataclass
class Order:
    id: int
    order_date: date
    status: str
    delivery_address: str
    tracking_number: str
    total_amount: Decimal
    items: list[OrderItem] = field(default_factory=list)
    user_id: int | None = None

    def calculate_total(self) -> Decimal:
        total = sum((item.price * item.quantity for item in self.items), Decimal("0.00"))
        self.total_amount = total
        return total

    def change_status(self, status: str) -> None:
        self.status = status


@dataclass
class Cart:
    id: int
    items: list[OrderItem] = field(default_factory=list)

    def add_product(self, product: Product, quantity: int = 1) -> None:
        for item in self.items:
            if item.product and item.product.id == product.id:
                item.quantity += quantity
                return
        self.items.append(OrderItem(quantity=quantity, price=product.price, product=product))

    def remove_product(self, product: Product) -> None:
        self.items = [
            item for item in self.items if not (item.product and item.product.id == product.id)
        ]

    def clear(self) -> None:
        self.items.clear()


@dataclass
class Message:
    id: int
    text: str
    sent_time: datetime
    author_id: int
    original_language: Language | None = None
    translated_text: str | None = None


@dataclass
class Chat:
    id: int
    topic: str
    company_id: int
    messages: list[Message] = field(default_factory=list)

    def add_message(self, message: Message) -> None:
        self.messages.append(message)


@dataclass
class StreamChat(Chat):
    stream: Stream | None = None

    def ask_host(self, text: str) -> None:
        pass


@dataclass
class Translation:
    id: int
    object_type: str
    object_id: int
    field_name: str
    source_text: str
    translated_text: str
    created_at: date = field(default_factory=date.today)
    language: Language | None = None

    def get_current(self) -> str:
        return self.translated_text


# --- Интерфейсы внешних систем и моделей ---
class PaymentGateway(Protocol):
    def process_payment(self, amount: Decimal) -> bool:
        ...


class VideoServer(Protocol):
    def create_stream(self) -> str:
        ...

    def get_stream_url(self, stream_key: str) -> str:
        ...

    def close_stream(self, stream_key: str) -> None:
        ...


class ExternalTranslator(Protocol):
    def translate_text(self, text: str, source_lang: str, target_lang: str) -> str:
        ...


class RecommendationModel(Protocol):
    def fit(self, data: list[AnalyticsEvent]) -> None:
        ...

    def predict(self, profile: InterestProfile) -> list[Recommendation]:
        ...

class CatalogService:
    def open_showcase(self, company: Company) -> Company:
        return company

    def get_products(self, company: Company, language: Language | None = None) -> list[Product]:
        return company.products

    def find_exhibition(self, query: str, exhibitions: list[Exhibition]) -> list[Exhibition]:
        q = query.strip().lower()
        if not q:
            return exhibitions
        return [
            ex for ex in exhibitions
            if q in ex.name.lower() or any(q in comp.name.lower() for comp in ex.companies)
        ]

    def get_personalized_showcase(self, user: User) -> list[Product]:
        return []


class TicketService:
    def buy_ticket(self, exhibition: Exhibition, visit_date: date, user: User | None = None) -> Ticket:
        return Ticket(
            id=1,
            price=Decimal("25.00"),
            description=f"Входной билет на «{exhibition.name}»",
            visit_date=visit_date,
            qr_code="QR-EXPO-11111-00001",
            status="Активен",
            exhibition_id=exhibition.id,
            user_id=user.id if user else None,
        )

    def issue_qr(self, ticket: Ticket) -> str:
        return ticket.qr_code


class OrderService:
    def create_order(
        self,
        items: list[OrderItem],
        address: str,
        user: User | None = None,
    ) -> Order:
        total = sum((item.price * item.quantity for item in items), Decimal("0.00")) + Decimal("10.00")
        return Order(
            id=1,
            order_date=date.today(),
            status="Оплачен",
            delivery_address=address,
            tracking_number="TRK-BY-904821",
            total_amount=total,
            items=list(items),
            user_id=user.id if user else None,
        )

    def calculate_delivery(self, order: Order) -> Decimal:
        return Decimal("10.00")

    def pay_order(self, order: Order) -> bool:
        return True

    def generate_tracking_number(self, order: Order) -> str:
        return order.tracking_number

    def cancel_transaction(self, order: Order) -> None:
        order.change_status("Отменён")


class ChatService:
    def send_message(self, chat: Chat, text: str, author_id: int = 1) -> Message:
        msg = Message(
            id=len(chat.messages) + 1,
            text=text,
            sent_time=datetime.now(),
            author_id=author_id,
        )
        chat.add_message(msg)
        return msg

    def get_messages(self, chat: Chat, language: Language | None = None) -> list[Message]:
        return chat.messages


class NotificationService:
    def notify_sale(self, order: Order) -> None:
        pass


class StreamService:
    def schedule_stream(self, company: Company, exhibition: Exhibition) -> Stream | None:
        return None

    def start_stream(self, stream: Stream) -> None:
        stream.start()

    def stop_stream(self, stream: Stream) -> None:
        stream.finish()

    def connect_viewer(self, stream: Stream, user: User) -> None:
        stream.add_viewer(user)


class TranslationService:
    def translate(self, text: str, source_lang: str, target_lang: str) -> str:
        return text

    def detect_language(self, text: str) -> Language:
        return Language(code="ru", name="Русский")

    def find_in_cache(self, obj_id: int, language: Language) -> Translation | None:
        return None

    def translate_message(self, message: Message, language: Language) -> str:
        return message.text


class RecommendationService:
    def get_recommendations(self, user: User, n: int) -> list[Recommendation]:
        return []

    def update_profile(self, event: AnalyticsEvent) -> None:
        pass

    def recalculate_scores(self, profile: InterestProfile) -> None:
        pass


class AnalyticsService:
    def record_stream_view(self, stream: Stream, user: User) -> None:
        pass

    def forward_event_to_recommendation(self, event: AnalyticsEvent) -> None:
        pass

class ModerationService:
    def moderate_content(self, item_label: str) -> str:
        return f"Контент «{item_label}» проверен (заглушка)"

    def assist_user(self, user_email: str, issue: str) -> str:
        return f"Запрос поддержки для {user_email}: {issue} (заглушка)"

class OrganizerService:
    def create_event(self, title: str, venue: str) -> Exhibition:
        return Exhibition(
                id=99999,
                name=title or "Новое мероприятие",
                description="Мероприятие создано организатором",
                start_date=date.today(),
                end_date=date.today(),
                venue=venue or "Площадка проведения",
                format_label="Живая и онлайн",
            )

    def add_event_info(self, exhibition: Exhibition, info: str) -> None:
        if info.strip():
            exhibition.description = info.strip()

    def configure_ticket_sales(self, exhibition: Exhibition) -> None:
        exhibition.open_ticket_sales()