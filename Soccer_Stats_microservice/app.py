import os
import socket

from flask import Flask, request, jsonify
from flask_status import FlaskStatus
import py_eureka_client.eureka_client as eureka_client
import requests
import mysql.connector
from datetime import datetime

#http://127.0.0.1:5000/matches-by-date?date=20240131&league_code=0&timezone_utc=0:00&country_code=0
app = Flask(__name__)


#MySQL connector
db_connection = mysql.connector.connect(
    host="127.0.0.1",
    port=3306,
    user="root",
    password="mysql",
    database="soccer_ivents"
)

# Create a cursor object to interact with the database
cursor = db_connection.cursor()


headers = {
    'X-RapidAPI-Key': "",#here should be api key
    'X-RapidAPI-Host': "livescore-football.p.rapidapi.com"
}

#Status Endpoint
FlaskStatus(app)

def fetch_matches_by_date_from_db(date, league_code, country_code):
    # Check if data already exists in the database
    query = """
    SELECT * FROM matches 
    WHERE scheduled_date = %s AND league_code = %s AND country_code = %s
    """
    cursor.execute(query, (date, league_code, country_code))
    existing_data = cursor.fetchall()
    return existing_data

def store_matches_by_date_in_db(date, api_data):
    # Store the data in the database
    # Assuming you have a table 'matches' with appropriate columns
    insert_query = """
    INSERT INTO matches (scheduled_date, league_code, country_code, match_id, team_1, team_2, status, 
                        scheduled_time, league_name, country_name, country_id)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """
    for league_data in api_data:
        for match in league_data.get('matches', []):
            cursor.execute(insert_query, (
                date,
                league_data.get('league_code', ''),
                league_data.get('country_code', ''),
                match.get('match_id', ''),
                match.get('team_1', {}).get('name', ''),
                match.get('team_2', {}).get('name', ''),
                match.get('status', ''),
                match.get('time', {}).get('scheduled', ''),
                league_data.get('league_name', ''),
                league_data.get('country_name', ''),
                league_data.get('country_id', ''),
            ))

    db_connection.commit()

@app.route('/matches-by-date')
def matches_by_date():
    date = request.args.get('date', datetime.today().strftime('%Y%m%d'))
    league_code = request.args.get('league_code', '0')
    timezone_utc = request.args.get('timezone_utc', '0:00')
    country_code = request.args.get('country_code', '0')

    # Check if at least one of the parameters is missing
    # if not date or not league_code or not timezone_utc or not country_code:
    #     return jsonify({"error": "'date', 'league_code', 'timezone_utc', and 'country_code' are required parameters."}), 400

    # Try to fetch data from the database
    existing_data = fetch_matches_by_date_from_db(date, league_code, country_code)

    if existing_data:
        # Data already exists in the database, return it
        return jsonify(existing_data)

    # Data doesn't exist, fetch from API
    url = "https://livescore-football.p.rapidapi.com/soccer/matches-by-date"
    querystring = {"date": str(date)}
        # , "league_code": str(league_code), "timezone_utc": str(timezone_utc),
        #            "country_code": str(country_code)}

    headers = {
        "X-RapidAPI-Key": "a0469d4c3bmsh20229adb5890402p170711jsn0b4b629e81dd",
        "X-RapidAPI-Host": "livescore-football.p.rapidapi.com"
    }

    response = requests.get(url, headers=headers, params=querystring)

    if response.status_code == 200:
        api_data = response.json().get("data", [])

        if api_data:
            # Store data in the database
            store_matches_by_date_in_db(date, api_data)

        return jsonify(api_data)
    else:
        # Handle the case where the API request fails
        return jsonify({"error": "Error fetching data from API"}), 500

def fetch_matches_by_league_from_db(country_code, league_code):
    # Check if data already exists in the database
    query = """
    SELECT * FROM matches 
    WHERE country_code = %s AND league_code = %s
    """
    cursor.execute(query, (country_code, league_code))
    existing_data = cursor.fetchall()
    return existing_data

