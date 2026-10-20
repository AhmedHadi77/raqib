// =====================================================================================
//  Raqib robot firmware 3.0 - Seeed Studio XIAO ESP32S3 Sense
// =====================================================================================
//  The ESP32 is the robot's body: it drives the two motors, reads the sensors and
//  serves the camera and the microphone over Wi-Fi. The robot program on your PC is
//  the brain: it plans routes, runs the AI and talks to the phone app.
//
//  Safety lives HERE, so it works even if Wi-Fi drops:
//    - the motors stop 0.6 s after the last drive command (dead-man), and
//    - the robot refuses to drive forward when something is closer than 15 cm.
//
//  Wiring (XIAO pin -> part):
//    D0 (GPIO1) -> DRV8833 AIN1   left motor        D4 (GPIO5) -> SDA  MPU6050 + AHT20/BMP280
//    D1 (GPIO2) -> DRV8833 AIN2   left motor        D5 (GPIO6) -> SCL  MPU6050 + AHT20/BMP280
//    D2 (GPIO3) -> DRV8833 BIN1   right motor       D6 (GPIO43) -> HC-SR04P TRIG
//    D3 (GPIO4) -> DRV8833 BIN2   right motor       D7 (GPIO44) -> HC-SR04P ECHO
//    3V3 -> sensors VCC     GND -> sensors GND and DRV8833 GND (common ground with the motor battery)
//    Camera and microphone are built into the Sense board.
//
//  Easiest: flash the ready-made raqib_esp32_xiao.bin from Chrome (see esp32/README.md), then join the
//  robot's own Wi-Fi "Raqib-Robot" and type your hotspot on http://192.168.4.1.
//  Arduino IDE: board "XIAO_ESP32S3", Tools -> PSRAM -> "OPI PSRAM" (wifi_config.h is optional).
//
//  HTTP API (used by the PC program; also try it in a browser):
//    http://raqib.local/              test page: live picture, sensors, drive buttons
//    /status                          sensors + motors as JSON
//    /drive?l=0.5&r=0.5               wheel power -1..1 (repeat at least every 0.6 s)
//    /stop                            stop now
//    /config?stop_cm=15&max_duty=0.7&ramp=4&deadman_ms=600&inv_l=0&inv_r=0
//    /turn?deg=90&power=0.5           turn on the spot with the gyro (positive = left)
//    /reset_yaw                       heading back to 0
//    /capture                         one JPEG photo
//    http://raqib.local:81/stream     live MJPEG video
//    http://raqib.local:82/audio?ms=1000   microphone recording as WAV (16 kHz, mono)
// =====================================================================================
#include <Arduino.h>
#include <ESPmDNS.h>
#include <ESP_I2S.h>
#include <WiFi.h>
#include <WiFiUdp.h>
#include <Preferences.h>
#include <Wire.h>
#include <math.h>

#include "esp_camera.h"
#include "esp_http_server.h"
#include "wifi_config.h"

#define FW_VERSION "3.0.0"

// ------------------------------------------------------------------ pins
static const int PIN_AIN1 = 1, PIN_AIN2 = 2;    // D0, D1: left motor
static const int PIN_BIN1 = 3, PIN_BIN2 = 4;    // D2, D3: right motor
static const int PIN_SDA = 5, PIN_SCL = 6;      // D4, D5
static const int PIN_TRIG = 43, PIN_ECHO = 44;  // D6, D7
static const int PIN_LED = 21;                  // orange user LED, on when LOW
static const int PIN_MIC_CLK = 42, PIN_MIC_DATA = 41;
static const uint16_t BEACON_PORT = 37021;

// ------------------------------------------------------------------ settings (the PC sends its own at start-up)
struct Settings {
  float stop_cm = 15.0f;      // refuse to drive forward below this distance
  float max_duty = 0.70f;     // 2 x 18650 = 8.4 V; TT motors are 3-6 V, so full power = 70 % PWM
  float ramp_per_s = 4.0f;    // soft start: 0 -> full in 0.25 s (stopping is immediate)
  uint32_t deadman_ms = 600;  // no drive command for this long = stop
  bool inv_l = false, inv_r = false;
  float min_power = 0.30f;    // lowest power that still turns the wheels (the PC sends the calibrated value)
} cfg;

// ------------------------------------------------------------------ shared state
static volatile float tgt_l = 0, tgt_r = 0, out_l = 0, out_r = 0;
static volatile uint32_t last_cmd_ms = 0;
static volatile bool blocked = false;
// turning on the spot is done HERE with the gyro (200 readings a second): exact, even if Wi-Fi is slow
static volatile bool turn_active = false;
static volatile float turn_target = 0, turn_power = 0.5f;
static volatile uint32_t turn_deadline = 0;
static volatile int turn_result = 0;  // 0 idle, 1 turning, 2 done, 3 timeout, 4 stopped
static volatile float yaw_total = 0;  // heading without wrapping at +-180 (for turns)
static volatile float dist_cm = 400;
static volatile bool us_ok = false;
static volatile uint32_t us_seen_ms = 0;
static volatile float yaw = 0, pitch = 0, roll = 0, gz = 0, ax = 0, ay = 0, az = 1;
static volatile bool imu_ok = false;
static volatile float temp_c = NAN, rh_pct = NAN, press_hpa = NAN;
static volatile bool aht_ok = false, bmp_ok = false;
static bool cam_ok = false, mic_ok = false, ap_mode = false;
static SemaphoreHandle_t i2c_lock, mic_lock;
static I2SClass i2s;
static WiFiUDP udp;
static Preferences prefs;
static String wifi_ssid, wifi_pass;

