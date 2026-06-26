import pandas as pd
from datetime import date, timedelta, datetime
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, case
from models import Order, Machine, DailySchedule, ShiftLog, DailyWorkLog

MACHINE_PIPELINE = ["Auto Fold", "Turret Punch", "Bending", "Gasketing", "PUF"]

# Priority labels for display
PRIORITY_LABELS = {0: "Emergency", 1: "High", 2: "Normal"}

def initialize_machines(db: Session):
    """Setup default machines if they don't exist.
    
    Capacity units per machine:
      Auto Fold    : 800 sheets/day   (2 sheets per panel → 400 panels/day)
      Turret Punch : 800 punches/day  (2 punches per panel → 400 panels/day)
      Bending      : 6400 strokes/day (16 strokes per panel → 400 panels/day)
      Gasketing    : 400 panels/day
      PUF          : 400 puffings/day
    """
    machines_data = [
        {"name": "Auto Fold",    "capacity_per_day": 800,  "order_in_pipeline": 1},
        {"name": "Turret Punch", "capacity_per_day": 800,  "order_in_pipeline": 2},
        {"name": "Bending",      "capacity_per_day": 640, "order_in_pipeline": 3},
        {"name": "Gasketing",    "capacity_per_day": 400,  "order_in_pipeline": 4},
        {"name": "PUF",          "capacity_per_day": 400,  "order_in_pipeline": 5},
    ]
    
    for m in machines_data:
        existing = db.query(Machine).filter(Machine.name == m["name"]).first()
        if not existing:
            new_m = Machine(**m)
            db.add(new_m)
        else:
            # Update capacity if it was the old wrong default of 800 for all
            if existing.capacity_per_day == 800 and m["name"] in ("Bending", "Gasketing", "PUF"):
                existing.capacity_per_day = m["capacity_per_day"]
    db.commit()

def import_orders_from_excel(file_path: str, db: Session):
    """Parse Excel file and create Order records in bulk.
    
    Tolerates column name whitespace/case variations.
    """
    initialize_machines(db)
    df = pd.read_excel(file_path)
    # Normalize column names: strip leading/trailing whitespace
    df.columns = [str(c).strip() for c in df.columns]
    
    def col(name):
        """Case-insensitive column lookup."""
        for c in df.columns:
            if c.lower() == name.strip().lower():
                return c
        return name  # fallback (will cause KeyError if truly missing)
    
    orders_to_add = []
    for index, row in df.iterrows():
        try:
            total_qty = int(row[col('Total panel qty')])
            if total_qty <= 0: continue
        except:
            continue
            
        # Check if a 'Priority' column exists in Excel
        priority_val = 2  # Default: Normal
        priority_col = col('Priority')
        if priority_col in df.columns and pd.notna(row.get(priority_col)):
            p = str(row.get(priority_col, '')).strip().lower()
            if p in ('0', 'emergency'):
                priority_val = 0
            elif p in ('1', 'high'):
                priority_val = 1
            elif p in ('2', 'normal'):
                priority_val = 2
        
        def safe_int(field, default=0):
            v = row.get(col(field))
            return int(v) if pd.notna(v) else default
        
        raw_strokes = safe_int('NO. OF STROKES', 0)
        
        order = Order(
            month=str(row.get(col('Month'), '')),
            sales_person=str(row.get(col('Sales Person'), '')),
            wo_no=str(row.get(col('WO.NO.'), '')),
            sap_code=str(row.get(col('SAP CODE'), '')),
            customer_name=str(row.get(col('CUSTOMER NAME'), '')),
            dwg_no=str(row.get(col('DWG NO.'), '')),
            cfm=safe_int('CFM', 0),
            qty=safe_int('QTY', 0),
            fab_code=str(row.get(col('FAB Code'), '')),
            ab_unit_qty=safe_int('AB/UNIT QTY/ COMP QTY', 0),
            panel_qty_per_unit=safe_int('Panel qty per unit', 0),
            total_panel_qty=total_qty,
            no_of_strokes=raw_strokes if raw_strokes > 0 else total_qty * 16,
            priority=priority_val,
            status="pending"
        )
        orders_to_add.append(order)
    
    # Bulk add all orders at once
    db.bulk_save_objects(orders_to_add, return_defaults=True)
    db.commit()
    return len(orders_to_add)

