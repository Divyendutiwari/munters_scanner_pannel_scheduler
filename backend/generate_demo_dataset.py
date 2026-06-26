import os
import qrcode
from sqlalchemy.orm import Session
from datetime import datetime

import models, schemas, database, scheduler
from database import SessionLocal, engine

# Create tables
models.Base.metadata.create_all(bind=engine)

def generate_barcodes_and_data():
    db = SessionLocal()
    
    # 1. Clear existing data
    db.query(models.DailyWorkLog).delete()
    db.query(models.ShiftLog).delete()
    db.query(models.DailySchedule).delete()
    db.query(models.Order).delete()
    db.commit()

    print("Existing data cleared.")

    # 2. Ensure machines exist
    scheduler.initialize_machines(db)

    # 3. Create DEMO order
    order = models.Order(
        month="June",
        sales_person="Demo Person",
        wo_no="WO-DEMO-001",
        sap_code="SAP-DEMO",
        customer_name="Demonstration Corp",
        dwg_no="DEMO-01",
        cfm=5000,
        qty=1,
        fab_code="FAB-01",
        ab_unit_qty=1,
        panel_qty_per_unit=5,
        total_panel_qty=5,      # 5 panels = 10 sheets
        no_of_strokes=80,       # 5 panels * 16 strokes
        priority=2,             # Normal
        status="pending",
        created_at=datetime.utcnow()
    )
    db.add(order)
    db.commit()
    db.refresh(order)

    print(f"Created demo order: {order.dwg_no} with {order.total_panel_qty} panels.")

    # 4. Generate Barcodes
    barcodes_dir = os.path.join(os.path.dirname(__file__), "barcodes")
    os.makedirs(barcodes_dir, exist_ok=True)
    
    # Clear old barcodes
    for f in os.listdir(barcodes_dir):
        if f.endswith(".png"):
            os.remove(os.path.join(barcodes_dir, f))

    print(f"Generating 10 barcodes in {barcodes_dir} ...")
    
    generated_barcodes = []
    
    for panel_idx in range(1, 6):
        # Each panel has an IN and an OUT sheet
        for sheet_type in ["IN", "OUT"]:
            barcode_str = f"DEMO-01-{panel_idx:02d}-{sheet_type}"
            generated_barcodes.append(barcode_str)
            
            # Generate QR Code
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=10,
                border=4,
            )
            qr.add_data(barcode_str)
            qr.make(fit=True)

            img = qr.make_image(fill_color="black", back_color="white")
            img_path = os.path.join(barcodes_dir, f"{barcode_str}.png")
            img.save(img_path)
            
    print("\n[SUCCESS] Barcode Generation Complete! You can find the image files in the 'backend/barcodes' folder.")
    print("\nBarcodes generated:")
    for b in generated_barcodes:
        print(f" - {b}")
        
    print("\nRun the server and 'Start Shift' on the dashboard to allocate this order!")

    # Generate the demo Excel file for upload testing
    import pandas as pd
    demo_excel_path = os.path.join(os.path.dirname(__file__), "demo_orders.xlsx")
    demo_df = pd.DataFrame([{
        "Month": "June",
        "Sales Person": "Demo Sales",
        "WO.NO.": "WO-DEMO-001",
        "SAP Code": "SAP-DEMO",
        "Customer Name": "Demonstration Corp",
        "DWG NO.": "DEMO-01",
        "CFM": 5000,
        "Qty": 1,
        "Fab.Code": "FAB-01",
        "A&B Unit Qty": 1,
        "Panel Qty/unit": 5,
        "Total panel qty": 5,
        "No of strokes": 80
    }])
    demo_df.to_excel(demo_excel_path, index=False)
    print(f"\n[OK] Generated Excel file for upload demo: demo_orders.xlsx")

if __name__ == "__main__":
    generate_barcodes_and_data()
