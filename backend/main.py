from fastapi import FastAPI, Depends, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session, joinedload
from typing import List, Optional
from datetime import date
import os
import shutil
import pandas as pd

import models, schemas, database, scheduler
from database import engine, get_db

models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="MES API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
def startup_event():
    db = database.SessionLocal()
    scheduler.initialize_machines(db)
    db.close()

# ───────────────────────────────────────────
# RESET (Clear All Production Data)
# ───────────────────────────────────────────

@app.post("/reset/")
def reset_all_data(db: Session = Depends(get_db)):
    """
    Wipe ALL production data: orders, schedules, shift logs, daily work logs, scanned barcodes.
    Machines are preserved. Use before a fresh import.
    """
    db.query(models.ScannedBarcode).delete()
    db.query(models.DailyWorkLog).delete()
    db.query(models.ShiftLog).delete()
    db.query(models.DailySchedule).delete()
    db.query(models.Order).delete()
    db.commit()
    return {"message": "All production data cleared. Machines preserved. Ready for fresh import."}

# ───────────────────────────────────────────
# UPLOAD
# ───────────────────────────────────────────

@app.post("/upload/")
async def upload_excel(file: UploadFile = File(...), db: Session = Depends(get_db)):
    if not file.filename.endswith(('.xlsx', '.xls')):
        raise HTTPException(status_code=400, detail="Only Excel files are allowed.")
    
    file_location = f"temp_{file.filename}"
    with open(file_location, "wb+") as file_object:
        shutil.copyfileobj(file.file, file_object)
        
    try:
        count = scheduler.import_orders_from_excel(file_location, db)
        return {"message": f"File parsed successfully. {count} orders imported as pending."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Parse error: {str(e)}")
    finally:
        if os.path.exists(file_location):
            os.remove(file_location)

# ───────────────────────────────────────────
# MACHINES
# ───────────────────────────────────────────

@app.get("/machines/", response_model=List[schemas.MachineOut])
def get_machines(db: Session = Depends(get_db)):
    return db.query(models.Machine).order_by(models.Machine.order_in_pipeline).all()

@app.post("/machines/update/{machine_id}")
def update_machine(machine_id: int, machine_in: schemas.MachineUpdate, db: Session = Depends(get_db)):
    machine = db.query(models.Machine).filter(models.Machine.id == machine_id).first()
    if not machine:
        raise HTTPException(status_code=404, detail="Machine not found")
    machine.capacity_per_day = machine_in.capacity_per_day
    db.commit()
    return {"message": "Machine capacity updated"}

@app.post("/machines/batch-capacity/")
def batch_update_capacities(update: schemas.BatchCapacityUpdate, db: Session = Depends(get_db)):
    """Update all machine capacities in one call (pre-shift config)."""
    for machine_id_str, capacity in update.capacities.items():
        machine_id = int(machine_id_str)
        machine = db.query(models.Machine).filter(models.Machine.id == machine_id).first()
        if machine:
            machine.capacity_per_day = int(capacity)
    db.commit()
    return {"message": "All machine capacities updated"}

# ───────────────────────────────────────────
# SHIFT MANAGEMENT
# ───────────────────────────────────────────

@app.post("/start-shift/")
def start_shift(db: Session = Depends(get_db)):
    """One-click: allocate pending orders, create shift log, return dashboard data."""
    shift_log = scheduler.start_shift(db)
    return {"message": "Shift started. Orders allocated.", "shift_id": shift_log.id}

@app.get("/shift-status/")
def get_shift_status(target_date: Optional[date] = None, db: Session = Depends(get_db)):
    """Get current shift state (active/ended/not started)."""
    check_date = target_date or date.today()
    shift = db.query(models.ShiftLog).filter(models.ShiftLog.shift_date == check_date).first()
    if not shift:
        return {"status": "not_started", "shift_date": str(check_date)}
    return {
        "status": "active" if shift.is_active else "ended",
        "shift_date": str(shift.shift_date),
        "started_at": str(shift.started_at) if shift.started_at else None,
        "ended_at": str(shift.ended_at) if shift.ended_at else None,
        "total_target": shift.total_target,
        "total_completed": shift.total_completed,
        "total_backlog": shift.total_backlog
    }

@app.post("/end-of-day/")
def run_end_of_day(date_to_process: date, db: Session = Depends(get_db)):
    result = scheduler.end_of_day_process(db, date_to_process)
    return {
        "message": f"End of day processing completed for {date_to_process}.",
        "backlogs_created": result["backlogs_created"],
        "total_backlog_qty": result["total_backlog_qty"]
    }

# ───────────────────────────────────────────
# PRIORITY MANAGEMENT
# ───────────────────────────────────────────

@app.put("/orders/{order_id}/priority")
def update_order_priority(order_id: int, body: schemas.PriorityUpdate, db: Session = Depends(get_db)):
    """
    Update the priority of an order. Cascades to all incomplete DailySchedule entries.
    Priority: 0 = Emergency (🔴), 1 = High (🟡), 2 = Normal (🟢)
    """
    if body.priority not in (0, 1, 2):
        raise HTTPException(status_code=400, detail="Priority must be 0 (Emergency), 1 (High), or 2 (Normal)")
    
    result = scheduler.update_order_priority(db, order_id, body.priority)
    if not result:
        raise HTTPException(status_code=404, detail="Order not found")
    
    return {
        "message": f"Priority updated to {result['priority_label']}",
        **result
    }

@app.get("/priority-queue/")
def get_priority_queue(target_date: Optional[date] = None, db: Session = Depends(get_db)):
    """
    Get the ordered priority queue for a given date.
    Order: Backlog first → Emergency → High → Normal → FIFO
    """
    check_date = target_date or date.today()
    queue = scheduler.get_priority_queue(db, check_date)
    return {"queue": queue, "total_items": len(queue)}

@app.get("/pending-orders/")
def get_pending_orders(db: Session = Depends(get_db)):
    """Get all pending (unscheduled) orders for priority editing before shift start."""
    orders = db.query(models.Order).filter(
        models.Order.status == "pending"
    ).order_by(models.Order.priority.asc(), models.Order.created_at.asc()).all()
    
    return [{
        "id": o.id,
        "wo_no": o.wo_no,
        "dwg_no": o.dwg_no,
        "customer_name": o.customer_name,
        "total_panel_qty": o.total_panel_qty,
        "priority": o.priority,
        "priority_label": scheduler.PRIORITY_LABELS.get(o.priority, "Normal"),
        "created_at": str(o.created_at)
    } for o in orders]

# ───────────────────────────────────────────
# DASHBOARD (SINGLE ENDPOINT)
# ───────────────────────────────────────────

@app.get("/dashboard/")
def get_dashboard(target_date: Optional[date] = None, db: Session = Depends(get_db)):
    """
    Single endpoint returning schedules + machine stats + shift summary + priority queue.
    Eliminates multiple API calls from frontend.
    """
    check_date = target_date or date.today()
    
    # Get schedules with eager loading
    query = db.query(models.DailySchedule).options(
        joinedload(models.DailySchedule.order),
        joinedload(models.DailySchedule.machine)
    ).filter(
        models.DailySchedule.scheduled_date == check_date
    )
    schedules_raw = query.all()
    
    # Format schedules — sorted by priority queue order
    schedules = []
    for s in schedules_raw:
        schedules.append({
            "id": s.id,
            "scheduled_date": str(s.scheduled_date),
            "target_qty": s.target_qty,
            "completed_qty": s.completed_qty,
            "is_backlog": s.is_backlog,
            "priority": s.priority,
            "machine_name": s.machine.name,
            "order": {
                "id": s.order.id,
                "wo_no": s.order.wo_no,
                "dwg_no": s.order.dwg_no,
                "total_panel_qty": s.order.total_panel_qty,
                "no_of_strokes": s.order.no_of_strokes,
                "customer_name": s.order.customer_name,
                "completed_qty": s.order.completed_qty,
                "is_completed": s.order.is_completed,
                "priority": s.order.priority,
                "created_at": str(s.order.created_at)
            }
        })
    
    # Sort schedules: priority first → backlog within same priority → FIFO by order id
    schedules.sort(key=lambda x: (
        x["priority"],             # Emergency (0) first
        not x["is_backlog"],       # Backlog before new within same priority (False=0 sorts after True)
        x["order"]["id"]           # FIFO by order id
    ))
    
    # Get machine stats
    machine_stats = scheduler.compute_machine_stats(db, check_date)
    
    # Get shift summary
    shift_summary = scheduler.compute_shift_summary(db, check_date)
    
    # Get machines
    machines = db.query(models.Machine).order_by(models.Machine.order_in_pipeline).all()
    machines_out = [
        {"id": m.id, "name": m.name, "capacity_per_day": m.capacity_per_day, "order_in_pipeline": m.order_in_pipeline}
        for m in machines
    ]
    
    # Get priority queue
    priority_queue = scheduler.get_priority_queue(db, check_date)
    
    return {
        "schedules": schedules,
        "machine_stats": machine_stats,
        "shift_summary": shift_summary,
        "machines": machines_out,
        "priority_queue": priority_queue
    }

# ───────────────────────────────────────────
# SCHEDULE & TICK
# ───────────────────────────────────────────

@app.get("/schedule/", response_model=List[schemas.ScheduleOut])
def get_schedule(target_date: date = None, machine_name: str = None, dwg_no: str = None, db: Session = Depends(get_db)):
    query = db.query(models.DailySchedule).join(models.Order).join(models.Machine)
    
    if target_date:
        query = query.filter(models.DailySchedule.scheduled_date == target_date)
    if machine_name:
        query = query.filter(models.Machine.name == machine_name)
    if dwg_no:
        query = query.filter(models.Order.dwg_no == dwg_no)
        
    schedules = query.all()
    
    # Format output for Pydantic
    results = []
    for s in schedules:
        out = schemas.ScheduleOut.from_orm(s)
        out.machine_name = s.machine.name
        results.append(out)
    return results

@app.post("/schedule/tick/")
def update_tick(tick: schemas.TickUpdate, db: Session = Depends(get_db)):
    schedule = db.query(models.DailySchedule).filter(models.DailySchedule.id == tick.schedule_id).first()
    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")
        
    if tick.completed_qty < 0:
        raise HTTPException(status_code=400, detail="Cannot be negative")
    if tick.completed_qty > schedule.target_qty:
        raise HTTPException(status_code=400, detail="Cannot complete more than target quantity")
        
    was_completed = schedule.completed_qty >= schedule.target_qty
    is_completed = tick.completed_qty >= schedule.target_qty

    schedule.completed_qty = tick.completed_qty  # Slider sets absolute value
    db.commit()
    db.refresh(schedule)
    
    today = schedule.scheduled_date
    shift_log = db.query(models.ShiftLog).filter(models.ShiftLog.shift_date == today).first()
    
    stage_completed_now = False

    # Hand off to next machine ONLY when this stage hits 100% completion
    if not was_completed and is_completed:
        stage_completed_now = True
        machines = db.query(models.Machine).order_by(models.Machine.order_in_pipeline).all()
        current_machine = schedule.machine
        next_machine = None
        for i, m in enumerate(machines):
            if m.id == current_machine.id and i + 1 < len(machines):
                next_machine = machines[i + 1]
                break
                
        if next_machine:
            # Cascade the full target quantity (equivalent panels)
            qty_for_next = scheduler.convert_qty(schedule.target_qty, schedule.machine.name, next_machine.name, schedule.order)
            
            existing_sched = db.query(models.DailySchedule).filter(
                models.DailySchedule.order_id == schedule.order_id,
                models.DailySchedule.machine_id == next_machine.id,
                models.DailySchedule.scheduled_date == today
            ).first()
            
            if existing_sched:
                existing_sched.target_qty += qty_for_next
            else:
                new_sched = models.DailySchedule(
                    order_id=schedule.order_id,
                    machine_id=next_machine.id,
                    scheduled_date=today,
                    target_qty=qty_for_next,
                    completed_qty=0,
                    is_backlog=False,
                    priority=schedule.priority
                )
                db.add(new_sched)
            db.commit()
        else:
            # If last machine (PUF), mark the order as fully completed
            schedule.order.completed_qty = schedule.order.total_panel_qty
            schedule.order.is_completed = True
            schedule.order.status = "completed"
            db.commit()

    # Update shift log totals
    if shift_log:
        from sqlalchemy import func
        total_completed = db.query(func.sum(models.DailySchedule.completed_qty)).filter(
            models.DailySchedule.scheduled_date == today
        ).scalar() or 0
        total_target = db.query(func.sum(models.DailySchedule.target_qty)).filter(
            models.DailySchedule.scheduled_date == today
        ).scalar() or 0
        shift_log.total_completed = total_completed
        shift_log.total_target = total_target
        db.commit()
    
    return {
        "message": "Updated",
        "id": schedule.id,
        "completed_qty": schedule.completed_qty,
        "target_qty": schedule.target_qty,
        "stage_completed": stage_completed_now,
        "machine_name": schedule.machine.name,
        "dwg_no": schedule.order.dwg_no
    }

@app.post("/schedule/scan/")
def update_scan(scan: schemas.ScanUpdate, db: Session = Depends(get_db)):
    """
    Handle a barcode scan. Automatically calculates the correct quantity to increment
    based on the machine's required unit, and calls the standard tick logic.
    """
    # Parse dwg_no from barcode (e.g., DEMO-01-01-IN -> DEMO-01)
    parts = scan.barcode.rsplit('-', 2)
    if len(parts) < 3:
        raise HTTPException(status_code=400, detail="Invalid barcode format. Expected [DWG]-[ID]-[IN/OUT]")
    dwg_no = parts[0]
    
    today = date.today()
    
    # Find the active schedule for this dwg_no and machine
    schedule = db.query(models.DailySchedule).join(models.Order).join(models.Machine).filter(
        models.DailySchedule.scheduled_date == today,
        models.Machine.name == scan.machine_name,
        models.Order.dwg_no == dwg_no
    ).first()
    
    if not schedule:
        raise HTTPException(status_code=404, detail=f"No active schedule found for {dwg_no} on {scan.machine_name}")
        
    if schedule.completed_qty >= schedule.target_qty:
        return {"message": "Job already 100% completed on this machine.", "status": "completed"}
        
    # Check for duplicate scan
    existing_scan = db.query(models.ScannedBarcode).filter(
        models.ScannedBarcode.barcode == scan.barcode,
        models.ScannedBarcode.machine_name == scan.machine_name
    ).first()
    
    if existing_scan:
        raise HTTPException(status_code=400, detail=f"Barcode {scan.barcode} has already been scanned on {scan.machine_name}!")
        
    # Each barcode = 1 sheet. Calculate increment in the machine's native unit.
    machine_name = scan.machine_name
    order = schedule.order
    
    if machine_name in ("Auto Fold", "Turret Punch"):
        # 1 sheet = 1 native unit (sheets / punches)
        increment_amount = 1
    elif machine_name == "Bending":
        # 1 sheet = 12 strokes for IN, 4 strokes for OUT
        if scan.barcode.endswith("-IN"):
            increment_amount = 12
        elif scan.barcode.endswith("-OUT"):
            increment_amount = 4
        else:
            # Fallback just in case
            strokes_per_panel = (
                order.no_of_strokes / order.total_panel_qty
                if order.total_panel_qty and order.total_panel_qty > 0 and order.no_of_strokes
                else 16
            )
            increment_amount = max(1, int(strokes_per_panel / 2))
    else:
        # Gasketing / PUF: unit is panels. 2 sheets = 1 panel.
        # Increment by 1 panel per scan (simplified for demo).
        increment_amount = 1
    
    new_qty = schedule.completed_qty + increment_amount
    if new_qty > schedule.target_qty:
        new_qty = schedule.target_qty
        
    # Reuse the tick logic to handle all cascading/handover rules
    tick_req = schemas.TickUpdate(schedule_id=schedule.id, completed_qty=new_qty)
    result = update_tick(tick_req, db)
    
    # Save successful scan
    new_scan_record = models.ScannedBarcode(
        barcode=scan.barcode,
        machine_name=scan.machine_name,
        schedule_id=schedule.id
    )
    db.add(new_scan_record)
    db.commit()
    
    unit_name = {"Auto Fold": "sheet", "Turret Punch": "punch", "Bending": "strokes", "Gasketing": "panel", "PUF": "puffing"}.get(machine_name, "unit")
    
    if result.get("stage_completed"):
        result["message"] = f"Scanned {scan.barcode}! {dwg_no} fully completed at {machine_name} & passed to next stage!"
    else:
        result["message"] = f"Scanned {scan.barcode}! +{increment_amount} {unit_name}(s) on {machine_name}."
        
    return result

# ───────────────────────────────────────────
# EXPORT & HISTORY
# ───────────────────────────────────────────

@app.get("/export-report/")
def export_report(target_date: date, db: Session = Depends(get_db)):
    """Export multi-sheet Excel for a specific day: Schedule, Backlog, Done Today."""
    schedules = db.query(models.DailySchedule).options(
        joinedload(models.DailySchedule.order),
        joinedload(models.DailySchedule.machine)
    ).filter(models.DailySchedule.scheduled_date == target_date).all()
    
    # Sheet 1: Full Schedule
    schedule_data = []
    done_data = []
    backlog_data = []
    
    priority_labels = {0: "Emergency", 1: "High", 2: "Normal"}
    
    for s in schedules:
        row = {
            "Date": str(s.scheduled_date),
            "Priority": priority_labels.get(s.priority, "Normal"),
            "Machine": s.machine.name,
            "WO NO": s.order.wo_no,
            "DWG NO": s.order.dwg_no,
            "Customer": s.order.customer_name,
            "Target Qty": s.target_qty,
            "Completed Qty": s.completed_qty,
            "Status": "Completed" if s.completed_qty >= s.target_qty else "Ongoing",
            "Is Backlog": "Yes" if s.is_backlog else "No"
        }
        schedule_data.append(row)
        
        if s.completed_qty >= s.target_qty:
            done_data.append(row)
        
        if s.is_backlog:
            backlog_data.append(row)
    
    file_path = f"daily_report_{target_date}.xlsx"
    with pd.ExcelWriter(file_path, engine='openpyxl') as writer:
        pd.DataFrame(schedule_data).to_excel(writer, sheet_name="Schedule", index=False)
        pd.DataFrame(done_data).to_excel(writer, sheet_name="Done Today", index=False)
        pd.DataFrame(backlog_data).to_excel(writer, sheet_name="Backlog", index=False)
    
    return FileResponse(
        file_path,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=file_path
    )

@app.get("/export-history/")
def export_history(db: Session = Depends(get_db)):
    """Export ALL historical DailyWorkLog entries as a growing Excel file."""
    logs = db.query(models.DailyWorkLog).order_by(models.DailyWorkLog.log_date.desc()).all()
    
    if not logs:
        raise HTTPException(status_code=404, detail="No historical data found. End at least one shift first.")
    
    data = []
    for log in logs:
        data.append({
            "Date": str(log.log_date),
            "WO NO": log.wo_no,
            "DWG NO": log.dwg_no,
            "Customer": log.customer_name,
            "Machine": log.machine_name,
            "Target Qty": log.target_qty,
            "Completed Qty": log.completed_qty,
            "Status": log.status,
            "Current Stage": log.current_stage,
            "Is Backlog": "Yes" if log.is_backlog else "No"
        })
    
    # Group by date into separate sheets
    df = pd.DataFrame(data)
    file_path = "production_history_export.xlsx"
    
    with pd.ExcelWriter(file_path, engine='openpyxl') as writer:
        # Summary sheet with all data
        df.to_excel(writer, sheet_name="All History", index=False)
        
        # Per-date sheets
        for log_date in df["Date"].unique():
            sheet_name = str(log_date)[:31]  # Excel sheet name limit
            df[df["Date"] == log_date].to_excel(writer, sheet_name=sheet_name, index=False)
    
    return FileResponse(
        file_path,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename="production_history_export.xlsx"
    )

@app.get("/history/")
def get_history(target_date: Optional[date] = None, db: Session = Depends(get_db)):
    """Get daily work history — for frontend caching in localStorage."""
    query = db.query(models.DailyWorkLog)
    if target_date:
        query = query.filter(models.DailyWorkLog.log_date == target_date)
    
    logs = query.order_by(models.DailyWorkLog.log_date.desc()).limit(500).all()
    
    return [{
        "id": log.id,
        "log_date": str(log.log_date),
        "wo_no": log.wo_no,
        "dwg_no": log.dwg_no,
        "customer_name": log.customer_name,
        "machine_name": log.machine_name,
        "target_qty": log.target_qty,
        "completed_qty": log.completed_qty,
        "status": log.status,
        "current_stage": log.current_stage,
        "is_backlog": log.is_backlog
    } for log in logs]
