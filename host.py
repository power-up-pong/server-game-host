import os
import paho.mqtt.client as mqtt
import random
import json
import math
from time import sleep, time

# Constants
BROKER = 'mqtt.eclipseprojects.io'
PORT = 1883
QOS = 0
USERNAME = 'cs326'  # broker username (if required)
PASSWORD = 'piot'  # broker password (if required)

GAME_STATE_TOPIC = 'pup/game'
GAME_PROPS_TOPIC = 'pup/game-props'
CTRL1_TOPIC = "pup/ctrl1"
CTRL2_TOPIC = "pup/ctrl2"
BUTTON_TOPIC = "pup/button"

INITIAL_PADDLE_WIDTH = 200
MAX_PADDLE_VALUE = 1023
GAME_CYCLE = 0.03
TIME_AFTER_SCORE = 1
MAX_BOUNCE_ANGLE = math.pi * 5 / 12
INITIAL_BALL_SPEED = 20
POWERUP_X_OFFSET = 200
POWERUP_GENERATION_TIME = 2
POWERUP_EFFECT_TIME = 5
POWERUP_RADIUS = 20
FASTBALL_SPEED_MULTIPLIER = 1.2

PADDLE_HALF = INITIAL_PADDLE_WIDTH // 2
X_CONSTRAINTS = [-PADDLE_HALF, MAX_PADDLE_VALUE + PADDLE_HALF]
Y_CONSTRAINTS = [-PADDLE_HALF, MAX_PADDLE_VALUE + PADDLE_HALF]
X_MIDDLE = X_CONSTRAINTS[1] // 2
Y_MIDDLE = Y_CONSTRAINTS[1] // 2


class PowerUp:
    def __init__(self):
        self.pos = [random.randint(X_CONSTRAINTS[0] + POWERUP_X_OFFSET, X_CONSTRAINTS[1] - POWERUP_X_OFFSET),
                    random.randint(Y_CONSTRAINTS[0], Y_CONSTRAINTS[1])]
        self.type = random.choice(['paddleGrow', 'fastBall'])
        self.owner = None
        self.time_used = None
        self.used = False

    def get_pos(self):
        return self.pos

    def get_type(self):
        return self.type

    def get_owner(self):
        return self.owner

    def get_dict(self):
        return {
            'pos': self.pos,
            'type': self.type,
            'owner': self.owner,
            'time_used': self.time_used,
        }

    def get_time_used(self):
        return self.time_used

    def set_pos(self, pos):
        self.pos = pos

    def set_owner(self, owner):
        self.owner = owner

    def set_time_used(self, time):
        self.time_used = time

    def set_used(self):
        self.used = not self.used

    def is_used(self):
        return self.used


