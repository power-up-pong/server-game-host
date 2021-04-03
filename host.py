import os
import paho.mqtt.client as mqtt
import random
from time import sleep

# Constants
BROKER = 'iot.cs.calvin.edu'  # CS MQTT broker
PORT = 1883
QOS = 0
USERNAME = 'cs326'  # broker username (if required)
PASSWORD = 'piot'  # broker password (if required)

PADDLE_WIDTH = 30
MAX_PADDLE_VALUE = 1023
X_CONSTRAINTS = [0, MAX_PADDLE_VALUE + PADDLE_WIDTH // 2]
Y_CONSTRAINTS = [0, MAX_PADDLE_VALUE + PADDLE_WIDTH // 2]
GAME_CYCLE = 0.1

# MQTT connection callback


def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print('Connected to', BROKER)
    else:
        print('Connection to {} failed. Return code={}'.format(BROKER, rc))
        os._exit(1)


class Game_State:
    def __init__(self):
        self.paddle_pos1 = 0
        self.paddle_pos2 = 0
        self.ball_pos = [X_CONSTRAINTS[1] // 2, Y_CONSTRAINTS[1] // 2]
        self.ball_Xvelocity = 3
        self.ball_Yvelocity = 2

        self.client = mqtt.Client()
        self.client.username_pw_set(USERNAME, password=PASSWORD)
        self.client.on_connect = on_connect
        self.client.connect(BROKER, PORT, 60)

        try:
            self.client.loop_start()
        except KeyboardInterrupt:
            self.client.loop_stop()
            self.client.disconnect()

    def get_state(self):
        return '\n"paddle1": {},\n"paddle2": {},\n"ball": {}\n'.format(str(self.paddle_pos1), str(self.paddle_pos2), str(self.ball_pos))

    def start(self):
        self.ball_pos[0] += self.ball_Xvelocity
        self.ball_pos[1] += self.ball_Yvelocity
        if self.ball_pos[0] < X_CONSTRAINTS[0] or self.ball_pos[0] > X_CONSTRAINTS[1]:
            self.ball_Xvelocity = -self.ball_Xvelocity
        if self.ball_pos[1] < Y_CONSTRAINTS[0] or self.ball_pos[1] > Y_CONSTRAINTS[1]:
            self.ball_Yvelocity = -self.ball_Yvelocity

        self.publish_state()
        sleep(GAME_CYCLE)
        self.start()

    def publish_state(self):
        (result, num) = self.client.publish(
            'pup/game', self.get_state(), qos=QOS)
        if result != 0:
            print('PUBLISH returned error:', result)


gs = Game_State()
gs.start()
