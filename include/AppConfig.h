#pragma once

#include <Arduino.h>

namespace AppConfig {

constexpr uint8_t SETPOINT_PIN = A0;
constexpr uint8_t FEEDBACK_PIN = A1;

constexpr uint8_t EN_PIN = 9;
constexpr uint8_t IN1_PIN = 7;
constexpr uint8_t IN2_PIN = 8;

constexpr bool INVERT_FEEDBACK = true;

constexpr float DEFAULT_KP = 0.8f;
constexpr float DEFAULT_KI = 0.0f;
constexpr float DEFAULT_KD = 0.0f;

constexpr float INTEGRAL_CONTRIBUTION_LIMIT = 255.0f;

constexpr int DEAD_BAND = 8;
constexpr int MIN_DRIVE = 70;
constexpr int MAX_DRIVE = 180;

constexpr unsigned long LOOP_PERIOD_MS = 10;
constexpr unsigned long SERIAL_BAUD = 115200;

constexpr size_t DEFAULT_CAPTURE_SAMPLES = 300;
constexpr unsigned long DEFAULT_CAPTURE_INTERVAL_MS = 10;
constexpr int DEFAULT_TRIGGER_DELTA = 25;

constexpr size_t COMMAND_BUFFER_SIZE = 96;

}  // namespace AppConfig
