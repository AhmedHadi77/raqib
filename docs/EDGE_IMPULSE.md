# Training the campus audio model (Edge Impulse)

Until this model exists, the robot uses a built-in feature-based classifier (`audio_analyzer.py`,
risk R7 fallback), so the system already works.

## 1. Collect data (on the Pi with the USB mic)

```
edge-impulse-linux --disable-camera          # log in, create project "campus-audio"
```

In Edge Impulse Studio → **Data acquisition**, record 1-second samples at **16 kHz**, at least 5 minutes per class:

| Label | Record |
|---|---|
| `quiet_room` | empty classrooms and labs, doors closed |
| `ac_fan` | split-unit AC, ceiling fans, lab exhaust fans (several rooms) |
| `crowd` | lectures, students talking, a corridor between classes |
| `alarm` | fire alarm test recordings, a dripping or running water leak (play back recordings at safe volume) |

Keep ~20 % as a **test set**. It gives the final accuracy numbers in Table 4 and must not be used for tuning.

## 2. Impulse

- Time series, window 1000 ms, stride 500 ms, 16000 Hz
- Processing block: **MFE** (or MFCC)
- Learning block: **Classification** (1D conv), with data augmentation on (noise, time masking)
- Target: > 85 % accuracy (5-fold cross-validation in the "Retrain" / EON Tuner)

## 3. Deploy to the robot

```
cd ~/edge
edge-impulse-linux-runner --download models/campus-audio.eim
sudo systemctl restart inspection-robot
```

The log should show `Edge Impulse model loaded`. If your label names differ, map them in
`config.yaml → audio.label_map` (e.g. `aircon: ac_fan`).

## 4. Calibrate loudness

Hold a phone SPL-meter app next to the mic in a running AC room. Adjust `audio.db_calibration_offset`
until the robot's dB value matches.
