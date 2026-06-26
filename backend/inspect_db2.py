import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from models import Order
from database import SessionLocal
from scheduler import convert_qty

db = SessionLocal()
order = db.query(Order).filter(Order.dwg_no == "FGFM252516-003").first()
if order:
    print(f"Bending -> Gasketing: {convert_qty(384, 'Bending', 'Gasketing', order)}")
    print(f"Gasketing -> PUF: {convert_qty(24, 'Gasketing', 'PUF', order)}")
else:
    print("Order not found")
db.close()
