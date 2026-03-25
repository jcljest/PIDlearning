#include "CaptureSession.h"

#include "AppConfig.h"

CaptureSession::CaptureSession(Stream& serial) : serial_(serial) {
  config_.sampleCount = AppConfig::DEFAULT_CAPTURE_SAMPLES;
  config_.intervalMs = AppConfig::DEFAULT_CAPTURE_INTERVAL_MS;
  config_.triggerDelta = AppConfig::DEFAULT_TRIGGER_DELTA;
}

void CaptureSession::arm(const CaptureConfig& config, int baselineSetpoint) {
  if (!isConfigValid(config)) {
    serial_.println(F("Capture config is invalid."));
    return;
  }

  config_ = config;
  baselineSetpoint_ = baselineSetpoint;
  sampleIndex_ = 0;
  nextSampleMs_ = 0;
  state_ = CaptureState::Armed;

  serial_.print(F("Capture armed. Move the setpoint by at least "));
  serial_.print(config_.triggerDelta);
  serial_.print(F(" counts to trigger. Samples="));
  serial_.print(config_.sampleCount);
  serial_.print(F(", interval_ms="));
  serial_.println(config_.intervalMs);
}

void CaptureSession::startImmediate(const CaptureConfig& config,
                                    unsigned long nowMs,
                                    float kp,
                                    float ki,
                                    float kd) {
  if (!isConfigValid(config)) {
    serial_.println(F("Capture config is invalid."));
    return;
  }

  config_ = config;
  beginCapture(nowMs, kp, ki, kd);
}

void CaptureSession::cancel() {
  if (state_ == CaptureState::Idle) {
    serial_.println(F("No capture is active."));
    return;
  }

  state_ = CaptureState::Idle;
  sampleIndex_ = 0;
  serial_.println(F("Capture cancelled."));
}

void CaptureSession::maybeTrigger(int currentSetpoint,
                                  unsigned long nowMs,
                                  float kp,
                                  float ki,
                                  float kd) {
  if (state_ != CaptureState::Armed) {
    return;
  }

  if (abs(currentSetpoint - baselineSetpoint_) >= config_.triggerDelta) {
    beginCapture(nowMs, kp, ki, kd);
  }
}

void CaptureSession::maybeRecord(const ControlTelemetry& telemetry) {
  if (state_ != CaptureState::Capturing) {
    return;
  }

  if (telemetry.timestampMs < nextSampleMs_) {
    return;
  }

  serial_.print(sampleIndex_);
  serial_.print(',');
  serial_.print(telemetry.timestampMs);
  serial_.print(',');
  serial_.print(telemetry.setpoint);
  serial_.print(',');
  serial_.print(telemetry.feedback);
  serial_.print(',');
  serial_.print(telemetry.error);
  serial_.print(',');
  serial_.print(telemetry.pid.p, 4);
  serial_.print(',');
  serial_.print(telemetry.pid.i, 4);
  serial_.print(',');
  serial_.print(telemetry.pid.d, 4);
  serial_.print(',');
  serial_.print(telemetry.pid.output, 4);
  serial_.print(',');
  serial_.print(telemetry.motor.pwm);
  serial_.print(',');
  serial_.println(telemetry.motor.direction);

  ++sampleIndex_;
  nextSampleMs_ += config_.intervalMs;

  if (sampleIndex_ >= config_.sampleCount) {
    finishCapture();
  }
}

CaptureState CaptureSession::state() const {
  return state_;
}

const CaptureConfig& CaptureSession::config() const {
  return config_;
}

void CaptureSession::beginCapture(unsigned long nowMs, float kp, float ki, float kd) {
  state_ = CaptureState::Capturing;
  sampleIndex_ = 0;
  nextSampleMs_ = nowMs;

  serial_.println(F("# capture_begin"));
  serial_.print(F("# kp="));
  serial_.print(kp, 4);
  serial_.print(F(",ki="));
  serial_.print(ki, 4);
  serial_.print(F(",kd="));
  serial_.print(kd, 4);
  serial_.print(F(",samples="));
  serial_.print(config_.sampleCount);
  serial_.print(F(",interval_ms="));
  serial_.print(config_.intervalMs);
  serial_.print(F(",trigger_delta="));
  serial_.println(config_.triggerDelta);
  serial_.println(F("sample,ms,setpoint,feedback,error,p_term,i_term,d_term,raw_output,pwm,direction"));
}

void CaptureSession::finishCapture() {
  serial_.println(F("# capture_end"));
  state_ = CaptureState::Idle;
  sampleIndex_ = 0;
}

bool CaptureSession::isConfigValid(const CaptureConfig& config) const {
  return config.sampleCount > 0 && config.intervalMs > 0;
}