def get_target_for_machine(machine_name: str, order: Order):
    """Calculate the exact target quantity for a given machine based on the order."""
    if machine_name == "Auto Fold":
        return order.total_panel_qty * 2  # 2 sheets per panel
    elif machine_name == "Turret Punch":
        return order.total_panel_qty * 2  # 2 punches per panel (1 per sheet)
    elif machine_name == "Bending":
        return order.no_of_strokes if order.no_of_strokes else order.total_panel_qty * 16
    else:
        return order.total_panel_qty  # Gasketing, PUF, etc.

def convert_qty(qty: int, from_machine: str, to_machine: str, order: Order):
    """Convert completed quantity from one machine's unit to the next machine's target unit.
    
    Pipeline units:
      Auto Fold    -> sheets (2 per panel)
      Turret Punch -> punches (2 per panel, 1 per sheet)
      Bending      -> strokes (16 per panel by default, or order.no_of_strokes / total_panel_qty)
      Gasketing    -> panels (1:1)
      PUF          -> puffings (1:1 with panels)
    """
    strokes_per_panel = (
        order.no_of_strokes / order.total_panel_qty
        if order.total_panel_qty and order.total_panel_qty > 0 and order.no_of_strokes
        else 16
    )

    # Step 1: Convert FROM unit → panels
    if from_machine in ("Auto Fold", "Turret Punch"):
        panels = qty / 2
    elif from_machine == "Bending":
        panels = qty / strokes_per_panel
    else:  # Gasketing, PUF, or "Panels" sentinel
        panels = qty

    # Step 2: Convert panels → TO unit
    if to_machine in ("Auto Fold", "Turret Punch"):
        return int(panels * 2)
    elif to_machine == "Bending":
        return int(panels * strokes_per_panel)
    else:  # Gasketing, PUF, or "Panels" sentinel
        return int(panels)

def allocate_pending_orders(db: Session):
    """
    Distribute pending orders across the Auto Fold machine based on capacity.
    Priority ORDER: Emergency (0) → High (1) → Normal (2), then FIFO.
    Backlogs for today are already in DailySchedule — we just pack remaining capacity.
    """
    pending_orders = db.query(Order).filter(
        Order.status == "pending"
    ).order_by(
        Order.priority.asc(),      # Emergency (0) → High (1) → Normal (2)
        Order.created_at.asc()     # FIFO within same priority
    ).all()
    
    if not pending_orders:
        return
        
    today = date.today()
    
    # Load first machine (Auto Fold)
    machines = db.query(Machine).order_by(Machine.order_in_pipeline).all()
    if not machines:
        return
    
    first_machine = machines[0]
    
    # Start packing from today, accounting for already-scheduled load today
    current_schedule_date = today
    current_day_load = db.query(func.sum(DailySchedule.target_qty)).filter(
        DailySchedule.machine_id == first_machine.id,
        DailySchedule.scheduled_date == today
    ).scalar() or 0

    schedules_to_add = []
    
    for order in pending_orders:
        remaining_qty = get_target_for_machine(first_machine.name, order)
        
        while remaining_qty > 0:
            available_capacity = first_machine.capacity_per_day - current_day_load
            
            if available_capacity <= 0:
                current_schedule_date += timedelta(days=1)
                current_day_load = 0
                available_capacity = first_machine.capacity_per_day
                
            qty_to_schedule = min(remaining_qty, available_capacity)
            
            ds = DailySchedule(
                order_id=order.id,
                machine_id=first_machine.id,
                scheduled_date=current_schedule_date,
                target_qty=qty_to_schedule,
                priority=order.priority
            )
            schedules_to_add.append(ds)
                
            current_day_load += qty_to_schedule
            remaining_qty -= qty_to_schedule
            
        order.status = "scheduled"
    
    db.bulk_save_objects(schedules_to_add)
    db.commit()


