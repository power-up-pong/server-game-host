'''
host.py hosts a Power-Up Pong game for two players. It handles all of the
game state such as paddle positions, ball positions, hits, misses, powerups, etc.
Written by Jon Ellis, Charlie Kornoelje, and Ryan Vreeke
for CS 326 Final Project at Calvin University, April 2021
'''

import os
import paho.mqtt.client as mqtt
import random
import json
import math
from time import sleep, time

# Constants
BROKER = 'iot.cs.calvin.edu'
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
BALL_SPEED = 20
POWERUP_X_OFFSET = 200
POWERUP_GENERATION_TIME = 2
POWERUP_EFFECT_TIME = 5
POWERUP_RADIUS = 20
FASTBALL_SPEED_MULTIPLIER = 1.5

PADDLE_HALF = INITIAL_PADDLE_WIDTH // 2
X_CONSTRAINTS = [-PADDLE_HALF, MAX_PADDLE_VALUE + PADDLE_HALF]
Y_CONSTRAINTS = [-PADDLE_HALF, MAX_PADDLE_VALUE + PADDLE_HALF]
X_MIDDLE = X_CONSTRAINTS[1] // 2
Y_MIDDLE = Y_CONSTRAINTS[1] // 2

DEV = False


class PowerUp:
    def __init__(self):
        self.pos = [random.randint(X_CONSTRAINTS[0] + POWERUP_X_OFFSET, X_CONSTRAINTS[1] - POWERUP_X_OFFSET),
                    random.randint(Y_CONSTRAINTS[0], Y_CONSTRAINTS[1])]
        self.type = random.choice(['paddleGrow', 'fastBall', 'trackBall'])
        self.owner = None
        self.time_used = None

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


class PUP_Player_State:
    def __init__(self, id):
        self.id = id
        self.score = 0
        self.connected = DEV
        self.paddle_pos = Y_MIDDLE
        self.paddle_width = INITIAL_PADDLE_WIDTH
        self.paddle_should_track = False
        self.powerups = []

    def get_id(self):
        return self.id

    def get_score(self):
        return self.score

    def is_connected(self):
        return self.connected

    def get_paddle_pos(self):
        return self.paddle_pos

    def get_paddle_width(self):
        return self.paddle_width

    def get_paddle_should_track(self):
        return self.paddle_should_track

    def get_powerups(self):
        return self.powerups

    def set_score(self, score):
        self.score = score

    def set_connected(self, connected):
        self.connected = connected

    def set_paddle_pos(self, pos):
        self.paddle_pos = pos

    def set_paddle_width(self, width):
        self.paddle_width = width

    def set_paddle_should_track(self, track):
        self.paddle_should_track = track

    def clear_powerups(self):
        self.powerups = []

    def add_powerup(self, powerup):
        self.powerups.append(powerup)

    def pop_powerup(self):
        return self.powerups.pop(0)

    def get_dict(self):
        powerup_dict = []
        for powerup in self.powerups:
            powerup_dict.append(powerup.get_dict())
        return {
            'id': self.id,
            'score': self.score,
            'paddle_pos': self.paddle_pos,
            'paddle_width': self.paddle_width,
            'powerups': powerup_dict
        }

    # If the top powerup of the queue has been used and its effect time has expired, remove and return it
    def get_expired_powerup(self):
        if len(self.powerups) > 0:
            powerup_time = self.powerups[0].get_time_used()
            if powerup_time is not None:
                if time() - powerup_time > POWERUP_EFFECT_TIME:
                    return self.pop_powerup()
        return None

    def increment_score(self):
        self.score += 1