def store_matches_by_league_in_db(country_code, league_code, api_data):
    # Store the data in the database
    # Assuming you have a table 'matches' with appropriate columns
    insert_query = """
    INSERT INTO matches (scheduled_date, country_code, league_code, match_id, team_1, team_2, status, 
                        scheduled_time, league_name, country_name, country_id)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """
    for match in api_data:
        cursor.execute(insert_query, (
            match['time']['scheduled'],
            country_code, league_code,
            match.get('match_id', ''),
            match.get('team_1', ''),
            match.get('team_2', ''),
            match.get('status', ''),
            match.get('scheduled', ''),
            match.get('league_name', ''),
            match.get('country_name', ''),
            match.get('country_id', ''),
        ))

    db_connection.commit()

@app.route('/matches-by-league')
def matches_by_league():
    country_code = request.args.get('country_code')
    league_code = request.args.get('league_code')

    # Check if at least one of the parameters is missing
    if not country_code or not league_code:
        return jsonify({"error": "'country_code' and 'league_code' are required parameters."}), 400

    # Try to fetch data from the database
    existing_data = fetch_matches_by_league_from_db(country_code, league_code)

    if existing_data:
        # Data already exists in the database, return it
        return jsonify(existing_data)

    # Data doesn't exist, fetch from API
    url = "https://livescore-football.p.rapidapi.com/soccer/matches-by-league"
    querystring = {"country_code": country_code, "league_code": league_code, "timezone_utc": "0:00"}

    response = requests.get(url, headers=headers, params=querystring)

    if response.status_code == 200:
        api_data = response.json().get("data", [])

        if api_data:
            # Store data in the database
            store_matches_by_league_in_db(country_code, league_code, api_data)

        return jsonify(api_data)
    else:
        # Handle the case where the API request fails
        return jsonify({"error": "Error fetching data from API"}), 500

#Fetch current league table from db
def fetch_league_table_from_db(country_code, league_code):
    # Check if data already exists in the database
    query = "SELECT * FROM leagues_results WHERE country_code = %s AND league_code = %s"
    cursor.execute(query, (country_code, league_code))
    existing_data = cursor.fetchone()
    return existing_data

#Store current league table into db
# def store_league_table_in_db(country_code, league_code, api_data):
#     # Store the data in the database
#     # Assuming you have a table 'league_tables' with appropriate columns
#     insert_query = """
#     INSERT INTO leagues_results (
#         country_code, league_code,
#         total_draw, total_games_played, total_goals_against, total_goals_diff, total_goals_for,
#         total_lost, total_points, total_rank, total_team_id, total_team_name, total_won,
#         home_draw, home_games_played, home_goals_against, home_goals_diff, home_goals_for,
#         home_lost, home_points, home_rank, home_team_id, home_team_name, home_won,
#         away_draw, away_games_played, away_goals_against, away_goals_diff, away_goals_for,
#         away_lost, away_points, away_rank, away_team_id, away_team_name, away_won
#     ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
#     """
#     cursor.execute(insert_query, (
#         country_code, league_code,
#         api_data['total'][0]['draw'], api_data['total'][0]['games_played'],
#         api_data['total'][0]['goals_against'], api_data['total'][0]['goals_diff'],
#         api_data['total'][0]['goals_for'], api_data['total'][0]['lost'],
#         api_data['total'][0]['points'], api_data['total'][0]['rank'],
#         api_data['total'][0]['team_id'], api_data['total'][0]['team_name'],
#         api_data['total'][0]['won'],
#         api_data['home'][0]['draw'], api_data['home'][0]['games_played'],
#         api_data['home'][0]['goals_against'], api_data['home'][0]['goals_diff'],
#         api_data['home'][0]['goals_for'], api_data['home'][0]['lost'],
#         api_data['home'][0]['points'], api_data['home'][0]['rank'],
#         api_data['home'][0]['team_id'], api_data['home'][0]['team_name'],
#         api_data['home'][0]['won'],
#         api_data['away'][0]['draw'], api_data['away'][0]['games_played'],
#         api_data['away'][0]['goals_against'], api_data['away'][0]['goals_diff'],
#         api_data['away'][0]['goals_for'], api_data['away'][0]['lost'],
#         api_data['away'][0]['points'], api_data['away'][0]['rank'],
#         api_data['away'][0]['team_id'], api_data['away'][0]['team_name'],
#         api_data['away'][0]['won']
#     ))
#     db_connection.commit()