// ================================================================== I2C helpers
static bool i2cWrite(uint8_t addr, uint8_t reg, uint8_t val) {
  Wire.beginTransmission(addr);
  Wire.write(reg);
  Wire.write(val);
  return Wire.endTransmission() == 0;
}

static bool i2cRead(uint8_t addr, uint8_t reg, uint8_t *buf, size_t n) {
  Wire.beginTransmission(addr);
  Wire.write(reg);
  if (Wire.endTransmission(false) != 0) return false;
  if (Wire.requestFrom((uint16_t)addr, n) != n) return false;
  for (size_t i = 0; i < n; i++) buf[i] = Wire.read();
  return true;
}

// ================================================================== motors (DRV8833)
static void motorWrite(int in1, int in2, float v) {
  const uint32_t FULL = 1023;  // 10-bit PWM
  if (fabsf(v) < 0.001f) {     // both high = brake: the wheel stops quickly
    ledcWrite(in1, FULL);
    ledcWrite(in2, FULL);
    return;
  }
  uint32_t duty = (uint32_t)(fminf(fabsf(v), 1.0f) * cfg.max_duty * FULL);
  if (v > 0) {
    ledcWrite(in1, duty);
    ledcWrite(in2, 0);
  } else {
    ledcWrite(in1, 0);
    ledcWrite(in2, duty);
  }
}

// Soft start: stopping, slowing down and reversing to zero are immediate; speeding up is limited.
static float stepTo(float out, float target, float max_up) {
  if (target == 0.0f || out * target < 0.0f) out = 0.0f;
  if (fabsf(target) <= fabsf(out)) return target;
  return out + copysignf(fminf(max_up, fabsf(target) - fabsf(out)), target);
}

static void controlTask(void *) {
  for (;;) {
    uint32_t now = millis();
    float tl = tgt_l, tr = tgt_r;
    if (turn_active) {
      float err = turn_target - yaw_total - gz * 0.015f;  // look 15 ms ahead: stop just before the target
      if (fabsf(err) < 1.5f) {
        turn_active = false;
        turn_result = 2;
      } else if ((int32_t)(now - turn_deadline) > 0 || !imu_ok) {
        turn_active = false;
        turn_result = 3;
      } else {  // slow down for the last 45 degrees, never below the power that still moves the wheels
        float p = fmaxf(cfg.min_power, fminf(turn_power, turn_power * fabsf(err) / 45.0f));
        float d = err > 0 ? 1.0f : -1.0f;  // positive = turn left
        tl = -d * p;
        tr = d * p;
        last_cmd_ms = now;
      }
      if (!turn_active) tl = tr = 0;
    } else if (now - last_cmd_ms > cfg.deadman_ms) {  // lost the PC (or Wi-Fi): stop
      tl = tr = 0;
      tgt_l = 0;
      tgt_r = 0;
    }
    bool forward = (tl + tr) > 0.05f;
    // no working distance sensor = no driving forward; something too close = no driving forward
    bool b = forward && (!us_ok || dist_cm < cfg.stop_cm);
    if (b) tl = tr = 0;
    blocked = b;
    float up = cfg.ramp_per_s * 0.01f;
    out_l = stepTo(out_l, tl, up);
    out_r = stepTo(out_r, tr, up);
    motorWrite(PIN_AIN1, PIN_AIN2, cfg.inv_l ? -out_l : out_l);
    motorWrite(PIN_BIN1, PIN_BIN2, cfg.inv_r ? -out_r : out_r);
    vTaskDelay(pdMS_TO_TICKS(10));
  }
}

// ================================================================== MPU6050 (heading)
static float gz_bias = 0;

static bool imuInit() {
  if (!i2cWrite(0x68, 0x6B, 0x00)) return false;  // wake up (clones answer too: no WHO_AM_I check)
  delay(50);
  i2cWrite(0x68, 0x1A, 0x03);  // 44 Hz low-pass filter
  i2cWrite(0x68, 0x1B, 0x08);  // gyro +-500 deg/s (65.5 per deg/s)
  i2cWrite(0x68, 0x1C, 0x00);  // accel +-2 g
  return true;
}

static bool imuRaw(float &gzr, float &axr, float &ayr, float &azr) {
  uint8_t b[14];
  if (!i2cRead(0x68, 0x3B, b, 14)) return false;
  axr = (int16_t)(b[0] << 8 | b[1]) / 16384.0f;
  ayr = (int16_t)(b[2] << 8 | b[3]) / 16384.0f;
  azr = (int16_t)(b[4] << 8 | b[5]) / 16384.0f;
  gzr = (int16_t)(b[12] << 8 | b[13]) / 65.5f;
  return true;
}

