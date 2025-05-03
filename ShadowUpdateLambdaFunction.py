import boto3
import json

client = boto3.client('iot-data', region_name='[Region]')

def lambda_handler(event, context):
    powerState = event['powerInput']
    throttleState = event['throttleInput']
    if(powerState == "None"):
        response = client.publish(
        topic='$aws/things/Power_Monitor/shadow/update',
        qos=1,
          payload=json.dumps(
            {"state": 
            {"desired": 
            {"throttle": throttleState,
            }
            }
            }))
    if(throttleState == "None"):
        response = client.publish(
        topic='$aws/things/Power_Monitor/shadow/update',
        qos=1,
          payload=json.dumps(
            {"state": 
            {"desired": 
            {"power": powerState,
            }
            }
            }))
    return(powerState, throttleState)
