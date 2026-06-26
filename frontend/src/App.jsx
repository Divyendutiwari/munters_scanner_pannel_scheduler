import React, { useState, useEffect, useRef, useMemo, useCallback } from 'react';
import axios from 'axios';
import { 
  UploadCloud, CheckCircle2, AlertCircle, Search, Calendar, Play, 
  Download, Settings, Zap, BarChart3, Clock, ChevronDown, ChevronUp,
  FileSpreadsheet, TrendingUp, Activity, Moon, AlertTriangle, Shield, ListOrdered, ScanLine,
  Minimize2, Maximize2, GripVertical, X, Monitor, RotateCcw
} from 'lucide-react';
import { format, addDays } from 'date-fns';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, Cell
} from 'recharts';
import ScannerDemo from './ScannerDemo';

const API_URL = 'http://localhost:8000';

// ─── Floating Machine Status Panel ─────────────────────────────
const FloatingMachineStatus = ({ machineStats, shiftStatus, targetDate }) => {
  const [minimized, setMinimized] = useState(false);
  const [position, setPosition] = useState({ x: window.innerWidth - 340, y: 80 });
  const [isDragging, setIsDragging] = useState(false);
  const dragOffset = useRef({ x: 0, y: 0 });
  const panelRef = useRef(null);

  const handleMouseDown = (e) => {
    if (e.target.closest('button')) return; // Don't drag on button clicks
    setIsDragging(true);
    const rect = panelRef.current.getBoundingClientRect();
    dragOffset.current = { x: e.clientX - rect.left, y: e.clientY - rect.top };
    e.preventDefault();
  };

  useEffect(() => {
    if (!isDragging) return;
    const handleMouseMove = (e) => {
      setPosition({
        x: Math.max(0, Math.min(window.innerWidth - 320, e.clientX - dragOffset.current.x)),
        y: Math.max(0, Math.min(window.innerHeight - 60, e.clientY - dragOffset.current.y))
      });
    };
    const handleMouseUp = () => setIsDragging(false);
    window.addEventListener('mousemove', handleMouseMove);
    window.addEventListener('mouseup', handleMouseUp);
    return () => {
      window.removeEventListener('mousemove', handleMouseMove);
      window.removeEventListener('mouseup', handleMouseUp);
    };
  }, [isDragging]);

  // Don't show floating panel if no shift is running
  if (shiftStatus === 'not_started') return null;

  const machineColors = {
    'Auto Fold': '#6366f1',
    'Turret Punch': '#8b5cf6',
    'Bending': '#3b82f6',
    'Gasketing': '#10b981',
    'PUF': '#f59e0b'
  };

  if (minimized) {
    return (
      <div
        ref={panelRef}
        className="floating-panel floating-minimized"
        style={{ left: position.x, top: position.y }}
        onMouseDown={handleMouseDown}
      >
        <Monitor size={16} />
        <span>Live Status</span>
        <button className="floating-btn" onClick={() => setMinimized(false)} title="Expand">
          <Maximize2 size={14} />
        </button>
      </div>
    );
  }

  return (
    <div
      ref={panelRef}
      className={`floating-panel floating-expanded ${isDragging ? 'dragging' : ''}`}
      style={{ left: position.x, top: position.y }}
    >
      <div className="floating-header" onMouseDown={handleMouseDown}>
        <div className="floating-header-left">
          <GripVertical size={14} className="drag-handle-icon" />
          <Monitor size={16} />
          <span>Live Machine Status</span>
        </div>
        <div className="floating-header-right">
          <button className="floating-btn" onClick={() => setMinimized(true)} title="Minimize">
            <Minimize2 size={14} />
          </button>
        </div>
      </div>
      <div className="floating-body">
        {machineStats && machineStats.length > 0 ? (
          machineStats.map(stat => {
            const pct = stat.target_today > 0
              ? Math.round((stat.actual_completed / stat.target_today) * 100)
              : 0;
            const barColor = pct >= 80 ? '#10b981' : pct >= 50 ? '#f59e0b' : '#ef4444';
            const machineColor = machineColors[stat.machine_name] || '#6366f1';
            return (
              <div key={stat.machine_name} className="floating-machine-row">
                <div className="floating-machine-name">
                  <span className="floating-dot" style={{ background: machineColor }}></span>
                  {stat.machine_name}
                </div>
                <div className="floating-machine-stats">
                  <div className="floating-bar-wrap">
                    <div className="floating-bar-bg">
                      <div
                        className="floating-bar-fill"
                        style={{ width: `${Math.min(pct, 100)}%`, background: barColor }}
                      ></div>
                    </div>
                    <span className="floating-pct" style={{ color: barColor }}>{pct}%</span>
                  </div>
                  <div className="floating-qty">
                    {stat.actual_completed} / {stat.target_today}
                  </div>
                </div>
              </div>
            );
          })
        ) : (
          <div className="floating-empty">No data for today</div>
        )}
      </div>
      <div className="floating-footer">
        <span className="floating-date">{targetDate}</span>
        <span className={`floating-shift-badge ${shiftStatus}`}>
          {shiftStatus === 'active' ? '● Active' : '○ Ended'}
        </span>
      </div>
    </div>
  );
};