class PUP_Game_State:
    def __init__(self):
        self.player1_score = 0
        self.player2_score = 0
        self.player1_connected = True
        self.player2_connected = True
        self.paddle_pos1 = Y_MIDDLE
        self.paddle_pos2 = Y_MIDDLE

        self.client = mqtt.Client()
        self.client.username_pw_set(USERNAME, password=PASSWORD)
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        self.client.connect(BROKER, PORT, 60)
        self.client.loop_start()

        self.publish_props()
        self.reset()

    def reset(self):
        self.paddle_width1 = INITIAL_PADDLE_WIDTH
        self.paddle_width2 = INITIAL_PADDLE_WIDTH
        self.ball_pos = [X_MIDDLE, Y_MIDDLE]
        self.ball_speed = INITIAL_BALL_SPEED
        self.ball_velocity = [INITIAL_BALL_SPEED * random.choice([-1, 1]), 0]
        self.last_hit = None
        self.powerups = []
        self.powerup_timer = time()
        self.publish_state()
        sleep(TIME_AFTER_SCORE)

    def on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            print('Connected to', BROKER)
        else:
            print('Connection to {} failed. Return code={}'.format(BROKER, rc))
            os._exit(1)

    def on_message(self, client, data, msg):
        if msg.topic == CTRL1_TOPIC:
            if not self.player1_connected:
                self.player1_connected = True
            self.paddle_pos1 = int(msg.payload)
        elif msg.topic == CTRL2_TOPIC:
            if not self.player2_connected:
                self.player2_connected = True
            self.paddle_pos2 = int(msg.payload)
        elif msg.topic == BUTTON_TOPIC:
            self.use_powerup(int(msg.payload))

    def get_state(self):
        powerup_dict = []
        for powerup in self.powerups:
            self.check_powerup_time(powerup)
            powerup_dict.append(powerup.get_dict())
        game_state = {
            'paddle1': self.paddle_pos1,
            'paddle2': self.paddle_pos2,
            'paddle1_width': self.paddle_width1,
            'paddle2_width': self.paddle_width2,
            'ball': self.ball_pos,
            'player1_score': self.player1_score,
            'player2_score': self.player2_score,
            'powerups': powerup_dict,
        }

        print(json.dumps(game_state))
        return json.dumps(game_state)

    def get_props(self):
        game_props = {
            'x_constraints': X_CONSTRAINTS,
            'y_constraints': Y_CONSTRAINTS,
            'powerup_radius': POWERUP_RADIUS,
        }
        return json.dumps(game_props)

    def generate_powerup(self):
        self.powerups.append(PowerUp())

    def check_powerup_time(self, powerup):
        powerup_time = powerup.get_time_used()
        if powerup_time is not None:
            if time() - powerup_time > POWERUP_EFFECT_TIME:
                self.stop_powerup(powerup)

    def use_powerup(self, player_id):
        for powerup in self.powerups:
            powerup_type = powerup.get_type()
            powerup_owner = powerup.get_owner()
            if powerup_owner == player_id and not powerup.is_used():
                powerup.set_used()
                powerup.set_time_used(time())
                if powerup_type == "paddleGrow":
                    if powerup_owner == 1:
                        self.paddle_width1 += INITIAL_PADDLE_WIDTH
                    elif powerup_owner == 2:
                        self.paddle_width2 += INITIAL_PADDLE_WIDTH
                elif powerup_type == "fastBall":
                    self.ball_velocity[0] *= FASTBALL_SPEED_MULTIPLIER
                    self.ball_velocity[1] *= FASTBALL_SPEED_MULTIPLIER
                break

    def stop_powerup(self, powerup):
        powerup_type = powerup.get_type()
        powerup_owner = powerup.get_owner()
        if powerup_type == "paddleGrow":
            if powerup_owner == 1:
                self.paddle_width1 -= INITIAL_PADDLE_WIDTH
            elif powerup_owner == 2:
                self.paddle_width2 -= INITIAL_PADDLE_WIDTH
        self.powerups.remove(powerup)

    def run_game_loop(self):
        while True:
            if self.player1_connected and self.player2_connected:
                if time() - self.powerup_timer > POWERUP_GENERATION_TIME:
                    self.generate_powerup()
                    self.powerup_timer = time()
                self.update_ball_pos()
                self.publish_state()
            sleep(GAME_CYCLE)

    def update_ball_pos(self):
        self.ball_pos[0] += self.ball_velocity[0]
        self.ball_pos[1] += self.ball_velocity[1]

        # Once the ball reaches the left side...
        if self.ball_pos[0] < X_CONSTRAINTS[0]:
            # Check if the ball hits player 1's paddle. If it does, update ball velocity. Otherwise, increase player 2's score and reset
            if self.paddle_pos1 - self.paddle_width1 // 2 < self.ball_pos[1] < self.paddle_pos1 + self.paddle_width1 // 2:
                self.update_ball_velocity(1)
                self.last_hit = 1
            else:
                self.player2_score += 1
                self.reset()

        # Once the ball reaches the right side...
        elif self.ball_pos[0] > X_CONSTRAINTS[1]:
            # Check if the ball hits player 2's paddle. If it does, update ball velocity. Otherwise, increase player 1's score and reset
            if self.paddle_pos2 - self.paddle_width2 // 2 < self.ball_pos[1] < self.paddle_pos2 + self.paddle_width2 // 2:
                self.update_ball_velocity(2)
                self.last_hit = 2
            else:
                self.player1_score += 1
                self.reset()

        # Loop through powerups
        for powerup in self.powerups:
            powerup_pos = powerup.get_pos()
            # If the ball hits an unclaimed powerup, give it to the player who last hit the ball
            if powerup_pos is not None:
                if powerup_pos[0] - POWERUP_RADIUS < self.ball_pos[0] < powerup_pos[0] + POWERUP_RADIUS and powerup_pos[1] - POWERUP_RADIUS < self.ball_pos[1] < powerup_pos[1] + POWERUP_RADIUS:
                    powerup.set_owner(self.last_hit)
                    powerup.set_pos(None)

        # Bounce the ball off the ceiling and floor
        if self.ball_pos[1] < Y_CONSTRAINTS[0] or self.ball_pos[1] > Y_CONSTRAINTS[1]:
            self.ball_velocity[1] *= -1

    # https://gamedev.stackexchange.com/questions/4253/in-pong-how-do-you-calculate-the-balls-direction-when-it-bounces-off-the-paddl
    def update_ball_velocity(self, paddle_num):
        # Select which paddle and paddle_width to evaluate and reset the ball position so it's not off the screen
        paddle_pos = 0
        paddle_width = 0
        if paddle_num == 1:
            paddle_pos = self.paddle_pos1
            paddle_width = self.paddle_width1
            self.ball_pos[0] = X_CONSTRAINTS[0]
        else:
            paddle_pos = self.paddle_pos2
            paddle_width = self.paddle_width2
            self.ball_pos[0] = X_CONSTRAINTS[1]

        # Calculate the angle and update the velocity
        relative_intersectY = paddle_pos - self.ball_pos[1]
        normalized_relative_intersectY = (
            relative_intersectY / (paddle_width // 2))
        bounce_angle = normalized_relative_intersectY * MAX_BOUNCE_ANGLE
        prior_velocityX = self.ball_velocity[0]
        self.ball_velocity[0] = int(
            self.ball_speed * math.cos(bounce_angle))
        self.ball_velocity[1] = int(
            self.ball_speed * -math.sin(bounce_angle))

        # Switch the direction if the sign is wrong
        if (prior_velocityX < 0 and self.ball_velocity[0] < 0) or (prior_velocityX > 0 and self.ball_velocity[0] > 0):
            self.ball_velocity[0] = -self.ball_velocity[0]

    def publish_state(self):
        (result, num) = self.client.publish(
            GAME_STATE_TOPIC, self.get_state(), qos=QOS)
        if result != 0:
            print('PUBLISH returned error:', result)

    def publish_props(self):
        (result, num) = self.client.publish(
            GAME_PROPS_TOPIC, self.get_props(), qos=QOS)
        if result != 0:
            print('PUBLISH returned error:', result)

    def get_client(self):
        return self.client


gs = PUP_Game_State()
client = gs.get_client()
client.subscribe(CTRL1_TOPIC, qos=QOS)
client.subscribe(CTRL2_TOPIC, qos=QOS)
client.subscribe(BUTTON_TOPIC, qos=QOS)

try:
    gs.run_game_loop()
except KeyboardInterrupt:
    client.loop_stop()
    client.disconnect()
