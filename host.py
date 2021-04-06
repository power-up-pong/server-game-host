import os
import paho.mqtt.client as mqtt
import random
import json
import math
from time import sleep

# Constants
BROKER = 'test.mosquitto.org'  # CS MQTT broker
PORT = 1883
QOS = 0
USERNAME = 'cs326'  # broker username (if required)
PASSWORD = 'piot'  # broker password (if required)

PADDLE_WIDTH = 50
MAX_PADDLE_VALUE = 1023
GAME_CYCLE = 0.03
TIME_AFTER_SCORE = 1
MAX_BOUNCE_ANGLE = math.pi * 5 / 12
BALL_SPEED = 20

PADDLE_HALF = PADDLE_WIDTH // 2
X_CONSTRAINTS = [0, MAX_PADDLE_VALUE + PADDLE_HALF]
Y_CONSTRAINTS = [0, MAX_PADDLE_VALUE + PADDLE_HALF]
X_MIDDLE = X_CONSTRAINTS[1] // 2
Y_MIDDLE = Y_CONSTRAINTS[1] // 2


class PUP_Game_State:
    def __init__(self):
        self.player1_score = 0
        self.player2_score = 0

        self.client = mqtt.Client()
        self.client.username_pw_set(USERNAME, password=PASSWORD)
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        self.client.connect(BROKER, PORT, 60)
        self.client.loop_start()

        self.reset()

    def reset(self):
        self.paddle_pos1 = Y_MIDDLE
        self.paddle_pos2 = Y_MIDDLE
        self.ball_pos = [X_MIDDLE, Y_MIDDLE]
        self.ball_velocity = [BALL_SPEED * random.choice([-1, 1]), 0]
        self.publish_state()
        sleep(TIME_AFTER_SCORE)

    def on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            print('Connected to', BROKER)
        else:
            print('Connection to {} failed. Return code={}'.format(BROKER, rc))
            os._exit(1)

    def on_message(self, client, data, msg):
        if msg.topic == "pup/ctrl1":
            self.paddle_pos1 = int(msg.payload)
        elif msg.topic == "pup/ctrl2":
            self.paddle_pos2 = int(msg.payload)

    def get_state(self):
        game_state = {
            'paddle1': self.paddle_pos1,
            'paddle2': self.paddle_pos2,
            'ball': self.ball_pos,
            'player1_score': self.player1_score,
            'player2_score': self.player2_score
        }

        print(json.dumps(game_state))
        return json.dumps(game_state)

    def run_game_loop(self):
        while True:
            self.update_ball_pos()
            self.publish_state()
            sleep(GAME_CYCLE)

    def update_ball_pos(self):
        self.ball_pos[0] += self.ball_velocity[0]
        self.ball_pos[1] += self.ball_velocity[1]

        # Once the ball reaches the left side...
        if self.ball_pos[0] < X_CONSTRAINTS[0]:
            # Check if the ball hits player 1's paddle. If it does, update ball velocity. Otherwise, increase player 2's score and reset
            if self.paddle_pos1 - PADDLE_HALF < self.ball_pos[1] < self.paddle_pos1 + PADDLE_HALF:
                self.update_ball_velocity(1)
            else:
                self.player2_score += 1
                self.reset()

        # Once the ball reaches the right side...
        elif self.ball_pos[0] > X_CONSTRAINTS[1]:
            # Check if the ball hits player 2's paddle. If it does, update ball velocity. Otherwise, increase player 1's score and reset
            if self.paddle_pos2 - PADDLE_HALF < self.ball_pos[1] < self.paddle_pos2 + PADDLE_HALF:
                self.update_ball_velocity(2)
            else:
                self.player1_score += 1
                self.reset()

        # Bounce the ball off the ceiling and floor
        if self.ball_pos[1] < Y_CONSTRAINTS[0] or self.ball_pos[1] > Y_CONSTRAINTS[1]:
            self.ball_velocity[1] = -self.ball_velocity[1]

    # https://gamedev.stackexchange.com/questions/4253/in-pong-how-do-you-calculate-the-balls-direction-when-it-bounces-off-the-paddl
    def update_ball_velocity(self, paddle_num):
        # Select which paddle to evaluate and reset the ball position so it's not off the screen
        paddle_pos = 0
        if paddle_num == 1:
            paddle_pos = self.paddle_pos1
            self.ball_pos[0] = X_CONSTRAINTS[0]
        else:
            paddle_pos = self.paddle_pos2
            self.ball_pos[0] = X_CONSTRAINTS[1]

        # Calculate the angle and update the velocity
        relative_intersectY = paddle_pos - self.ball_pos[1]
        normalized_relative_intersectY = (relative_intersectY / (PADDLE_HALF))
        bounce_angle = normalized_relative_intersectY * MAX_BOUNCE_ANGLE
        prior_velocityX = self.ball_velocity[0]
        self.ball_velocity[0] = int(BALL_SPEED * math.cos(bounce_angle))
        self.ball_velocity[1] = int(BALL_SPEED * -math.sin(bounce_angle))

        # Switch the direction if the sign is wrong
        if (prior_velocityX < 0 and self.ball_velocity[0] < 0) or (prior_velocityX > 0 and self.ball_velocity[0] > 0):
            self.ball_velocity[0] = -self.ball_velocity[0]

    def publish_state(self):
        (result, num) = self.client.publish(
            'pup/game', self.get_state(), qos=QOS)
        if result != 0:
            print('PUBLISH returned error:', result)

    def get_client(self):
        return self.client


gs = PUP_Game_State()
client = gs.get_client()
client.subscribe("pup/ctrl1", qos=QOS)
client.subscribe("pup/ctrl2", qos=QOS)

try:
    gs.run_game_loop()
except KeyboardInterrupt:
    client.loop_stop()
    client.disconnect()