// ─── Custom Tooltip for Charts ─────────────────────────────────
const CustomTooltip = ({ active, payload, label }) => {
  if (active && payload && payload.length) {
    const unit = payload[0]?.payload?.unit || 'units';
    return (
      <div className="chart-tooltip">
        <p className="chart-tooltip-label">{label} <span style={{opacity:0.6, fontSize:'0.8rem'}}>({unit})</span></p>
        {payload.map((p, i) => (
          <p key={i} style={{ color: p.color, margin: '4px 0' }}>
            {p.name}: <strong>{p.value.toLocaleString()}</strong> <span style={{opacity:0.7, fontSize:'0.8rem'}}>{unit}</span>
          </p>
        ))}
      </div>
    );
  }
  return null;
};

// ─── Circular Progress Gauge ────────────────────────────────────
const CompletionGauge = ({ percentage, size = 120 }) => {
  const radius = (size - 16) / 2;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (percentage / 100) * circumference;
  const color = percentage >= 80 ? '#10b981' : percentage >= 50 ? '#f59e0b' : '#ef4444';

  return (
    <div className="gauge-container">
      <svg width={size} height={size} className="gauge-svg">
        <circle cx={size/2} cy={size/2} r={radius} fill="none" stroke="rgba(255,255,255,0.07)" strokeWidth="10" />
        <circle cx={size/2} cy={size/2} r={radius} fill="none" stroke={color} strokeWidth="10"
          strokeDasharray={circumference} strokeDashoffset={offset}
          strokeLinecap="round" transform={`rotate(-90 ${size/2} ${size/2})`}
          style={{ transition: 'stroke-dashoffset 0.8s cubic-bezier(.4,0,.2,1)' }}
        />
      </svg>
      <div className="gauge-value" style={{ color }}>
        {Math.round(percentage)}%
      </div>
    </div>
  );
};

