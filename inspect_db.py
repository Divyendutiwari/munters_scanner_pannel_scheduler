from backend.database import SessionLocal
from backend.models import Order, DailySchedule, Machine

db = SessionLocal()
order = db.query(Order).filter(Order.dwg_no == "FGFM252516-003").first()
if order:
    print(f"Order: {order.dwg_no}, Total Panels: {order.total_panel_qty}, Strokes: {order.no_of_strokes}")
    
    schedules = db.query(DailySchedule).filter(DailySchedule.order_id == order.id).all()
    for s in schedules:
        machine = db.query(Machine).filter(Machine.id == s.machine_id).first()
        print(f"Schedule ID: {s.id}, Machine: {machine.name}, Target: {s.target_qty}, Completed: {s.completed_qty}, Date: {s.scheduled_date}")
else:
    print("Order not found")
db.close()
