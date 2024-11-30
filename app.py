import streamlit as st
import openai
from dotenv import load_dotenv
import re
import json
import matplotlib.pyplot as plt
from mplsoccer import Pitch
from matplotlib.patches import Circle
from io import BytesIO
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import random

import json

# Access GCP credentials from secrets
gcp_credentials = json.loads(st.secrets["GCP_CREDENTIALS"])


# Authenticate and connect to Google Sheets using in-memory credentials
def connect_to_google_sheet(gcp_credentials, spreadsheet_name):
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    # Use in-memory credentials
    creds = ServiceAccountCredentials.from_json_keyfile_dict(gcp_credentials, scope)
    client = gspread.authorize(creds)
    sheet = client.open(spreadsheet_name).sheet1
    return sheet


# Example usage
spreadsheet_name = "Matchango Quiz Bank of Questions"
try:
    sheet = connect_to_google_sheet(gcp_credentials, spreadsheet_name)
except Exception as e:
    st.error(f"Failed to connect to Google Sheets: {e}")


# Function to add a new row to Google Sheets
def add_to_google_sheet(sheet, values):
    try:
        # Append the row to the sheet
        result = sheet.append_row(values)
        print("Append Row Result:", result)  # Debugging
        return True  # Indicate success
    except Exception as e:
        print("Error during append_row:", str(e))  # Log the error
        return False, str(e)  # Return failure and the error message


# Load service account credentials
SPREADSHEET_NAME = "Matchango Quiz Bank of Questions"

# Load environment variables from .env
load_dotenv()

# Access the API key
api_key = st.secrets["OPENAI_API_KEY"]

client = openai.OpenAI(
    api_key=api_key,
)

# Title
st.title("Matchango Questions Generator")
st.logo("logo matchango", size="large", link=None, icon_image=None)
# Sidebar with dropdown options
st.sidebar.header("Options")

# Ensure session state to store the generated output
if "generated_output" not in st.session_state:
    st.session_state.generated_output = None


# Define the PlayerPositionPlotter class
class PlayerPositionPlotter:
    def __init__(self, pitch_length=120, pitch_width=80):
        """
        Initialize the PlayerPositionPlotter with pitch dimensions.
        """
        self.pitch_length = pitch_length
        self.pitch_width = pitch_width
        self.pitch = Pitch(pitch_length=self.pitch_length, pitch_width=self.pitch_width,
                           line_color='white', pitch_color='#aabb97')

    def plot_player_positions(self, player_data):
        """
        Plots the players' positions based on input data.
        """
        # st.write("Player Data to be Plotted:", player_data)  # DEBUG

        fig, ax = self.pitch.draw(figsize=(10, 7))

        team_players = player_data.get('team_players', [])
        opponent_players = player_data.get('opponent_players', [])
        ball_position = player_data.get('ball', None)
        main_player = player_data.get('main_player', None)

        self._plot_players(team_players, ax, color='#4CAF50', label='Team Player', main_player=main_player)
        self._plot_players(opponent_players, ax, color='#FF5733', label='Opponent Player')

        if ball_position:
            self._plot_ball(ax, ball_position)

        plt.title("Player and Ball Positions", fontsize=16, color='#34495e', weight='bold')
        plt.tight_layout()
        return fig

    def _plot_players(self, players, ax, color, label, main_player=None):
        """
        Private method to plot multiple players on the pitch.

        Args:
        players (list): List of player dictionaries containing position information.
        ax: The axis to plot the players on.
        color (str): Color of the players for the respective team or opponent.
        label (str): Label for the player type (team or opponent).
        main_player (list): The position of the main player to highlight.
        """
        for player in players:
            position = player.get('position')
            is_main = (position == main_player) if main_player else False
            self._plot_player(ax, position, color, is_main=is_main, label=label)

    def _plot_player(self, ax, position, color, is_main=False, label=None):
        """
        Private method to plot a single player at a specific position.

        Args:
        ax: The axis to plot the player on.
        position (list): The [x, y] position on the pitch.
        color (str): Color of the player marker.
        is_main (bool): Whether the player is the main player.
        label (str): Player type (team or opponent).
        """
        marker_size = 300
        edge_color = 'gold' if is_main else 'black'
        ax.scatter(position[0], position[1], s=marker_size, color=color, edgecolor=edge_color, lw=2.5, label=label,
                   zorder=3)

    def _plot_ball(self, ax, position):
        """
        Private method to plot the ball on the pitch.

        Args:
        ax: The axis to plot the ball on.
        position (list): The [x, y] position of the ball on the pitch.
        """
        # Plot the ball as a circle
        ball = Circle((position[0], position[1]), radius=1, color='white', zorder=4)
        ax.add_patch(ball)


