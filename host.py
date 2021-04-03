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

PADDLE_WIDTH = 50
MAX_PADDLE_VALUE = 1023
GAME_CYCLE = 0.1
TIME_AFTER_SCORE = 1
PADDLE_HALF = PADDLE_WIDTH // 2
X_CONSTRAINTS = [0, MAX_PADDLE_VALUE + PADDLE_HALF]
Y_CONSTRAINTS = [0, MAX_PADDLE_VALUE + PADDLE_HALF]
X_MIDDLE = X_CONSTRAINTS[1] // 2
Y_MIDDLE = Y_CONSTRAINTS[1] // 2


class Game_State:
    def __init__(self):
        self.player1_score = 0
        self.player2_score = 0
        self.reset()

        self.client = mqtt.Client()
        self.client.username_pw_set(USERNAME, password=PASSWORD)
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        self.client.subscribe("pup/ctrl1", qos=QOS)
        self.client.subscribe("pup/ctrl2", qos=QOS)
        self.client.connect(BROKER, PORT, 60)
        self.client.loop_start()

    def reset(self):
        self.publish_state()
        self.paddle_pos1 = Y_MIDDLE
        self.paddle_pos2 = Y_MIDDLE
        self.ball_pos = [X_MIDDLE, Y_MIDDLE]
        self.ball_Xvelocity = 70 * random.choice([-1, 1])
        self.ball_Yvelocity = 50 * random.choice([-1, 1])
        sleep(TIME_AFTER_SCORE)

    def on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            print('Connected to', BROKER)
        else:
            print('Connection to {} failed. Return code={}'.format(BROKER, rc))
            os._exit(1)

    def on_message(self, client, data, msg):
        if msg.topic == "pup/ctrl1":
            self.paddle_pos1 = msg.payload
        elif msg.topic == "pup/ctrl2":
            self.paddle_pos2 = msg.payload

    def get_state(self):
        return '\{\n"paddle1": {},\n"paddle2": {},\n"ball": {},\n"player1_score": {},\n"player2_score": {}\n\}'.format(
            self.paddle_pos1, self.paddle_pos2, self.ball_pos, self.player1_score, self.player2_score)

    def run_game_loop(self):
        self.update_ball_pos()

        self.publish_state()
        sleep(GAME_CYCLE)
        self.run_game_loop()

    def update_ball_pos(self):
        self.ball_pos[0] += self.ball_Xvelocity
        self.ball_pos[1] += self.ball_Yvelocity

        if self.ball_pos[0] < X_CONSTRAINTS[0]:
            if self.paddle_pos1 - PADDLE_HALF < self.ball_pos[1] < self.paddle_pos1 + PADDLE_HALF:
                self.ball_Xvelocity = -self.ball_Xvelocity
            else:
                self.player2_score += 1
                self.reset()

        elif self.ball_pos[0] > X_CONSTRAINTS[1]:
            if self.paddle_pos2 - PADDLE_HALF < self.ball_pos[1] < self.paddle_pos2 + PADDLE_HALF:
                self.ball_Xvelocity = -self.ball_Xvelocity
            else:
                self.player1_score += 1
                self.reset()

        if self.ball_pos[1] < Y_CONSTRAINTS[0] or self.ball_pos[1] > Y_CONSTRAINTS[1]:
            self.ball_Yvelocity = -self.ball_Yvelocity

    def publish_state(self):
        (result, num) = self.client.publish(
            'pup/game', self.get_state(), qos=QOS)
        if result != 0:
            print('PUBLISH returned error:', result)

    def get_client(self):
        return self.client


gs = Game_State()
try:
    gs.run_game_loop()
except KeyboardInterrupt:
    client = gs.get_client()
    client.loop_stop()
    client.disconnect()
