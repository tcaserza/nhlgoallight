import sys
import requests
import os.path
import subprocess
import time
from datetime import datetime
from optparse import OptionParser
from led import run_goal_light

NHL_API_URL = "http://statsapi.web.nhl.com/api/v1/"


def get_team_id(team):
    teams_url = os.path.join(NHL_API_URL, "teams")
    response = requests.get(teams_url)
    for record in response.json()['teams']:
        if record['name'] == team:
            return record['id']
    return None


def check_game_today(team_id, today):
    schedule_url = os.path.join(NHL_API_URL, "schedule?teamId=%s&date=%s" % (team_id, today))
    response = requests.get(schedule_url)
    data = response.json()
    if data['totalGames'] != 0:
        return data['dates'][0]['games'][0]
    else:
        return None


def check_game_state(team_id):
    game_url = os.path.join(NHL_API_URL, "schedule?teamId=%s&expand=schedule.linescore" % team_id)
    response = requests.get(game_url)
    data = response.json()
    return data['dates'][0]['games'][0]['status']['detailedState']


def monitor_game(team_id, home_or_away, game_state, goals):
    # play start of game music
    while game_state != "Final":
        game_url = os.path.join(NHL_API_URL, "schedule?teamId=%s&expand=schedule.linescore" % team_id)
        response = requests.get(game_url)
        data = response.json()
        if data['dates'][0]['games'][0]['linescore']['teams'][home_or_away]['goals'] > goals:
            play_goal_horn()
            goals = data['dates'][0]['games'][0]['linescore']['teams'][home_or_away]['goals']
        #  add power play check
        game_state = data['dates'][0]['games'][0]['status']['detailedState']
        time.sleep(2)
    #  add victory goal horn


def play_power_play_tune():
    print("POWER PLAY")


def play_goal_horn():
    print("GOAL HORN")
    p = subprocess.Popen(['/usr/bin/omxplayer', '/home/pi/nhlgoallight/audio/goal_horn_1.mp3'])
    while p.poll() is None:
        run_goal_light(1)

def play_intro_tune():
    print("INTRO")
    subprocess.Popen(['/usr/bin/omxplayer', '/home/pi/nhlgoallight/audio/seek_and_destroy.mp3'])


def light_goal_lamp():
    print("GOAL LAMP")

def get_options():
    program = os.path.basename(sys.argv[0])
    parser = OptionParser(usage='%s --option] ' % program, description='NHL Goal lamp/horn',
                          version='%s version 0.1' % program)
    parser.add_option('-t', '--team', dest='team', metavar='<team>', default=None,
                      help='Team name including city, ex. San Jose Sharks')
    parser.add_option('-i', '--teamid', dest='team_id', metavar='<team_id>', default=None,
                      help='Team id from nhl.com api, ex. 28')
    parser.add_option('--nolight', '--nolamp', dest='no_light', metavar='<no_light>', default=None,
                      help='Do not enable goal light')
    parser.add_option('--nohorn', dest='no_horn', metavar='<no_horn>', default=None,
                      help='Do not enable goal horn')
    (options, args) = parser.parse_args()
    return options


if __name__ == "__main__":
    options = get_options()
    team_id = "28"
    if options.team_id:
        team_id = options.team_id
    elif options.team:
        team_id = get_team_id(options.team)
    while True:
        now = datetime.now()
        now_utc = datetime.utcnow()
        todays_date = now.strftime("%Y-%m-%d")
        print("todays_date: %s" % todays_date)
        game_info = check_game_today(team_id, todays_date)
        if not game_info:
            time.sleep(86400)  # find better way to do this
        start_time = datetime.strptime(game_info['gameDate'], '%Y-%m-%dT%H:%M:%SZ')
        print("start_time: %s" % start_time)
        seconds_until_start = int((start_time - now_utc).total_seconds())
        print("seconds_until_start: %s" % seconds_until_start)
        time.sleep(seconds_until_start - 60)
        game_state = game_info['status']['detailedState']
        if game_info['linescore']['teams']['home']['team']['id'] == team_id:
            home_or_away = "home"
        else:
            home_or_away = "away"
        if game_state != "Pre-game" and game_state != "In Progress":
            print("Game state is not as it should be")
        if game_state == "Pre-game":
            play_intro_tune()
        goals = game_info['linescore']['teams'][home_or_away]['goals']
        monitor_game(team_id, home_or_away, game_state, goals)
