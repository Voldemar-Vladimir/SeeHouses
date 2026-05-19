import uvicorn
import datetime
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from starlette.responses import RedirectResponse
from starlette.staticfiles import StaticFiles

from models import SessionLocal,Booking
from fastapi import FastAPI,HTTPException,Form,Depends,Request
from fastapi.openapi.utils import status_code_ranges
from pydantic import BaseModel,Field
from mako.template import Template
from mako.lookup import TemplateLookup


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:db.close()

app = FastAPI()
template_lookup = TemplateLookup(directories=["templates"])
app.mount("/static", StaticFiles(directory="static"), name="static")

users=[]
homes = [
    {"id": 1, "price_per_day": 3000, "distance_to_sea": 300, "rooms": 3, "pool": True,"img":"/static/img/home1.png","img_room":["/static/img/home1_room1.png","/static/img/home1_room2.png","/static/img/home1_room3.png"], "tv":True, "wifi": True,"batut": False, "rating": 4.99},
    {"id": 2, "price_per_day": 2000, "distance_to_sea": 600, "rooms": 2, "pool": False,"img":"/static/img/home2.png","img_room":["/static/img/home2_room1.png","/static/img/home2_room2.png"], "tv":True, "wifi": True,"batut": True, "rating": 4.89}
]

class User(BaseModel):
    name: str
    age: int = Field(ge=0, le=130)
    tell: int

@app.get("/",tags=["Главная"],summary="Приветствие")
def root(request: Request):
    template = template_lookup.get_template("index.html")
    html_content = template.render(homes=homes)
    return HTMLResponse(content=html_content)

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
    price=0
    days=(check_out-check_in).days
    if home_id==1:
        img_room=homes[0]["img_room"]
        price_per_day=3000
        price+=price_per_day*days
    elif home_id==2:
        img_room=homes[1]["img_room"]
        price_per_day=2000
        price+=price_per_day*days
    else:
        raise HTTPException(status_code=404, detail="Неверный номер дома")

    if mini_bar:
        price+=4000

    if transfer:
        price+=1000

    booking = Booking(home_id=home_id, check_in=check_in, check_out=check_out, name=name, phone=phone, email=email, mini_bar=mini_bar, transfer=transfer, total_price=price)
    db.add(booking)
    db.commit()
    db.refresh(booking)

    return RedirectResponse(url="/success", status_code=303)

@app.get("/success")
def success():
    template = template_lookup.get_template("success.html")
    html_content = template.render()
    return HTMLResponse(content=html_content)

@app.get("/homes/{home_id}",tags=["Дома🏡"],summary="Конкретный дом")
def show_home(home_id: int):
    for home in homes:
        if home["id"] == home_id:
            return home
    raise HTTPException(status_code=404, detail="Дом не найден")

@app.get("/booking")
def show_booking_form(request: Request, home_id: int = None):
    global img_room,price
    price=3000
    img_room=[]
    if home_id==1:
        price=homes[0]["price_per_day"]
        img_room=homes[0]["img_room"]
    elif home_id==2:
        price=homes[1]["price_per_day"]
        img_room=homes[1]["img_room"]
    template = template_lookup.get_template("booking.html")
    html_content = template.render(home_id=home_id,img_rooms=img_room,price_per_day=price)
    return HTMLResponse(content=html_content)

if __name__ == "__main__":
    uvicorn.run(app)