#pragma once

#include <Arduino.h>

#include "AppTypes.h"

class CaptureSession {
 public:
  explicit CaptureSession(Stream& serial);

  void arm(const CaptureConfig& config, int baselineSetpoint);
  void startImmediate(const CaptureConfig& config,
                      unsigned long nowMs,
                      float kp,
                      float ki,
                      float kd);
  void cancel();
  void maybeTrigger(int currentSetpoint,
                    unsigned long nowMs,
                    float kp,
                    float ki,
                    float kd);
  void maybeRecord(const ControlTelemetry& telemetry);

  CaptureState state() const;
  const CaptureConfig& config() const;

 private:
  void beginCapture(unsigned long nowMs, float kp, float ki, float kd);
  void finishCapture();
  bool isConfigValid(const CaptureConfig& config) const;

  Stream& serial_;
  CaptureState state_ = CaptureState::Idle;
  CaptureConfig config_{};
  int baselineSetpoint_ = 0;
  unsigned long nextSampleMs_ = 0;
  size_t sampleIndex_ = 0;
};
