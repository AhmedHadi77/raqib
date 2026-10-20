// =====================================================================================
//  Raqib ESP32 robot - Wi-Fi settings (OPTIONAL).
//  Easiest: leave this file alone. The robot then makes its own Wi-Fi "Raqib-Robot";
//  join it, open http://192.168.4.1 and type your hotspot there. It is remembered.
//  Or type your hotspot here before you upload from Arduino IDE.
// =====================================================================================
//  Use your PHONE'S HOTSPOT (best: the PC and the robot both join it, and the PC
//  still has internet for the AI), or the Wi-Fi your PC is on. 2.4 GHz only:
//  the ESP32 cannot see 5 GHz networks.
#pragma once

#define WIFI_SSID     "MyPhoneHotspot"
#define WIFI_PASSWORD "my-hotspot-password"

// If that Wi-Fi is not found within 20 s the robot makes its own network instead.
// Join it from the PC to test the robot without internet (the AI needs internet).
#define AP_SSID       "Raqib-Robot"
#define AP_PASSWORD   "raqib1234"   // at least 8 characters

// The robot answers at http://raqib.local (and announces its IP address to the PC).
#define ROBOT_HOSTNAME "raqib"
