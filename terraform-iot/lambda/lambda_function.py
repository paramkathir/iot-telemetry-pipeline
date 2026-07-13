import json
import time
import boto3

dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table('DeviceTelemetryTF')

def lambda_handler(event, context):
    try:
        device_id = event['device_id']
        timestamp = event['timestamp']
        metrics = event['metrics']

        table.put_item(
            Item={
                'DeviceID': device_id,
                'Timestamp': int(timestamp),
                'Temperature': str(metrics['temperature_c']),
                'Humidity': str(metrics['humidity_pct']),
                'Voltage': str(metrics['voltage_mv']),
                'ProcessedAt': int(time.time())
            }
        )
        return {'statusCode': 200, 'body': 'Telemetry stored successfully.'}
    except Exception as e:
        print(f"Error processing: {str(e)}")
        raise e
