#include "MotorDriver.h"

MotorDriver::MotorDriver(uint8_t enPin,
                         uint8_t in1Pin,
                         uint8_t in2Pin,
                         int deadBand,
                         int minDrive,
                         int maxDrive)
    : enPin_(enPin),
      in1Pin_(in1Pin),
      in2Pin_(in2Pin),
      deadBand_(deadBand),
      minDrive_(minDrive),
      maxDrive_(maxDrive) {}

void MotorDriver::begin() {
  pinMode(enPin_, OUTPUT);
  pinMode(in1Pin_, OUTPUT);
  pinMode(in2Pin_, OUTPUT);
  stop();
}

void MotorDriver::stop() {
  digitalWrite(in1Pin_, LOW);
  digitalWrite(in2Pin_, LOW);
  analogWrite(enPin_, 0);

  state_.pwm = 0;
  state_.direction = 0;
  state_.inDeadband = true;
  state_.saturated = false;
}

void MotorDriver::drive(float command) {
  const float magnitude = fabsf(command);

  if (magnitude < static_cast<float>(deadBand_)) {
    stop();
    return;
  }

  state_.inDeadband = false;

  if (command >= 0.0f) {
    digitalWrite(in1Pin_, HIGH);
    digitalWrite(in2Pin_, LOW);
    state_.direction = 1;
  } else {
    digitalWrite(in1Pin_, LOW);
    digitalWrite(in2Pin_, HIGH);
    state_.direction = -1;
  }

  int pwm = static_cast<int>(magnitude);
  if (pwm < minDrive_) {
    pwm = minDrive_;
  }

  state_.saturated = false;
  if (pwm > maxDrive_) {
    pwm = maxDrive_;
    state_.saturated = true;
  }

  analogWrite(enPin_, pwm);
  state_.pwm = pwm;
}

const MotorState& MotorDriver::state() const {
  return state_;
}
