import streamlit as st
import numpy as np
import pandas as pd
import requests
import matplotlib.pyplot as plt
import datetime
from requests.exceptions import RequestException

# -----------------------------
# 1. Roster Configuration
# -----------------------------
st.title("Fantasy Hockey Matchup Simulator")

st.subheader("⚙️ Configure Your Roster Spots (applies to both teams)")
center_spots = st.number_input("Number of Center spots", min_value=0, value=2, step=1)
lw_spots = st.number_input("Number of Left Wing spots", min_value=0, value=2, step=1)
rw_spots = st.number_input("Number of Right Wing spots", min_value=0, value=2, step=1)
d_spots = st.number_input("Number of Defense spots", min_value=0, value=2, step=1)
utility_spots = st.number_input("Number of Utility spots", min_value=0, value=2, step=1)
bench_spots = st.number_input("Number of Bench spots", min_value=0, value=3, step=1)
goalie_spots = st.number_input("Number of Goalie spots", min_value=0, value=1, step=1)

roster_config = {
    "Center": center_spots,
    "LW": lw_spots,
    "RW": rw_spots,
    "Defense": d_spots,
    "Utility": utility_spots,
    "Bench": bench_spots,
    "Goalie": goalie_spots
}

# -----------------------------
# 2. Category & Date Range Selection
# -----------------------------
# Updated list of available categories (make sure the API returns matching keys)
available_categories = [
    "Goals", "Assists", "Shots", "Hits", "Blocks",
    "Wins", "Saves", "Shutouts", "Power Play Points", "Faceoff Wins",
    "Plus/Minus", "Penalty Minutes", "Goals Against Average", "Save Percentage"
]

st.subheader("⚙️ Select Categories Used in Your Fantasy League")
selected_categories = st.multiselect(
    "Choose the categories your league tracks:",
    available_categories,
    default=["Goals", "Assists", "Shots", "Hits", "Blocks"]
)
# For category-based scoring, each selected category counts as one point.
custom_scoring = {cat: 1 for cat in selected_categories}

# Define category preferences:
# For categories where higher is better, use 1.
# For categories where lower is better (e.g., Penalty Minutes, Goals Against Average), use -1.
category_preferences = {
    "Goals": 1,
    "Assists": 1,
    "Shots": 1,
    "Hits": 1,
    "Blocks": 1,
    "Wins": 1,
    "Saves": 1,
    "Shutouts": 1,
    "Power Play Points": 1,
    "Faceoff Wins": 1,
    "Plus/Minus": 1,
    "Penalty Minutes": -1,
    "Goals Against Average": -1,
    "Save Percentage": 1
}

st.subheader("📆 Select Date Range for Simulation")
start_date = st.date_input("Select Start Date", datetime.date.today())
end_date = st.date_input("Select End Date", datetime.date.today() + datetime.timedelta(days=7))


# -----------------------------
# 3. NHL API Helper Functions
# -----------------------------
def search_player(name):
    """Search for NHL players matching the name."""
    url = f"https://suggest.svc.nhl.com/svc/suggest/v1/minplayers/{name}"
    try:
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        data = response.json()
        if "suggestions" in data:
            players = data["suggestions"]
            # Return a dict with player names as keys and NHL IDs as values.
            return {p.split("|")[0]: int(p.split("|")[1]) for p in players}
        else:
            st.error("No suggestions found for that player name.")
            return {}
    except RequestException as e:
        st.error("Error connecting to the NHL API. Please try again later.")
        # For debugging (viewable in logs):
        print("Connection error in search_player:", e)
        return {}


def get_player_stats(player_id, season="20232024"):
    """Get basic season stats for the selected categories for a given player."""
    url = f"https://statsapi.web.nhl.com/api/v1/people/{player_id}/stats?stats=statsSingleSeason&season={season}"
    try:
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        data = response.json()
        stats = data["stats"][0]["splits"][0]["stat"]
        # Return only stats for the selected categories.
        return {key: stats.get(key, 0) for key in selected_categories}
    except (IndexError, RequestException) as e:
        st.error("Error retrieving player stats.")
        print("Error in get_player_stats:", e)
        return {}


# -----------------------------
# 4. Placeholder Advanced Stats & Opponent Adjustments (Optional)
# -----------------------------
def compute_advanced_factor(advanced_stats):
    # Example: combine advanced metrics into one multiplier (placeholder logic)
    return (advanced_stats.get("Corsi", 50) * 0.3 +
            advanced_stats.get("Fenwick", 50) * 0.3 +
            advanced_stats.get("PDO", 100) * 0.4) / 100


def adjust_for_opponent(base_value, opponent_defense_rating, is_home):
    # Adjust performance based on opponent and home/away factor (placeholder logic)
    adjustment = 1 + (1 - opponent_defense_rating / 100)
    home_bonus = 1.05 if is_home else 0.95
    return base_value * adjustment * home_bonus


# -----------------------------
# 5. Simulation Functions
# -----------------------------
@st.cache_data
def simulate_matchup(team1, team2, scoring, start_date, end_date, num_simulations=500):
    """
    Aggregated simulation over the date range using all players.
    Teams are structured as nested dictionaries by position.
    """
    days = (end_date - start_date).days + 1
    team1_total = np.zeros(num_simulations)
    team2_total = np.zeros(num_simulations)

    # Iterate over each day and add simulated performance across all roster spots.
    for day in range(days):
        for team_dict, scores in [(team1, team1_total), (team2, team2_total)]:
            for pos, players in team_dict.items():
                for player, stats in players.items():
                    simulated_stats = {
                        stat: np.random.normal(value, value * 0.2, num_simulations)
                        for stat, value in stats.items()
                    }
                    scores += sum(scoring.get(stat, 0) * simulated_stats.get(stat, 0)
                                  for stat in selected_categories)
    team1_wins = np.sum(team1_total > team2_total)
    return team1_wins / num_simulations, (num_simulations - team1_wins) / num_simulations


