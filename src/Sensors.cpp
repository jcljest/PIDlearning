#include "Sensors.h"

Sensors::Sensors(uint8_t setpointPin, uint8_t feedbackPin, bool invertFeedback)
    : setpointPin_(setpointPin),
      feedbackPin_(feedbackPin),
      invertFeedback_(invertFeedback) {}

void Sensors::begin() const {
  pinMode(setpointPin_, INPUT);
  pinMode(feedbackPin_, INPUT);
}

int Sensors::readSetpoint() const {
  return analogRead(setpointPin_);
}

int Sensors::readFeedbackRaw() const {
  return analogRead(feedbackPin_);
}

int Sensors::readFeedback() const {
  const int raw = readFeedbackRaw();
  if (invertFeedback_) {
    return 1023 - raw;
  }
  return raw;
}
