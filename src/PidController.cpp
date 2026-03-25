#include "PidController.h"

namespace {

float clampValue(float value, float minValue, float maxValue) {
  if (value < minValue) {
    return minValue;
  }
  if (value > maxValue) {
    return maxValue;
  }
  return value;
}

}  // namespace

PidController::PidController(float kp,
                             float ki,
                             float kd,
                             float integralContributionLimit)
    : kp_(kp),
      ki_(ki),
      kd_(kd),
      integralContributionLimit_(integralContributionLimit) {}

void PidController::setTunings(float kp, float ki, float kd) {
  kp_ = kp;
  ki_ = ki;
  kd_ = kd;
}

void PidController::reset() {
  integralState_ = 0.0f;
  lastMeasurement_ = 0.0f;
  hasPreviousMeasurement_ = false;
  terms_ = {};
}

PidTerms PidController::update(float setpoint, float measurement, float dtSeconds) {
  const float error = setpoint - measurement;
  terms_.p = kp_ * error;

  if (dtSeconds > 0.0f) {
    integralState_ += error * dtSeconds;

    if (ki_ != 0.0f) {
      const float maxIntegralState = integralContributionLimit_ / fabsf(ki_);
      integralState_ = clampValue(integralState_, -maxIntegralState, maxIntegralState);
    }

    if (hasPreviousMeasurement_) {
      const float measurementRate = (measurement - lastMeasurement_) / dtSeconds;
      terms_.d = -kd_ * measurementRate;
    } else {
      terms_.d = 0.0f;
    }
  } else {
    terms_.d = 0.0f;
  }

  terms_.i = ki_ * integralState_;
  terms_.output = terms_.p + terms_.i + terms_.d;

  lastMeasurement_ = measurement;
  hasPreviousMeasurement_ = true;

  return terms_;
}

float PidController::kp() const {
  return kp_;
}

float PidController::ki() const {
  return ki_;
}

float PidController::kd() const {
  return kd_;
}

const PidTerms& PidController::terms() const {
  return terms_;
}
