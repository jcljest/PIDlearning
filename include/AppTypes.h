#pragma once

#include <Arduino.h>

struct MotorState {
  int pwm = 0;
  int direction = 0;
  bool inDeadband = true;
  bool saturated = false;
};

struct PidTerms {
  float p = 0.0f;
  float i = 0.0f;
  float d = 0.0f;
  float output = 0.0f;
};

struct ControlTelemetry {
  unsigned long timestampMs = 0;
  int setpoint = 0;
  int feedbackRaw = 0;
  int feedback = 0;
  int error = 0;
  PidTerms pid;
  MotorState motor;
};

enum class CaptureState : uint8_t {
  Idle,
  Armed,
  Capturing,
};

struct CaptureConfig {
  size_t sampleCount = 0;
  unsigned long intervalMs = 0;
  int triggerDelta = 0;
};

enum class CommandType : uint8_t {
  None,
  Help,
  Status,
  StatusCsv,
  SetPid,
  RunController,
  ArmCapture,
  StartCapture,
  CancelCapture,
  ResetController,
  StopMotor,
};

struct Command {
  CommandType type = CommandType::None;
  float kp = 0.0f;
  float ki = 0.0f;
  float kd = 0.0f;
  CaptureConfig captureConfig;
};