def flatten_positions(positions):
    """
    Converts player positions to a string representation suitable for Google Sheets.
    """
    return [json.dumps(player["position"]) for player in positions]


def generate_text(prompt, model="gpt-4o"):
    openai.api_key = api_key

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": prompt}
        ],
        max_tokens=1000,
    )

    model_resp = response.choices[0].message.content.strip()
    print(model_resp)
    return model_resp


def extract_json_from_generated(model_resp):
    json_match = re.search(r'<JSON>(.*?)</JSON>', model_resp, re.DOTALL)

    if json_match:
        json_str = json_match.group(1).strip()

        # Remove any comments like `//` using regex
        json_str = re.sub(r'//.*', '', json_str)  # This removes any inline comments starting with //

        try:
            quiz_data = json.loads(json_str)
        except json.JSONDecodeError as e:
            print(f"Error parsing JSON: {e}")
            return None
    else:
        print("No JSON data found between <JSON> tags.")
        return None
    return quiz_data


random_instruction = random.choice([
    "Focus on the player's decision-making process and how they should prioritize options in this scenario.",
    "Emphasize the tactical implications of the scenario and how it impacts team dynamics.",
    "Highlight the psychological aspects of the player's actions under pressure in this scenario.",
    "Explore the technical skills required for a player to execute optimal actions in this situation.",
    "Consider the game's context (e.g., time left, scoreline) and how it influences the player's choices.",
    "Frame the question to reflect a high-stakes scenario, such as a critical moment in the match.",
    "Incorporate elements of player positioning and spatial awareness in the decision-making process.",
    "Focus on the interaction between teammates and how their positions affect the player's options.",
    "Explore how the opponent's defensive setup creates challenges or opportunities for the player.",
    "Use specific terminology related to the scenario (e.g., 'breaking the lines,' 'high press,' 'compact defense')."
])


def generate_questions(situation, scenario, axe, random_instruction, difficulty):
    """
    Generates a soccer quiz question based on the provided inputs.

    Args:
        situation (str): The game situation (e.g., "Offense", "Defense").
        scenario (str): The specific scenario (e.g., "Attaque Positionnelle").
        axe (str): The axis of evaluation (e.g., "Créativité").

    Returns:
        dict: Parsed JSON containing the generated question and answers.
    """
    prompt = f"""You are a highly skilled soccer tactician and quiz author. Your task is to create a high quality 
    question aimed at assessing a soccer player’s skills. The question should cover soccer tactics, rules, 
    or specific game scenarios. Your question must be followed by four possible answers. Each answer should be 
    evaluated on a scale from 1 to 4 based on its relevance to the situation, with 1 being the least optimal and 4 
    being the most optimal.
    The question has to assess the player based on the axis of evaluation.
    The question doesn't have to explicitely announce the scenario, situation and axis.

    Follow these guidelines:
        
    The question and answers must be written in French.
    Each answer should be clearly associated with an evaluation score.
    Format the final output in a JSON-like structure.
    IMPERATIVE: JSON format must be wrapped with <JSON></JSON> tags, contain no extraneous 
    characters, and be valid JSON. 
    IMPERATIVE: Never use `//` comments.

    Inputs:
    - Situation: {situation}.
    - Scenario: {scenario}.
    - Axis of evaluation: {axe}.
    - Question specific instruction: {random_instruction}
    - Difficulty of the question: {difficulty}

    JSON format:
    <JSON>
    {{
      "question": "",
      "answers": [
        {{
          "text": "",
          "score": 4
        }},
        {{
          "text": "",
          "score": 3
        }},
        {{
          "text": "",
          "score": 2
        }},
        {{
          "text": "",
          "score": 1
        }}
      ]
    }}
    </JSON>
    """
    # Generate and parse the response
    question_raw = generate_text(prompt)
    question_json = extract_json_from_generated(question_raw)
    print(random_instruction)
    return question_json