def simulate_category_matchup(team1, team2, start_date, end_date, num_simulations=500):
    """
    Simulate each selected category independently over the date range and count
    which team wins each category. Adjust scores for categories where lower values
    are better. Returns the average number of category wins (rounded) for each team and ties.
    """
    days = (end_date - start_date).days + 1
    team1_cat_wins_list = []
    team2_cat_wins_list = []
    ties_list = []

    for _ in range(num_simulations):
        team1_cat_wins = 0
        team2_cat_wins = 0
        ties = 0

        for cat in selected_categories:
            team1_cat_score = 0
            team2_cat_score = 0

            # Sum performance over all roster spots for the category
            for team, cat_score in [(team1, 'team1'), (team2, 'team2')]:
                for pos, players in team.items():
                    for player, stats in players.items():
                        daily_scores = np.random.normal(stats.get(cat, 0), stats.get(cat, 0) * 0.2, days)
                        if team is team1:
                            team1_cat_score += np.sum(daily_scores)
                        else:
                            team2_cat_score += np.sum(daily_scores)

            # Adjust scores for categories where lower values are better
            if category_preferences.get(cat, 1) < 0:
                team1_cat_score *= -1
                team2_cat_score *= -1

            if team1_cat_score > team2_cat_score:
                team1_cat_wins += 1
            elif team2_cat_score > team1_cat_score:
                team2_cat_wins += 1
            else:
                ties += 1

        team1_cat_wins_list.append(team1_cat_wins)
        team2_cat_wins_list.append(team2_cat_wins)
        ties_list.append(ties)

    avg_team1_cat = np.mean(team1_cat_wins_list)
    avg_team2_cat = np.mean(team2_cat_wins_list)
    avg_ties = np.mean(ties_list)
    return round(avg_team1_cat), round(avg_team2_cat), round(avg_ties)


# -----------------------------
# 6. Input Teams (by Roster Position)
# -----------------------------
st.subheader("🏒 Enter Your Fantasy Teams")
team1, team2 = {}, {}

for team in ["Team 1", "Team 2"]:
    st.markdown(f"### {team}")
    team_data = {}  # Data organized by roster position
    for pos, count in roster_config.items():
        st.markdown(f"**{pos} Spots ({count})**")
        team_data[pos] = {}
        for i in range(count):
            player_name = st.text_input(f"Search Player for {team} - {pos} #{i + 1}", key=f"{team}_{pos}_{i}")
            if player_name:
                player_options = search_player(player_name)
                if player_options:
                    selected_player = st.selectbox(
                        f"Select Player for {team} - {pos} #{i + 1}",
                        list(player_options.keys()),
                        key=f"{team}_{pos}_select_{i}"
                    )
                    player_id = player_options[selected_player]
                    player_stats = get_player_stats(player_id)
                    # Display player image and stats
                    img_url = f"https://nhl.bamcontent.com/images/headshots/current/168x168/{player_id}.jpg"
                    st.image(img_url, caption=selected_player, width=100)
                    st.write(f"Stats: {player_stats}")
                    team_data[pos][selected_player] = player_stats
                else:
                    st.warning("No players found for that search.")
    if team == "Team 1":
        team1 = team_data
    else:
        team2 = team_data

# -----------------------------
# 7. Run Simulation and Display Results
# -----------------------------
if st.button("Run Simulation"):
    if team1 and team2:
        # Run aggregated simulation (win probabilities)
        team1_prob, team2_prob = simulate_matchup(team1, team2, custom_scoring, start_date, end_date)
        st.write(f"**Team 1 Win Probability:** {team1_prob * 100:.2f}%")
        st.write(f"**Team 2 Win Probability:** {team2_prob * 100:.2f}%")

        # Run category-based simulation for predicted final score
        team1_cat, team2_cat, ties = simulate_category_matchup(team1, team2, start_date, end_date)
        st.write(
            f"**Predicted Final Score (Categories Won):** Team 1: {team1_cat} - Team 2: {team2_cat} (Ties: {ties})")

        # Identify weak players (example based on total stat contribution across selected categories)
        weak_players = []
        for pos, players in team1.items():
            for player, stats in players.items():
                if sum(stats.get(stat, 0) for stat in selected_categories) < 10:
                    weak_players.append((player, pos))
        for p, pos in weak_players:
            st.markdown(f"🚨 **:red[{p}] in {pos} is underperforming!**")
            if team1[pos][p]:
                weakest_stat = min(team1[pos][p], key=team1[pos][p].get)
            else:
                weakest_stat = "N/A"
            st.markdown(f"🔄 **Consider replacing {p} with a player strong in `{weakest_stat}`.**")

        # Plot simulation results (win probability)
        fig, ax = plt.subplots()
        ax.bar(["Team 1", "Team 2"], [team1_prob, team2_prob], color=['blue', 'red'])
        ax.set_ylabel("Win Probability")
        ax.set_title("Matchup Win Probabilities")
        st.pyplot(fig)
    else:
        st.warning("Please enter at least one player for each team.")
