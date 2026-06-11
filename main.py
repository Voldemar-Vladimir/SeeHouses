import uvicorn
import datetime
from datetime import datetime, date, timedelta, timezone
from fastapi.security import HTTPBasic
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from starlette.responses import RedirectResponse
from starlette.staticfiles import StaticFiles
from models import SessionLocal, Booking
from fastapi import FastAPI, HTTPException, Form, Depends, Request
from mako.lookup import TemplateLookup
import requests
from Admin_Info import token, chat_id, secret
from apscheduler.schedulers.background import BackgroundScheduler

# -------------------- Планировщик очистки просроченных броней --------------------
def clean_expired_bookings():
    db = SessionLocal()
    now_utc = datetime.now(timezone.utc)
    deleted = db.query(Booking).filter(
        Booking.payment_status == 'pending',
        Booking.expires_at < now_utc
    ).delete()
    db.commit()
    db.close()
    if deleted:
        print(f"Удалено {deleted} просроченных неоплаченных броней")

scheduler = BackgroundScheduler()
scheduler.add_job(clean_expired_bookings, 'interval', hours=1)
scheduler.start()
# --------------------------------------------------------------------------------

secret_key = secret()
security = HTTPBasic()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

app = FastAPI()
template_lookup = TemplateLookup(directories=["templates"])
app.mount("/static", StaticFiles(directory="static"), name="static")

homes = [
    {"id": 1, "price_per_day": 6000, "distance_to_sea": 300, "rooms": 4, "pool": False,
     "img": "/static/img/home1.png",
     "img_room": ["/static/img/img.png", "/static/img/img_1.png", "/static/img/img_2.png", "/static/img/img_3.png",
                  "/static/img/img_4.png", "/static/img/img_5.png", "/static/img/img_6.png", "/static/img/img_7.png",
                  "/static/img/img_8.png", "/static/img/img_9.png"],
     "tv": True, "wifi": True, "batut": False, "rating": 5},
]

@app.get("/")
def root(request: Request):
    template = template_lookup.get_template("index.html")
    return HTMLResponse(template.render(homes=homes))

# ----- Проверка доступности и API для календаря -----
def is_home_available(home_id: int, check_in: date, check_out: date, db: Session):
    overlapping = db.query(Booking).filter(
        Booking.home_id == home_id,
        Booking.status == 'confirmed',
        Booking.check_in < check_out,
        Booking.check_out > check_in
    ).first()
    return overlapping is None

@app.get("/api/blocked_dates/{home_id}")
def get_blocked_dates(home_id: int, db: Session = Depends(get_db)):
    bookings = db.query(Booking).filter(
        Booking.home_id == home_id,
        Booking.status == 'confirmed'
    ).all()
    blocked = []
    for b in bookings:
        delta = (b.check_out - b.check_in).days
        for i in range(delta):
            date_str = (b.check_in + timedelta(days=i)).isoformat()
            blocked.append(date_str)
    return {"blocked": blocked}
# ----------------------------------------------------

@app.post("/booking")
def create_form(
    home_id: int = Form(...),
    check_in: str = Form(...),          # строка
    check_out: str = Form(...),         # строка
    name: str = Form(...),
    phone: str = Form(...),
    email: str = Form(""),
    mini_bar: bool = Form(False),
    transfer: bool = Form(False),
    peoples: str = Form(...),
    db: Session = Depends(get_db)
):
    # Преобразуем строки в даты
    try:
        check_in_date = datetime.strptime(check_in, '%Y-%m-%d').date()
        check_out_date = datetime.strptime(check_out, '%Y-%m-%d').date()
    except ValueError:
        raise HTTPException(400, "Неверный формат даты")

    # Проверяем, свободны ли даты
    if not is_home_available(home_id, check_in_date, check_out_date, db):
        raise HTTPException(400, "Эти дни уже забронированы")

    days = (check_out_date - check_in_date).days
    if days <= 0:
        raise HTTPException(400, "Дата выезда должна быть позже даты заезда")
    if days < 2:
        raise HTTPException(400, "Минимальная длительность — 2 дня")

    home = next((h for h in homes if h["id"] == home_id), None)
    if not home:
        raise HTTPException(404, "Дом не найден")

    price = home["price_per_day"] * days
    if mini_bar:
        price += 4000
    if transfer:
        price += 1500

    booking = Booking(
        home_id=home_id,
        check_in=check_in_date,
        check_out=check_out_date,
        name=name,
        phone=phone,
        email=email,
        mini_bar=mini_bar,
        transfer=transfer,
        total_price=price,
        peoples=peoples,
        payment_status='pending',
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=30)
    )
    db.add(booking)
    db.commit()

    message = f"Новый заказ!\nДом №{home_id}\nИмя: {name}\nТелефон: {phone}\nДаты: {check_in} – {check_out}\nГостей: {peoples}\nСумма: {price}₽"
    RostovHomes(message)
    return RedirectResponse(url=f"/success?booking_id={booking.id}", status_code=303)

# -------------------- Фейковая оплата --------------------
@app.get("/fake_pay/{booking_id}")
def fake_pay(booking_id: int, db: Session = Depends(get_db)):
    booking = db.get(Booking, booking_id)  # новый стиль
    if not booking:
        raise HTTPException(404, "Бронь не найдена")
    if booking.status == 'confirmed':
        return RedirectResponse(url=f"/success?booking_id={booking_id}")
    booking.status = 'confirmed'
    booking.payment_status = 'paid'
    db.commit()
    RostovHomes(f"✅ Фейк-оплата! Бронь #{booking.id} подтверждена.")
    return RedirectResponse(url=f"/success?booking_id={booking_id}")

