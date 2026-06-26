import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from models import Order, DailySchedule
from database import SessionLocal

db = SessionLocal()
order = db.query(Order).filter(Order.dwg_no == "FGFM252516-003").first()
if order:
    print(f"Fixing order {order.dwg_no}")
    
    # 1. Restore the completed_qty of the order itself
    order.completed_qty = 23
    
    # 2. Fix the broken PUF schedule targets
    puf_today = db.query(DailySchedule).filter(
        DailySchedule.order_id == order.id,
        DailySchedule.machine_id == 5,
        DailySchedule.is_backlog == False
    ).first()
    if puf_today:
        puf_today.target_qty = 24
        print(f"Restored PUF today target to 24")
        
    db.commit()
    print("Database fix applied successfully.")
else:
    print("Order not found")
db.close()
