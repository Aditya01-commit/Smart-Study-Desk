# Smart Study Desk Dashboard

A Streamlit dashboard for the  IoT Smart Study Desk prototype.

## Features
- Demo mode with automatically changing sensor readings (no Arduino needed)
- Arduino USB serial input
- Normal / Too close / Sustained close / Away state classification
- Study timer, distance trend, alerts and indicative Focus Score
- CSV download and local logging

## 1. Install Python
Use Python 3.10 or newer.

## 2. Open a terminal in this folder
Windows PowerShell:
```powershell
cd path\to\smart_study_desk_dashboard
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
streamlit run app.py
```

Ubuntu / macOS:
```bash
cd smart_study_desk_dashboard
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

The dashboard opens in your browser (usually http://localhost:8501).

## 3. Try Demo Mode
- Select **Demo mode** in the sidebar.
- Click **Start session**.
- Watch the distance, state, graph, alerts and Focus Score update.
- Click **End session** when finished.
- Download the readings CSV from the dashboard.

## 4. Connect Arduino Uno R3
1. Wire the components as shown below.
2. Open `arduino/smart_study_desk.ino` in Arduino IDE.
3. Select **Arduino Uno** and the correct COM port, then upload the sketch.
4. Close Arduino IDE Serial Monitor (only one program can normally use the serial port).
5. In the dashboard, choose **Arduino USB**, select the Arduino COM port, and click **Connect**.
6. Press the physical desk button to start/stop a session. You can also use the dashboard session controls.

### Serial format
The Arduino sends one line every 500 ms:
`distance_cm,session_active`
Example: `42.5,1`

## 5. Wiring (Arduino Uno R3)
| Component | Arduino pin |
|---|---|
| HC-SR04 TRIG | D9 |
| HC-SR04 ECHO | D10 |
| Green LED (through 220–330Ω resistor) | D5 |
| Red LED (through 220–330Ω resistor) | D6 |
| Active buzzer (+) | D7 |
| Push button | D2 and GND |
| All component GND | GND |
| HC-SR04 VCC | 5V |

Connect LED cathodes to GND (each LED must have its own resistor). Use a 5V active buzzer. Check the buzzer current rating; use a transistor driver if it exceeds the Arduino pin's safe current.

## Threshold calibration
The default dashboard limits are 30 cm for too-close and 120 cm for away. Change these in the sidebar after testing the sensor in the final enclosure and desk position. The Arduino sketch has its own simple 30 cm alert threshold; edit its constants if you want the hardware alerts to match your dashboard settings.

## Focus Score note
The Focus Score is a simple project-defined indicator based on the proportion of readings classified as too close/sustained close and away. It is **not** a scientific measurement of attention, posture, sleep or health.

## Troubleshooting
- **No COM port:** install the Arduino USB driver and reconnect the board.
- **Port busy:** close Arduino IDE Serial Monitor and any other serial application.
- **Permission denied (Linux):** add your user to the `dialout` group, log out/in, then reconnect.
- **Dashboard doesn't update:** install `requirements.txt`, confirm the correct port and baud rate (9600), and press Connect.
- **Demo mode:** always works without hardware and is suitable for a software demonstration.