def start_shift(db: Session):
    """
    Start a new shift: allocate pending orders, create ShiftLog, return summary.
    BACKLOG-FIRST: Backlog items from previous days are already in DailySchedule.
    New pending orders are allocated AFTER backlogs (they go into remaining capacity).
    """
    today = date.today()
    
    # Check if shift already active
    active_shift = db.query(ShiftLog).filter(
        ShiftLog.shift_date == today,
        ShiftLog.is_active == True
    ).first()
    
    if active_shift:
        # Shift already started, just re-allocate any new pending orders
        allocate_pending_orders(db)
        # Update totals
        total_target = db.query(func.sum(DailySchedule.target_qty)).filter(
            DailySchedule.scheduled_date == today
        ).scalar() or 0
        total_completed = db.query(func.sum(DailySchedule.completed_qty)).filter(
            DailySchedule.scheduled_date == today
        ).scalar() or 0
        active_shift.total_target = total_target
        active_shift.total_completed = total_completed
        db.commit()
        return active_shift
    
    # Allocate all pending orders (backlogs are already scheduled for today from end_of_day)
    allocate_pending_orders(db)
    
    # Calculate totals for today
    total_target = db.query(func.sum(DailySchedule.target_qty)).filter(
        DailySchedule.scheduled_date == today
    ).scalar() or 0
    
    backlog_count = db.query(func.sum(DailySchedule.target_qty)).filter(
        DailySchedule.scheduled_date == today,
        DailySchedule.is_backlog == True
    ).scalar() or 0
    
    # Create shift log
    shift_log = ShiftLog(
        shift_date=today,
        started_at=datetime.utcnow(),
        is_active=True,
        total_target=total_target,
        total_completed=0,
        total_backlog=backlog_count
    )
    db.add(shift_log)
    db.commit()
    db.refresh(shift_log)
    
    return shift_log


def compute_machine_stats(db: Session, target_date: date):
    """
    Compute actual vs ideal stats per machine for the given date.
    Returns list of dicts for chart rendering.
    """
    machines = db.query(Machine).order_by(Machine.order_in_pipeline).all()
    stats = []
    
    for machine in machines:
        target_today = db.query(func.sum(DailySchedule.target_qty)).filter(
            DailySchedule.machine_id == machine.id,
            DailySchedule.scheduled_date == target_date
        ).scalar() or 0
        
        actual_completed = db.query(func.sum(DailySchedule.completed_qty)).filter(
            DailySchedule.machine_id == machine.id,
            DailySchedule.scheduled_date == target_date
        ).scalar() or 0
        
        completion_pct = (actual_completed / target_today * 100) if target_today > 0 else 0.0
        
        stats.append({
            "machine_name": machine.name,
            "ideal_capacity": machine.capacity_per_day,
            "actual_completed": actual_completed,
            "target_today": target_today,
            "completion_pct": round(completion_pct, 1)
        })
    
    return stats


def compute_shift_summary(db: Session, target_date: date):
    """
    Aggregate shift summary for the given date in terms of unique equivalent panels.
    """
    shift_log = db.query(ShiftLog).filter(ShiftLog.shift_date == target_date).first()
    
    if shift_log and not shift_log.is_active:
        total_target = shift_log.total_target
        total_completed = shift_log.total_completed
        total_backlog = shift_log.total_backlog
    else:
        schedules = db.query(DailySchedule).options(joinedload(DailySchedule.order), joinedload(DailySchedule.machine)).filter(
            DailySchedule.scheduled_date == target_date
        ).all()
        
        order_targets = {}
        order_completions = {}
        order_backlogs = {}
        
        for sched in schedules:
            if not sched.order or not sched.machine:
                continue
            eq_target = convert_qty(sched.target_qty, sched.machine.name, "Panels", sched.order)
            eq_comp = convert_qty(sched.completed_qty, sched.machine.name, "Panels", sched.order)
            
            order_targets[sched.order_id] = max(order_targets.get(sched.order_id, 0), eq_target)
            
            # For Shift Progress, ONLY count panels that have fully exited the PUF machine
            if sched.machine.name == "PUF":
                order_completions[sched.order_id] = max(order_completions.get(sched.order_id, 0), eq_comp)
            
            if sched.is_backlog:
                order_backlogs[sched.order_id] = max(order_backlogs.get(sched.order_id, 0), eq_target)
                
        total_target = sum(order_targets.values())
        total_completed = sum(order_completions.values())
        total_backlog = sum(order_backlogs.values())

    completion_pct = (total_completed / total_target * 100) if total_target > 0 else 0.0
    
    return {
        "shift_date": target_date,
        "is_active": shift_log.is_active if shift_log else False,
        "total_target": total_target,
        "total_completed": total_completed,
        "total_backlog": total_backlog,
        "completion_pct": round(completion_pct, 1),
        "shift_started_at": shift_log.started_at if shift_log else None
    }


