#pragma once

#include <Arduino.h>

#include "AppTypes.h"

class SerialCommands {
 public:
  bool poll(Stream& serial,
            Command& command,
            float currentKp,
            float currentKi,
            float currentKd);

  static void printHelp(Stream& serial);
  static void printStatus(Stream& serial,
                          const ControlTelemetry& telemetry,
                          float kp,
                          float ki,
                          float kd,
                          bool controllerEnabled,
                          CaptureState captureState,
                          const CaptureConfig& captureConfig);
  static void printStatusCsv(Stream& serial,
                             const ControlTelemetry& telemetry,
                             float kp,
                             float ki,
                             float kd,
                             bool controllerEnabled,
                             CaptureState captureState,
                             const CaptureConfig& captureConfig);

 private:
  bool parseLine(char* line,
                 Command& command,
                 float currentKp,
                 float currentKi,
                 float currentKd);
  bool parsePidCommand(char* firstToken,
                       char* context,
                       Command& command,
                       float currentKp,
                       float currentKi,
                       float currentKd);
  bool parseCaptureCommand(char* firstToken, char* context, Command& command);
  static char* nextToken(char*& context);

  char buffer_[96] = {};
  size_t length_ = 0;
};
