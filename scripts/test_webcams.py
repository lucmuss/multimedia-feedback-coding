
import cv2
import sys
import time
import threading

def test_camera(index):
    print(f"\n--- Teste Kamera Index {index} ---")
    
    # Nutze DShow auf Windows (wie in der App)
    backend = cv2.CAP_DSHOW if sys.platform == "win32" else cv2.CAP_ANY
    backend_name = "CAP_DSHOW" if sys.platform == "win32" else "CAP_ANY"
    
    print(f"Versuche zu öffnen mit {backend_name}...")
    
    start_time = time.time()
    cap = cv2.VideoCapture(index, backend)
    
    if cap is None:
        print(f"[!] Fehler: VideoCapture({index}) ist None")
        return False
        
    if not cap.isOpened():
        print(f"[!] Fehler: Kamera Index {index} konnte nicht geöffnet werden.")
        cap.release()
        return False
        
    duration = time.time() - start_time
    print(f"[OK] Kamera geöffnet in {duration:.2f} Sekunden.")
    
    # Teste verschiedene Auflösungen
    resolutions = [
        ("640x480", 640, 480),
        ("1280x720", 1280, 720),
        ("1920x1080", 1920, 1080)
    ]
    
    for name, w, h in resolutions:
        print(f"Teste Auflösung {name}...")
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, w)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, h)
        
        # Kurze Pause für Treiber
        time.sleep(0.3)
        
        ret, frame = cap.read()
        if ret and frame is not None:
            actual_h, actual_w = frame.shape[:2]
            print(f"  -> [OK] Gelesen: {actual_w}x{actual_h}")
        else:
            print(f"  -> [!] Fehler bei {name}")
        
    cap.release()
    print(f"Kamera Index {index} freigegeben.")
    return True

def scan_all_cameras(limit=5):
    print(f"Scanne Kamera-Indizes 0 bis {limit}...")
    found_any = False
    for i in range(limit + 1):
        try:
            if test_camera(i):
                found_any = True
        except Exception as e:
            print(f"[ERROR] Exception bei Index {i}: {e}")
            
    if not found_any:
        print("\n[!] Keine Kameras gefunden.")
    else:
        print("\nScan abgeschlossen.")

if __name__ == "__main__":
    print("OpenCV Version:", cv2.__version__)
    print("Plattform:", sys.platform)
    scan_all_cameras()
