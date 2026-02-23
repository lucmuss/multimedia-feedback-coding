import cv2
import sounddevice as sd
import numpy as np
import time

def test_hardware():
    print("Testing Audio (sounddevice)...")
    try:
        devices = sd.query_devices()
        print(f"Found {len(devices)} audio devices.")
        for i, d in enumerate(devices):
            if d['max_input_channels'] > 0:
                print(f"  [Input {i}] {d['name']}")
    except Exception as e:
        print(f"Audio error: {e}")

    print("\nTesting Webcams (cv2)...")
    for i in range(5):
        print(f"Testing camera index {i}...")
        try:
            # Test directshow first
            started = time.time()
            cap = cv2.VideoCapture(i, cv2.CAP_DSHOW)
            if cap.isOpened():
                ok, frame = cap.read()
                if ok:
                    print(f"  Camera {i} works via DSHOW. Resolution: {frame.shape[1]}x{frame.shape[0]}")
                else:
                    print(f"  Camera {i} opened via DSHOW but failed to read frame.")
            else:
                elapsed = time.time() - started
                print(f"  Camera {i} failed DSHOW open (took {elapsed:.2f}s). Trying MSMF fallback...")
                cap = cv2.VideoCapture(i)
                if cap.isOpened():
                    ok, frame = cap.read()
                    if ok:
                         print(f"  Camera {i} works via MSMF fallback. Resolution: {frame.shape[1]}x{frame.shape[0]}")
                    else:
                         print(f"  Camera {i} opened via MSMF but failed to read frame.")
                else:
                    print(f"  Camera {i} not available.")
            if cap is not None:
                cap.release()
        except Exception as e:
            print(f"  Error on camera {i}: {e}")

if __name__ == '__main__':
    test_hardware()
