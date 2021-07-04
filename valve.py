import argparse
import json
import logging
import logging.config
import random
import time

from paho.mqtt import client as mqtt_client

import config
from valvemachine import ValveMachine

# args
parser = argparse.ArgumentParser(description="Valve simulator.")
parser.add_argument('--valve-id', required=True,
                    help="Valve ID.")
args = parser.parse_args()

# mqtt
mqtt_broker = config.MQTT_BROKER
mqtt_port = config.MQTT_PORT
mqtt_client_id = args.valve_id
mqtt_topic = f"sensors/valves/{mqtt_client_id}"

# logging
logging.config.fileConfig('logging.ini', defaults={'logfile': 'valve.log'})
log = logging.getLogger(mqtt_topic)


def connect_mqtt():
    def on_connect(client, userdata, flags, rc):
        if rc == 0:
            log.debug("Connected to MQTT mqtt_broker!")
        else:
            log.error(f"Failed to connect [{rc}].")

    client = mqtt_client.Client(mqtt_client_id)
    client.on_connect = on_connect
    client.connect(mqtt_broker, mqtt_port)

    return client


def publish(client):
    state_machine = ValveMachine()

    message_id = 1

    while True:
        time.sleep(config.MESSAGE_INTERVAL)

        message = {
            "id": message_id,
            "valve_id": mqtt_client_id,
            "state": state_machine.current_state.name,
            "value": state_machine.current_state.value,
            "timestamp": time.time()
        }

        # set wrong valve message
        if random.random() < 1 / config.CHANCE_WRONG_STATE:
            log.debug("Wrong state")
            message["value"] = "closed" if "opened" else "opened"
        elif random.random() < 1 / config.CHANCE_WRONG_TIMESTAMP:
            log.debug("Wrong timestamp")
            message["timestamp"] = message["timestamp"] + 20
        elif random.random() < 1 / config.CHANCE_WRONG_ID:
            log.debug("Wrong id")
            message["id"] = message["id"] - 1

        current_message = json.dumps(message)

        result = client.publish(mqtt_topic, current_message)
        status = result[0]
        if status == 0:
            log.info(f"Send {current_message} to topic {mqtt_topic}")
        else:
            log.error(f"Failed to send message to topic {mqtt_topic}")

        message_id += 1

        # set next valve state
        if random.random() < 1 / config.CHANCE_FAULTY_VALVE:
            log.debug("Faulty valve. Auto reset in 10 seconds.")
            state_machine.fault()
        else:
            state_machine.cycle()


def run():
    client = connect_mqtt()
    client.loop_start()
    publish(client)


if __name__ == '__main__':
    run()