def generate_positions(question_context):
    """
    Generates player positions based on the provided question context.

    Args:
        question_context (str): The context of the question (e.g., "How should players position themselves?").

    Returns:
        dict: Parsed JSON containing the generated player positions.
    """
    prompt = f"""
    You are an AI model tasked with generating player positions and coordinates for a 
    soccer scenario based on a quiz generated by another agent. 

    Question: {question_context}


    Follow these steps carefully to ensure precision:

    Step 1: Understand the context. The quiz question is related to soccer tactics, rules, or scenarios. The aim is to 
    illustrate the scenario clearly on a soccer pitch using player positions. Consider the information provided in the 
    question and options and align the positions with the given scenario.

    Step 2: Define the pitch dimensions. The soccer pitch dimensions are 120 (coordinates from 0 (left) to 120 (right)) 
    for the x-axis and 80 (from 0 (top) to 80 (bottom)) for the y-axis. This will help in placing the players 
    appropriately on the field. Make sure the coordinates respect these boundaries and align logically with the scenario. 
    Calculate the key stadium areas, like the penalty area, corners, attacking and defending positions, half spaces, 
    goalkeeper position... these will help you be more conscious about the stadium dimensions.

    Step 3: Position the main player. Place the main player at a position that reflects their key role in the scenario. 
    Think about whether this player is attacking or defending, and place them accordingly. Make sure to assign the main 
    player a unique position.

    Step 4: Place the team players (5 players, including the main player and the goalkeeper). Distribute the remaining 4 players from the 
    main player’s team around the pitch based on the scenario. These players should be positioned strategically to 
    reflect typical game dynamics, such as positioning during an attack, defense, or counterattack.

    Step 5: Position the opponent players (5 players, including the goalkeeper). Place the defending team's players in 
    appropriate positions to counter the team with the ball. Ensure that one of the players is clearly positioned as the 
    goalkeeper, staying close to the goal. The other 4 opponent players should be positioned according to the game flow.

    Step 6: Place the ball. The ball should be positioned near the main player, reflecting its role in the scenario. 
    Ensure that the ball’s coordinates are logical in relation to the main player's position.

    Format the final output in a JSON-like structure.
    IMPERATIVE: JSON format must be wrapped with <JSON></JSON> tags, contain no extraneous 
    characters, and be valid JSON. 
    IMPERATIVE: Never use `//` comments.

    Output JSON Format:
    <JSON>
    {{
      "coordinates": {{
        "team_players": [
          {{"position": [x1, y1]}},
          {{"position": [x2, y2]}},
          {{"position": [x3, y3]}},
          {{"position": [x4, y4]}},
          {{"position": [x5, y5]}}
        ],
        "opponent_players": [
          {{"position": [x6, y6]}},
          {{"position": [x7, y7]}},
          {{"position": [x8, y8]}},
          {{"position": [x9, y9]}},
          {{"position": [x10, y10]}}
        ],
        "main_player": [x_main, y_main],
        "ball": [ball_x, ball_y]
      }}
    }}
    </JSON>
    """

    # Generate and parse the response
    positions_raw = generate_text(prompt)
    positions_json = extract_json_from_generated(positions_raw)
    return positions_json


