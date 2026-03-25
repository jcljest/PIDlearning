#include "SerialCommands.h"

#include <stdlib.h>
#include <string.h>

#include "AppConfig.h"

namespace {

bool parseFloatToken(char* token, float& value) {
  if (token == nullptr) {
    return false;
  }

  char* end = nullptr;
  value = static_cast<float>(strtod(token, &end));
  return end != token && *end == '\0';
}

bool parseUnsignedLongToken(char* token, unsigned long& value) {
  if (token == nullptr) {
    return false;
  }

  char* end = nullptr;
  const unsigned long parsed = strtoul(token, &end, 10);
  if (end == token || *end != '\0') {
    return false;
  }

  value = parsed;
  return true;
}

bool parseIntToken(char* token, int& value) {
  if (token == nullptr) {
    return false;
  }

  char* end = nullptr;
  const long parsed = strtol(token, &end, 10);
  if (end == token || *end != '\0') {
    return false;
  }

  value = static_cast<int>(parsed);
  return true;
}

}  // namespace

bool SerialCommands::poll(Stream& serial,
                          Command& command,
                          float currentKp,
                          float currentKi,
                          float currentKd) {
  while (serial.available() > 0) {
    const int incoming = serial.read();
    if (incoming < 0) {
      break;
    }

    if (incoming == '\r') {
      continue;
    }

    if (incoming == '\n') {
      buffer_[length_] = '\0';
      length_ = 0;
      return parseLine(buffer_, command, currentKp, currentKi, currentKd);
    }

    if (length_ < (AppConfig::COMMAND_BUFFER_SIZE - 1)) {
      buffer_[length_++] = static_cast<char>(incoming);
    }
  }

  return false;
}

void SerialCommands::printHelp(Stream& serial) {
  serial.println(F("Commands:"));
  serial.println(F("  status"));
  serial.println(F("  statuscsv"));
  serial.println(F("  pid <kp> <ki> <kd>"));
  serial.println(F("  kp <value>"));
  serial.println(F("  ki <value>"));
  serial.println(F("  kd <value>"));
  serial.println(F("  run"));
  serial.println(F("  arm [samples] [trigger_delta] [interval_ms]"));
  serial.println(F("  capture [samples] [interval_ms]"));
  serial.println(F("  cancel"));
  serial.println(F("  reset"));
  serial.println(F("  stop"));
  serial.println(F("  help"));
}

void SerialCommands::printStatus(Stream& serial,
                                 const ControlTelemetry& telemetry,
                                 float kp,
                                 float ki,
                                 float kd,
                                 bool controllerEnabled,
                                 CaptureState captureState,
                                 const CaptureConfig& captureConfig) {
  serial.print(F("PID kp="));
  serial.print(kp, 4);
  serial.print(F(", ki="));
  serial.print(ki, 4);
  serial.print(F(", kd="));
  serial.println(kd, 4);

  serial.print(F("Latest setpoint="));
  serial.print(telemetry.setpoint);
  serial.print(F(", feedback="));
  serial.print(telemetry.feedback);
  serial.print(F(", error="));
  serial.println(telemetry.error);

  serial.print(F("Motor pwm="));
  serial.print(telemetry.motor.pwm);
  serial.print(F(", direction="));
  serial.print(telemetry.motor.direction);
  serial.print(F(", deadband="));
  serial.print(telemetry.motor.inDeadband ? 1 : 0);
  serial.print(F(", saturated="));
  serial.println(telemetry.motor.saturated ? 1 : 0);

  serial.print(F("Controller="));
  serial.println(controllerEnabled ? F("enabled") : F("disabled"));

  serial.print(F("Capture state="));
  switch (captureState) {
    case CaptureState::Idle:
      serial.println(F("idle"));
      break;
    case CaptureState::Armed:
      serial.println(F("armed"));
      break;
    case CaptureState::Capturing:
      serial.println(F("capturing"));
      break;
  }

  serial.print(F("Capture config samples="));
  serial.print(captureConfig.sampleCount);
  serial.print(F(", trigger_delta="));
  serial.print(captureConfig.triggerDelta);
  serial.print(F(", interval_ms="));
  serial.println(captureConfig.intervalMs);
}

void SerialCommands::printStatusCsv(Stream& serial,
                                    const ControlTelemetry& telemetry,
                                    float kp,
                                    float ki,
                                    float kd,
                                    bool controllerEnabled,
                                    CaptureState captureState,
                                    const CaptureConfig& captureConfig) {
  serial.print(F("status,"));
  serial.print(telemetry.timestampMs);
  serial.print(',');
  serial.print(telemetry.setpoint);
  serial.print(',');
  serial.print(telemetry.feedback);
  serial.print(',');
  serial.print(telemetry.error);
  serial.print(',');
  serial.print(telemetry.pid.p, 4);
  serial.print(',');
  serial.print(telemetry.pid.i, 4);
  serial.print(',');
  serial.print(telemetry.pid.d, 4);
  serial.print(',');
  serial.print(telemetry.pid.output, 4);
  serial.print(',');
  serial.print(telemetry.motor.pwm);
  serial.print(',');
  serial.print(telemetry.motor.direction);
  serial.print(',');
  serial.print(telemetry.motor.inDeadband ? 1 : 0);
  serial.print(',');
  serial.print(telemetry.motor.saturated ? 1 : 0);
  serial.print(',');
  serial.print(kp, 4);
  serial.print(',');
  serial.print(ki, 4);
  serial.print(',');
  serial.print(kd, 4);
  serial.print(',');
  serial.print(controllerEnabled ? 1 : 0);
  serial.print(',');
  serial.print(static_cast<uint8_t>(captureState));
  serial.print(',');
  serial.print(captureConfig.sampleCount);
  serial.print(',');
  serial.print(captureConfig.triggerDelta);
  serial.print(',');
  serial.println(captureConfig.intervalMs);
}