static void imuTask(void *) {
  float g, x, y, z;
  for (;;) {  // (re)connect, then measure the gyro's resting offset for 1.5 s (keep the robot still)
    xSemaphoreTake(i2c_lock, portMAX_DELAY);
    bool ok = imuInit();
    xSemaphoreGive(i2c_lock);
    if (!ok) {
      imu_ok = false;
      vTaskDelay(pdMS_TO_TICKS(2000));
      continue;
    }
    double sum = 0;
    int n = 0;
    for (int i = 0; i < 300; i++) {
      xSemaphoreTake(i2c_lock, portMAX_DELAY);
      bool r = imuRaw(g, x, y, z);
      xSemaphoreGive(i2c_lock);
      if (r) {
        sum += g;
        n++;
      }
      vTaskDelay(pdMS_TO_TICKS(5));
    }
    if (n < 200) continue;
    gz_bias = sum / n;
    imu_ok = true;
    uint32_t last = micros();
    int fails = 0;
    while (fails < 50) {
      xSemaphoreTake(i2c_lock, portMAX_DELAY);
      bool r = imuRaw(g, x, y, z);
      xSemaphoreGive(i2c_lock);
      uint32_t now = micros();
      float dt = (now - last) / 1e6f;
      last = now;
      if (!r) {
        fails++;
        vTaskDelay(pdMS_TO_TICKS(5));
        continue;
      }
      fails = 0;
      float rate = g - gz_bias;
      // standing still: slowly re-learn the offset, so the heading does not drift
      if (out_l == 0 && out_r == 0 && fabsf(rate) < 1.0f) gz_bias += 0.002f * (g - gz_bias), rate = 0;
      yaw_total = yaw_total + rate * dt;
      float yw = yaw + rate * dt;  // positive = turning left (counter-clockwise from above)
      while (yw > 180) yw -= 360;
      while (yw <= -180) yw += 360;
      yaw = yw;
      gz = rate;
      ax = x;
      ay = y;
      az = z;
      pitch = atan2f(-x, sqrtf(y * y + z * z)) * 57.2958f;
      roll = atan2f(y, z) * 57.2958f;
      vTaskDelay(pdMS_TO_TICKS(5));  // ~200 Hz
    }
    imu_ok = false;  // lost it: start again
  }
}

// ================================================================== HC-SR04P (3.3 V version: no divider needed)
static float pingOnce(bool &seen) {
  digitalWrite(PIN_TRIG, LOW);
  delayMicroseconds(3);
  digitalWrite(PIN_TRIG, HIGH);
  delayMicroseconds(10);
  digitalWrite(PIN_TRIG, LOW);
  uint32_t t0 = micros();
  while (digitalRead(PIN_ECHO) == LOW)
    if (micros() - t0 > 4000) {
      seen = false;  // the sensor never answered: missing or unpowered
      return 400;
    }
  seen = true;
  uint32_t rise = micros();
  while (digitalRead(PIN_ECHO) == HIGH)
    if (micros() - rise > 30000) return 400;  // nothing in range
  float cm = (micros() - rise) / 58.0f;
  return cm > 400 ? 400 : cm;
}

static void sonarTask(void *) {
  float h[3] = {400, 400, 400};
  int i = 0;
  for (;;) {
    bool seen;
    float cm = pingOnce(seen);
    uint32_t now = millis();
    if (seen) {
      us_seen_ms = now;
      us_ok = true;
      h[i++ % 3] = cm;
      float a = h[0], b = h[1], c = h[2];  // median of the last 3 = ignores one bad echo
      dist_cm = fmaxf(fminf(a, b), fminf(fmaxf(a, b), c));
    } else if (now - us_seen_ms > 1000) {
      us_ok = false;
    }
    vTaskDelay(pdMS_TO_TICKS(50));  // ~15 readings a second; quiet time for echoes to die out
  }
}

// ================================================================== AHT20 + BMP280 (climate)
static uint8_t bmp_addr = 0;
static uint16_t kT1, kP1;
static int16_t kT2, kT3, kP2, kP3, kP4, kP5, kP6, kP7, kP8, kP9;

static bool bmpInit() {
  for (uint8_t a : {0x77, 0x76}) {
    uint8_t id = 0;
    if (i2cRead(a, 0xD0, &id, 1) && (id == 0x58 || id == 0x60)) {
      uint8_t c[24];
      if (!i2cRead(a, 0x88, c, 24)) return false;
      kT1 = c[1] << 8 | c[0], kT2 = c[3] << 8 | c[2], kT3 = c[5] << 8 | c[4];
      kP1 = c[7] << 8 | c[6], kP2 = c[9] << 8 | c[8], kP3 = c[11] << 8 | c[10], kP4 = c[13] << 8 | c[12];
      kP5 = c[15] << 8 | c[14], kP6 = c[17] << 8 | c[16], kP7 = c[19] << 8 | c[18], kP8 = c[21] << 8 | c[20];
      kP9 = c[23] << 8 | c[22];
      i2cWrite(a, 0xF5, 0xA0);  // 1 s standby
      i2cWrite(a, 0xF4, 0x27);  // temperature + pressure, normal mode
      bmp_addr = a;
      return true;
    }
  }
  return false;
}

