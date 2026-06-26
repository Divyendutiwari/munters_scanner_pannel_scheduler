from backend.database import SessionLocal
from backend.models import Order, DailySchedule

db = SessionLocal()
orders = db.query(Order).count()
schedules = db.query(DailySchedule).count()
print(f"Orders: {orders}, Schedules: {schedules}")

first_sched = db.query(DailySchedule).first()
if first_sched:
    print(f"First schedule date: {first_sched.scheduled_date}")
db.close()