@app.post("/webhook/yookassa")
async def yookassa_webhook(request: Request, db: Session = Depends(get_db)):
    body = await request.json()
    if body.get('event') == 'payment.succeeded':
        payment_id = body['object']['id']
        booking = db.query(Booking).filter_by(payment_id=payment_id).first()
        if booking:
            booking.status = 'confirmed'
            booking.payment_status = 'paid'
            db.commit()
            RostovHomes(f"✅ Оплачено! Бронь #{booking.id} подтверждена.")
    return {"ok": True}

@app.get("/success")
def success(booking_id: int = None, db: Session = Depends(get_db)):
    booking = db.get(Booking, booking_id) if booking_id else None
    template = template_lookup.get_template("success.html")
    if not booking:
        return HTMLResponse(template.render(all=None))
    return HTMLResponse(template.render(all=booking))

@app.get("/booking")
def show_booking_form(request: Request, home_id: int = None):
    if home_id is None:
        raise HTTPException(400, "Не указан ID домика")
    home = next((h for h in homes if h["id"] == home_id), None)
    if not home:
        raise HTTPException(404, "Домик не найден")
    template = template_lookup.get_template("booking.html")
    return HTMLResponse(template.render(
        home_id=home_id,
        img_rooms=home["img_room"],
        price_per_day=home["price_per_day"]
    ))

def RostovHomes(message):
    # Используем импортированные token и chat_id как функции (или как строки, смотри как в Admin_Info)
    # Допустим, что token() и chat_id() возвращают нужные значения
    t = token() if callable(token) else token
    cid = chat_id() if callable(chat_id) else chat_id
    url = f"https://api.telegram.org/bot{t}/sendMessage"
    data = {"chat_id": cid, "text": message}
    try:
        requests.post(url, json=data, timeout=5, proxies={"http": None, "https": None})
    except Exception as e:
        print(f"Ошибка отправки в Telegram: {e}")

@app.get("/admin/{password}")
def admin(password, db: Session = Depends(get_db)):
    if password == secret_key:
        bookings = db.query(Booking).order_by(Booking.created_at.desc()).all()
        template = template_lookup.get_template("admin.html")
        return HTMLResponse(template.render(bookings=bookings, password=password))
    else:
        raise HTTPException(404)

@app.get("/admin/{password}/confirm/{booking_id}")
def confirm(password, booking_id, db: Session = Depends(get_db)):
    if password != secret_key: raise HTTPException(404)
    booking = db.get(Booking, booking_id)
    if not booking: raise HTTPException(404)
    booking.status = "confirmed"
    db.commit()
    return RedirectResponse(url=f"/admin/{password}", status_code=303)

@app.get("/admin/{password}/cancel/{booking_id}")
def cancel(password, booking_id, db: Session = Depends(get_db)):
    if password != secret_key: raise HTTPException(404)
    booking = db.get(Booking, booking_id)
    if not booking: raise HTTPException(404)
    booking.status = "cancelled"
    db.commit()
    return RedirectResponse(url=f"/admin/{password}", status_code=303)

@app.get("/login")
def login_page(request: Request):
    template = template_lookup.get_template("login.html")
    return HTMLResponse(template.render())

@app.post("/login")
def login_check(pin: str = Form(...)):
    if pin == secret_key:
        return RedirectResponse(url=f"/admin/{secret_key}", status_code=303)
    else:
        return RedirectResponse(url="/login", status_code=303)

@app.get("/track")
def track(booking_id: int = None, db: Session = Depends(get_db)):
    booking = db.get(Booking, booking_id) if booking_id else None
    if not booking:
        raise HTTPException(404)
    template = template_lookup.get_template("track.html")
    return HTMLResponse(template.render(all=booking))

@app.get("/support")
def support_page(request: Request):
    template = template_lookup.get_template("support.html")
    return HTMLResponse(template.render())

@app.post("/support")
def support_send(
    name: str = Form(...),
    contact: str = Form(...),
    message: str = Form(...)
):
    msg = f"📩 Новое обращение!\nИмя: {name}\nКонтакты: {contact}\nВопрос: {message}"
    RostovHomes(msg)
    return RedirectResponse(url="/success", status_code=303)

reviews_data = [
    {"name": "Марина", "date": "12 мая 2026", "rating": 5, "text": "Отдыхали с семьёй, очень понравилось! Дом чистый, удобный, до моря рукой подать. Обязательно вернёмся.", "answer": "Спасибо, Марина! Ждём вас снова!"},
    {"name": "Алексей", "date": "3 мая 2026", "rating": 5, "text": "Хороший дом, но телевизор староват. А так всё отлично.", "answer": "Алексей, спасибо за отзыв! Телевизор уже заменили."},
    {"name": "Ольга", "date": "20 апреля 2026", "rating": 5, "text": "Превосходное место! Рекомендую."},
]

@app.get("/reviews")
def reviews_page(request: Request):
    template = template_lookup.get_template("reviews.html")
    return HTMLResponse(template.render(reviews=reviews_data))

if __name__ == "__main__":
    uvicorn.run(app)