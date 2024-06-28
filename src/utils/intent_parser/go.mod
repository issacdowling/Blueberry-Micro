module blueberry/intent_parser

go 1.19

require github.com/eclipse/paho.mqtt.golang v1.4.3

replace "blueberry/gobloob" => ../../gobloob

require (
	blueberry/gobloob v0.0.0-00010101000000-000000000000
	github.com/gorilla/websocket v1.5.0 // indirect
	golang.org/x/net v0.8.0 // indirect
	golang.org/x/sync v0.1.0 // indirect
)