def get_order_current_stage(db: Session, order_id: int, target_date: date):
    """
    Determine which machine stage an order is currently at.
    Returns the name of the first incomplete machine stage, or 'All Done'.
    """
    schedules = db.query(DailySchedule).filter(
        DailySchedule.order_id == order_id,
        DailySchedule.scheduled_date == target_date
    ).join(Machine).order_by(Machine.order_in_pipeline).all()
    
    for sched in schedules:
        if sched.completed_qty < sched.target_qty:
            return sched.machine.name
    
    return "All Done"


def get_priority_queue(db: Session, target_date: date):
    """
    Get the FIFO priority queue for a given date.
    Order: Backlog first → Emergency (0) → High (1) → Normal (2) → FIFO (created_at).
    Returns a de-duplicated list of orders with their queue position.
    """
    schedules = db.query(DailySchedule).options(
        joinedload(DailySchedule.order),
        joinedload(DailySchedule.machine)
    ).filter(
        DailySchedule.scheduled_date == target_date
    ).order_by(
        DailySchedule.priority.asc(),      # Emergency (0) → High (1) → Normal (2) — ALWAYS first by priority
        DailySchedule.is_backlog.desc(),   # Within same priority: Backlog before new
        DailySchedule.order_id.asc()       # FIFO by order id
    ).all()
    
    # De-duplicate by order_id — we want unique orders in queue order
    seen_orders = set()
    queue = []
    position = 1
    
    for sched in schedules:
        if sched.order_id not in seen_orders:
            seen_orders.add(sched.order_id)
            
            queue.append({
                "position": position,
                "order_id": sched.order_id,
                "dwg_no": sched.order.dwg_no,
                "wo_no": sched.order.wo_no,
                "customer_name": sched.order.customer_name,
                "priority": sched.priority,
                "priority_label": PRIORITY_LABELS.get(sched.priority, "Normal"),
                "is_backlog": sched.is_backlog,
                "total_target": sched.order.total_panel_qty,
                "total_completed": sched.order.completed_qty,
                "total_panel_qty": sched.order.total_panel_qty,
                "is_done": sched.order.is_completed
            })
            position += 1
    
    return queue


def update_order_priority(db: Session, order_id: int, new_priority: int):
    """
    Update priority for an order and cascade to all its DailySchedule entries.
    Priority: 0 = Emergency, 1 = High, 2 = Normal
    """
    if new_priority not in (0, 1, 2):
        raise ValueError("Priority must be 0 (Emergency), 1 (High), or 2 (Normal)")
    
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        return None
    
    order.priority = new_priority
    
    # Cascade to all future (incomplete) DailySchedule entries for this order
    db.query(DailySchedule).filter(
        DailySchedule.order_id == order_id,
        DailySchedule.completed_qty < DailySchedule.target_qty  # Only update incomplete ones
    ).update({DailySchedule.priority: new_priority}, synchronize_session='fetch')
    
    db.commit()
    
    return {
        "order_id": order_id,
        "dwg_no": order.dwg_no,
        "new_priority": new_priority,
        "priority_label": PRIORITY_LABELS.get(new_priority, "Normal")
    }


