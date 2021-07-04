# Prerequisites
The prerequisites are:
* Python version 3 installed for the valve simulator and validator
* Git installed (or download the ZIP file)
* Docker installed for the message broker (or use an existing installation)

# Setup
## Valve simulator and validator
```
git clone https://github.com/technorabilia/valve-sim.git
cd valve-sim
python3 -m venv venv
source ./venv/bin/activate
pip3 install -r requirements.txt
```

## Message broker
Both valve simulator and validator use a MQTT message broker for exchanging messages.

In this case [EMQ X](https://www.emqx.io/) is used where EMQ X will run in a Docker container.

Start the Docker container by following the [Installation instructions](https://docs.emqx.io/en/broker/v4.3/getting-started/install.html) from the EMQ X documentation.

```
docker run -d \
  --name emqx-ee \
  -p 1883:1883 \
  -p 8081:8081 \
  -p 8083:8083 \
  -p 8084:8084 \
  -p 8883:8883 \
  -p 18083:18083 \
  emqx/emqx-ee:4.3.1
```

The broker connection information is configured in `config.py`.

```
MQTT_BROKER = "192.168.0.115"
MQTT_PORT = 1883
```

The EMQ X dashboard is available on port 18083 with username/password is admin/public.

# State machine
Diagram of the state machine for the valve.

![](https://github.com/technorabilia/valve-sim/blob/main/images/state-machine.gif)

In code:

```
class ValveMachine(StateMachine):
    opened = State("Valve opened")
    closed = State("Valve closed", initial=True)
    faulty = State("Valve faulty")

    open = closed.to(opened)

    close = opened.to(closed)
    fault = opened.to(faulty) | closed.to(faulty)
    reset = faulty.to(closed)
    cycle = open | close

    def on_enter_faulty(self):
        time.sleep(10)
        self.reset()
```

The initial state of the valve is closed.

If the valve cycles it will go from the opened state to the closed state and vice versa.

Once the valve is in the faulty state, it will automatically reset itself to the closed state in 10 seconds.

# Application
The application consists of two parts:
* Valve simulator
* Validator

Boths parts communicate using the message broker. The valve simulator publishes messages on a topic (one topic per valve) and the validator subscribes to all active valve topics.

The message format is:
```
{
  'id': 67,
  'valve_id': '1',
  'state': 'Valve open',
  'value': 'opened',
  'timestamp': 1625402771.7205207
}
```
Field | Description |
--- | ---
id | Message id
valve id | Valve id
state | Valve state long
value | Valve state short
timestamp | Timestamp in seconds since Unix epoch

## Valve simulator
The value simulator takes one argument valve-id and can be run from the command line.

```
$ python3 valve.py -h
usage: valve.py [-h] --valve-id VALVE_ID

Valve simulator.

optional arguments:
  -h, --help           show this help message and exit
  --valve-id VALVE_ID  Valve ID.
$
```

The valve simulator will simulate different failures:
* Faulty valve
* Wrong message state
* Wrong message timestamp
* Wrong message id (sequence)

The chance of a failure is configured in `config.py`.
```
CHANCE_WRONG_STATE = 50
CHANCE_WRONG_TIMESTAMP = 25
CHANCE_WRONG_ID = 15
CHANCE_FAULTY_VALVE = 100
```
E.g. a value of 25 means that there is a chance of 1 in 25 (or 4%) the failure will occur.

## Validator
The validator takes no arguments and can be run from the command line.

```
$ python3 validator.py
```

The validator will validate if a failure occurs:
* Faulty valve
* Wrong message state
* Wrong message timestamp
* Wrong message id (sequence)

The validation is done by applying the valve state change to the corresponding state machine in the validator and by comparing the previous message with the current message data.

# Example scenario
Run 3 valve simulators. As long as the valve id is unique, you can run as many valve simulators as you like.

```
python3 valve.py --valve-id 1
python3 valve.py --valve-id 2
python3 valve.py --valve-id 3
```

Run the valve validator. The validator will check all valve simulators simultaneously.

```
python3 validator.py
```

# Debugging
Logging settings in `logging.ini`.

The valve simulators will simultaneously log to `valve.log` and the validator to `validator.log`.

Other logging settings are shared between the valve simulators and the validator.

Logging levels used:
* DEBUG
* INFO
* ERROR

The default logging level is set to `DEBUG` in `logging.ini`. If the logging level is changed to `ERROR` then only the failures are recorded in the validator logfile.

If needed the logfiles of the valve(s) and validator can be manually merged and sorted for easier debugging.

The log messages in the valve simulator are marked with `DEBUG` if a failure occurs.

```
2021-07-04 17:28:00,272 sensors/valves/1 [INFO] Send {"id": 53, "valve_id": "1", "state": "Valve closed", "value": "closed", "timestamp": 1625412500.2711403} to topic sensors/valves/1
2021-07-04 17:28:02,275 sensors/valves/1 [DEBUG] Wrong id
2021-07-04 17:28:02,275 sensors/valves/1 [INFO] Send {"id": 53, "valve_id": "1", "state": "Valve open", "value": "opened", "timestamp": 1625412482.2749424} to topic sensors/valves/1
2021-07-04 17:28:04,279 sensors/valves/1 [INFO] Send {"id": 55, "valve_id": "1", "state": "Valve closed", "value": "closed", "timestamp": 1625412484.2793055} to topic sensors/valves/1
```

The log messages in de validator are marked with `ERROR` if a failure occurs followed by the previous (marked `PREV`) and current message (marked `CURR`).

```
2021-07-04 17:28:02,279 sensors/valves/+ [ERROR] Wrong id: 53
2021-07-04 17:28:02,280 sensors/valves/+ [ERROR] PREV: {'id': 53, 'valve_id': '1', 'state': 'Valve closed', 'value': 'closed', 'timestamp': 1625412500.2711403}
2021-07-04 17:28:02,280 sensors/valves/+ [ERROR] CURR: {'id': 53, 'valve_id': '1', 'state': 'Valve open', 'value': 'opened', 'timestamp': 1625412482.2749424}
2021-07-04 17:28:04,284 sensors/valves/+ [INFO] Received {'id': 55, 'valve_id': '1', 'state': 'Valve closed', 'value': 'closed', 'timestamp': 1625412484.2793055} from sensors/valves/1 topic
```

In this example the current message has a wrong message id (53 should be 54).

# Known issues
* Synchronisation of the state machine between valve simulator and validator has some quicks especially after a failure
* Failure recovery can give some false positives