class PUP_Game_State:
    def __init__(self):
        self.players = (PUP_Player_State(1), PUP_Player_State(2))
        self.track_offset = self.generate_track_offset()

        self.client = mqtt.Client()
        self.client.username_pw_set(USERNAME, password=PASSWORD)
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        self.client.connect(BROKER, PORT, 60)
        self.client.loop_start()

        self.publish_props()
        self.reset()

    def reset(self):
        for player in self.players:
            player.set_paddle_width(INITIAL_PADDLE_WIDTH)
            player.set_paddle_should_track(DEV)
            player.clear_powerups()

        self.ball_pos = [X_MIDDLE, Y_MIDDLE]
        self.ball_velocity = [BALL_SPEED * random.choice([-1, 1]), 0]
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
            self.handle_paddle_move(1, int(msg.payload))
        elif msg.topic == CTRL2_TOPIC:
            self.handle_paddle_move(2, int(msg.payload))
        elif msg.topic == BUTTON_TOPIC:
            self.use_powerup(int(msg.payload))

    def handle_paddle_move(self, player_id, new_pos):
        for player in self.players:
            if player.get_id() == player_id:
                if not player.is_connected():
                    player.set_connected(True)
                if not player.get_paddle_should_track():
                    player.set_paddle_pos(new_pos)

    def get_state(self):
        players_dict = []
        powerup_dict = []
        for player in self.players:
            players_dict.append(player.get_dict())
        for powerup in self.powerups:
            powerup_dict.append(powerup.get_dict())
        game_state = {
            'players': players_dict,
            'ball': self.ball_pos,
            'powerups': powerup_dict,
        }

        game_state_json = json.dumps(game_state)
        print(game_state_json)
        return game_state_json

    def get_props(self):
        game_props = {
            'x_constraints': X_CONSTRAINTS,
            'y_constraints': Y_CONSTRAINTS,
            'powerup_radius': POWERUP_RADIUS,
        }
        return json.dumps(game_props)

    def generate_powerup(self):
        self.powerups.append(PowerUp())

    def use_powerup(self, player_id):
        for player in self.players:
            if player_id == player.get_id():
                # Loop through the player's powerups and find the first in the queue which is not used
                for powerup in player.get_powerups():
                    powerup_type = powerup.get_type()
                    if powerup.get_time_used() is None:
                        # Once found, use the powerup effect
                        powerup.set_time_used(time())
                        if powerup_type == "paddleGrow":
                            player.set_paddle_width(
                                player.get_paddle_width() + INITIAL_PADDLE_WIDTH)
                        elif powerup_type == "fastBall":
                            self.ball_velocity[0] *= FASTBALL_SPEED_MULTIPLIER
                            self.ball_velocity[1] *= FASTBALL_SPEED_MULTIPLIER
                        elif powerup_type == "trackBall":
                            player.set_paddle_should_track(True)
                        break

    def stop_powerup(self, powerup):
        powerup_type = powerup.get_type()
        powerup_owner = powerup.get_owner()
        # Find which player owns the powerup and remove the effect
        for player in self.players:
            player_id = player.get_id()
            if powerup_owner == player_id:
                if powerup_type == "paddleGrow":
                    player.set_paddle_width(
                        player.get_paddle_width() - INITIAL_PADDLE_WIDTH)
                elif powerup_type == "trackBall":
                    player.set_paddle_should_track(False)

    def run_game_loop(self):
        while True:
            # if both players are connected
            if all([player.is_connected() for player in self.players]):
                self.handle_powerups()
                self.update_ball_pos()
                self.publish_state()
            sleep(GAME_CYCLE)

    def handle_powerups(self):
        if time() - self.powerup_timer > POWERUP_GENERATION_TIME:
            self.generate_powerup()
            self.powerup_timer = time()
        self.handle_expired_powerups()

    def handle_expired_powerups(self):
        for player in self.players:
            expired_powerup = player.get_expired_powerup()
            if expired_powerup is not None:
                self.stop_powerup(expired_powerup)

    def update_ball_pos(self):
        self.ball_pos[0] += self.ball_velocity[0]
        self.ball_pos[1] += self.ball_velocity[1]

        # Keep the ball in the constraints
        if self.ball_pos[1] < Y_CONSTRAINTS[0]:
            self.ball_pos[1] = Y_CONSTRAINTS[0]
        elif self.ball_pos[1] > Y_CONSTRAINTS[1]:
            self.ball_pos[1] = Y_CONSTRAINTS[1]

        for player in self.players:
            # Set paddle position to ball position (plus an offset) if trackBall powerup is activated
            paddle_width = player.get_paddle_width()
            paddle_half = paddle_width // 2
            if player.get_paddle_should_track():
                new_paddle_pos = self.ball_pos[1] + self.track_offset
                if 0 <= new_paddle_pos <= MAX_PADDLE_VALUE:
                    player.set_paddle_pos(new_paddle_pos)
                elif new_paddle_pos > MAX_PADDLE_VALUE:
                    player.set_paddle_pos(MAX_PADDLE_VALUE)
                else:
                    player.set_paddle_pos(0)

            player_id = player.get_id()
            paddle_pos = player.get_paddle_pos()
            paddle_top = paddle_pos + paddle_half
            paddle_bottom = paddle_pos - paddle_half

            self.handle_paddle_ball_bounce(
                player_id, paddle_bottom, paddle_top)

            self.check_powerup_hits(player)

        # Bounce the ball off the ceiling and floor
        if self.ball_pos[1] <= Y_CONSTRAINTS[0] or self.ball_pos[1] >= Y_CONSTRAINTS[1]:
            self.ball_velocity[1] *= -1

    def handle_paddle_ball_bounce(self, player_id, paddle_bottom, paddle_top):
        # Once the ball reaches the player's side of the screen...
        if (player_id == 1 and self.ball_pos[0] < X_CONSTRAINTS[0]) or (player_id == 2 and self.ball_pos[0] > X_CONSTRAINTS[1]):
            # Check if the ball hits a player's paddle. If it does, update ball velocity. Otherwise, increase the other player's score and reset
            if paddle_bottom <= self.ball_pos[1] <= paddle_top:
                self.update_ball_velocity(player_id)
                self.last_hit = player_id
                self.track_offset = self.generate_track_offset()
            else:
                self.increment_other_score(player_id)
                self.reset()

    def check_powerup_hits(self, player):
        # Loop through powerups
        for powerup in self.powerups:
            powerup_pos = powerup.get_pos()
            # If the ball hits an unclaimed powerup, give it to the player who last hit the ball
            if powerup_pos is not None:
                if powerup_pos[0] - POWERUP_RADIUS <= self.ball_pos[0] <= powerup_pos[0] + POWERUP_RADIUS and powerup_pos[1] - POWERUP_RADIUS <= self.ball_pos[1] <= powerup_pos[1] + POWERUP_RADIUS:
                    if self.last_hit == player.get_id():
                        powerup.set_owner(self.last_hit)
                        powerup.set_pos(None)
                        player.add_powerup(powerup)

    # https://gamedev.stackexchange.com/questions/4253/in-pong-how-do-you-calculate-the-balls-direction-when-it-bounces-off-the-paddl
    def update_ball_velocity(self, player_id):
        # Select which paddle and paddle_width to evaluate and reset the ball position so it's not off the screen
        paddle_pos = 0
        paddle_width = 0
        for player in self.players:
            if player.get_id() == player_id:
                paddle_pos = player.get_paddle_pos()
                paddle_width = player.get_paddle_width()
                self.ball_pos[0] = X_CONSTRAINTS[player_id - 1]

        # Calculate the angle and update the velocity
        relative_intersectY = paddle_pos - self.ball_pos[1]
        normalized_relative_intersectY = (
            relative_intersectY / (paddle_width // 2))
        bounce_angle = normalized_relative_intersectY * MAX_BOUNCE_ANGLE
        prior_velocityX = self.ball_velocity[0]
        self.ball_velocity[0] = int(
            BALL_SPEED * math.cos(bounce_angle))
        self.ball_velocity[1] = int(
            BALL_SPEED * -math.sin(bounce_angle))

        # Switch the direction if the sign is wrong
        if (prior_velocityX < 0 and self.ball_velocity[0] < 0) or (prior_velocityX > 0 and self.ball_velocity[0] > 0):
            self.ball_velocity[0] = -self.ball_velocity[0]

    def increment_other_score(self, other_player_id):
        for player in self.players:
            if player.get_id() != other_player_id:
                player.increment_score()

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

    def generate_track_offset(self):
        return random.randint(-PADDLE_HALF + 1, PADDLE_HALF - 1)


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
