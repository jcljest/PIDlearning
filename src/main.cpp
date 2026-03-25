#include <Arduino.h>

#include "AppConfig.h"
#include "AppTypes.h"
#include "CaptureSession.h"
#include "MotorDriver.h"
#include "PidController.h"
#include "Sensors.h"
#include "SerialCommands.h"

namespace {

Sensors sensors(AppConfig::SETPOINT_PIN, AppConfig::FEEDBACK_PIN, AppConfig::INVERT_FEEDBACK);
MotorDriver motor(AppConfig::EN_PIN,
                  AppConfig::IN1_PIN,
                  AppConfig::IN2_PIN,
                  AppConfig::DEAD_BAND,
                  AppConfig::MIN_DRIVE,
                  AppConfig::MAX_DRIVE);
PidController pid(AppConfig::DEFAULT_KP,
                  AppConfig::DEFAULT_KI,
                  AppConfig::DEFAULT_KD,
                  AppConfig::INTEGRAL_CONTRIBUTION_LIMIT);
CaptureSession capture(Serial);
SerialCommands commands;

ControlTelemetry telemetry;
unsigned long previousMicros = 0;
bool controllerEnabled = true;

void executeCommand(const Command& command) {
  switch (command.type) {
    case CommandType::None:
      break;

    case CommandType::Help:
      SerialCommands::printHelp(Serial);
      break;

    case CommandType::Status:
      SerialCommands::printStatus(Serial,
                                  telemetry,
                                  pid.kp(),
                                  pid.ki(),
                                  pid.kd(),
                                  controllerEnabled,
                                  capture.state(),
                                  capture.config());
      break;

    case CommandType::StatusCsv:
      SerialCommands::printStatusCsv(Serial,
                                     telemetry,
                                     pid.kp(),
                                     pid.ki(),
                                     pid.kd(),
                                     controllerEnabled,
                                     capture.state(),
                                     capture.config());
      break;

    case CommandType::SetPid:
      pid.setTunings(command.kp, command.ki, command.kd);
      pid.reset();
      Serial.print(F("PID updated to kp="));
      Serial.print(pid.kp(), 4);
      Serial.print(F(", ki="));
      Serial.print(pid.ki(), 4);
      Serial.print(F(", kd="));
      Serial.println(pid.kd(), 4);
      break;

    case CommandType::RunController:
      controllerEnabled = true;
      pid.reset();
      Serial.println(F("Controller enabled."));
      break;

    case CommandType::ArmCapture:
      capture.arm(command.captureConfig, telemetry.setpoint);
      break;

    case CommandType::StartCapture:
      capture.startImmediate(command.captureConfig, millis(), pid.kp(), pid.ki(), pid.kd());
      break;

    case CommandType::CancelCapture:
      capture.cancel();
      break;

    case CommandType::ResetController:
      pid.reset();
      Serial.println(F("PID state reset."));
      break;

    case CommandType::StopMotor:
      controllerEnabled = false;
      pid.reset();
      motor.stop();
      Serial.println(F("Controller disabled and motor stopped. Use 'run' to re-enable."));
      break;
  }
}

void pollCommands() {
  Command command;
  while (commands.poll(Serial, command, pid.kp(), pid.ki(), pid.kd())) {
    executeCommand(command);
  }
}

}  // namespace

void setup() {
  Serial.begin(AppConfig::SERIAL_BAUD);

  sensors.begin();
  motor.begin();
  pid.reset();

  previousMicros = micros();

  telemetry.timestampMs = millis();
  telemetry.setpoint = sensors.readSetpoint();
  telemetry.feedbackRaw = sensors.readFeedbackRaw();
  telemetry.feedback = sensors.readFeedback();
  telemetry.error = telemetry.setpoint - telemetry.feedback;
  telemetry.motor = motor.state();

  Serial.println(F("PID capture console ready."));
  SerialCommands::printHelp(Serial);
  Serial.println(F("Use 'arm' to wait for a setpoint step or 'capture' to start immediately."));
}

void loop() {
  pollCommands();

  const unsigned long nowMicros = micros();
  const unsigned long nowMillis = millis();
  const float dtSeconds = (nowMicros - previousMicros) / 1000000.0f;

  telemetry.timestampMs = nowMillis;
  telemetry.setpoint = sensors.readSetpoint();
  telemetry.feedbackRaw = sensors.readFeedbackRaw();
  telemetry.feedback = AppConfig::INVERT_FEEDBACK ? (1023 - telemetry.feedbackRaw) : telemetry.feedbackRaw;
  telemetry.error = telemetry.setpoint - telemetry.feedback;

  if (controllerEnabled) {
    telemetry.pid = pid.update(static_cast<float>(telemetry.setpoint),
                               static_cast<float>(telemetry.feedback),
                               dtSeconds);
    motor.drive(telemetry.pid.output);
  } else {
    telemetry.pid = {};
    motor.stop();
  }

  telemetry.motor = motor.state();

  capture.maybeTrigger(telemetry.setpoint, nowMillis, pid.kp(), pid.ki(), pid.kd());
  capture.maybeRecord(telemetry);

  previousMicros = nowMicros;
  delay(AppConfig::LOOP_PERIOD_MS);
}