offensive_axes = [
    "Select Axe",
    "Contrôle de la possession",
    "Créativité",
    "Finition",
    "Capacité de dribble",
    "Précision des passes",
    "Vision de jeu",
    "Adaptabilité tactique",
    "Puissance physique",
    "Vitesse d'exécution"
]

defensive_axes = [
    "Select Axe",
    "Engagement défensif",
    "Pressing et Récupération",
    "Anticipation",
    "Adaptabilité tactique",
    "Puissance physique",
    "Vitesse d'exécution",
    "Vision de jeu"
]

# Offensive scenarios
offensive_scenarios = [
    "Select Scenario",
    "Attaque Positionnelle",
    "Contre-Attaque Rapide",
    "Débordement sur les Côtés",
    "Jeu en Profondeur",
    "Centre en Retrait",
    "Mouvement de Rupture (Appel sans Ballon)"
]

# Defensive scenarios
defensive_scenarios = [
    "Select Scenario",
    "Défense en Bloc Bas",
    "Marquage Individuel",
    "Marquage en Zone",
    "Réaction Rapide après un Tir Contré",
    "Interception des Passes",
    "Défense en Bloc Haut"
]

# Offensive scenarios with player positions
offensive_scenarios = {
    "Select Scenario": None,
    "Attaque Positionnelle": {
        "team_players": [
            {"position": [5, 40]},  # GK
            {"position": [40, 30]},  # Player 1
            {"position": [60, 50]},  # Player 2
            {"position": [80, 60]},  # Player 3
            {"position": [100, 40]}  # Player 4
        ],
        "opponent_players": [
            {"position": [115, 40]},  # Opp GK
            {"position": [90, 20]},  # Opp Player 1
            {"position": [85, 50]},  # Opp Player 2
            {"position": [80, 35]},  # Opp Player 3
            {"position": [75, 45]}  # Opp Player 4
        ],
        "main_player": [60, 50],
        "ball": [58, 48]
    },
    "Contre-Attaque Rapide": {
        "team_players": [
            {"position": [5, 40]},  # GK
            {"position": [30, 50]},  # Player 1
            {"position": [50, 40]},  # Player 2
            {"position": [70, 45]},  # Player 3
            {"position": [90, 55]}  # Player 4
        ],
        "opponent_players": [
            {"position": [115, 40]},  # Opp GK
            {"position": [100, 35]},  # Opp Player 1
            {"position": [95, 50]},  # Opp Player 2
            {"position": [85, 40]},  # Opp Player 3
            {"position": [80, 30]}  # Opp Player 4
        ],
        "main_player": [70, 45],
        "ball": [68, 43]
    },
    "Mouvement de Rupture (Appel sans Ballon)": {
        "team_players": [
            {"position": [5, 40]},  # GK
            {"position": [30, 60]},  # Player 1
            {"position": [50, 70]},  # Player 2
            {"position": [80, 65]},  # Player 3
            {"position": [100, 60]}  # Player 4
        ],
        "opponent_players": [
            {"position": [115, 40]},  # Opp GK
            {"position": [90, 55]},  # Opp Player 1
            {"position": [85, 65]},  # Opp Player 2
            {"position": [80, 50]},  # Opp Player 3
            {"position": [75, 40]}  # Opp Player 4
        ],
        "main_player": [80, 65],
        "ball": [78, 63]
    },
    "Jeu en Profondeur": {
        "team_players": [
            {"position": [5, 40]},  # GK
            {"position": [30, 60]},  # Player 1
            {"position": [50, 70]},  # Player 2
            {"position": [80, 65]},  # Player 3
            {"position": [100, 60]}  # Player 4
        ],
        "opponent_players": [
            {"position": [115, 40]},  # Opp GK
            {"position": [90, 55]},  # Opp Player 1
            {"position": [85, 65]},  # Opp Player 2
            {"position": [80, 50]},  # Opp Player 3
            {"position": [75, 40]}  # Opp Player 4
        ],
        "main_player": [80, 65],
        "ball": [78, 63]
    },
    "Centre en Retrait": {
        "team_players": [
            {"position": [5, 40]},  # GK
            {"position": [30, 60]},  # Player 1
            {"position": [50, 70]},  # Player 2
            {"position": [80, 65]},  # Player 3
            {"position": [100, 60]}  # Player 4
        ],
        "opponent_players": [
            {"position": [115, 40]},  # Opp GK
            {"position": [90, 55]},  # Opp Player 1
            {"position": [85, 65]},  # Opp Player 2
            {"position": [80, 50]},  # Opp Player 3
            {"position": [75, 40]}  # Opp Player 4
        ],
        "main_player": [80, 65],
        "ball": [78, 63]
    },
    "Débordement sur les Côtés": {
        "team_players": [
            {"position": [5, 40]},  # GK
            {"position": [30, 60]},  # Player 1
            {"position": [50, 70]},  # Player 2
            {"position": [80, 65]},  # Player 3
            {"position": [100, 60]}  # Player 4
        ],
        "opponent_players": [
            {"position": [115, 40]},  # Opp GK
            {"position": [90, 55]},  # Opp Player 1
            {"position": [85, 65]},  # Opp Player 2
            {"position": [80, 50]},  # Opp Player 3
            {"position": [75, 40]}  # Opp Player 4
        ],
        "main_player": [80, 65],
        "ball": [78, 63]
    },
    # Add more offensive scenarios as needed
}