static bool bmpRead(float &t, float &p) {
  uint8_t d[6];
  if (!i2cRead(bmp_addr, 0xF7, d, 6)) return false;
  int32_t adc_p = (int32_t)d[0] << 12 | d[1] << 4 | d[2] >> 4;
  int32_t adc_t = (int32_t)d[3] << 12 | d[4] << 4 | d[5] >> 4;
  double v1 = (adc_t / 16384.0 - kT1 / 1024.0) * kT2;
  double v2 = (adc_t / 131072.0 - kT1 / 8192.0) * (adc_t / 131072.0 - kT1 / 8192.0) * kT3;
  double tf = v1 + v2;
  t = tf / 5120.0;
  v1 = tf / 2.0 - 64000.0;
  v2 = v1 * v1 * kP6 / 32768.0 + v1 * kP5 * 2.0;
  v2 = v2 / 4.0 + kP4 * 65536.0;
  v1 = (kP3 * v1 * v1 / 524288.0 + kP2 * v1) / 524288.0;
  v1 = (1.0 + v1 / 32768.0) * kP1;
  if (v1 == 0) return false;
  double pa = 1048576.0 - adc_p;
  pa = (pa - v2 / 4096.0) * 6250.0 / v1;
  v1 = kP9 * pa * pa / 2147483648.0;
  v2 = pa * kP8 / 32768.0;
  pa = pa + (v1 + v2 + kP7) / 16.0;
  p = pa / 100.0;
  return p > 300 && p < 1200;
}

static void envTask(void *) {
  bool aht_init = false;
  for (;;) {
    // AHT20: start a measurement, read it 90 ms later
    xSemaphoreTake(i2c_lock, portMAX_DELAY);
    if (!aht_init) {
      uint8_t st = 0;
      if (i2cRead(0x38, 0x71, &st, 1)) {
        if (!(st & 0x08)) {  // not calibrated yet
          Wire.beginTransmission(0x38);
          Wire.write(0xBE), Wire.write(0x08), Wire.write(0x00);
          Wire.endTransmission();
        }
        aht_init = true;
      }
    }
    bool started = false;
    if (aht_init) {
      Wire.beginTransmission(0x38);
      Wire.write(0xAC), Wire.write(0x33), Wire.write(0x00);
      started = Wire.endTransmission() == 0;
    }
    if (!bmp_addr) bmpInit();
    xSemaphoreGive(i2c_lock);
    vTaskDelay(pdMS_TO_TICKS(90));

    xSemaphoreTake(i2c_lock, portMAX_DELAY);
    uint8_t d[7];
    bool ok = started && Wire.requestFrom((uint16_t)0x38, (size_t)7) == 7;
    if (ok) {
      for (int i = 0; i < 7; i++) d[i] = Wire.read();
      ok = !(d[0] & 0x80);  // not busy
    }
    if (ok) {
      uint32_t hr = ((uint32_t)d[1] << 12) | ((uint32_t)d[2] << 4) | (d[3] >> 4);
      uint32_t tr = (((uint32_t)d[3] & 0x0F) << 16) | ((uint32_t)d[4] << 8) | d[5];
      rh_pct = hr * 100.0f / 1048576.0f;
      temp_c = tr * 200.0f / 1048576.0f - 50.0f;
    } else {
      aht_init = false;
    }
    aht_ok = ok;
    float t, p;
    bool bok = bmp_addr && bmpRead(t, p);
    if (bok) {
      press_hpa = p;
      if (!ok) temp_c = t;  // no AHT20: use the BMP280's temperature
    } else {
      bmp_addr = 0;
    }
    bmp_ok = bok;
    xSemaphoreGive(i2c_lock);
    vTaskDelay(pdMS_TO_TICKS(1900));
  }
}

// ================================================================== camera (built into the Sense board)
static bool cameraInit() {
  camera_config_t c = {};
  c.pin_pwdn = -1, c.pin_reset = -1, c.pin_xclk = 10;
  c.pin_sccb_sda = 40, c.pin_sccb_scl = 39;
  c.pin_d7 = 48, c.pin_d6 = 11, c.pin_d5 = 12, c.pin_d4 = 14;
  c.pin_d3 = 16, c.pin_d2 = 18, c.pin_d1 = 17, c.pin_d0 = 15;
  c.pin_vsync = 38, c.pin_href = 47, c.pin_pclk = 13;
  c.xclk_freq_hz = 20000000;
  c.ledc_timer = LEDC_TIMER_3;  // the motors use the other timers
  c.ledc_channel = LEDC_CHANNEL_7;
  c.pixel_format = PIXFORMAT_JPEG;
  c.frame_size = FRAMESIZE_VGA;  // 640 x 480
  c.jpeg_quality = 12;
  c.fb_count = 2;
  c.fb_location = CAMERA_FB_IN_PSRAM;
  c.grab_mode = CAMERA_GRAB_LATEST;
  if (esp_camera_init(&c) != ESP_OK) return false;
  sensor_t *s = esp_camera_sensor_get();
  if (s) s->set_vflip(s, 0);
  return true;
}

// ================================================================== HTTP: helpers
static void putNum(String &j, const char *key, float v, int dec = 2) {
  j += '"';
  j += key;
  j += "\":";
  if (isnan(v)) j += "null";
  else j += String(v, dec);
  j += ',';
}

static void putBool(String &j, const char *key, bool v) {
  j += '"';
  j += key;
  j += "\":";
  j += v ? "true," : "false,";
}

