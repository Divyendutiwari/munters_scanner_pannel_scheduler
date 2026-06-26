from sqlalchemy import Column, Integer, String, Float, ForeignKey, DateTime, Boolean, Date
from sqlalchemy.orm import relationship
import datetime
from database import Base

class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, index=True)
    month = Column(String)
    sales_person = Column(String)
    wo_no = Column(String, index=True)
    sap_code = Column(String)
    customer_name = Column(String)
    dwg_no = Column(String, index=True)
    cfm = Column(Integer)
    qty = Column(Integer)
    fab_code = Column(String)
    ab_unit_qty = Column(Integer)
    panel_qty_per_unit = Column(Integer)
    total_panel_qty = Column(Integer)
    no_of_strokes = Column(Integer)
    
    # Priority: 0 = Emergency (done first), 1 = High, 2 = Normal (default FIFO)
    priority = Column(Integer, default=2, index=True)
    
    # Track completion status
    completed_qty = Column(Integer, default=0)
    is_completed = Column(Boolean, default=False)
    status = Column(String, default="pending")
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    
    schedules = relationship("DailySchedule", back_populates="order")


class Machine(Base):
    __tablename__ = "machines"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True) # e.g. 'Auto Fold', 'Turret Punch', 'Bending', 'Gasketing', 'PUF'
    capacity_per_day = Column(Integer) # e.g. 800 for Auto Fold
    order_in_pipeline = Column(Integer) # 1 = Auto Fold, 2 = Turret, etc.


class DailySchedule(Base):
    """
    Represents the scheduled workload for a specific order on a specific machine for a specific day.
    """
    __tablename__ = "daily_schedules"

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"))
    machine_id = Column(Integer, ForeignKey("machines.id"))
    scheduled_date = Column(Date, index=True)
    
    target_qty = Column(Integer) # How many sheets/panels are expected to be done today
    completed_qty = Column(Integer, default=0) # How many were actually done
    is_backlog = Column(Boolean, default=False) # True if this was carried over from a previous day
    priority = Column(Integer, default=2) # Inherited from order: 0=Emergency, 1=High, 2=Normal
    
    order = relationship("Order", back_populates="schedules")
    machine = relationship("Machine")

    @property
    def machine_name(self):
        return self.machine.name


class ShiftLog(Base):
    """
    Records each shift's metadata — start/end time, active status, and summary stats.
    """
    __tablename__ = "shift_logs"

    id = Column(Integer, primary_key=True, index=True)
    shift_date = Column(Date, index=True)
    started_at = Column(DateTime, default=datetime.datetime.utcnow)
    ended_at = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True)
    total_target = Column(Integer, default=0)
    total_completed = Column(Integer, default=0)
    total_backlog = Column(Integer, default=0)


class DailyWorkLog(Base):
    """
    Per-order, per-machine, per-day summary snapshot — created at end of shift.
    Used for historical Excel export (growing file).
    """
    __tablename__ = "daily_work_logs"

    id = Column(Integer, primary_key=True, index=True)
    log_date = Column(Date, index=True)
    wo_no = Column(String)
    dwg_no = Column(String)
    customer_name = Column(String)
    machine_name = Column(String)
    target_qty = Column(Integer)
    completed_qty = Column(Integer)
    status = Column(String)  # "Completed", "Ongoing", "Backlog"
    current_stage = Column(String)  # e.g. "Auto Fold", "Bending", "All Done"
    is_backlog = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

class ScannedBarcode(Base):
    """
    Prevents duplicate scanning of the same physical barcode on the same machine.
    """
    __tablename__ = "scanned_barcodes"

    id = Column(Integer, primary_key=True, index=True)
    barcode = Column(String, index=True)
    machine_name = Column(String, index=True)
    schedule_id = Column(Integer, ForeignKey("daily_schedules.id"))
    scanned_at = Column(DateTime, default=datetime.datetime.utcnow)
