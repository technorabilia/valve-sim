import json
import logging
import logging.config
import random

from paho.mqtt import client as mqtt_client

import config
from valvemachine import ValveMachine

# mqtt
mqtt_broker = config.MQTT_BROKER
mqtt_port = config.MQTT_PORT
mqtt_client_id = "999"
mqtt_topic = "sensors/valves/+"  # all valve topics

# logging
logging.config.fileConfig('logging.ini', defaults={'logfile': 'validator.log'})
log = logging.getLogger(mqtt_topic)

previous_messages = {}


def connect_mqtt() -> mqtt_client:
    def on_connect(client, userdata, flags, rc):
        if rc == 0:
            log.debug("Connected to MQTT mqtt_broker!")
        else:
            log.error(f"Failed to connect [{rc}].")

    client = mqtt_client.Client(mqtt_client_id)
    client.on_connect = on_connect
    client.connect(mqtt_broker, mqtt_port)
    return client


def subscribe(client: mqtt_client):
    state_machines = {}

    def on_message(client, userdata, msg):
        global previous_messages # FIXME: global var

        mqtt_message = msg.payload.decode()
        mqtt_topic = msg.topic
        current_message = json.loads(mqtt_message)

        log.info(f"Received {current_message} from {mqtt_topic} topic")

        if current_message["valve_id"] in previous_messages:
            previous_message = previous_messages[current_message["valve_id"]]

            if current_message["timestamp"] - previous_message["timestamp"] > 5:
                log.debug("Possible faulty valve: {} seconds elapsed since last message".format(
                    current_message["timestamp"] - previous_message["timestamp"]))

            if current_message["timestamp"] <= previous_message["timestamp"]:
                log.error("Wrong timestamp: {}".format(
                    current_message["timestamp"]))
                log.error("PREV: {}".format(previous_message))
                log.error("CURR: {}".format(current_message))

            if current_message["id"] != previous_message["id"] + 1:
                log.error("Wrong id: {}".format(current_message["id"]))
                log.error("PREV: {}".format(previous_message))
                log.error("CURR: {}".format(current_message))

        # init state machine
        if current_message["valve_id"] not in state_machines:
            state_machine = ValveMachine()

            # sync state from last message
            if state_machine.current_state.value != current_message["value"]:
                apply_state(state_machine, current_message["value"])

            state_machines[current_message["valve_id"]] = state_machine
        else:
            # retrieve state machine for client-id
            state_machine = state_machines[current_message["valve_id"]]

            # apply state
            try:
                apply_state(state_machine, current_message["value"])
            except Exception as e:
                log.error("Wrong state: {} [{}]".format(
                    current_message["value"], str(e)))
                log.error("PREV: {}".format(previous_message))
                log.error("CURR: {}".format(current_message))

        previous_messages[current_message["valve_id"]] = current_message

    client.subscribe(mqtt_topic)
    client.on_message = on_message


def run():
    client = connect_mqtt()
    subscribe(client)
    client.loop_forever()


def apply_state(state_machine, message_state):
    if message_state == "opened":
        state_machine.open()
    elif message_state == "closed":
        state_machine.close()
    elif message_state == "faulty":
        state_machine.fault()


if __name__ == '__main__':
    run()
