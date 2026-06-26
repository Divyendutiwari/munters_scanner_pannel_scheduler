import React, { useEffect, useState, useRef, useCallback } from 'react';
import { Html5QrcodeScanner, Html5QrcodeScanType } from 'html5-qrcode';
import { ScanLine, CheckCircle2, AlertCircle, Camera, Keyboard, Video, VideoOff } from 'lucide-react';
import axios from 'axios';

const API_URL = 'http://localhost:8000';

const MACHINES = [
  { name: 'Auto Fold', color: '#6366f1', unit: 'sheets' },
  { name: 'Turret Punch', color: '#8b5cf6', unit: 'punches' },
  { name: 'Bending', color: '#3b82f6', unit: 'strokes' },
  { name: 'Gasketing', color: '#10b981', unit: 'panels' },
  { name: 'PUF', color: '#f59e0b', unit: 'puffings' },
];

const ScannerBox = ({ machine, onScanSuccess, activeCameraId, onRequestCamera }) => {
  const [status, setStatus] = useState(null);
  const [manualInput, setManualInput] = useState('');
  const [scanCount, setScanCount] = useState(0);
  const scannerRef = useRef(null);
  const isPausedRef = useRef(false);
  const containerId = `qr-reader-${machine.name.replace(/\s+/g, '-')}`;

  // Is THIS machine's camera currently active?
  const isCameraActive = activeCameraId === machine.name;

  const handleScanResult = useCallback(async (barcode) => {
    try {
      const res = await axios.post(`${API_URL}/schedule/scan/`, {
        barcode: barcode,
        machine_name: machine.name
      });
      
      setStatus({ type: 'success', msg: `${res.data.message} (${barcode})` });
      setScanCount(prev => prev + 1);
      if (onScanSuccess) onScanSuccess();
      
    } catch (err) {
      const detail = err.response?.data?.detail || err.message;
      setStatus({ type: 'error', msg: detail });
    }

    // Clear status after 3 seconds
    setTimeout(() => setStatus(null), 3000);
  }, [machine.name, onScanSuccess]);

  // Camera scanner init — ONLY when this machine is the active camera
  useEffect(() => {
    if (!isCameraActive) {
      // Clean up scanner if it exists and camera was deactivated
      if (scannerRef.current) {
        scannerRef.current.clear().catch(() => {});
        scannerRef.current = null;
      }
      return;
    }

    let scanner = null;
    // Small delay to ensure DOM element exists
    const timer = setTimeout(() => {
      try {
        scanner = new Html5QrcodeScanner(
          containerId,
          {
            fps: 10,
            qrbox: { width: 180, height: 180 },
            rememberLastUsedCamera: true,
            supportedScanTypes: [Html5QrcodeScanType.SCAN_TYPE_CAMERA],
            showTorchButtonIfSupported: true,
          },
          false
        );
        scannerRef.current = scanner;

        scanner.render(
          (decodedText) => {
            if (isPausedRef.current) return;
            isPausedRef.current = true;

            handleScanResult(decodedText);

            // Allow next scan after 3s
            setTimeout(() => { isPausedRef.current = false; }, 3000);
          },
          () => {} // Ignore scan failures (no code visible)
        );
      } catch (err) {
        console.warn(`Scanner init failed for ${machine.name}:`, err);
      }
    }, 200);

    return () => {
      clearTimeout(timer);
      if (scanner) {
        scanner.clear().catch(() => {});
      }
      scannerRef.current = null;
    };
  }, [containerId, handleScanResult, machine.name, isCameraActive]);

  const handleManualSubmit = (e) => {
    e.preventDefault();
    if (!manualInput.trim()) return;
    handleScanResult(manualInput.trim());
    setManualInput('');
  };

  const handleToggleCamera = () => {
    if (isCameraActive) {
      // Turn OFF this machine's camera
      onRequestCamera(null);
    } else {
      // Turn ON this machine's camera (will turn off any other)
      onRequestCamera(machine.name);
    }
  };

  return (
    <div className={`scanner-box ${isCameraActive ? 'scanner-camera-active' : ''}`} style={{ '--machine-color': machine.color }}>
      <div className="scanner-header" style={{ borderLeftColor: machine.color }}>
        <div className="scanner-header-icon" style={{ background: `${machine.color}22`, color: machine.color }}>
          <ScanLine size={18} />
        </div>
        <div className="scanner-header-info">
          <h3>{machine.name}</h3>
          <span className="scanner-unit-hint">{machine.unit}</span>
        </div>
        <div className="scanner-header-right">
          {scanCount > 0 && (
            <span className="scan-counter">{scanCount} scanned</span>
          )}
          <button
            className={`camera-toggle-btn ${isCameraActive ? 'camera-on' : ''}`}
            onClick={handleToggleCamera}
            title={isCameraActive ? 'Turn off camera' : 'Activate camera for this machine'}
          >
            {isCameraActive ? <VideoOff size={16} /> : <Video size={16} />}
            <span>{isCameraActive ? 'Stop' : 'Camera'}</span>
          </button>
        </div>
      </div>
      
      {isCameraActive ? (
        /* Camera mode — only rendered when THIS machine's camera is active */
        <div id={containerId} className="scanner-viewport"></div>
      ) : (
        /* Manual input mode — default for all machines */
        <div className="scanner-viewport manual-mode">
          <form onSubmit={handleManualSubmit} className="manual-form">
            <div className="manual-icon">
              <Keyboard size={32} />
            </div>
            <p>Type or paste barcode value</p>
            <div className="manual-input-row">
              <input
                type="text"
                className="input manual-barcode-input"
                placeholder="e.g. DEMO-01-01-IN"
                value={manualInput}
                onChange={(e) => setManualInput(e.target.value)}
                autoFocus={false}
              />
              <button type="submit" className="btn btn-scan-submit">
                <ScanLine size={16} /> Scan
              </button>
            </div>
          </form>
        </div>
      )}
      
      <div className="scanner-status">
        {status ? (
          <div className={`status-msg ${status.type}`}>
            {status.type === 'success' ? <CheckCircle2 size={16} /> : <AlertCircle size={16} />}
            <span>{status.msg}</span>
          </div>
        ) : (
          <div className="status-msg neutral">
            <span className="pulse-dot" style={{ background: machine.color }}></span>
            {isCameraActive ? '📷 Camera active — point at barcode...' : 'Ready — type barcode or activate camera'}
          </div>
        )}
      </div>
    </div>
  );
};

const ScannerDemo = ({ triggerDashboardRefresh }) => {
  // Only ONE machine can have its camera active at a time
  const [activeCameraId, setActiveCameraId] = useState(null);

  return (
    <div className="scanner-demo-container fade-in">
      <div className="demo-header">
        <h2><ScanLine size={24}/> Barcode Scanner — Automated Machine Line</h2>
        <p>
          Each box represents a physical scanner station at a machine.
          Use <strong>Camera</strong> button to activate scanning on ONE machine at a time,
          or type the barcode value manually in any machine's input field.
        </p>
        {activeCameraId && (
          <div className="camera-active-indicator">
            📷 Camera active on: <strong>{activeCameraId}</strong>
          </div>
        )}
      </div>
      
      <div className="scanners-grid">
        {MACHINES.map(machine => (
          <ScannerBox 
            key={machine.name} 
            machine={machine} 
            onScanSuccess={triggerDashboardRefresh}
            activeCameraId={activeCameraId}
            onRequestCamera={setActiveCameraId}
          />
        ))}
      </div>
    </div>
  );
};

export default ScannerDemo;