#Update current league table into db

def store_league_table_in_db(country_code, league_code, api_data):
    # Store the data in the database
    # Assuming you have a table 'league_tables' with appropriate columns
    insert_query = """
    INSERT INTO leagues_results (
        country_code, league_code,
        total_draw, total_games_played, total_goals_against, total_goals_diff, total_goals_for,
        total_lost, total_points, total_rank, total_team_id, total_team_name, total_won,
        home_draw, home_games_played, home_goals_against, home_goals_diff, home_goals_for,
        home_lost, home_points, home_rank, home_team_id, home_team_name, home_won,
        away_draw, away_games_played, away_goals_against, away_goals_diff, away_goals_for,
        away_lost, away_points, away_rank, away_team_id, away_team_name, away_won
    ) VALUES (
        %(country_code)s, %(league_code)s,
        %(total_draw)s, %(total_games_played)s, %(total_goals_against)s, %(total_goals_diff)s,
        %(total_goals_for)s, %(total_lost)s, %(total_points)s, %(total_rank)s,
        %(total_team_id)s, %(total_team_name)s, %(total_won)s,
        %(home_draw)s, %(home_games_played)s, %(home_goals_against)s, %(home_goals_diff)s,
        %(home_goals_for)s, %(home_lost)s, %(home_points)s, %(home_rank)s,
        %(home_team_id)s, %(home_team_name)s, %(home_won)s,
        %(away_draw)s, %(away_games_played)s, %(away_goals_against)s, %(away_goals_diff)s,
        %(away_goals_for)s, %(away_lost)s, %(away_points)s, %(away_rank)s,
        %(away_team_id)s, %(away_team_name)s, %(away_won)s
    )
    """

    cursor.execute(insert_query, {
        'country_code': country_code,
        'league_code': league_code,
        'total_draw': api_data['total'][0]['draw'],
        'total_games_played': api_data['total'][0]['games_played'],
        'total_goals_against': api_data['total'][0]['goals_against'],
        'total_goals_diff': api_data['total'][0]['goals_diff'],
        'total_goals_for': api_data['total'][0]['goals_for'],
        'total_lost': api_data['total'][0]['lost'],
        'total_points': api_data['total'][0]['points'],
        'total_rank': api_data['total'][0]['rank'],
        'total_team_id': api_data['total'][0]['team_id'],
        'total_team_name': api_data['total'][0]['team_name'],
        'total_won': api_data['total'][0]['won'],
        'home_draw': api_data['home'][0]['draw'],
        'home_games_played': api_data['home'][0]['games_played'],
        'home_goals_against': api_data['home'][0]['goals_against'],
        'home_goals_diff': api_data['home'][0]['goals_diff'],
        'home_goals_for': api_data['home'][0]['goals_for'],
        'home_lost': api_data['home'][0]['lost'],
        'home_points': api_data['home'][0]['points'],
        'home_rank': api_data['home'][0]['rank'],
        'home_team_id': api_data['home'][0]['team_id'],
        'home_team_name': api_data['home'][0]['team_name'],
        'home_won': api_data['home'][0]['won'],
        'away_draw': api_data['away'][0]['draw'],
        'away_games_played': api_data['away'][0]['games_played'],
        'away_goals_against': api_data['away'][0]['goals_against'],
        'away_goals_diff': api_data['away'][0]['goals_diff'],
        'away_goals_for': api_data['away'][0]['goals_for'],
        'away_lost': api_data['away'][0]['lost'],
        'away_points': api_data['away'][0]['points'],
        'away_rank': api_data['away'][0]['rank'],
        'away_team_id': api_data['away'][0]['team_id'],
        'away_team_name': api_data['away'][0]['team_name'],
        'away_won': api_data['away'][0]['won'],
    })

    db_connection.commit()


