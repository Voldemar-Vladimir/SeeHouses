from datetime import datetime, timedelta
from sqlalchemy import create_engine, Column, Integer, String, Date, Boolean, DateTime
from sqlalchemy.orm import declarative_base, sessionmaker

engine = create_engine('sqlite:///a.db')
Base = declarative_base()
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)

class Booking(Base):
    __tablename__ = 'bookings'
    id = Column(Integer, primary_key=True)
    home_id = Column(Integer)
    check_in = Column(Date)
    check_out = Column(Date)
    name = Column(String)
    phone = Column(String)
    email = Column(String)
    mini_bar = Column(Boolean, default=False)
    transfer = Column(Boolean, default=False)
    total_price = Column(Integer)
    status = Column(String, default='new')
    created_at = Column(DateTime, default=datetime.utcnow)
    peoples = Column(String)

    # Новые поля для оплаты
    payment_id = Column(String, unique=True, nullable=True)
    payment_status = Column(String, default='pending')   # pending, paid, failed
    expires_at = Column(DateTime, default=lambda: datetime.utcnow() + timedelta(minutes=30))

Base.metadata.create_all(bind=engine)