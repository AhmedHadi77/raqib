"""Step 5 - camera snapshot + microphone + speaker.   python -m hwtest.test_camera_audio
Saves test_snapshot.jpg and test_audio.wav in the edge folder.
"""
import time
import wave

from robot.imaging import save_jpeg

from . import real_cfg


def main():
    cfg = real_cfg()
    from robot.audio_analyzer import AudioAnalyzer
    from robot.hal.real import create_real_hardware

    hw = create_real_hardware(cfg)
    try:
        frame = hw.camera.capture()
        save_jpeg("test_snapshot.jpg", frame)
        print("Saved test_snapshot.jpg", frame.shape)

        print("Recording 3 s of audio...")
        sr = int(cfg["audio"]["sample_rate"])
        samples = hw.microphone.record(3.0, sr)
        with wave.open("test_audio.wav", "wb") as w:
            w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr); w.writeframes(samples.tobytes())
        print("Saved test_audio.wav")
        print("Classifier:", AudioAnalyzer(hw, cfg).listen(1.0))

        hw.speaker.say("Speaker test. Hello from the inspection robot.")
        time.sleep(3)
    finally:
        hw.close()


if __name__ == "__main__":
    main()
