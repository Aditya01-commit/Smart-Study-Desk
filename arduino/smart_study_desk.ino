// Smart Study Desk - Arduino Uno R3 + HC-SR04
// Serial protocol to the Python dashboard: distance_cm,session_active
// Example: 42.5,1
// Button toggles the study session.

const int TRIG_PIN = 9;
const int ECHO_PIN = 10;
const int GREEN_LED = 5;
const int RED_LED = 6;
const int BUZZER_PIN = 7;
const int BUTTON_PIN = 2;

const float TOO_CLOSE_CM = 30.0;
const float AWAY_CM = 120.0;

bool sessionActive = false;
bool lastButtonReading = HIGH;
bool buttonState = HIGH;
unsigned long lastDebounceTime = 0;
const unsigned long debounceDelay = 45;
unsigned long lastSample = 0;

float readDistanceCm() {
  digitalWrite(TRIG_PIN, LOW);
  delayMicroseconds(3);
  digitalWrite(TRIG_PIN, HIGH);
  delayMicroseconds(10);
  digitalWrite(TRIG_PIN, LOW);

  unsigned long duration = pulseIn(ECHO_PIN, HIGH, 30000UL);
  if (duration == 0) return 250.0;
  return duration * 0.0343 / 2.0;
}

void setup() {
  pinMode(TRIG_PIN, OUTPUT);
  pinMode(ECHO_PIN, INPUT);
  pinMode(GREEN_LED, OUTPUT);
  pinMode(RED_LED, OUTPUT);
  pinMode(BUZZER_PIN, OUTPUT);
  pinMode(BUTTON_PIN, INPUT_PULLUP);
  Serial.begin(9600);
}

void loop() {
  bool reading = digitalRead(BUTTON_PIN);
  if (reading != lastButtonReading) lastDebounceTime = millis();

  if ((millis() - lastDebounceTime) > debounceDelay) {
    if (reading != buttonState) {
      buttonState = reading;
      if (buttonState == LOW) sessionActive = !sessionActive;
    }
  }
  lastButtonReading = reading;

  if (millis() - lastSample >= 500) {
    lastSample = millis();
    float distance = readDistanceCm();

    if (sessionActive) {
      if (distance < TOO_CLOSE_CM) {
        digitalWrite(RED_LED, HIGH);
        digitalWrite(GREEN_LED, LOW);
        tone(BUZZER_PIN, 1800, 120);
      } else if (distance >= AWAY_CM) {
        digitalWrite(RED_LED, HIGH);
        digitalWrite(GREEN_LED, LOW);
        noTone(BUZZER_PIN);
      } else {
        digitalWrite(RED_LED, LOW);
        digitalWrite(GREEN_LED, HIGH);
        noTone(BUZZER_PIN);
      }
    } else {
      digitalWrite(RED_LED, LOW);
      digitalWrite(GREEN_LED, LOW);
      noTone(BUZZER_PIN);
    }

    Serial.print(distance, 1);
    Serial.print(",");
    Serial.println(sessionActive ? 1 : 0);
  }
}