static String statusJson() {
  String j = "{";
  j += "\"fw\":\"" FW_VERSION "\",\"board\":\"xiao_esp32s3_sense\",";
  j += "\"ip\":\"" + (ap_mode ? WiFi.softAPIP() : WiFi.localIP()).toString() + "\",";
  j += "\"mode\":\"" + String(ap_mode ? "ap" : "sta") + "\",";
  String ss = ap_mode ? String(AP_SSID) : wifi_ssid;
  ss.replace("\\", "/");
  ss.replace("\"", "'");
  j += "\"ssid\":\"" + ss + "\",";
  putNum(j, "up_s", millis() / 1000.0f, 1);
  putNum(j, "rssi", ap_mode ? NAN : (float)WiFi.RSSI(), 0);
  putNum(j, "dist_cm", dist_cm, 1);
  putBool(j, "us_ok", us_ok);
  putBool(j, "blocked", blocked);
  static const char *turn_names[] = {"idle", "turning", "done", "timeout", "stopped"};
  j += "\"turn\":\"";
  j += turn_names[turn_result];
  j += "\",";
  putNum(j, "turn_err", turn_active ? turn_target - yaw_total : 0.0f, 1);
  putNum(j, "yaw", yaw, 2);
  putNum(j, "pitch", pitch, 1);
  putNum(j, "roll", roll, 1);
  putNum(j, "gz", gz, 2);
  putNum(j, "ax", ax, 3);
  putNum(j, "ay", ay, 3);
  putNum(j, "az", az, 3);
  putBool(j, "imu_ok", imu_ok);
  putNum(j, "temp_c", temp_c, 2);
  putNum(j, "rh", rh_pct, 1);
  putNum(j, "press_hpa", press_hpa, 1);
  putBool(j, "aht_ok", aht_ok);
  putBool(j, "bmp_ok", bmp_ok);
  putBool(j, "cam_ok", cam_ok);
  putBool(j, "mic_ok", mic_ok);
  putNum(j, "heap_kb", ESP.getFreeHeap() / 1024.0f, 0);
  j += "\"motors\":[" + String(out_l, 2) + "," + String(out_r, 2) + "],";
  j += "\"target\":[" + String(tgt_l, 2) + "," + String(tgt_r, 2) + "]}";
  return j;
}

static esp_err_t sendJson(httpd_req_t *req, const String &body) {
  httpd_resp_set_type(req, "application/json");
  httpd_resp_set_hdr(req, "Access-Control-Allow-Origin", "*");
  httpd_resp_set_hdr(req, "Cache-Control", "no-store");
  return httpd_resp_send(req, body.c_str(), body.length());
}

static bool queryFloat(httpd_req_t *req, const char *key, float &out) {
  char q[160], v[24];
  if (httpd_req_get_url_query_str(req, q, sizeof(q)) != ESP_OK) return false;
  if (httpd_query_key_value(q, key, v, sizeof(v)) != ESP_OK) return false;
  out = atof(v);
  return true;
}