bool SerialCommands::parseLine(char* line,
                               Command& command,
                               float currentKp,
                               float currentKi,
                               float currentKd) {
  command = {};

  char* context = nullptr;
  char* token = strtok_r(line, " \t", &context);
  if (token == nullptr) {
    return false;
  }

  if (strcmp(token, "help") == 0) {
    command.type = CommandType::Help;
    return true;
  }

  if (strcmp(token, "status") == 0) {
    command.type = CommandType::Status;
    return true;
  }

  if (strcmp(token, "statuscsv") == 0) {
    command.type = CommandType::StatusCsv;
    return true;
  }

  if (strcmp(token, "cancel") == 0) {
    command.type = CommandType::CancelCapture;
    return true;
  }

  if (strcmp(token, "run") == 0) {
    command.type = CommandType::RunController;
    return true;
  }

  if (strcmp(token, "reset") == 0) {
    command.type = CommandType::ResetController;
    return true;
  }

  if (strcmp(token, "stop") == 0) {
    command.type = CommandType::StopMotor;
    return true;
  }

  if (strcmp(token, "pid") == 0 || strcmp(token, "kp") == 0 || strcmp(token, "ki") == 0 ||
      strcmp(token, "kd") == 0) {
    return parsePidCommand(token, context, command, currentKp, currentKi, currentKd);
  }

  if (strcmp(token, "arm") == 0 || strcmp(token, "capture") == 0) {
    return parseCaptureCommand(token, context, command);
  }

  command.type = CommandType::Help;
  return true;
}

bool SerialCommands::parsePidCommand(char* firstToken,
                                     char* context,
                                     Command& command,
                                     float currentKp,
                                     float currentKi,
                                     float currentKd) {
  command.type = CommandType::SetPid;
  command.kp = currentKp;
  command.ki = currentKi;
  command.kd = currentKd;

  if (strcmp(firstToken, "pid") == 0) {
    if (!parseFloatToken(nextToken(context), command.kp) ||
        !parseFloatToken(nextToken(context), command.ki) ||
        !parseFloatToken(nextToken(context), command.kd)) {
      command.type = CommandType::Help;
    }
    return true;
  }

  float parsedValue = 0.0f;
  if (!parseFloatToken(nextToken(context), parsedValue)) {
    command.type = CommandType::Help;
    return true;
  }

  if (strcmp(firstToken, "kp") == 0) {
    command.kp = parsedValue;
  } else if (strcmp(firstToken, "ki") == 0) {
    command.ki = parsedValue;
  } else {
    command.kd = parsedValue;
  }

  return true;
}

bool SerialCommands::parseCaptureCommand(char* firstToken, char* context, Command& command) {
  command.type = strcmp(firstToken, "arm") == 0 ? CommandType::ArmCapture : CommandType::StartCapture;
  command.captureConfig.sampleCount = AppConfig::DEFAULT_CAPTURE_SAMPLES;
  command.captureConfig.intervalMs = AppConfig::DEFAULT_CAPTURE_INTERVAL_MS;
  command.captureConfig.triggerDelta = AppConfig::DEFAULT_TRIGGER_DELTA;

  char* token = nextToken(context);
  if (token != nullptr) {
    unsigned long parsed = 0;
    if (!parseUnsignedLongToken(token, parsed)) {
      command.type = CommandType::Help;
      return true;
    }
    command.captureConfig.sampleCount = static_cast<size_t>(parsed);
  }

  token = nextToken(context);
  if (token != nullptr) {
    if (command.type == CommandType::ArmCapture) {
      int parsed = 0;
      if (!parseIntToken(token, parsed)) {
        command.type = CommandType::Help;
        return true;
      }
      command.captureConfig.triggerDelta = parsed;

      token = nextToken(context);
      if (token != nullptr) {
        unsigned long parsedInterval = 0;
        if (!parseUnsignedLongToken(token, parsedInterval)) {
          command.type = CommandType::Help;
          return true;
        }
        command.captureConfig.intervalMs = parsedInterval;
      }
    } else {
      unsigned long parsedInterval = 0;
      if (!parseUnsignedLongToken(token, parsedInterval)) {
        command.type = CommandType::Help;
        return true;
      }
      command.captureConfig.intervalMs = parsedInterval;
    }
  }

  return true;
}

char* SerialCommands::nextToken(char*& context) {
  return strtok_r(nullptr, " \t", &context);
}
