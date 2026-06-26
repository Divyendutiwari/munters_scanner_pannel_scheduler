from pydantic import BaseModel
from typing import List, Optional
from datetime import date, datetime

class OrderBase(BaseModel):
    wo_no: str
    dwg_no: str
    total_panel_qty: int
    no_of_strokes: int
    customer_name: str

class OrderOut(OrderBase):
    id: int
    priority: int = 2
    completed_qty: int
    is_completed: bool
    created_at: datetime
    
    class Config:
        from_attributes = True

class ScheduleOut(BaseModel):
    id: int
    scheduled_date: date
    target_qty: int
    completed_qty: int
    is_backlog: bool
    priority: int = 2
    machine_name: str
    order: OrderOut

    class Config:
        from_attributes = True

class TickUpdate(BaseModel):
    schedule_id: int
    completed_qty: int

class ScanUpdate(BaseModel):
    barcode: str
    machine_name: str

class MachineOut(BaseModel):
    id: int
    name: str
    capacity_per_day: int
    order_in_pipeline: int

    class Config:
        from_attributes = True

class MachineUpdate(BaseModel):
    capacity_per_day: int

class BatchCapacityUpdate(BaseModel):
    """Update all machine capacities before shift start."""
    capacities: dict  # { machine_id: capacity_per_day }

# --- Priority schemas ---

class PriorityUpdate(BaseModel):
    """Update priority of an order. 0=Emergency, 1=High, 2=Normal"""
    priority: int  # 0, 1, or 2

class PriorityQueueItem(BaseModel):
    """A single item in the priority queue display."""
    position: int
    order_id: int
    dwg_no: str
    wo_no: str
    customer_name: str
    priority: int
    priority_label: str
    is_backlog: bool
    total_target: int
    total_completed: int
    total_panel_qty: int
    is_done: bool

# --- Analytics / Dashboard schemas ---

class MachineStats(BaseModel):
    """Per-machine stats for Actual vs Ideal chart."""
    machine_name: str
    ideal_capacity: int
    actual_completed: int
    target_today: int
    completion_pct: float

class ShiftSummary(BaseModel):
    """Aggregated shift statistics."""
    shift_date: date
    is_active: bool
    total_target: int
    total_completed: int
    total_backlog: int
    completion_pct: float
    shift_started_at: Optional[datetime] = None

class DashboardData(BaseModel):
    """Single-response endpoint combining all dashboard data."""
    schedules: List[ScheduleOut]
    machine_stats: List[MachineStats]
    shift_summary: Optional[ShiftSummary] = None
    machines: List[MachineOut]
    priority_queue: List[PriorityQueueItem] = []

# --- History / Export schemas ---

class ShiftLogOut(BaseModel):
    id: int
    shift_date: date
    started_at: datetime
    ended_at: Optional[datetime] = None
    is_active: bool
    total_target: int
    total_completed: int
    total_backlog: int

    class Config:
        from_attributes = True

class DailyWorkLogOut(BaseModel):
    id: int
    log_date: date
    wo_no: str
    dwg_no: str
    customer_name: str
    machine_name: str
    target_qty: int
    completed_qty: int
    status: str
    current_stage: str
    is_backlog: bool

    class Config:
        from_attributes = True