// ================================================================== HTTP: control (port 80)
static const char TEST_PAGE[] = R"HTML(<!doctype html><html><head><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Raqib robot</title><style>body{font-family:sans-serif;margin:12px;background:#0d1530;color:#eef2ff}
img{width:100%;max-width:480px;border-radius:10px;background:#222}button{font-size:22px;width:70px;height:56px;margin:4px;border-radius:12px;border:0}
pre{background:#1a2550;padding:8px;border-radius:8px;font-size:12px;white-space:pre-wrap}</style></head><body>
<h2>Raqib robot - test page</h2><p id="net"></p><img id="cam" alt="camera"><div>
<div><button data-l="1" data-r="1">&#9650;</button></div>
<div><button data-l="-0.8" data-r="0.8">&#9664;</button><button onclick="fetch('/stop')">&#9632;</button><button data-l="0.8" data-r="-0.8">&#9654;</button></div>
<div><button data-l="-0.7" data-r="-0.7">&#9660;</button></div></div><p>Hold a button to drive. Robot on a box, wheels in the air first!</p>
<pre id="st">...</pre>
<h3>Wi-Fi</h3><p>Type your phone hotspot (2.4 GHz). The robot restarts and joins it.</p>
<form action="/wifi"><input name="ssid" placeholder="Hotspot name" required> <input name="pass" type="password" placeholder="Password">
<button style="width:auto;font-size:16px;padding:0 14px">Save</button></form><script>
let drive=null;document.querySelectorAll('button[data-l]').forEach(b=>{const go=e=>{e.preventDefault();clearInterval(drive);
const f=()=>fetch(`/drive?l=${b.dataset.l*0.6}&r=${b.dataset.r*0.6}`);f();drive=setInterval(f,200)};const end=()=>{clearInterval(drive);fetch('/stop')};
b.onmousedown=go;b.ontouchstart=go;b.onmouseup=end;b.onmouseleave=end;b.ontouchend=end;});
setInterval(async()=>{try{const s=await (await fetch('/status')).json();st.textContent=JSON.stringify(s,null,1);
net.textContent=s.mode=='ap'?'Own network Raqib-Robot: set your hotspot below.':'On Wi-Fi '+s.ssid+' at '+s.ip}catch(e){}},700);
setInterval(()=>{cam.src='/capture?t='+Date.now()},1000);</script></body></html>)HTML";

static esp_err_t h_root(httpd_req_t *req) {
  httpd_resp_set_type(req, "text/html");
  return httpd_resp_send(req, TEST_PAGE, sizeof(TEST_PAGE) - 1);
}

static esp_err_t h_status(httpd_req_t *req) { return sendJson(req, statusJson()); }

static esp_err_t h_drive(httpd_req_t *req) {
  if (turn_active) {
    turn_active = false;
    turn_result = 4;
  }
  float l = 0, r = 0;
  queryFloat(req, "l", l);
  queryFloat(req, "r", r);
  tgt_l = fmaxf(-1, fminf(1, l));
  tgt_r = fmaxf(-1, fminf(1, r));
  last_cmd_ms = millis();
  return sendJson(req, statusJson());
}

static esp_err_t h_stop(httpd_req_t *req) {
  if (turn_active) {
    turn_active = false;
    turn_result = 4;
  }
  tgt_l = 0;
  tgt_r = 0;
  out_l = 0;
  out_r = 0;
  return sendJson(req, statusJson());
}

// /turn?deg=90&power=0.5 : turn on the spot (positive = left); /status "turn" says when it is done
static esp_err_t h_turn(httpd_req_t *req) {
  float deg = 0, power = 0.5f;
  queryFloat(req, "deg", deg);
  queryFloat(req, "power", power);
  deg = fmaxf(-720, fminf(720, deg));
  tgt_l = 0;
  tgt_r = 0;
  turn_power = fmaxf(0.1f, fminf(1, power));
  turn_target = yaw_total + deg;
  turn_deadline = millis() + (uint32_t)(fabsf(deg) / 30.0f * 1000) + 4000;
  turn_result = 1;
  turn_active = imu_ok;
  if (!imu_ok) turn_result = 3;
  return sendJson(req, statusJson());
}

static esp_err_t h_reset_yaw(httpd_req_t *req) {
  yaw = 0;
  return sendJson(req, statusJson());
}

static esp_err_t h_config(httpd_req_t *req) {
  float v;
  if (queryFloat(req, "stop_cm", v)) cfg.stop_cm = fmaxf(5, fminf(60, v));
  if (queryFloat(req, "max_duty", v)) cfg.max_duty = fmaxf(0.2f, fminf(1, v));
  if (queryFloat(req, "ramp", v)) cfg.ramp_per_s = fmaxf(0.5f, fminf(50, v));
  if (queryFloat(req, "deadman_ms", v)) cfg.deadman_ms = (uint32_t)fmaxf(200, fminf(3000, v));
  if (queryFloat(req, "inv_l", v)) cfg.inv_l = v != 0;
  if (queryFloat(req, "inv_r", v)) cfg.inv_r = v != 0;
  if (queryFloat(req, "min_power", v)) cfg.min_power = fmaxf(0, fminf(0.9f, v));
  String j = "{";
  putNum(j, "min_power", cfg.min_power, 2);
  putNum(j, "stop_cm", cfg.stop_cm, 1);
  putNum(j, "max_duty", cfg.max_duty, 2);
  putNum(j, "ramp", cfg.ramp_per_s, 1);
  putNum(j, "deadman_ms", cfg.deadman_ms, 0);
  putBool(j, "inv_l", cfg.inv_l);
  j += "\"inv_r\":";
  j += cfg.inv_r ? "true}" : "false}";
  return sendJson(req, j);
}

static esp_err_t h_capture(httpd_req_t *req) {
  if (!cam_ok) {
    httpd_resp_send_err(req, HTTPD_500_INTERNAL_SERVER_ERROR, "camera not working");
    return ESP_FAIL;
  }
  camera_fb_t *fb = esp_camera_fb_get();
  if (!fb) {
    httpd_resp_send_err(req, HTTPD_500_INTERNAL_SERVER_ERROR, "no frame");
    return ESP_FAIL;
  }
  httpd_resp_set_type(req, "image/jpeg");
  httpd_resp_set_hdr(req, "Access-Control-Allow-Origin", "*");
  httpd_resp_set_hdr(req, "Cache-Control", "no-store");
  esp_err_t r = httpd_resp_send(req, (const char *)fb->buf, fb->len);
  esp_camera_fb_return(fb);
  return r;
}

static esp_err_t h_wifi(httpd_req_t *req) {
  char q[200], s[64] = "", p[64] = "";
  if (httpd_req_get_url_query_str(req, q, sizeof(q)) == ESP_OK) {
    httpd_query_key_value(q, "ssid", s, sizeof(s));
    httpd_query_key_value(q, "pass", p, sizeof(p));
  }
  if (!s[0]) return httpd_resp_send_err(req, HTTPD_400_BAD_REQUEST, "hotspot name missing");
  // form fields arrive URL-encoded: turn + into space and %XX into the character
  auto decode = [](char *v) {
    char *o = v;
    for (char *i = v; *i; i++) {
      if (*i == '+') *o++ = ' ';
      else if (*i == '%' && i[1] && i[2]) {
        char hex[3] = {i[1], i[2], 0};
        *o++ = (char)strtol(hex, nullptr, 16);
        i += 2;
      } else *o++ = *i;
    }
    *o = 0;
  };
  decode(s), decode(p);
  prefs.putString("ssid", s);
  prefs.putString("pass", p);
  static const char ok[] = "<!doctype html><meta name=viewport content='width=device-width'><body style='font-family:sans-serif'>"
                           "<h2>Saved</h2><p>The robot restarts and joins your hotspot. Join the hotspot too, then open "
                           "<b>http://raqib.local</b>. If it cannot join, it makes the Raqib-Robot network again.</p>";
  httpd_resp_set_type(req, "text/html");
  httpd_resp_send(req, ok, sizeof(ok) - 1);
  delay(800);
  ESP.restart();
  return ESP_OK;
}

// ================================================================== HTTP: video (port 81)
static esp_err_t h_stream(httpd_req_t *req) {
  if (!cam_ok) return httpd_resp_send_err(req, HTTPD_500_INTERNAL_SERVER_ERROR, "camera not working");
  httpd_resp_set_type(req, "multipart/x-mixed-replace;boundary=frame");
  httpd_resp_set_hdr(req, "Access-Control-Allow-Origin", "*");
  char head[80];
  for (;;) {
    camera_fb_t *fb = esp_camera_fb_get();
    if (!fb) return ESP_FAIL;
    int n = snprintf(head, sizeof(head), "\r\n--frame\r\nContent-Type: image/jpeg\r\nContent-Length: %u\r\n\r\n", fb->len);
    esp_err_t r = httpd_resp_send_chunk(req, head, n);
    if (r == ESP_OK) r = httpd_resp_send_chunk(req, (const char *)fb->buf, fb->len);
    esp_camera_fb_return(fb);
    if (r != ESP_OK) return r;  // the viewer closed the page
    vTaskDelay(pdMS_TO_TICKS(80));  // ~10 frames a second
  }
}

// ================================================================== HTTP: microphone (port 82)
static esp_err_t h_audio(httpd_req_t *req) {
  if (!mic_ok) return httpd_resp_send_err(req, HTTPD_500_INTERNAL_SERVER_ERROR, "microphone not working");
  float ms = 1000;
  queryFloat(req, "ms", ms);
  ms = fmaxf(100, fminf(5000, ms));
  const uint32_t rate = 16000;
  uint32_t samples = (uint32_t)(rate * ms / 1000.0f);
  uint32_t bytes = samples * 2;
  uint8_t *buf = (uint8_t *)ps_malloc(44 + bytes);
  if (!buf) return httpd_resp_send_err(req, HTTPD_500_INTERNAL_SERVER_ERROR, "out of memory");
  // 44-byte WAV header: PCM, mono, 16-bit, 16 kHz
  auto put32 = [&](int at, uint32_t v) { for (int i = 0; i < 4; i++) buf[at + i] = (v >> (8 * i)) & 0xFF; };
  auto put16 = [&](int at, uint16_t v) { buf[at] = v & 0xFF, buf[at + 1] = v >> 8; };
  memcpy(buf, "RIFF", 4), put32(4, 36 + bytes), memcpy(buf + 8, "WAVEfmt ", 8), put32(16, 16), put16(20, 1);
  put16(22, 1), put32(24, rate), put32(28, rate * 2), put16(32, 2), put16(34, 16), memcpy(buf + 36, "data", 4);
  put32(40, bytes);
  xSemaphoreTake(mic_lock, portMAX_DELAY);
  size_t got = 0;
  uint32_t t0 = millis();
  while (got < bytes && millis() - t0 < ms + 2000) got += i2s.readBytes((char *)buf + 44 + got, bytes - got);
  xSemaphoreGive(mic_lock);
  httpd_resp_set_type(req, "audio/wav");
  httpd_resp_set_hdr(req, "Access-Control-Allow-Origin", "*");
  esp_err_t r = httpd_resp_send(req, (const char *)buf, 44 + got);
  free(buf);
  return r;
}

// ================================================================== servers
static httpd_handle_t startServer(uint16_t port, uint16_t ctrl, const httpd_uri_t *uris, int n) {
  httpd_config_t c = HTTPD_DEFAULT_CONFIG();
  c.server_port = port;
  c.ctrl_port = ctrl;
  c.max_uri_handlers = 12;
  c.stack_size = 8192;
  c.lru_purge_enable = true;
  httpd_handle_t h = nullptr;
  if (httpd_start(&h, &c) != ESP_OK) return nullptr;
  for (int i = 0; i < n; i++) httpd_register_uri_handler(h, &uris[i]);
  return h;
}

static void startServers() {
  static const httpd_uri_t ctrl[] = {
      {"/", HTTP_GET, h_root, nullptr},           {"/status", HTTP_GET, h_status, nullptr},
      {"/drive", HTTP_GET, h_drive, nullptr},     {"/stop", HTTP_GET, h_stop, nullptr},
      {"/config", HTTP_GET, h_config, nullptr},   {"/reset_yaw", HTTP_GET, h_reset_yaw, nullptr},
      {"/capture", HTTP_GET, h_capture, nullptr}, {"/wifi", HTTP_GET, h_wifi, nullptr},
      {"/turn", HTTP_GET, h_turn, nullptr},
  };
  static const httpd_uri_t video[] = {{"/stream", HTTP_GET, h_stream, nullptr}};
  static const httpd_uri_t audio[] = {{"/audio", HTTP_GET, h_audio, nullptr}};
  startServer(80, 32768, ctrl, sizeof(ctrl) / sizeof(ctrl[0]));
  startServer(81, 32769, video, 1);
  startServer(82, 32770, audio, 1);
}

// ================================================================== Wi-Fi
static void connectWifi() {
  WiFi.mode(WIFI_STA);
  WiFi.setHostname(ROBOT_HOSTNAME);
  WiFi.setSleep(false);  // quick answers to the PC
  WiFi.setAutoReconnect(true);
  prefs.begin("raqib", false);
  wifi_ssid = prefs.getString("ssid", WIFI_SSID);   // set on the robot's own page, or in wifi_config.h
  wifi_pass = prefs.getString("pass", WIFI_PASSWORD);
  WiFi.begin(wifi_ssid.c_str(), wifi_pass.c_str());
  Serial.printf("Joining Wi-Fi \"%s\"", wifi_ssid.c_str());
  uint32_t t0 = millis();
  bool unset = wifi_ssid.length() == 0 || wifi_ssid == "MyPhoneHotspot";  // never set: go straight to own network
  while (!unset && WiFi.status() != WL_CONNECTED && millis() - t0 < 20000) {
    digitalWrite(PIN_LED, !digitalRead(PIN_LED));  // fast blink = joining
    delay(150);
    Serial.print('.');
  }
  if (WiFi.status() == WL_CONNECTED) {
    Serial.printf("\nConnected. Robot address: http://%s  (or http://%s.local)\n",
                  WiFi.localIP().toString().c_str(), ROBOT_HOSTNAME);
  } else {
    ap_mode = true;
    WiFi.disconnect(true);
    WiFi.mode(WIFI_AP);
    WiFi.softAP(AP_SSID, AP_PASSWORD);
    Serial.printf("\nWi-Fi \"%s\" not found. Made own network \"%s\" (password %s): http://%s\n", wifi_ssid.c_str(),
                  AP_SSID, AP_PASSWORD, WiFi.softAPIP().toString().c_str());
  }
  MDNS.begin(ROBOT_HOSTNAME);
  MDNS.addService("http", "tcp", 80);
  MDNS.addService("raqib", "tcp", 80);
}

// ================================================================== setup / loop
void setup() {
  // motors first, so the wheels can never twitch at power-on
  for (int p : {PIN_AIN1, PIN_AIN2, PIN_BIN1, PIN_BIN2}) {
    ledcAttach(p, 20000, 10);  // 20 kHz: no motor whine
    ledcWrite(p, 0);
  }
  pinMode(PIN_LED, OUTPUT);
  digitalWrite(PIN_LED, HIGH);
  pinMode(PIN_TRIG, OUTPUT);
  digitalWrite(PIN_TRIG, LOW);
  pinMode(PIN_ECHO, INPUT);
  Serial.begin(115200);
  delay(300);
  Serial.println("\nRaqib robot firmware " FW_VERSION);

  i2c_lock = xSemaphoreCreateMutex();
  mic_lock = xSemaphoreCreateMutex();
  Wire.begin(PIN_SDA, PIN_SCL, 400000);
  Wire.setTimeOut(20);

  cam_ok = psramFound() && cameraInit();
  Serial.printf("Camera: %s\n", cam_ok ? "OK" : (psramFound() ? "NOT FOUND (check the camera ribbon)" : "needs Tools -> PSRAM -> OPI PSRAM"));
  i2s.setPinsPdmRx(PIN_MIC_CLK, PIN_MIC_DATA);
  mic_ok = i2s.begin(I2S_MODE_PDM_RX, 16000, I2S_DATA_BIT_WIDTH_16BIT, I2S_SLOT_MODE_MONO);
  Serial.printf("Microphone: %s\n", mic_ok ? "OK" : "NOT FOUND");

  xTaskCreatePinnedToCore(controlTask, "control", 4096, nullptr, 5, nullptr, 1);
  xTaskCreatePinnedToCore(imuTask, "imu", 4096, nullptr, 4, nullptr, 1);
  xTaskCreatePinnedToCore(sonarTask, "sonar", 3072, nullptr, 3, nullptr, 1);
  xTaskCreatePinnedToCore(envTask, "env", 4096, nullptr, 1, nullptr, 1);

  connectWifi();
  startServers();
  udp.begin(BEACON_PORT);
}

void loop() {
  static uint32_t last_beacon = 0, last_log = 0;
  uint32_t now = millis();
  // tell the PC where the robot is (it listens on UDP 37021)
  if (now - last_beacon > 2000) {
    last_beacon = now;
    IPAddress me = ap_mode ? WiFi.softAPIP() : WiFi.localIP();
    IPAddress bcast = ap_mode ? IPAddress(192, 168, 4, 255) : WiFi.broadcastIP();
    udp.beginPacket(bcast, BEACON_PORT);
    udp.printf("RAQIB-ESP32 %s %s", FW_VERSION, me.toString().c_str());
    udp.endPacket();
  }
  // LED: steady = on Wi-Fi, slow blink = own network, off for a moment = something is missing
  bool parts_ok = imu_ok && us_ok && cam_ok && mic_ok && (aht_ok || bmp_ok);
  bool on = ap_mode ? (now / 700) % 2 : (parts_ok || (now / 150) % 10 != 0);
  digitalWrite(PIN_LED, on ? LOW : HIGH);
  if (now - last_log > 5000) {
    last_log = now;
    Serial.printf("dist %.0f cm | yaw %.1f | %.1f C %.0f%% %.0f hPa | imu %d sonar %d aht %d bmp %d cam %d mic %d\n",
                  dist_cm, yaw, temp_c, rh_pct, press_hpa, imu_ok, us_ok, aht_ok, bmp_ok, cam_ok, mic_ok);
  }
  delay(20);
}