def snapshot_daily_work(db: Session, target_date: date):
    """
    Create DailyWorkLog entries for all schedules on this date.
    Called at end of shift to preserve the historical record.
    """
    # Delete any existing logs for this date (idempotent re-run)
    db.query(DailyWorkLog).filter(DailyWorkLog.log_date == target_date).delete()
    
    schedules = db.query(DailySchedule).options(
        joinedload(DailySchedule.order),
        joinedload(DailySchedule.machine)
    ).filter(
        DailySchedule.scheduled_date == target_date
    ).all()
    
    logs_to_add = []
    for sched in schedules:
        if sched.completed_qty >= sched.target_qty:
            status = "Completed"
        elif sched.completed_qty > 0:
            status = "Ongoing"
        else:
            status = "Not Started"
        
        if sched.is_backlog:
            status = "Backlog"
        
        current_stage = get_order_current_stage(db, sched.order_id, target_date)
        
        log = DailyWorkLog(
            log_date=target_date,
            wo_no=sched.order.wo_no,
            dwg_no=sched.order.dwg_no,
            customer_name=sched.order.customer_name,
            machine_name=sched.machine.name,
            target_qty=sched.target_qty,
            completed_qty=sched.completed_qty,
            status=status,
            current_stage=current_stage,
            is_backlog=sched.is_backlog
        )
        logs_to_add.append(log)
    
    db.bulk_save_objects(logs_to_add)
    db.commit()


def end_of_day_process(db: Session, date_to_process: date):
    """
    End of shift: snapshot daily work, shift unmet targets to backlog, close shift.
    BACKLOG INHERITS PRIORITY from the parent order — so emergency orders stay emergency.
    """
    # 1. Snapshot the day's work for historical records
    snapshot_daily_work(db, date_to_process)
    
    # 2. Find unmet schedules and create backlog
    schedules = db.query(DailySchedule).options(
        joinedload(DailySchedule.order)
    ).filter(
        DailySchedule.scheduled_date == date_to_process,
        DailySchedule.target_qty > DailySchedule.completed_qty
    ).all()
    
    next_day = date_to_process + timedelta(days=1)
    backlogs_to_add = []
    total_backlog_qty = 0
    
    for sched in schedules:
        unmet_qty = sched.target_qty - sched.completed_qty
        
        eq_unmet = convert_qty(unmet_qty, sched.machine.name, "Panels", sched.order)
        total_backlog_qty += eq_unmet
        
        # We DO NOT modify sched.target_qty = sched.completed_qty here anymore.
        # Modifying it would mask the missed target on historical dashboards (making it look like 100% completion).
        
        # Check if backlog already exists for tomorrow (idempotency if end-of-day is run multiple times)
        existing_backlog = db.query(DailySchedule).filter(
            DailySchedule.order_id == sched.order_id,
            DailySchedule.machine_id == sched.machine_id,
            DailySchedule.scheduled_date == next_day,
            DailySchedule.is_backlog == True
        ).first()
        
        if existing_backlog:
            existing_backlog.target_qty = unmet_qty
        else:
            backlog_sched = DailySchedule(
                order_id=sched.order_id,
                machine_id=sched.machine_id,
                scheduled_date=next_day,
                target_qty=unmet_qty,
                completed_qty=0,
                is_backlog=True,
                priority=sched.order.priority
            )
            backlogs_to_add.append(backlog_sched)
    
    db.bulk_save_objects(backlogs_to_add)
    
    # 3. Close the shift log
    shift_log = db.query(ShiftLog).filter(ShiftLog.shift_date == date_to_process).first()
    if shift_log:
        # Get final accurate equivalent panels
        summary = compute_shift_summary(db, date_to_process)
        
        shift_log.is_active = False
        shift_log.ended_at = datetime.utcnow()
        shift_log.total_completed = summary["total_completed"]
        shift_log.total_target = summary["total_target"]
        shift_log.total_backlog = total_backlog_qty
    
    db.commit()
    
    return {
        "backlogs_created": len(backlogs_to_add),
        "total_backlog_qty": total_backlog_qty
    }