// ─── Main App ───────────────────────────────────────────────────
function App() {
  // State
  const [activeTab, setActiveTab] = useState('dashboard');
  const [file, setFile] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [dashboardData, setDashboardData] = useState(null);
  const [filterDwg, setFilterDwg] = useState('');
  const [filterMachine, setFilterMachine] = useState('All');
  const [targetDate, setTargetDate] = useState(format(new Date(), 'yyyy-MM-dd'));
  const [loading, setLoading] = useState(false);
  const [shiftStatus, setShiftStatus] = useState('not_started'); // not_started | active | ended
  const [machines, setMachines] = useState([]);
  const [capacityInputs, setCapacityInputs] = useState({});
  const [history, setHistory] = useState([]);
  const [historyDate, setHistoryDate] = useState('');
  const [notification, setNotification] = useState(null);
  const [startingShift, setStartingShift] = useState(false);
  const [pendingOrders, setPendingOrders] = useState([]);

  // Unit Helper
  const getUnit = (machineName) => {
    switch (machineName) {
      case 'Auto Fold': return 'sheets';
      case 'Turret Punch': return 'punches';
      case 'Bending': return 'strokes';
      case 'PUF': return 'puffings';
      default: return 'panels';
    }
  };

  // Priority helpers
  const priorityLabel = (p) => ({0:'Emergency',1:'High',2:'Normal'}[p] || 'Normal');
  const priorityClass = (p) => ({0:'priority-emergency',1:'priority-high',2:'priority-normal'}[p] || 'priority-normal');
  const priorityIcon = (p) => ({0:'🔴',1:'🟡',2:'🟢'}[p] || '🟢');

  // Debounce timers for sliders
  const sliderTimers = useRef({});

  // ─── Notifications ──────────────────────────────────────────
  const showNotify = useCallback((msg, type = 'success') => {
    setNotification({ msg, type });
    setTimeout(() => setNotification(null), 3500);
  }, []);

  // ─── Fetch Machines (always load independently) ────────────
  const fetchMachines = useCallback(async () => {
    try {
      const res = await axios.get(`${API_URL}/machines/`);
      setMachines(res.data || []);
      setCapacityInputs(prev => {
        if (Object.keys(prev).length > 0) return prev;
        const caps = {};
        (res.data || []).forEach(m => { caps[m.id] = m.capacity_per_day; });
        return caps;
      });
    } catch (e) {
      console.error('Failed to load machines:', e);
    }
  }, []);

  // ─── Fetch Dashboard ────────────────────────────────────────
  const fetchDashboard = useCallback(async () => {
    setLoading(true);
    try {
      const res = await axios.get(`${API_URL}/dashboard/?target_date=${targetDate}`);
      setDashboardData(res.data);
      if (res.data.machines?.length) {
        setMachines(res.data.machines);
        setCapacityInputs(prev => {
          const hasValues = Object.keys(prev).length > 0;
          return hasValues ? prev : Object.fromEntries((res.data.machines || []).map(m => [m.id, m.capacity_per_day]));
        });
      }
      // Derive shift status
      if (res.data.shift_summary?.shift_started_at) {
        setShiftStatus(res.data.shift_summary.is_active ? 'active' : 'ended');
      }
    } catch (error) {
      console.error("Dashboard fetch error", error);
    }
    setLoading(false);
  }, [targetDate]);

  // Always load machines on mount + whenever date changes
  // Clear localStorage on mount for a fresh start every time
  useEffect(() => {
    localStorage.removeItem('mes_shift_history');
    localStorage.removeItem('mes_history_cache');
  }, []);

  useEffect(() => { fetchMachines(); }, [fetchMachines]);
  useEffect(() => { fetchDashboard(); }, [fetchDashboard]);

  // ─── Shift Status Check ──────────────────────────────────
  useEffect(() => {
    const checkShift = async () => {
      try {
        const res = await axios.get(`${API_URL}/shift-status/?target_date=${targetDate}`);
        setShiftStatus(res.data.status);
      } catch (e) {}
    };
    checkShift();
  }, [targetDate]);

  // ─── Upload ─────────────────────────────────────────────────
  const handleUpload = async () => {
    if (!file) return;
    setUploading(true);
    const formData = new FormData();
    formData.append('file', file);
    try {
      const res = await axios.post(`${API_URL}/upload/`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });
      showNotify(res.data.message || 'Orders imported successfully.');
      setFile(null);
      fetchDashboard();
      fetchPendingOrders();
    } catch (error) {
      const detail = error.response?.data?.detail || error.message || 'Unknown error';
      showNotify(`Upload failed: ${detail}`, 'error');
    }
    setUploading(false);
  };

  // ─── Reset All Data ──────────────────────────────────────────
  const handleReset = async () => {
    if (!window.confirm('⚠️ This will DELETE all orders, schedules and shift history. Machines will be preserved. Continue?')) return;
    try {
      await axios.post(`${API_URL}/reset/`);
      // Clear localStorage completely
      localStorage.removeItem('mes_shift_history');
      localStorage.removeItem('mes_history_cache');
      showNotify('✅ All data cleared. Ready for a fresh import.');
      setDashboardData(null);
      setPendingOrders([]);
      setShiftStatus('not_started');
      setHistory([]);
      fetchDashboard();
    } catch (err) {
      showNotify('Reset failed: ' + (err.response?.data?.detail || err.message), 'error');
    }
  };

  // ─── Priority Change ──────────────────────────────────────
  const handlePriorityChange = async (orderId, newPriority) => {
    try {
      await axios.put(`${API_URL}/orders/${orderId}/priority`, { priority: parseInt(newPriority) });
      showNotify(`Priority updated to ${priorityLabel(parseInt(newPriority))}`);
      fetchDashboard();
      fetchPendingOrders();
    } catch (err) {
      showNotify(err.response?.data?.detail || 'Error updating priority', 'error');
    }
  };

  // ─── Fetch Pending Orders ─────────────────────────────────
  const fetchPendingOrders = async () => {
    try {
      const res = await axios.get(`${API_URL}/pending-orders/`);
      setPendingOrders(res.data);
    } catch {}
  };

  useEffect(() => {
    if (shiftStatus === 'not_started') fetchPendingOrders();
  }, [shiftStatus]);

  // ─── Start Shift ────────────────────────────────────────────
  const handleStartShift = async () => {
    setStartingShift(true);
    try {
      // 1. Save machine capacities
      await axios.post(`${API_URL}/machines/batch-capacity/`, {
        capacities: capacityInputs
      });
      // 2. Start shift (allocates + creates log)
      await axios.post(`${API_URL}/start-shift/`);
      setShiftStatus('active');
      showNotify('⚡ Shift started! Orders distributed based on machine capacities.');
      fetchDashboard();
    } catch (error) {
      showNotify('Error starting shift', 'error');
    }
    setStartingShift(false);
  };



  // ─── Slider Tick (debounced) ────────────────────────────────
  const handleSliderChange = useCallback((scheduleId, value, targetQty) => {
    // Optimistic UI update
    setDashboardData(prev => {
      if (!prev) return prev;
      return {
        ...prev,
        schedules: prev.schedules.map(s =>
          s.id === scheduleId ? { ...s, completed_qty: value } : s
        )
      };
    });

    // Debounced API call
    clearTimeout(sliderTimers.current[scheduleId]);
    sliderTimers.current[scheduleId] = setTimeout(async () => {
      try {
        const res = await axios.post(`${API_URL}/schedule/tick/`, {
          schedule_id: scheduleId,
          completed_qty: value
        });
        // When job is 100% done, re-fetch dashboard to reveal the next machine's task instantly
        if (value >= targetQty) {
          fetchDashboard();
          if (res.data.stage_completed) {
            showNotify(`✅ ${res.data.dwg_no} fully completed at ${res.data.machine_name}! Handed over to next stage.`, 'success');
          } else {
            showNotify('✅ Job complete!', 'success');
          }
        }
      } catch (err) {
        showNotify(err.response?.data?.detail || 'Error updating', 'error');
      }
    }, 300);
  }, [showNotify, fetchDashboard]);

  // ─── End of Shift ───────────────────────────────────────────
  const handleEndOfDay = async () => {
    if (!window.confirm(`End shift for ${targetDate}? Unmet targets will shift to tomorrow as backlog.`)) return;
    try {
      const res = await axios.post(`${API_URL}/end-of-day/?date_to_process=${targetDate}`);
      showNotify(`Shift ended. ${res.data.backlogs_created} backlogs created (${res.data.total_backlog_qty} qty).`);
      setShiftStatus('ended');
      
      // Cache to localStorage
      if (dashboardData) {
        const cached = JSON.parse(localStorage.getItem('mes_shift_history') || '[]');
        cached.push({
          date: targetDate,
          summary: dashboardData.shift_summary,
          stats: dashboardData.machine_stats,
          timestamp: new Date().toISOString()
        });
        localStorage.setItem('mes_shift_history', JSON.stringify(cached));
      }
      
      fetchDashboard();
    } catch (error) {
      showNotify('Error ending shift', 'error');
    }
  };

  // ─── History ────────────────────────────────────────────────
  const fetchHistory = async (dateFilter) => {
    try {
      const url = dateFilter 
        ? `${API_URL}/history/?target_date=${dateFilter}`
        : `${API_URL}/history/`;
      const res = await axios.get(url);
      setHistory(res.data);
      // Cache
      localStorage.setItem('mes_history_cache', JSON.stringify(res.data));
    } catch {
      // Fallback to cache
      const cached = JSON.parse(localStorage.getItem('mes_history_cache') || '[]');
      setHistory(cached);
    }
  };

  useEffect(() => {
    if (activeTab === 'history') {
      fetchHistory(historyDate || null);
    }
  }, [activeTab, historyDate]);

  // ─── Export ─────────────────────────────────────────────────
  const handleExportDaily = () => {
    window.open(`${API_URL}/export-report/?target_date=${targetDate}`, '_blank');
  };

  const handleExportHistory = () => {
    window.open(`${API_URL}/export-history/`, '_blank');
  };

  // ─── Computed values ────────────────────────────────────────
  const schedules = dashboardData?.schedules || [];
  const machineStats = dashboardData?.machine_stats || [];
  const shiftSummary = dashboardData?.shift_summary || {};
  const priorityQueue = dashboardData?.priority_queue || [];

  const machineNames = ['All', 'Auto Fold', 'Turret Punch', 'Bending', 'Gasketing', 'PUF'];

  const filteredSchedules = useMemo(() => {
    return schedules.filter(s => {
      const matchDwg = !filterDwg || s.order.dwg_no.toLowerCase().includes(filterDwg.toLowerCase());
      const matchMachine = filterMachine === 'All' || s.machine_name === filterMachine;
      return matchDwg && matchMachine;
    });
  }, [schedules, filterDwg, filterMachine]);

  // Group by machine for kanban view
  const groupedSchedules = useMemo(() => {
    const grouped = {};
    machineNames.slice(1).forEach(m => grouped[m] = []);
    filteredSchedules.forEach(s => {
      if (grouped[s.machine_name]) grouped[s.machine_name].push(s);
    });
    return grouped;
  }, [filteredSchedules]);

  // ─── Render ─────────────────────────────────────────────────
  return (
    <div className="app-container">
      {/* Notification Toast */}
      {notification && (
        <div className={`toast toast-${notification.type}`}>
          {notification.type === 'success' ? <CheckCircle2 size={18}/> : <AlertCircle size={18}/>}
          {notification.msg}
        </div>
      )}

      {/* Header */}
      <header className="header">
        <div className="header-left">
          <h1 className="title">
            <Activity size={28} className="title-icon"/>
            MES Production Planner
          </h1>
          <div className={`shift-indicator ${shiftStatus}`}>
            <span className="shift-dot"></span>
            {shiftStatus === 'active' ? 'Shift Active' : shiftStatus === 'ended' ? 'Shift Ended' : 'No Shift'}
          </div>
        </div>
        <div className="header-right">
          <input type="date" className="input date-input" value={targetDate}
            onChange={(e) => setTargetDate(e.target.value)} />
        </div>
      </header>

      {/* Tab Navigation */}
      <nav className="tab-bar">
        <button className={`tab ${activeTab === 'dashboard' ? 'active' : ''}`}
          onClick={() => setActiveTab('dashboard')}>
          <BarChart3 size={16}/> Dashboard
        </button>
        <button className={`tab ${activeTab === 'scanner' ? 'active' : ''}`}
          onClick={() => setActiveTab('scanner')}>
          <ScanLine size={16}/> Scanner
        </button>
        <button className={`tab ${activeTab === 'history' ? 'active' : ''}`}
          onClick={() => setActiveTab('history')}>
          <Clock size={16}/> History
        </button>
        <button className={`tab ${activeTab === 'export' ? 'active' : ''}`}
          onClick={() => setActiveTab('export')}>
          <FileSpreadsheet size={16}/> Export
        </button>
      </nav>

      {/* ═══════════════════════════════════════════════════════ */}
      {/* DASHBOARD TAB                                          */}
      {/* ═══════════════════════════════════════════════════════ */}
      {activeTab === 'dashboard' && (
        <div className="dashboard-content">

          {/* Configuration & Upload */}
          {(shiftStatus === 'not_started' || shiftStatus === 'active') && (
            <div className="card preshift-panel">
              <h2 className="card-title"><Settings size={20}/> {shiftStatus === 'active' ? 'Mid-Shift Configuration' : 'Pre-Shift Configuration'}</h2>
              
              {/* Upload */}
              <div className="upload-area"
                onDragOver={(e) => e.preventDefault()}
                onDrop={(e) => { e.preventDefault(); if(e.dataTransfer.files[0]) setFile(e.dataTransfer.files[0]); }}
                onClick={() => document.getElementById('fileUpload').click()}>
                <UploadCloud className="upload-icon" />
                {file ? <p>Selected: <strong>{file.name}</strong></p> : <p>Drop Excel file here or click to browse</p>}
                <input type="file" id="fileUpload" style={{display: 'none'}} accept=".xlsx,.xls"
                  onChange={(e) => setFile(e.target.files[0])} />
              </div>
              {file && (
                <div style={{marginTop: '1rem', display:'flex', gap:'0.75rem', justifyContent:'flex-end'}}>
                  <button className="btn btn-outline" onClick={handleUpload} disabled={uploading}>
                    <UploadCloud size={16}/> {uploading ? 'Processing...' : 'Upload Orders'}
                  </button>
                </div>
              )}
              <div style={{marginTop:'0.75rem', textAlign:'right'}}>
                <button className="btn" style={{background:'rgba(239,68,68,0.15)', color:'#ef4444', border:'1px solid rgba(239,68,68,0.3)', fontSize:'0.8rem', padding:'0.4rem 1rem'}} onClick={handleReset}>
                  🗑️ Clear All Data
                </button>
              </div>

              {/* Machine Capacities */}
              <div className="capacity-grid">
                <h3 className="section-subtitle">Machine Capacities <span style={{fontWeight:400, opacity:0.6}}>(set daily capacity per machine unit)</span></h3>
                {machines.length === 0 ? (
                  <p style={{color:'#f59e0b', fontSize:'0.85rem', margin:'0.5rem 0'}}>⚠️ Backend not reachable — start the FastAPI server first.</p>
                ) : (
                  <div className="capacity-cards">
                    {machines.map(m => {
                      const unitHint = {
                        'Auto Fold':    'sheets/day (2 per panel)',
                        'Turret Punch': 'punches/day (2 per panel)',
                        'Bending':      'strokes/day (16 per panel)',
                        'Gasketing':    'panels/day',
                        'PUF':          'puffings/day',
                      }[m.name] || 'units/day';
                      return (
                        <div key={m.id} className="capacity-card">
                          <label className="capacity-label">{m.name}</label>
                          <span style={{fontSize:'0.7rem', color:'#64748b', marginBottom:'0.25rem', display:'block'}}>{unitHint}</span>
                          <input type="number" className="input capacity-input"
                            value={capacityInputs[m.id] ?? m.capacity_per_day}
                            onChange={(e) => setCapacityInputs({...capacityInputs, [m.id]: parseInt(e.target.value) || 0})} />
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>

              {/* Pending Orders — Set Priority Before Shift */}
              {pendingOrders.length > 0 && (
                <div className="pending-orders-section">
                  <h3 className="section-subtitle"><AlertTriangle size={16}/> Set Order Priority ({pendingOrders.length} pending)</h3>
                  <div className="pending-table-wrap">
                    <table className="live-table">
                      <thead>
                        <tr>
                          <th>DWG NO</th>
                          <th>WO NO</th>
                          <th>Customer</th>
                          <th>Panels</th>
                          <th>Priority</th>
                        </tr>
                      </thead>
                      <tbody>
                        {pendingOrders.map(o => (
                          <tr key={o.id} className="table-row">
                            <td className="mono bold">{o.dwg_no}</td>
                            <td className="mono">{o.wo_no}</td>
                            <td>{o.customer_name}</td>
                            <td className="num">{o.total_panel_qty}</td>
                            <td>
                              <select className="priority-select"
                                value={o.priority}
                                onChange={(e) => handlePriorityChange(o.id, e.target.value)}>
                                <option value={0}>🔴 Emergency</option>
                                <option value={1}>🟡 High</option>
                                <option value={2}>🟢 Normal</option>
                              </select>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}

              {/* Start Shift / Allocate */}
              <button className="btn btn-start-shift" onClick={handleStartShift} disabled={startingShift}>
                <Zap size={20}/>
                {startingShift ? 'Processing...' : (shiftStatus === 'active' ? '⚡ Allocate New Orders' : '⚡ Start Shift')}
              </button>
            </div>
          )}

          {/* Stats Cards Row */}
          {shiftStatus !== 'not_started' && (
            <div className="stats-row">
              <div className="stats-card">
                <div className="stats-card-header">
                  <span className="stats-label">Target Today</span>
                  <TrendingUp size={18} className="stats-icon accent"/>
                </div>
                <div className="stats-value">{shiftSummary.total_target || 0}</div>
                <div className="stats-sub">panels</div>
              </div>
              <div className="stats-card">
                <div className="stats-card-header">
                  <span className="stats-label">Completed</span>
                  <CheckCircle2 size={18} className="stats-icon success"/>
                </div>
                <div className="stats-value success-text">{shiftSummary.total_completed || 0}</div>
                <div className="stats-sub">panels done</div>
              </div>
              <div className="stats-card">
                <div className="stats-card-header">
                  <span className="stats-label">Backlog</span>
                  <AlertCircle size={18} className="stats-icon danger"/>
                </div>
                <div className="stats-value danger-text">{shiftSummary.total_backlog || 0}</div>
                <div className="stats-sub">carryover</div>
              </div>
              <div className="stats-card gauge-card">
                <CompletionGauge percentage={shiftSummary.completion_pct || 0} size={100}/>
                <span className="stats-label" style={{marginTop: '0.5rem'}}>Shift Progress</span>
              </div>
            </div>
          )}

          {/* Actual vs Ideal Chart */}
          {shiftStatus !== 'not_started' && machineStats.length > 0 && (
            <div className="card chart-card">
              <h2 className="card-title"><BarChart3 size={20}/> Actual vs Ideal Production Rate</h2>
              <div className="chart-container">
                <ResponsiveContainer width="100%" height={300}>
                  <BarChart data={machineStats} barCategoryGap="20%">
                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.06)" />
                    <XAxis dataKey="machine_name" stroke="#94a3b8" tick={{ fill: '#94a3b8', fontSize: 12 }} />
                    <YAxis stroke="#94a3b8" tick={{ fill: '#94a3b8', fontSize: 12 }} />
                    <Tooltip content={<CustomTooltip/>} />
                    <Legend wrapperStyle={{ color: '#94a3b8', fontSize: 13 }} />
                    <Bar dataKey="ideal_capacity" name="Ideal Capacity" radius={[6, 6, 0, 0]}>
                      {machineStats.map((entry, idx) => (
                        <Cell key={idx} fill="rgba(99, 102, 241, 0.35)" />
                      ))}
                    </Bar>
                    <Bar dataKey="target_today" name="Target Today" radius={[6, 6, 0, 0]}>
                      {machineStats.map((entry, idx) => (
                        <Cell key={idx} fill="rgba(59, 130, 246, 0.7)" />
                      ))}
                    </Bar>
                    <Bar dataKey="actual_completed" name="Actual Completed" radius={[6, 6, 0, 0]}>
                      {machineStats.map((entry, idx) => (
                        <Cell key={idx} fill={entry.completion_pct >= 80 ? '#10b981' : entry.completion_pct >= 50 ? '#f59e0b' : '#ef4444'} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>
          )}

          {/* Priority Queue Panel */}
          {shiftStatus !== 'not_started' && priorityQueue.length > 0 && (
            <div className="card priority-queue-card">
              <h2 className="card-title"><ListOrdered size={20}/> FIFO Priority Queue — Processing Order</h2>
              <div className="queue-list">
                {priorityQueue.map(item => (
                  <div key={item.order_id} className={`queue-item ${item.is_done ? 'queue-done' : ''} ${item.is_backlog ? 'queue-backlog' : ''}`}>
                    <div className="queue-position">{item.position}</div>
                    <div className="queue-info">
                      <div className="queue-dwg">{item.dwg_no}</div>
                      <div className="queue-customer">{item.customer_name}</div>
                    </div>
                    <div className="queue-meta">
                      {item.is_backlog && <span className="backlog-tag">BACKLOG</span>}
                      <span className={`priority-badge ${priorityClass(item.priority)}`}>
                        {priorityIcon(item.priority)} {item.priority_label}
                      </span>
                      <span className="queue-qty">{item.total_completed}/{item.total_target} panels</span>
                      {shiftStatus === 'active' && (
                        <select className="priority-select"
                          value={item.priority}
                          onChange={(e) => handlePriorityChange(item.order_id, e.target.value)}>
                          <option value={0}>🔴 Emergency</option>
                          <option value={1}>🟡 High</option>
                          <option value={2}>🟢 Normal</option>
                        </select>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Live Status Table & Kanban */}
          {shiftStatus !== 'not_started' && (
            <div className="card">
              <div className="table-header">
                <h2 className="card-title"><Calendar size={20}/> Live WIP Status</h2>
                <div className="table-controls">
                  <div className="search-box">
                    <Search size={16} className="search-icon"/>
                    <input type="text" className="input" placeholder="Filter DWG..."
                      value={filterDwg} onChange={(e) => setFilterDwg(e.target.value)} />
                  </div>
                  <select className="input select-input" value={filterMachine}
                    onChange={(e) => setFilterMachine(e.target.value)}>
                    {machineNames.map(m => <option key={m} value={m}>{m}</option>)}
                  </select>
                  {shiftStatus === 'active' && (
                    <button className="btn btn-end-shift" onClick={handleEndOfDay}>
                      <Moon size={16}/> End Shift
                    </button>
                  )}
                </div>
              </div>

              {loading ? <div className="loader"></div> : (
                <div className="live-table-wrapper">
                  <table className="live-table">
                    <thead>
                      <tr>
                        <th>Priority</th>
                        <th>Machine</th>
                        <th>WO NO</th>
                        <th>DWG NO</th>
                        <th>Customer</th>
                        <th>Target</th>
                        <th>Completed</th>
                        <th style={{minWidth: '200px'}}>Progress</th>
                        <th>Status</th>
                      </tr>
                    </thead>
                    <tbody>
                      {filteredSchedules.map(item => {
                        const pct = item.target_qty > 0 ? Math.round((item.completed_qty / item.target_qty) * 100) : 0;
                        const isDone = pct >= 100;
                        const statusClass = isDone ? 'status-done' : item.is_backlog ? 'status-backlog' : 'status-ongoing';
                        const statusText = isDone ? 'Completed' : item.is_backlog ? 'Backlog' : 'Ongoing';
                        
                        return (
                          <tr key={item.id} className={`table-row ${isDone ? 'row-done' : ''} ${item.is_backlog ? 'row-backlog' : ''}`}>
                            <td>
                              <select className="priority-select"
                                value={item.priority ?? item.order.priority ?? 2}
                                disabled={shiftStatus !== 'active'}
                                onChange={(e) => handlePriorityChange(item.order.id, e.target.value)}>
                                <option value={0}>🔴 Emg</option>
                                <option value={1}>🟡 High</option>
                                <option value={2}>🟢 Nrml</option>
                              </select>
                            </td>
                            <td>
                              <span className="machine-badge">{item.machine_name}</span>
                            </td>
                            <td className="mono">{item.order.wo_no}</td>
                            <td className="mono bold">{item.order.dwg_no}</td>
                            <td>{item.order.customer_name}</td>
                            <td className="num">{item.target_qty} <span style={{fontSize:'0.75rem', opacity:0.7, marginLeft:'4px'}}>{getUnit(item.machine_name)}</span></td>
                            <td className="num bold">{item.completed_qty} <span style={{fontSize:'0.75rem', opacity:0.7, marginLeft:'4px'}}>{getUnit(item.machine_name)}</span></td>
                            <td>
                              <div className="slider-cell">
                                <input
                                  type="range"
                                  className="completion-slider"
                                  min="0"
                                  max={item.target_qty}
                                  value={item.completed_qty}
                                  disabled={shiftStatus !== 'active'}
                                  onChange={(e) => handleSliderChange(item.id, parseInt(e.target.value), item.target_qty)}
                                  style={{ '--progress': `${pct}%` }}
                                />
                                <span className={`slider-pct ${isDone ? 'pct-done' : ''}`}>{pct}%</span>
                              </div>
                            </td>
                            <td>
                              <span className={`status-badge ${statusClass}`}>{statusText}</span>
                            </td>
                          </tr>
                        );
                      })}
                      {filteredSchedules.length === 0 && (
                        <tr><td colSpan="9" className="empty-row">No jobs scheduled for this date</td></tr>
                      )}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* ═══════════════════════════════════════════════════════ */}
      {/* SCANNER TAB                                            */}
      {/* ═══════════════════════════════════════════════════════ */}
      {activeTab === 'scanner' && (
        <ScannerDemo triggerDashboardRefresh={fetchDashboard} />
      )}

      {/* ═══════════════════════════════════════════════════════ */}
      {/* HISTORY TAB                                            */}
      {/* ═══════════════════════════════════════════════════════ */}
      {activeTab === 'history' && (
        <div className="history-content">
          <div className="card">
            <div className="table-header">
              <h2 className="card-title"><Clock size={20}/> Shift History</h2>
              <div className="table-controls">
                <input type="date" className="input date-input" value={historyDate}
                  onChange={(e) => setHistoryDate(e.target.value)} />
                <button className="btn btn-outline" onClick={() => { setHistoryDate(''); fetchHistory(null); }}>
                  Show All
                </button>
              </div>
            </div>

            {history.length > 0 ? (
              <div className="live-table-wrapper">
                <table className="live-table">
                  <thead>
                    <tr>
                      <th>Date</th>
                      <th>WO NO</th>
                      <th>DWG NO</th>
                      <th>Customer</th>
                      <th>Machine</th>
                      <th>Target</th>
                      <th>Completed</th>
                      <th>Status</th>
                      <th>Stage</th>
                    </tr>
                  </thead>
                  <tbody>
                    {history.map(log => (
                      <tr key={log.id} className={`table-row ${log.status === 'Completed' ? 'row-done' : ''}`}>
                        <td className="mono">{log.log_date}</td>
                        <td className="mono">{log.wo_no}</td>
                        <td className="mono bold">{log.dwg_no}</td>
                        <td>{log.customer_name}</td>
                        <td><span className="machine-badge">{log.machine_name}</span></td>
                        <td className="num">{log.target_qty}</td>
                        <td className="num bold">{log.completed_qty}</td>
                        <td>
                          <span className={`status-badge ${
                            log.status === 'Completed' ? 'status-done' :
                            log.status === 'Backlog' ? 'status-backlog' : 'status-ongoing'
                          }`}>{log.status}</span>
                        </td>
                        <td>
                          <span className={`stage-badge ${log.current_stage === 'All Done' ? 'stage-done' : ''}`}>
                            {log.current_stage}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <div className="empty-state">
                <Clock size={48} className="empty-icon"/>
                <p>No history data yet. Complete a shift to see records here.</p>
                <p className="text-sm">Data is cached locally for instant access.</p>
              </div>
            )}
          </div>
        </div>
      )}

      {/* ═══════════════════════════════════════════════════════ */}
      {/* EXPORT TAB                                             */}
      {/* ═══════════════════════════════════════════════════════ */}
      {activeTab === 'export' && (
        <div className="export-content">
          <div className="export-grid">
            <div className="card export-card">
              <div className="export-card-icon accent-bg">
                <FileSpreadsheet size={32} className="accent"/>
              </div>
              <h3>Daily Report</h3>
              <p className="text-sm">Download today's schedule, done items, and backlogs as a multi-sheet Excel file.</p>
              <input type="date" className="input date-input" value={targetDate}
                onChange={(e) => setTargetDate(e.target.value)} style={{margin: '1rem 0'}}/>
              <button className="btn" onClick={handleExportDaily}>
                <Download size={16}/> Export Daily Report
              </button>
            </div>
            <div className="card export-card">
              <div className="export-card-icon success-bg">
                <TrendingUp size={32} className="success"/>
              </div>
              <h3>Full Production History</h3>
              <p className="text-sm">Export ALL historical work data as a growing Excel file with per-date sheets.</p>
              <div style={{flex: 1}}></div>
              <button className="btn btn-success" onClick={handleExportHistory}>
                <Download size={16}/> Export Complete History
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Floating Live Machine Status Panel */}
      <FloatingMachineStatus
        machineStats={machineStats}
        shiftStatus={shiftStatus}
        targetDate={targetDate}
      />
      {/* Floating Demo Reset Button */}
      <button 
        onClick={handleReset}
        title="Hard Reset for Demo"
        className="demo-reset-btn"
        style={{
          position: 'fixed',
          bottom: '20px',
          left: '20px',
          zIndex: 1000,
          background: 'rgba(239, 68, 68, 0.15)',
          color: '#fca5a5',
          border: '1px solid rgba(239, 68, 68, 0.3)',
          borderRadius: '12px',
          padding: '0.6rem 1rem',
          display: 'flex',
          alignItems: 'center',
          gap: '0.5rem',
          boxShadow: '0 4px 20px rgba(0, 0, 0, 0.3)',
          cursor: 'pointer',
          fontWeight: '600',
          fontSize: '0.8rem',
          backdropFilter: 'blur(10px)',
          transition: 'all 0.2s ease'
        }}
        onMouseEnter={(e) => { e.currentTarget.style.background = 'rgba(239, 68, 68, 0.25)'; }}
        onMouseLeave={(e) => { e.currentTarget.style.background = 'rgba(239, 68, 68, 0.15)'; }}
      >
        <RotateCcw size={16} /> Demo Reset
      </button>
    </div>
  );
}

export default App;
