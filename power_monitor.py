from AWSIoTPythonSDK.MQTTLib import AWSIoTMQTTClient
import logging
import time
import argparse
import json
import board
import adafruit_ds3502
import adafruit_ina260
import RPi.GPIO as GPIO

from datetime import datetime

# Configuration

host = "XXXXXXXXXXXX-ats.iot.[Region].amazonaws.com"
certPath = "/home/[Rest of file path]//cert/"
clientId = "Power_Monitor"

# Topics

topic = "Power_Monitor"     # MQTT publish topic
topic_sub_loopback = "$aws/things/Power_Monitor/shadow/update/accepted"    # subscribe device shadow update
topic_sub_delta = "$aws/things/Power_Monitor/shadow/update/delta"          # subscribe device shadow delta
topic_shadow_update = "$aws/things/Power_Monitor/shadow/update"            # update/publish to device shadow


# Variables
i2c = board.I2C()
ds3502 = adafruit_ds3502.DS3502(i2c)
GPIO.setmode(GPIO.BCM)
GPIO.setup(22, GPIO.OUT)
relay=1
ina260 = adafruit_ina260.INA260(i2c)
loopCount = 0
pot = 100
amp = 0
power = "off"

# Function defined for device shadow operations

def display_current_on_led(amp):
    message = f"{amp:.1f}A"
    sense.show_message(message, scroll_speed=0.05, text_colour=[255, 0, 0])

def shadow_loopback_callback(client, userdata, message):
    try:
        payload = json.loads(message.payload)
        amp = payload.get("state", {}).get("reported", {}).get("current", None)
        if amp is not None:
            print(f"Received loopback current: {amp}")
            # display_current_on_led(amp)
    except Exception as e:
        print(f"[Shadow] Failed to parse message: {e}")

def shadow_delta_callback(client, userdata, message):
    global power
    global pot
    try:
        payload = json.loads(message.payload)
        desired_power = payload.get("state", {}).get("power", None)
        print(f"[Delta] Received desired power state: {desired_power}")
        desired_throttle = payload.get("state", {}).get("throttle", None)
        print(f"[Delta] Received desired throttle state: {desired_throttle}")
        if desired_power is not None:
            if desired_power == "on":
                GPIO.output(22, GPIO.HIGH)
            elif desired_power == "off":
                GPIO.output(22, GPIO.LOW)
            power = desired_power
        if desired_throttle is not None:
            pot = desired_throttle

        #if desired_power or desired_throttle is not None:
        update_power_reported_state(desired_power, desired_throttle)


    except Exception as e:
        print(f"[Delta] Failed to handle actuation: {e}")

def update_power_reported_state(power_value, throttle_value):
    payload = {
        "state": {
            "reported": {
                "power": power_value,
                "throttle": throttle_value
            },
            "desired": None
        }
    }
    myAWSIoTMQTTClient.publish(topic_shadow_update, json.dumps(payload), 1)
    print(f"[Shadow] Reported power state updated to: {power_value}")
    print(f"[Shadow] Reported throttle state updated to: {throttle_value}")

# Init AWSIoTMQTTClient

myAWSIoTMQTTClient = None
myAWSIoTMQTTClient = AWSIoTMQTTClient(clientId)
myAWSIoTMQTTClient.configureEndpoint(host, 8883)
myAWSIoTMQTTClient.configureCredentials(
	"{}RootCA1.pem".format(certPath),
	"{}RaspberryPi-private.pem.key".format(certPath),
	"{}RaspberryPi-cert.pem.crt".format(certPath))

# AWSIoTMQTTClient connection configuration

myAWSIoTMQTTClient.configureAutoReconnectBackoffTime(1, 32, 20)
myAWSIoTMQTTClient.configureOfflinePublishQueueing(-1)  # Infinite offline Publish queueing
myAWSIoTMQTTClient.configureDrainingFrequency(2)  # Draining: 2 Hz
myAWSIoTMQTTClient.configureConnectDisconnectTimeout(10)  # 10 sec
myAWSIoTMQTTClient.configureMQTTOperationTimeout(5)  # 5 sec
myAWSIoTMQTTClient.connect()

# Subscribe to shadow topics

myAWSIoTMQTTClient.subscribe(topic_sub_loopback, 1, shadow_loopback_callback)
myAWSIoTMQTTClient.subscribe(topic_sub_delta, 1, shadow_delta_callback)
print("Subscribed to loopback and delta topics.")

# Publish to the same topic in a loop forever

# Initialization
GPIO.output(22, GPIO.LOW)

while True:
	amp = round(((5.12-3.21*((100 - pot)/127))/872)*1000, 5)
	ds3502.wiper = 100-pot
	if(power == "off"): amp = 0
	timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")  # Local time, pandas-friendly

	payload = {
		"sequence": loopCount,
		"timestamp": timestamp,
		"throttle": pot,
		"current": amp,
		"power": power
		}
	messageJson = json.dumps(payload)
	myAWSIoTMQTTClient.publish(topic, messageJson, 1)
	print('Published topic %s: %s\n' % (topic, messageJson))
	loopCount += 1
	time.sleep(20)

myAWSIoTMQTTClient.disconnect()