# Defensive scenarios with player positions
defensive_scenarios = {
    "Select Scenario": None,
    "Défense en Bloc Bas": {
        "team_players": [
            {"position": [5, 40]},  # GK
            {"position": [20, 30]},  # Player 1
            {"position": [25, 50]},  # Player 2
            {"position": [30, 35]},  # Player 3
            {"position": [40, 40]}  # Player 4
        ],
        "opponent_players": [
            {"position": [115, 40]},  # Opp GK
            {"position": [90, 20]},  # Opp Player 1
            {"position": [95, 50]},  # Opp Player 2
            {"position": [85, 35]},  # Opp Player 3
            {"position": [75, 40]}  # Opp Player 4
        ],
        "main_player": [25, 50],
        "ball": [23, 48]
    },
    "Marquage Individuel": {
        "team_players": [
            {"position": [5, 40]},  # GK
            {"position": [20, 40]},  # Player 1
            {"position": [25, 35]},  # Player 2
            {"position": [30, 50]},  # Player 3
            {"position": [40, 45]}  # Player 4
        ],
        "opponent_players": [
            {"position": [115, 40]},  # Opp GK
            {"position": [90, 30]},  # Opp Player 1
            {"position": [95, 40]},  # Opp Player 2
            {"position": [85, 50]},  # Opp Player 3
            {"position": [75, 60]}  # Opp Player 4
        ],
        "main_player": [30, 50],
        "ball": [28, 48]
    },
    "Marquage en Zone": {
        "team_players": [
            {"position": [5, 40]},  # GK
            {"position": [20, 40]},  # Player 1
            {"position": [25, 35]},  # Player 2
            {"position": [30, 50]},  # Player 3
            {"position": [40, 45]}  # Player 4
        ],
        "opponent_players": [
            {"position": [115, 40]},  # Opp GK
            {"position": [90, 30]},  # Opp Player 1
            {"position": [95, 40]},  # Opp Player 2
            {"position": [85, 50]},  # Opp Player 3
            {"position": [75, 60]}  # Opp Player 4
        ],
        "main_player": [30, 50],
        "ball": [28, 48]
    },
    "Réaction Rapide après un Tir Contré": {
        "team_players": [
            {"position": [5, 40]},  # GK
            {"position": [20, 40]},  # Player 1
            {"position": [25, 35]},  # Player 2
            {"position": [30, 50]},  # Player 3
            {"position": [40, 45]}  # Player 4
        ],
        "opponent_players": [
            {"position": [115, 40]},  # Opp GK
            {"position": [90, 30]},  # Opp Player 1
            {"position": [95, 40]},  # Opp Player 2
            {"position": [85, 50]},  # Opp Player 3
            {"position": [75, 60]}  # Opp Player 4
        ],
        "main_player": [30, 50],
        "ball": [28, 48]
    },
    "Interception des Passes": {
        "team_players": [
            {"position": [5, 40]},  # GK
            {"position": [20, 40]},  # Player 1
            {"position": [25, 35]},  # Player 2
            {"position": [30, 50]},  # Player 3
            {"position": [40, 45]}  # Player 4
        ],
        "opponent_players": [
            {"position": [115, 40]},  # Opp GK
            {"position": [90, 30]},  # Opp Player 1
            {"position": [95, 40]},  # Opp Player 2
            {"position": [85, 50]},  # Opp Player 3
            {"position": [75, 60]}  # Opp Player 4
        ],
        "main_player": [30, 50],
        "ball": [28, 48]
    },
    "Défense en Bloc Haut": {
        "team_players": [
            {"position": [5, 40]},  # GK
            {"position": [20, 40]},  # Player 1
            {"position": [25, 35]},  # Player 2
            {"position": [30, 50]},  # Player 3
            {"position": [40, 45]}  # Player 4
        ],
        "opponent_players": [
            {"position": [115, 40]},  # Opp GK
            {"position": [90, 30]},  # Opp Player 1
            {"position": [95, 40]},  # Opp Player 2
            {"position": [85, 50]},  # Opp Player 3
            {"position": [75, 60]}  # Opp Player 4
        ],
        "main_player": [30, 50],
        "ball": [28, 48]
    }
    # Add more defensive scenarios as needed
}

