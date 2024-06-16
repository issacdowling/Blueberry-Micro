#!/bin/sh

echo "If you don't have your Python Venv activated, this will silently fail!"
echo "If you don't have your MQTT Broker (likely Mosquitto) running, this will not-silently fail!"

cd src/orchestrator
go build -o orchestrator orchestrator.go mqtt.go cores.go

cd ../utils/intent_parser
go build -o intent_parser_util_bb_core intent_parser_util.go checks.go mqtt.go

cd ../../../

./src/orchestrator/orchestrator