import sys
import requests
import os.path
import subprocess
import time
import datetime as dt
from datetime import datetime
from datetime import timedelta
from optparse import OptionParser
from led import run_goal_light, clear_goal_light
import multiprocessing

NHL_API_URL = "http://statsapi.web.nhl.com/api/v1/"


def get_team_id(team):
    teams_url = os.path.join(NHL_API_URL, "teams")
    response = requests.get(teams_url)
    for record in response.json()['teams']:
        if record['name'] == team:
            return record['id']
    return None


def check_game_today(team_id, today):
    schedule_url = os.path.join(NHL_API_URL, "schedule?teamId=%s&date=%s&expand=schedule.linescore" % (team_id, today))
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
    previous_power_play = False
    if game_state != "In Progress":
        play_intro_tune()
    while game_state != "Final":
        game_url = os.path.join(NHL_API_URL, "schedule?teamId=%s&expand=schedule.linescore" % team_id)
        response = requests.get(game_url)
        data = response.json()
        if previous_game_state == "Pre-Game" and game_state == "In Progress":
            play_puck_drop()
        if data['dates'][0]['games'][0]['linescore']['teams'][home_or_away]['goals'] > goals:
            play_goal_horn()
            goals = data['dates'][0]['games'][0]['linescore']['teams'][home_or_away]['goals']
        power_play = data['dates'][0]['games'][0]['linescore']['teams'][home_or_away]['powerPlay']
        if not previous_power_play and power_play:
            play_power_play_tune()
        game_state = data['dates'][0]['games'][0]['status']['detailedState']
        time.sleep(1)
        previous_power_play = power_play
        previous_game_state = game_state
    game_url = os.path.join(NHL_API_URL, "schedule?teamId=%s&expand=schedule.linescore" % team_id)
    response = requests.get(game_url)
    data = response.json()
    status_code = data['dates'][0]['games'][0]['status']['statusCode']
    if (home_or_away == "home" and status_code == "7") or (home_or_away == "away" and status_code == "6"):
        play_victory_tune()


def play_goal_horn():
    print("GOAL HORN")
    audio_process = subprocess.Popen(['/usr/bin/omxplayer', '/home/pi/nhlgoallight/audio/goal_horn_1.mp3'])
    print("GOAL LAMP")
    led_process = multiprocessing.Process(target=run_goal_light)
    led_process.start()
    if audio_process:
        while audio_process.poll() is None:
            time.sleep(1)
    else:
        time.sleep(30)
    led_process.terminate()
    clear_goal_light()


def play_intro_tune():
    print("INTRO")
    subprocess.Popen(['/usr/bin/omxplayer', '/home/pi/nhlgoallight/audio/intro.mp3'])


def play_power_play_tune():
    print("POWER PLAY")
    subprocess.Popen(['/usr/bin/omxplayer', '/home/pi/nhlgoallight/audio/power_play.mp3'])


def play_victory_tune():
    print("VICTORY")
    audio_process = subprocess.Popen(['/usr/bin/omxplayer', '/home/pi/nhlgoallight/audio/victory.mp3'])
    print("GOAL LAMP")
    led_process = multiprocessing.Process(target=run_goal_light)
    led_process.start()
    if audio_process:
        while audio_process.poll() is None:
            time.sleep(1)
    else:
        time.sleep(30)
    led_process.terminate()
    clear_goal_light()


def play_puck_drop():
    print("PUCK DROP")
    subprocess.Popen(['/usr/bin/omxplayer', '/home/pi/nhlgoallight/audio/puck_drop.mp3'])


def light_goal_lamp():
    print("GOAL LAMP")
    process = multiprocessing.Process(target=run_goal_light)
    process.start()
    time.sleep(30)
    process.terminate()
    clear_goal_light()


def sleep_until_tomorrow():
    tomorrows_date = (now + timedelta(days=1)).replace(hour=options.check_hour, minute=0, second=0)
    sleep_seconds = int((tomorrows_date - now).total_seconds())
    print("Sleeping %s seconds" % sleep_seconds)
    time.sleep(sleep_seconds)  # find better way to do this


def get_options():
    program = os.path.basename(sys.argv[0])
    parser = OptionParser(usage='%s --option] ' % program, description='NHL Goal lamp/horn',
                          version='%s version 0.1' % program)
    parser.add_option('-t', '--team', dest='team', metavar='<team>', default=None,
                      help='Team name including city, ex. San Jose Sharks')
    parser.add_option('-i', '--teamid', dest='team_id', metavar='<team_id>', default=28,
                      help='Team id from nhl.com api, ex. 28')
    parser.add_option('--nolight', '--nolamp', dest='no_light', metavar='<no_light>', default=None,
                      help='Do not enable goal light')
    parser.add_option('--nohorn', dest='no_horn', metavar='<no_horn>', default=None,
                      help='Do not enable goal horn')
    parser.add_option('--checktime', dest='check_hour', metavar='<check_time>', default=10,
                      help='Hour (24 hour) to check game info')

    (options, args) = parser.parse_args()
    return options


if __name__ == "__main__":
    options = get_options()
    if options.team_id:
        team_id = options.team_id
    elif options.team:
        team_id = get_team_id(options.team)
    else:
        print("--team or --teamid required")
        exit(1)
    while True:
        now = datetime.now()
        now_utc = datetime.utcnow()
        todays_date = now.strftime("%Y-%m-%d")
        game_info = check_game_today(team_id, todays_date)
        if not game_info:
            sleep_until_tomorrow()
            continue
        game_state = game_info['status']['detailedState']
        if game_state == "Final":
            sleep_until_tomorrow()
            continue
        start_time_utc = datetime.strptime(game_info['gameDate'], '%Y-%m-%dT%H:%M:%SZ')
        print("start_time: %s" % start_time_utc)
        seconds_until_start = int((start_time_utc - now_utc).total_seconds())
        print("seconds_until_start: %s" % seconds_until_start)
        if seconds_until_start > 0:
            time.sleep(seconds_until_start)
        if game_info['linescore']['teams']['home']['team']['id'] == team_id:
            home_or_away = "home"
        else:
            home_or_away = "away"
        if game_state != "Pre-Game" and game_state != "In Progress":
            print("Game state is not as it should be")
        goals = game_info['linescore']['teams'][home_or_away]['goals']
        monitor_game(team_id, home_or_away, game_state, goals)