# Other scenarios
other_scenarios = []

plotter = PlayerPositionPlotter(pitch_length=120, pitch_width=80)

# Dropdown menus for user inputs
situation = st.sidebar.selectbox("Situation", ["Select Situation", "Offense", "Defense", "Other"])

if situation == "Offense":
    scenario = st.sidebar.selectbox("Scenario", list(offensive_scenarios.keys()))
    axe = st.sidebar.selectbox("Axe", offensive_axes)
if situation == "Defense":
    scenario = st.sidebar.selectbox("Scenario", list(defensive_scenarios.keys()))
    axe = st.sidebar.selectbox("Axe", defensive_axes)
if situation == "Other":
    scenario = st.sidebar.selectbox("Scenario", other_scenarios)
    axe = st.sidebar.selectbox("Axe", offensive_axes + defensive_axes)
use_ai_positions = st.sidebar.selectbox("Use AI Positions", ["Yes", "No"])
difficulty = st.sidebar.selectbox("Difficulty", ["Easy", "Medium", "Complex", "Unusual situations"])

if "generated_output" not in st.session_state:
    st.session_state["generated_output"] = None

if "generated_positions" not in st.session_state:
    st.session_state["generated_positions"] = None

if "generated_questions_history" not in st.session_state:
    st.session_state["generated_questions_history"] = []

positions_data = {
    "coordinates": {
        "team_players": [
            {"position": [5, 40]},  # GK
            {"position": [63, 55]},  # Player 1
            {"position": [78, 50]},  # Player 2 (MAIN)
            {"position": [97, 5]},  # Player 3
            {"position": [98, 76]}  # Player 4
        ],
        "opponent_players": [
            {"position": [115, 40]},  # Opp GK
            {"position": [107, 20]},  # Opp Player 1
            {"position": [107, 60]},  # Opp Player 2
            {"position": [99, 42]},  # Opp Player 3
            {"position": [74, 50]}  # Opp Player 4
        ],
        "main_player": [78, 50],  # Player 2 (MAIN)
        "ball": [0, 0]  # Update this if ball coordinates are provided
    }
}

