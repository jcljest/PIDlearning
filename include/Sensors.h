#pragma once

#include <Arduino.h>

class Sensors {
 public:
  Sensors(uint8_t setpointPin, uint8_t feedbackPin, bool invertFeedback);

  void begin() const;
  int readSetpoint() const;
  int readFeedbackRaw() const;
  int readFeedback() const;

 private:
  uint8_t setpointPin_;
  uint8_t feedbackPin_;
  bool invertFeedback_;
};
