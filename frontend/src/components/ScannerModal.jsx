import { useEffect, useRef, useState } from 'react'
import { Html5Qrcode } from 'html5-qrcode'

export default function ScannerModal({ onScan, onClose }) {
  const regionId = useRef(`qr-scanner-${Math.random().toString(36).slice(2, 9)}`)
  const scannerRef = useRef(null)
  const [error, setError] = useState('')
  const onScanRef = useRef(onScan)
  onScanRef.current = onScan

  useEffect(() => {
    let active = true
    const scanner = new Html5Qrcode(regionId.current)
    scannerRef.current = scanner

    async function startScanner() {
      try {
        await scanner.start(
          { facingMode: 'environment' },
          {
            fps: 10,
            qrbox: { width: 260, height: 120 },
            aspectRatio: 1.3,
            experimentalFeatures: {
              useBarCodeDetectorIfSupported: true,
            },
          },
          async (decodedText) => {
            if (!active) return
            try {
              if (scanner.isScanning) {
                await scanner.stop()
                await scanner.clear()
              }
            } finally {
              onScanRef.current(decodedText)
            }
          },
          () => {}
        )
        if (!active && scanner.isScanning) {
          await scanner.stop().catch(() => {})
        }
      } catch (e) {
        if (!active) return
        const msg = String(e?.message || e)
        if (/NotAllowed|NotFoundError|permission/i.test(msg)) {
          setError('Camera permission denied or no camera found. Check browser permissions and try again.')
        } else if (/https|secure/i.test(msg)) {
          setError('Camera scanning requires a secure (HTTPS) or localhost connection.')
        } else {
          setError(`Could not start camera: ${msg}`)
        }
      }
    }

    startScanner()

    return () => {
      active = false
      const sc = scannerRef.current
      if (sc && sc.isScanning) {
        sc.stop().then(() => sc.clear()).catch(() => {})
      }
    }
  }, [])

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h3>Scan Barcode / QR Code</h3>
          <button className="btn btn-secondary btn-sm" onClick={onClose}>Close</button>
        </div>
        <div className="modal-body">
          <div id={regionId.current} className="scanner-region" />
          {error && <div className="alert alert-error">{error}</div>}
          <p className="modal-hint">Point your camera at a product barcode or QR code. It is detected automatically.</p>
        </div>
      </div>
    </div>
  )
}