#pragma once

#include <Arduino.h>

#include "AppTypes.h"

class PidController {
 public:
  PidController(float kp, float ki, float kd, float integralContributionLimit);

  void setTunings(float kp, float ki, float kd);
  void reset();
  PidTerms update(float setpoint, float measurement, float dtSeconds);

  float kp() const;
  float ki() const;
  float kd() const;
  const PidTerms& terms() const;

 private:
  float kp_;
  float ki_;
  float kd_;
  float integralContributionLimit_;

  float integralState_ = 0.0f;
  float lastMeasurement_ = 0.0f;
  bool hasPreviousMeasurement_ = false;
  PidTerms terms_;
};
