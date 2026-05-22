import uvicorn
import datetime
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from starlette.responses import RedirectResponse
from starlette.staticfiles import StaticFiles
from models import SessionLocal, Booking
from fastapi import FastAPI, HTTPException, Form, Depends, Request
from pydantic import BaseModel, Field
from mako.lookup import TemplateLookup
import requests

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
    {"id": 1, "price_per_day": 4000, "distance_to_sea": 300, "rooms": 3, "pool": True,
     "img": "/static/img/home1.png",
     "img_room": ["/static/img/home1_room1.png", "/static/img/home1_room2.png", "/static/img/home1_room3.png"],
     "tv": True, "wifi": True, "batut": False, "rating": 4.99},
    {"id": 2, "price_per_day": 3000, "distance_to_sea": 600, "rooms": 2, "pool": False,
     "img": "/static/img/home2.png",
     "img_room": ["/static/img/home2_room1.png", "/static/img/home2_room2.png"],
     "tv": True, "wifi": True, "batut": True, "rating": 4.89}
]

class User(BaseModel):
    name: str
    age: int = Field(ge=0, le=130)
    tell: int

@app.get("/")
def root(request: Request):
    template = template_lookup.get_template("index.html")
    return HTMLResponse(template.render(homes=homes))

@app.post("/booking")
def create_form(
    home_id: int = Form(...),
    check_in: datetime.date = Form(...),
    check_out: datetime.date = Form(...),
    name: str = Form(...),
    phone: str = Form(...),
    email: str = Form(""),
    mini_bar: bool = Form(False),
    transfer: bool = Form(False),
    peoples: str = Form(...),
    db: Session = Depends(get_db)
):
    days = (check_out - check_in).days
    if days <= 0:
        raise HTTPException(400, "Дата выезда должна быть позже даты заезда")
    if days < 2:
        raise HTTPException(400, "Минимальная длительность — 2 дня")

    # Ищем дом
    home = next((h for h in homes if h["id"] == home_id), None)
    if not home:
        raise HTTPException(404, "Дом не найден")

    price = home["price_per_day"] * days
    if mini_bar:
        price += 4000
    if transfer:
        price += 1500   # фиксированная цена трансфера

    booking = Booking(
        home_id=home_id,
        check_in=check_in,
        check_out=check_out,
        name=name,
        phone=phone,
        email=email,
        mini_bar=mini_bar,
        transfer=transfer,
        total_price=price,
        peoples=peoples
        # city больше не сохраняем
    )
    db.add(booking)
    db.commit()
    message = f"Новый заказ!\nДом №{home_id}\nИмя: {name}\nТелефон: {phone}\nДаты: {check_in} – {check_out}\nГостей: {peoples}\nСумма: {price}₽"
    RostovHomes(message)
    return RedirectResponse(url="/success", status_code=303)

@app.get("/success")
def success():
    template = template_lookup.get_template("success.html")
    return HTMLResponse(template.render())

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
    token = "8601793998:AAH0Kqg5_eR9rccweqscC3EVAIiwHovmq7A"
    chat_id = "5977647337"
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    data = {"chat_id": chat_id, "text": message}
    try:
        requests.post(url, json=data, timeout=5)
    except:pass
if __name__ == "__main__":
    uvicorn.run(app)