# Generate Button
if st.sidebar.button("Generate"):
    # Check if all required options are selected
    if situation == "Select Situation" or scenario == "Select Scenario" or axe == "Select Axe":
        st.error("Please select valid options for Situation, Scenario, and Axe.")
    else:
        # Generate the question and answers
        generated_output = generate_questions(situation, scenario, axe, random_instruction, difficulty)

        if generated_output:
            # Store the output in session state for persistence
            st.session_state.generated_output = generated_output

            if use_ai_positions == "No":
                # Visualize field positions
                scenario_data = {
                    "team_players": positions_data["coordinates"]["team_players"],
                    "opponent_players": positions_data["coordinates"]["opponent_players"],
                    "main_player": positions_data["coordinates"]["main_player"],
                    "ball": positions_data["coordinates"]["ball"]
                }
                with st.spinner("Displaying player positions..."):
                    fig = plotter.plot_player_positions(scenario_data)
                    buf = BytesIO()
                    fig.savefig(buf, format="png")
                    st.image(buf)

            if use_ai_positions == "Yes":
                question_context = st.session_state["generated_output"].get("question", "")
                if question_context:
                    positions_data = generate_positions(question_context)
                    if positions_data:
                        st.session_state["generated_positions"] = positions_data  # Store in session state
                    else:
                        st.error("Failed to generate positions.")

                print(positions_data)
                # Visualize field positions
                scenario_data = {
                    "team_players": positions_data["coordinates"]["team_players"],
                    "opponent_players": positions_data["coordinates"]["opponent_players"],
                    "main_player": positions_data["coordinates"]["main_player"],
                    "ball": positions_data["coordinates"]["ball"]
                }
                with st.spinner("Displaying player positions..."):
                    fig = plotter.plot_player_positions(scenario_data)
                    buf = BytesIO()
                    fig.savefig(buf, format="png")
                    st.image(buf)

# Display the generated question and answers if available
if st.session_state.generated_output:
    st.subheader("Generated Question:")
    st.markdown(f"**{st.session_state.generated_output['question']}**")

    st.subheader("Answers:")
    for i, answer in enumerate(st.session_state.generated_output["answers"], start=1):
        st.write(f"**Option {i}:** {answer['text']}")

    # Action buttons
    col1, col2 = st.columns(2)

    with col1:
        if st.button("Validate"):
            try:
                # Ensure generated_positions exists and has valid data
                if not st.session_state["generated_positions"]:
                    st.error("No generated positions found. Please generate positions first.")
                    st.stop()

                # Ensure generated_output exists and has valid data
                if not st.session_state["generated_output"]:
                    st.error("No generated output found. Please generate a question first.")
                    st.stop()

                positions = st.session_state["generated_positions"].get("coordinates", {})
                if not positions:
                    st.error("Generated positions are missing coordinates.")
                    st.stop()

                # Prepare data to insert into Google Sheet
                row_data = [
                    situation,  # Selected situation
                    scenario,  # Selected scenario
                    axe,  # Selected axis
                    use_ai_positions,  # Use AI Positions (Yes/No)
                    st.session_state["generated_output"]["question"],  # Generated question
                    *[answer["text"] for answer in st.session_state["generated_output"]["answers"]],  # Answers
                    "; ".join(flatten_positions(positions.get("team_players", []))),  # Flattened team positions
                    "; ".join(flatten_positions(positions.get("opponent_players", []))),  # Flattened opponent positions
                    json.dumps(positions.get("ball", {})),  # Serialize ball position
                    positions.get("main_player", "N/A")  # Add the main player field, defaulting to "N/A" if not present
                ]

                # Add the data to Google Sheets
                success = add_to_google_sheet(sheet, row_data)

                if success:
                    st.success("Question successfully validated and shared!")
                    # Clear session state after successful validation
                    st.session_state["generated_output"] = None
                    st.session_state["generated_positions"] = None
                else:
                    st.error("Failed to share the question. Please check your Google Sheets configuration.")
            except Exception as e:
                st.error(f"An unexpected error occurred: {e}")

    with col2:
        if st.button("Reject"):
            st.warning("Question rejected.")
            # Clear session state when rejected
            st.session_state.generated_output = None