def update_league_table_in_db(country_code, league_code, api_data):
    # Update the data in the database
    # Assuming you have a table 'league_tables' with appropriate columns
    update_query = """
    UPDATE leagues_results SET
        total_draw = %s, total_games_played = %s,
        total_goals_against = %s, total_goals_diff = %s, total_goals_for = %s,
        total_lost = %s, total_points = %s, total_rank = %s,
        total_team_id = %s, total_team_name = %s, total_won = %s,
        home_draw = %s, home_games_played = %s,
        home_goals_against = %s, home_goals_diff = %s, home_goals_for = %s,
        home_lost = %s, home_points = %s, home_rank = %s,
        home_team_id = %s, home_team_name = %s, home_won = %s,
        away_draw = %s, away_games_played = %s,
        away_goals_against = %s, away_goals_diff = %s, away_goals_for = %s,
        away_lost = %s, away_points = %s, away_rank = %s,
        away_team_id = %s, away_team_name = %s, away_won = %s,
        created_at = %s
    WHERE country_code = %s AND league_code = %s
    """
    cursor.execute(update_query, (
        api_data['total'][0]['draw'], api_data['total'][0]['games_played'],
        api_data['total'][0]['goals_against'], api_data['total'][0]['goals_diff'],
        api_data['total'][0]['goals_for'], api_data['total'][0]['lost'],
        api_data['total'][0]['points'], api_data['total'][0]['rank'],
        api_data['total'][0]['team_id'], api_data['total'][0]['team_name'],
        api_data['total'][0]['won'],
        api_data['home'][0]['draw'], api_data['home'][0]['games_played'],
        api_data['home'][0]['goals_against'], api_data['home'][0]['goals_diff'],
        api_data['home'][0]['goals_for'], api_data['home'][0]['lost'],
        api_data['home'][0]['points'], api_data['home'][0]['rank'],
        api_data['home'][0]['team_id'], api_data['home'][0]['team_name'],
        api_data['home'][0]['won'],
        api_data['away'][0]['draw'], api_data['away'][0]['games_played'],
        api_data['away'][0]['goals_against'], api_data['away'][0]['goals_diff'],
        api_data['away'][0]['goals_for'], api_data['away'][0]['lost'],
        api_data['away'][0]['points'], api_data['away'][0]['rank'],
        api_data['away'][0]['team_id'], api_data['away'][0]['team_name'],
        api_data['away'][0]['won'],
        datetime.now(),
        country_code, league_code
    ))
    db_connection.commit()

#Get info about current league table
@app.route('/league-table')
def league_table():
    country_code = request.args.get('country_code')
    league_code = request.args.get('league_code')

    # Check if at least one of the parameters is missing
    if not country_code or not league_code:
        return jsonify({"error": "Both 'country_code' and 'league_code' are required parameters."}), 400

    # Try to fetch data from the database
    existing_data = fetch_league_table_from_db(country_code, league_code)

    # Check if the data in the database is from the current date
    if existing_data and existing_data[-1].date() == datetime.now().date():
        # Data in the database is up-to-date, return it
        return jsonify(existing_data)

    # Data doesn't exist or is outdated, fetch from API
    url = "https://livescore-football.p.rapidapi.com/soccer/league-table"
    querystring = {"country_code": country_code, "league_code": league_code}

    response = requests.get(url, headers=headers, params=querystring)

    if response.status_code == 200:
        api_data = response.json().get("data", {})

        if existing_data:
            # Update data in the database
            update_league_table_in_db(country_code, league_code, api_data)
        else:
            # Store data in the database
            store_league_table_in_db(country_code, league_code, api_data)

        return jsonify(api_data)
    else:
        # Handle the case where the API request fails
        return jsonify({"error": "Error fetching data from API"}), 500

@app.route('/live-matches')
def live_matches():
    url = "https://livescore-football.p.rapidapi.com/soccer/live-matches"

    querystring = {"timezone_utc": "0:00"}

    response = requests.get(url, headers=headers, params=querystring)
    if response.status_code == 200:
        api_data = response.json().get("data", {})
        return jsonify(api_data)
    else:
        # Handle the case where the API request fails
        return jsonify({"error": "Error fetching data from API"}), 500


# Close the cursor and database connection when the application shuts down
# @app.teardown_appcontext
# def close_db_connection(exception=None):
#     cursor.close()
#     db_connection.close()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ['port']))


eureka_client.init(eureka_server="http://localhost:8761",
                   app_name="Soccer-Stats-Server",
                   instance_port=int(os.environ['port']))


