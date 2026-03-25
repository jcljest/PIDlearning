#pragma once

#include <Arduino.h>

#include "AppTypes.h"

class MotorDriver {
 public:
  MotorDriver(uint8_t enPin,
              uint8_t in1Pin,
              uint8_t in2Pin,
              int deadBand,
              int minDrive,
              int maxDrive);

  void begin();
  void stop();
  void drive(float command);

  const MotorState& state() const;

 private:
  uint8_t enPin_;
  uint8_t in1Pin_;
  uint8_t in2Pin_;
  int deadBand_;
  int minDrive_;
  int maxDrive_;
  MotorState state_;
};
