# -*- coding: utf-8 -*-
# Required for Python 2/3 compatibility with non-ASCII characters

# --- Import necessary libraries ---
import pygame       # The main library for game development
import sys          # For system-level operations like exiting
import random       # For generating random numbers (though not heavily used currently)
import textwrap     # For wrapping long lines of text in the dialogue box
import re           # For regular expressions (used to parse AI responses)
import os           # For operating system interactions, like finding file paths
import traceback    # For getting detailed error information if the program crashes

# --- OpenAI Integration ---
# Try to import the OpenAI library
try:
    import openai
    OPENAI_ENABLED = True # Flag indicating OpenAI library is available
# If the library is not installed, handle the error
except ImportError:
    # Print a clear warning message to the console
    print("="*30); print("WARNING: 'openai' library not found."); print("OpenAI dialogue disabled."); print("To enable OpenAI dialogue, run: pip install openai"); print("="*30)
    OPENAI_ENABLED = False # Flag indicating OpenAI features are disabled

# --- Constants ---
# Define fixed values used throughout the game for easier configuration and readability

# Screen dimensions and performance
SCREEN_WIDTH = 800
SCREEN_HEIGHT = 600
FPS = 60  # Target frames per second

# Color definitions (RGB format: Red, Green, Blue, 0-255)
SKY_BLUE = (135, 206, 250)
GRASS_GREEN = (100, 180, 100)
FIELD_GREEN_LIGHT = (144, 238, 144)
FIELD_BROWN_TILLED = (139, 90, 43)
FENCE_BROWN = (101, 67, 33)
SUN_YELLOW = (255, 255, 0)
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
# Dialogue box colors (RGBA format, last value is Alpha/transparency, 0-255)
DIALOGUE_BG = (60, 100, 180, 230) # Semi-transparent blue
DIALOGUE_BORDER = (200, 200, 255)
# Object colors
SEED_GOLD = (255, 215, 0)
CHICK_YELLOW = (255, 230, 100)
CHICK_BROWN = (210, 180, 140)
CHICK_BEAK = (255, 165, 0)

# Gameplay values
PLAYER_SPEED = 4 # Pixels moved per frame
INTERACTION_DISTANCE_SQ = 70**2 # Squared distance for triggering talk prompt (avoids slow sqrt calculation)
MAX_DIALOGUE_COUNT = 7 # Limit conversation length per interaction
HORIZON_LINE = SCREEN_HEIGHT * 0.4 # Y-coordinate where sky meets ground

# Farm layout definitions using Pygame Rectangles (left, top, width, height)
FIELD_LAYOUT = {
    "main_grass": pygame.Rect(0, HORIZON_LINE, SCREEN_WIDTH, SCREEN_HEIGHT - HORIZON_LINE),
    "west_tilled": pygame.Rect(20, HORIZON_LINE + 20, SCREEN_WIDTH * 0.25, SCREEN_HEIGHT * 0.5),
    "east_crop": pygame.Rect(SCREEN_WIDTH * 0.7, HORIZON_LINE + 50, SCREEN_WIDTH * 0.28, SCREEN_HEIGHT * 0.4)
}
# Information about the goal location
TARGET_FIELD_KEY = "west_tilled" # Key in FIELD_LAYOUT where the seed is hidden
SEED_LOCATION_DESCRIPTION = "hidden somewhere in the western tilled field patch (dark brown soil area on the left side of the farm)." # Description passed to the AI

# --- System Prompt for LLM ---
# These are the instructions sent to the OpenAI model to define its role and response format.
LLM_SYSTEM_PROMPT = f"""You are Pip, a friendly but VERY scatterbrained and curious chick NPC in a simple farm game.
You love chatting but get easily distracted by things on the farm (worms, shiny things, the color of the sky). Peep! Chirp!
The player is another chick looking for a hidden Golden Seed. You want to help them, but you give hints indirectly because you're forgetful and easily sidetracked.

**Your Personality:**
*   **Friendly & Curious:** You like the player and want to chat. Ask them questions sometimes! ("Peep! What are YOU looking for?", "Did you see that fluffy cloud?").
*   **Scatterbrained:** You might start talking about one thing and drift to another. Sometimes you forget what you just said. Use lots of "Chirp!", "Peep!".
*   **Observant (of small things):** You notice details on the farm, especially near the ground.

**Giving Hints about the Seed:**
*   The seed's location info is: **{SEED_LOCATION_DESCRIPTION}**.
*   **DO NOT state the location directly.** Be subtle and indirect!
*   **Hint Strategies:**
    *   Talk about the **dark brown soil** in the western field. ("Chirp! The dirt over there feels funny on my feet!", "Lots of juicy worms hide in that dark patch!").
    *   Mention things **near** that area (like the fence bordering it, or the fact it's separate from the green grass). ("Peep! I saw Old Man McGregor fixing the fence near the tilled patch yesterday.").
    *   Ask the player if they've **looked in places with similar features.** ("Have you tried digging where the ground is soft and brown?").
    *   Connect the seed to **things often found underground.** ("Shiny things sometimes get buried... like yummy seeds! Peep!").
*   **Gradual Clues:** Don't give the best hint right away. Let the conversation build. Respond to what the player chooses.

**Conversation Flow:**
*   Try to connect your response slightly to the player's previous choice.
*   Keep sentences relatively simple, but make the overall conversation feel like you're genuinely trying (in your own scatterbrained way) to help.
*   Let the conversation continue for a few turns if the player seems interested in hints.

*** VERY IMPORTANT - RESPONSE FORMAT (MUST FOLLOW EXACTLY) ***
1.  Start with your dialogue as Pip (1-4 short, chick-like sentences). Use "Chirp!", "Peep!", etc.
2.  AFTER your dialogue, provide EXACTLY 3 possible replies for the PLAYER to choose from.
3.  Each player reply option MUST start on a new line and be numbered like "1.", "2.", "3.". (e.g., `1. Option text`)
4.  Make the player options short (a few words).
5.  Assign a state based on the option: Use `llm_continue` if the conversation should carry on. Use `llm_end` if the option is a natural end point (like saying goodbye, acknowledging they found the seed, or giving up). Most options should lead to `llm_continue` unless it's clearly time to stop. You don't need to write the state in the output, the parser will infer it based on keywords like 'bye', 'thanks', 'okay', or default to continue.
6.  Your output MUST be *only* the NPC dialogue followed by the 3 numbered options. No extra explanations, no introductory text.

**Example of a *PERFECT* response format (What you should output):**
Peep! Hello there! The ground is extra soft today, isn't it? Chirp! Makes digging easy!
1. Soft ground?
2. Hello Pip!
3. Just passing through.

**Another *PERFECT* example:**
Chirp! Did you see that wiggly worm near the fence by the dark soil patch? Looked juicy! Peep!
1. Worm? Where?
2. Dark soil patch?
3. No, I missed it.
"""

# --- Asset Loader Class ---
# Handles loading images and fonts, providing fallbacks if loading fails.
class AssetLoader:
    # Constructor: Initializes dictionaries for images/fonts and starts loading.
    def __init__(self):
        self.images = {} # Dictionary to store loaded images
        self.fonts = {}  # Dictionary to store loaded fonts
        self.use_images = True # Flag to track if image loading was successful
        self._load_assets() # Call the private method to load everything

    # Private helper method to load a single image file.
    def _load_image(self, filename, size=None):
        try:
            # Determine the directory of the script to find assets relative to it
            script_dir = os.path.dirname(__file__) if '__file__' in locals() else os.getcwd()
            # Create the full path to the image file
            filepath = os.path.join(script_dir, filename)
            # Load the image using Pygame, convert_alpha() helps with transparency
            image = pygame.image.load(filepath).convert_alpha()
            # print(f"Successfully loaded image: {filepath}") # Less verbose now
        # Handle Pygame-specific errors during loading
        except pygame.error as e:
            print(f"Warning: Pygame error loading image '{filename}': {e}")
            self.use_images = False; return None # Set flag and return nothing
        # Handle error if the file doesn't exist
        except FileNotFoundError:
            print(f"ERROR: Image file not found: '{filename}' (Expected path: {filepath})")
            self.use_images = False; return None # Set flag and return nothing
        # If a specific size is requested, resize the image
        if size: image = pygame.transform.scale(image, size)
        return image # Return the loaded (and possibly resized) image

    # Private helper method to load all required assets.
    def _load_assets(self):
        print("Loading assets...")
        # Load images for player, NPC, and goal
        self.images['player'] = self._load_image("player_chick.png", (40, 40))
        self.images['npc'] = self._load_image("npc_chick.png", (40, 40))
        self.images['goal'] = self._load_image("golden_seed.png", (20, 20))
        # If any image failed to load, print a warning
        if not self.use_images:
            print("-" * 30); print(f"WARNING: Image loading failed. Using fallbacks."); script_dir = os.path.dirname(os.path.abspath(__file__)) if '__file__' in locals() else os.getcwd(); print(f"Check images in: {script_dir}"); print("-" * 30)
        # Try loading standard Pygame fonts by size
        try:
            self.fonts['default_16'] = pygame.font.Font(None, 16); self.fonts['default_18'] = pygame.font.Font(None, 18); self.fonts['default_20'] = pygame.font.Font(None, 20); self.fonts['default_30'] = pygame.font.Font(None, 30); self.fonts['default_50'] = pygame.font.Font(None, 50)
            # print("Fonts loaded successfully.") # Less verbose
        # If loading fails, use default system fonts as a fallback
        except Exception as e:
            print(f"Warning: Font loading failed: {e}. Using SysFont."); self.fonts['default_16'] = pygame.font.SysFont(None, 16); self.fonts['default_18'] = pygame.font.SysFont(None, 18); self.fonts['default_20'] = pygame.font.SysFont(None, 20); self.fonts['default_30'] = pygame.font.SysFont(None, 30); self.fonts['default_50'] = pygame.font.SysFont(None, 50)
        print("Assets loading finished.")

    # Public method to get a loaded image by its key (e.g., 'player')
    def get_image(self, key): return self.images.get(key)
    # Public method to get a loaded font by its key (e.g., 'default_20')
    def get_font(self, key): return self.fonts.get(key)

    # Static method: Draws a simple chick shape if image loading fails.
    @staticmethod
    def create_fallback_chick_surface(color): surf=pygame.Surface((40,40),pygame.SRCALPHA);pygame.draw.ellipse(surf,color,(5,10,30,28));pygame.draw.circle(surf,color,(20,12),10);pygame.draw.circle(surf,BLACK,(25,10),3);pygame.draw.polygon(surf,CHICK_BEAK,[(28,12),(34,14),(28,16)]);pygame.draw.line(surf,BLACK,(15,38),(12,42),2);pygame.draw.line(surf,BLACK,(25,38),(28,42),2);return surf
    # Static method: Draws a simple seed shape if image loading fails.
    @staticmethod
    def create_fallback_seed_surface(): surf=pygame.Surface((20,20),pygame.SRCALPHA);pygame.draw.ellipse(surf,SEED_GOLD,(2,2,16,16));pygame.draw.circle(surf,WHITE,(7,7),3);return surf

# --- LLM Handler Class ---
# Manages interaction with the OpenAI API.
class LLMHandler:
    # Constructor: Initializes OpenAI client if enabled and API key is found.
    def __init__(self, enabled=OPENAI_ENABLED):
        self.client = None # Holds the OpenAI client object
        self.llm_enabled = False # Flag indicating if AI connection is active
        self.model_name = "gpt-4o" # Specify which OpenAI model to use
        # Only proceed if OpenAI was enabled during import
        if not enabled: print("OpenAI integration explicitly disabled."); return
        # --- IMPORTANT: Use environment variable in production! ---
        api_key = "write_your_api_key"
        # api_key = "YOUR_API_KEY_HERE" # Hardcoded key - ONLY FOR TESTING, REMOVE IF SHARING
        # Check if the API key was found
        if not api_key: print("="*30); print("ERROR: OPENAI_API_KEY missing."); print("OpenAI dialogue disabled."); print("="*30); return
        # Try to initialize the OpenAI client and test the connection
        try:
            self.client = openai.OpenAI(api_key=api_key)
            print("Attempting initial connection test to OpenAI...")
            self.client.models.list() # Simple API call to check authentication/connection
            print("OpenAI client initialized and connection tested successfully.")
            self.llm_enabled = True # Set flag to True on success
        # Handle authentication errors (bad API key)
        except openai.AuthenticationError: print(f"ERROR: OpenAI Authentication Failed."); traceback.print_exc(); self.llm_enabled = False
        # Handle other potential errors during initialization
        except Exception as e: print(f"ERROR: Failed to initialize OpenAI client: {e}"); traceback.print_exc(); self.llm_enabled = False

    # Method to generate dialogue by calling the OpenAI API.
    def generate_dialogue(self, history, seed_location_info):
        # If AI is disabled or client failed to init, use fallback immediately
        if not self.llm_enabled or not self.client: print("LLM Disabled or client not initialized. Using fallback."); return self._fallback_response()
        print("\n--- Generating OpenAI Dialogue ---")
        # Prepare the messages list: Start with system prompt, add conversation history
        messages = [{"role": "system", "content": LLM_SYSTEM_PROMPT}]
        for turn in history: # Add previous turns (player input, then AI response)
            if turn.get('player'): messages.append({"role": "user", "content": turn['player']})
            if turn.get('npc') and turn['npc'] != "...": messages.append({"role": "assistant", "content": turn['npc']}) # Avoid sending placeholder history back
        # Try making the API call
        try:
            # Call the chat completions endpoint
            completion = self.client.chat.completions.create(model=self.model_name, messages=messages, temperature=0.7, max_tokens=250)
            # Extract the response text content
            response_message = completion.choices[0].message if completion.choices else None; response_content = response_message.content if response_message else None
            # Check if the response is empty
            if response_content is None or response_content.strip() == "":
                print("Warning: OpenAI returned empty content. Using fallback."); return self._fallback_response()
            # If response looks good, parse it
            return self._parse_response(response_content)
        # Handle specific OpenAI errors and provide fallback responses
        except openai.APIConnectionError as e: print(f"OpenAI APIConnectionError: {e}"); print(">>> FALLBACK: APIConnectionError."); traceback.print_exc(); return self._fallback_response(error=True)
        except openai.RateLimitError as e: print(f"OpenAI RateLimitError: {e}"); print(">>> FALLBACK: RateLimitError."); traceback.print_exc(); return self._fallback_response(error=True)
        except openai.AuthenticationError as e: print(f"OpenAI AuthenticationError: {e}."); print(">>> FALLBACK: AuthenticationError."); traceback.print_exc(); return self._fallback_response(error=True)
        except openai.APIError as e: print(f"OpenAI APIError: {e}"); print(">>> FALLBACK: APIError."); traceback.print_exc(); return self._fallback_response(error=True)
        # Handle any other unexpected error during the API call
        except Exception as e: print(f"Unexpected error during OpenAI call: {e}"); print(">>> FALLBACK: Unexpected Exception."); traceback.print_exc(); return self._fallback_response(error=True)

    # Method to parse the raw text response from OpenAI.
    def _parse_response(self, response_text):
        # Split the response into lines
        lines = response_text.strip().split('\n')
        npc_lines_collected = [] # To store Pip's dialogue
        options_list_final = [] # To store player options as (text, state) tuples
        options_started = False # Flag to track if we've hit the numbered options yet
        # Regular expression to find lines like "1. Option text"
        option_pattern = re.compile(r'^\s*([1-3])\.\s+(.*?)(?:\s*\[(llm_continue|llm_end)\])?\s*$')
        # Process each line
        for i, line in enumerate(lines):
            line_stripped = line.strip();
            if not line_stripped: continue # Skip empty lines
            # Try to match the option pattern
            match = option_pattern.match(line_stripped)
            if match: # If it looks like an option line
                options_started = True # Mark that options have begun
                try:
                    text = match.group(2).strip() # Extract the option text
                    state = 'llm_continue' # Default state is to continue conversation
                    # Infer 'llm_end' state if option text suggests ending
                    if text.lower() in ["bye", "goodbye", "okay, bye!", "got it!", "thanks!", "see ya"]: state = 'llm_end'
                    if text: options_list_final.append((text, state)) # Add (text, state) to list
                except Exception as e: print(f"Parser: Error processing option line '{line_stripped}': {e}")
            elif not options_started: # If options haven't started yet, assume it's NPC dialogue
                npc_lines_collected.append(line_stripped)
        # Join collected NPC lines into a single string
        npc_line_final = " ".join(npc_lines_collected).strip()
        # Handle cases where parsing might have failed
        if not npc_line_final: npc_line_final = "Pip chirps thoughtfully..."; print("Warning: Parser couldn't find NPC dialogue. Using fallback.")
        if not options_list_final: print("Warning: Parser couldn't find options. Using fallback options."); options_list_final = self._fallback_options(end=True)
        # Ensure there are always 3 options (pad with fallback ending options if needed)
        while len(options_list_final) < 3: options_list_final.append(("...", "llm_end"))
        options_list_final = options_list_final[:3] # Limit to exactly 3 options
        # Return the parsed NPC dialogue and the list of player options
        return npc_line_final, options_list_final

    # Method to return a hardcoded fallback response (used on error or if AI disabled).
    def _fallback_response(self, error=False):
        npc = "Chirp... chirp! (Fuzzy thoughts!)" if error else "Pip looks around curiously. Peep!"
        options = self._fallback_options(end=True) # Get fallback options
        print(f"Using fallback dialogue: NPC='{npc}', Options={options}")
        return npc, options # Return the fallback NPC text and options

    # Method to return hardcoded fallback options (always ending the conversation).
    def _fallback_options(self, end=True):
        state = 'llm_end' # Fallback options always end the dialogue
        return [("Okay.", state), ("Maybe later.", state), ("Bye!", state)]

# --- Player Class ---
# Represents the player-controlled character. Inherits from Pygame's Sprite class.
class Player(pygame.sprite.Sprite):
    # Constructor: Sets up the player's image and starting position.
    def __init__(self, assets: AssetLoader, start_pos=(SCREEN_WIDTH * 0.4, SCREEN_HEIGHT * 0.7)):
        super().__init__() # Initialize the parent Sprite class
        self.assets = assets # Store reference to asset loader
        player_img = self.assets.get_image('player') # Get player image
        # Use loaded image or fallback shape
        self.image = player_img if player_img else self.assets.create_fallback_chick_surface(CHICK_YELLOW)
        # Get the rectangle representing the image's position and size
        self.rect = self.image.get_rect(center=start_pos)

    # Method to move the player and keep them within screen bounds.
    def move(self, dx, dy):
        # Update position
        self.rect.x += dx
        self.rect.y += dy
        # Prevent moving off-screen or above the horizon
        self.rect.left = max(0, self.rect.left)
        self.rect.right = min(SCREEN_WIDTH, self.rect.right)
        self.rect.top = max(HORIZON_LINE, self.rect.top)
        self.rect.bottom = min(SCREEN_HEIGHT, self.rect.bottom)

    # Method called each frame to check for movement input.
    def update(self, keys_pressed):
        dx, dy = 0, 0 # Change in x and y, start at zero
        # Check which keys are held down and set dx/dy accordingly
        if keys_pressed[pygame.K_LEFT] or keys_pressed[pygame.K_a]: dx = -PLAYER_SPEED
        if keys_pressed[pygame.K_RIGHT] or keys_pressed[pygame.K_d]: dx = PLAYER_SPEED
        if keys_pressed[pygame.K_UP] or keys_pressed[pygame.K_w]: dy = -PLAYER_SPEED
        if keys_pressed[pygame.K_DOWN] or keys_pressed[pygame.K_s]: dy = PLAYER_SPEED
        # If there was movement input, call the move method
        if dx != 0 or dy != 0: self.move(dx, dy)

# --- NPC Class ---
# Represents the non-player character (Pip). Inherits from Pygame's Sprite class.
class NPC(pygame.sprite.Sprite):
    # Constructor: Sets up Pip's image, position, and dialogue state.
    def __init__(self, assets: AssetLoader, llm_handler: LLMHandler, pos=(SCREEN_WIDTH * 0.65, SCREEN_HEIGHT * 0.6)):
        super().__init__() # Initialize the parent Sprite class
        self.assets = assets # Store asset loader
        self.llm_handler = llm_handler # Store LLM handler
        npc_img = self.assets.get_image('npc') # Get NPC image
        # Use loaded image or fallback shape
        self.image = npc_img if npc_img else self.assets.create_fallback_chick_surface(CHICK_BROWN)
        # Get rectangle for position and size
        self.rect = self.image.get_rect(center=pos)
        # Dialogue state variables
        self.conversation_history = [] # Stores list of {"player": ..., "npc": ...} turns
        self.dialogue_count = 0 # Tracks number of turns in the current conversation
        # Initial non-AI dialogue shown before interaction starts
        self._current_npc_response = "Pip is pecking at the ground."
        self._current_options = [("Say Hello", 'start'), ("Ask about seeds", 'start'), ("Walk away", 'end')]

    # Method called when player chooses a 'start' option. Initiates AI conversation.
    def start_conversation(self):
        self.reset_dialogue() # Clear previous history/count
        self.dialogue_count = 1 # Start counting turns
        print("Starting LLM conversation...")
        # Call the LLM handler to get the first AI response
        self._current_npc_response, self._current_options = self.llm_handler.generate_dialogue(
            self.conversation_history, # Pass empty history initially
            SEED_LOCATION_DESCRIPTION
        )

    # Method to retrieve the current dialogue state for display.
    def get_dialogue(self):
        # Check if the conversation limit has been reached
        if self.dialogue_count > MAX_DIALOGUE_COUNT:
            max_response = "Whoa, easy there! Chirp! Talk more later." # Specific message for limit
            max_options = [("Okay, Pip.", 'llm_end'), ("Sounds good.", 'llm_end'), ("Right!", 'llm_end')] # Ending options
            return max_response, max_options
        # Otherwise, return the currently stored response and options
        return self._current_npc_response, self._current_options

    # Method called when player chooses an option during an AI conversation.
    def advance_dialogue(self, choice_index, options_displayed):
        # Basic error check for valid choice
        if not options_displayed or choice_index >= len(options_displayed): print("Error: Invalid choice index."); self.reset_dialogue(); return False
        # Get the text and state of the chosen option
        chosen_option_text, chosen_state = options_displayed[choice_index]
        # Get the NPC response the player was reacting to
        response_just_seen = self._current_npc_response
        # Add this exchange to the conversation history
        self.conversation_history.append({"player": chosen_option_text, "npc": response_just_seen})
        print(f"Player chose ({choice_index+1}): '{chosen_option_text}' (State: {chosen_state})")
        # If the chosen option itself signals the end, return False immediately
        if chosen_state == 'llm_end': print("Ending conversation based on chosen state 'llm_end'."); return False
        # Increment the turn counter for this conversation
        self.dialogue_count += 1
        # Check if the limit is reached AFTER incrementing
        if self.dialogue_count > MAX_DIALOGUE_COUNT: print("Max dialogue count reached."); return True # Return True to show the limit message next time
        # Call LLM handler to get the NEXT response based on the updated history
        self._current_npc_response, self._current_options = self.llm_handler.generate_dialogue(self.conversation_history, SEED_LOCATION_DESCRIPTION)
        return True # Signal that conversation continues

    # Method to reset the conversation state back to the beginning.
    def reset_dialogue(self):
        print("Resetting conversation history.")
        self.conversation_history = [] # Clear history
        self.dialogue_count = 0 # Reset turn count
        # Reset displayed text/options to the initial non-AI state
        self._current_npc_response = "Pip is pecking at the ground."
        self._current_options = [("Say Hello", 'start'), ("Ask about seeds", 'start'), ("Walk away", 'end')]

# --- Goal Class ---
# Represents the hidden Golden Seed object. Inherits from Pygame's Sprite class.
class Goal(pygame.sprite.Sprite):
    # Constructor: Sets up the goal's image and *fixed* hidden position.
    def __init__(self, assets: AssetLoader):
        super().__init__() # Initialize parent Sprite class
        self.assets = assets # Store asset loader
        goal_img = self.assets.get_image('goal') # Get goal image
        # Use loaded image or fallback shape
        self.image = goal_img if goal_img else self.assets.create_fallback_seed_surface()
        # Get rectangle for image size
        self.rect = self.image.get_rect()
        # Calculate the hidden position within the target field
        target_rect = FIELD_LAYOUT[TARGET_FIELD_KEY]
        self.rect.centerx = target_rect.left + target_rect.width * 0.6
        self.rect.centery = target_rect.top + target_rect.height * 0.7
        # Ensure the calculated position is actually inside the target field bounds
        self.rect.clamp_ip(target_rect)
        print(f"Goal placed (invisibly) at: {self.rect.center} within target field {target_rect}")
        # Note: This sprite is NOT added to any drawing group initially.

# --- Scenery Class ---
# Responsible for drawing the background elements (sky, ground, fields, fences).
class Scenery:
    # Method to draw all scenery elements onto the provided surface (the screen).
    def draw(self, surface):
        # Draw background
        surface.fill(SKY_BLUE) # Fill screen with blue
        pygame.draw.rect(surface, GRASS_GREEN, FIELD_LAYOUT["main_grass"]) # Draw main grass area
        # Draw specific field patches
        pygame.draw.rect(surface, FIELD_BROWN_TILLED, FIELD_LAYOUT["west_tilled"])
        pygame.draw.rect(surface, FIELD_GREEN_LIGHT, FIELD_LAYOUT["east_crop"])
        # Draw Fences using loops and rect drawing
        fence_post_width = 8; fence_rail_height = 5
        num_posts_top = 10 # Top horizon fence
        [pygame.draw.rect(surface, FENCE_BROWN, (int(i*(SCREEN_WIDTH/num_posts_top))-fence_post_width//2, HORIZON_LINE-15, fence_post_width, 30)) for i in range(num_posts_top+1)] # Posts
        pygame.draw.rect(surface, FENCE_BROWN, (0, HORIZON_LINE-10, SCREEN_WIDTH, fence_rail_height)) # Top rail
        pygame.draw.rect(surface, FENCE_BROWN, (0, HORIZON_LINE+5, SCREEN_WIDTH, fence_rail_height)) # Bottom rail
        f_rect=FIELD_LAYOUT["west_tilled"]; fence_x=f_rect.right; num_posts_vert=5 # Vertical fence
        [pygame.draw.rect(surface, FENCE_BROWN, (fence_x-fence_post_width//2, int(f_rect.top+i*(f_rect.height/num_posts_vert))-10, fence_post_width, 20)) for i in range(num_posts_vert+1)] # Posts
        pygame.draw.line(surface, FENCE_BROWN, (fence_x, f_rect.top), (fence_x, f_rect.bottom), fence_post_width//2) # Rail (simplified)

# --- UI Manager Class ---
# Handles drawing all user interface elements (text, dialogue box, etc.).
class UIManager:
    # Constructor: Stores reference to AssetLoader to get fonts.
    def __init__(self, assets: AssetLoader): self.assets = assets

    # Private helper method to draw text with specified properties.
    def _draw_text(self, surface, text, size_key, x, y, color=WHITE, align="topleft"):
        font = self.assets.get_font(size_key) # Get the font object
        if not font: font = pygame.font.SysFont(None, 20) # Use system font if specified one failed
        try:
            # Render the text into a Pygame Surface
            text_surface = font.render(str(text), True, color) # Ensure text is a string
            text_rect = text_surface.get_rect() # Get the rectangle for the rendered text
            # Position the rectangle based on the desired alignment
            if align == "center": text_rect.center = (x, y)
            elif align == "topright": text_rect.topright = (x, y)
            else: text_rect.topleft = (x, y) # Default alignment
            # Draw the rendered text onto the main surface
            surface.blit(text_surface, text_rect)
        # Handle errors during text rendering
        except Exception as e:
            print(f"Error rendering text '{text}': {e}")
            try: # Attempt to draw a fallback error message
                err_font = pygame.font.SysFont(None, 20)
                err_surf = err_font.render("TEXT ERR", True, (255, 0, 0)) # Red text
                # Position error message approximately
                if align == "center": err_rect = err_surf.get_rect(center=(x, y))
                elif align == "topright": err_rect = err_surf.get_rect(topright=(x, y))
                else: err_rect = err_surf.get_rect(topleft=(x, y))
                surface.blit(err_surf, err_rect)
            except: pass # Ignore errors even in the error handler

    # Method to draw the dialogue box interface.
    def draw_dialogue_box(self, surface, npc_text, options, selected_index):
        # Define box dimensions and position
        box_height = 190; box_margin = 40
        box_rect = pygame.Rect(box_margin, SCREEN_HEIGHT - box_height - 15, SCREEN_WIDTH - 2 * box_margin, box_height)
        # Create a temporary surface for the box (allows transparency)
        box_surface = pygame.Surface(box_rect.size, pygame.SRCALPHA)
        # Draw the background and border onto the temporary surface
        pygame.draw.rect(box_surface, DIALOGUE_BG, (0, 0, box_rect.width, box_rect.height), border_radius=15)
        pygame.draw.rect(box_surface, DIALOGUE_BORDER, (0, 0, box_rect.width, box_rect.height), 3, border_radius=15)

        # --- Draw NPC Text ---
        npc_text_str = str(npc_text) # Ensure string
        npc_font = self.assets.get_font('default_20') or pygame.font.SysFont(None, 20) # Get font
        text_area_width = box_rect.width - 40 # Calculate available width for text
        avg_char_width = npc_font.size("a")[0] or 8 # Estimate character width
        wrap_width = max(10, text_area_width // avg_char_width) # Calculate wrap width
        wrapped_text = textwrap.wrap(npc_text_str, width=wrap_width) # Wrap the text
        y_offset = 18; line_height = npc_font.get_linesize() # Starting position and line spacing
        # Draw each wrapped line (up to 4 lines)
        for line in wrapped_text[:4]:
            self._draw_text(box_surface, line, 'default_20', 20, y_offset, WHITE)
            y_offset += line_height # Move down for the next line

        # --- Draw Player Options ---
        option_y_start = y_offset + 10; option_line_height = 25 # Position for first option
        if options: # Check if there are options to draw
            option_font = self.assets.get_font('default_20') or pygame.font.SysFont(None, 20)
            # Loop through the options (max 3)
            for i, (option_text, _) in enumerate(options):
                if i >= 3: break # Stop after 3 options
                prefix = f"{i + 1}. "; display_text = prefix + str(option_text) # Add number prefix
                # Set color (yellow if selected, white otherwise)
                color = SUN_YELLOW if i == selected_index else WHITE
                try:
                     # Render the option text
                     text_surface = option_font.render(display_text, True, color)
                     text_rect = text_surface.get_rect(topleft=(25, option_y_start + i * option_line_height))
                     # Draw highlight rectangle if this option is selected
                     if i == selected_index:
                         highlight_rect = text_rect.inflate(10, 4) # Make highlight slightly bigger than text
                         pygame.draw.rect(box_surface, (255, 255, 0, 60), highlight_rect, border_radius=5) # Semi-transparent yellow
                     # Draw the option text onto the box surface
                     box_surface.blit(text_surface, text_rect)
                # Handle errors during option rendering
                except Exception as e:
                     print(f"Error rendering option text '{display_text}': {e}")
                     try: # Draw fallback error text for the option
                         err_surf = pygame.font.SysFont(None, 20).render(f"{i+1}. OPT ERR", True, (255, 0, 0))
                         box_surface.blit(err_surf, (25, option_y_start + i * option_line_height))
                     except: pass # Ignore errors in error handler

        # Draw the completed dialogue box (temporary surface) onto the main screen
        surface.blit(box_surface, box_rect.topleft)

    # Method to draw the interaction prompt ("Press [E]...") near the NPC.
    def draw_interaction_prompt(self, surface, position):
        self._draw_text(surface, "Press [E] or [SPACE] to talk", 'default_18', position[0], position[1], BLACK, align="center")

    # Method to draw the win screen overlay and text.
    def draw_win_screen(self, surface, goal_image, goal_rect_orig):
        # Draw a dark semi-transparent overlay covering the whole screen
        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 180))
        surface.blit(overlay, (0, 0))
        # If a goal image exists, draw it near the center
        if goal_image:
            goal_rect = goal_image.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 - 80))
            surface.blit(goal_image, goal_rect)
        # Draw the congratulatory text lines
        self._draw_text(surface, "Congratulations!", 'default_50', SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2, SUN_YELLOW, align="center")
        self._draw_text(surface, "You found the Golden Seed!", 'default_30', SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 + 50, WHITE, align="center")
        self._draw_text(surface, "(Press any key to exit)", 'default_20', SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 + 90, (200, 200, 200), align="center")

    # Method to draw the basic game instructions at the top-left.
    def draw_instructions(self, surface, is_talking):
        self._draw_text(surface, "Move: Arrow Keys / WASD", 'default_16', 10, 10, BLACK);
        # Show different interaction instructions depending on whether dialogue is active
        if is_talking: self._draw_text(surface, "Select: Up/Down/1/2/3 | Confirm: Enter/Space/E | Exit: ESC", 'default_16', 10, 30, BLACK)
        else: self._draw_text(surface, "Interact: E / Space (when near Pip)", 'default_16', 10, 30, BLACK)

# --- Game Class ---
# The main class that orchestrates the entire game.
class Game:
    # Constructor: Initializes Pygame, creates all game objects, sets initial state.
    def __init__(self):
        print("Initializing Pygame..."); pygame.init() # Initialize all Pygame modules
        try: pygame.mixer.init(); print("Pygame mixer initialized.") # Initialize sound mixer (optional)
        except pygame.error as e: print(f"Warning: Pygame mixer failed: {e}. No sound.")
        print("Setting up display..."); self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT)); pygame.display.set_caption("Chick Quest: OpenAI Seed Hunt"); self.clock = pygame.time.Clock() # Create window and clock
        print("Initializing game components...")
        # Create instances of all our custom classes
        self.assets = AssetLoader()
        self.llm_handler = LLMHandler(enabled=OPENAI_ENABLED)
        self.player = Player(self.assets)
        self.npc = NPC(self.assets, self.llm_handler)
        self.goal = Goal(self.assets) # Goal object holds position but isn't drawn initially
        self.scenery = Scenery()
        self.ui_manager = UIManager(self.assets)
        # Create a sprite group for easier drawing/updating of multiple sprites
        self.all_sprites = pygame.sprite.Group(); self.all_sprites.add(self.player); self.all_sprites.add(self.npc)
        # --- Game State Variables ---
        self.running = True # Controls the main game loop
        self.is_talking = False # Is the dialogue box currently active?
        self.can_talk = False # Is the player close enough to the NPC to talk?
        self.game_won = False # Has the player found the seed?
        self.selected_option_index = 0 # Which dialogue option is currently highlighted?
        self.has_sufficient_clues = False # Does player have enough info to find the seed? (Set by conversation)
        # --- End Game State ---
        # Get initial dialogue state from NPC object
        self.current_npc_text_display = self.npc._current_npc_response
        self.current_options_display = self.npc._current_options
        print("Game initialization complete.")
        if not self.has_sufficient_clues: print("Player does not yet have sufficient clues to find the seed.") # Initial status

    # --- Main Game Loop Methods ---

    # Method to handle all user input events (keyboard, window close).
    def _handle_events(self):
        # Process all events Pygame has detected since last check
        for event in pygame.event.get():
            # Handle window close button
            if event.type == pygame.QUIT: self.running = False
            # Handle key presses
            if event.type == pygame.KEYDOWN:
                # Handle ESC key press
                if event.key == pygame.K_ESCAPE:
                     if self.is_talking: # If talking, ESC closes dialogue
                         print("ESC pressed: Ending conversation."); self.is_talking = False; self.npc.reset_dialogue(); self.current_npc_text_display = self.npc._current_npc_response; self.current_options_display = self.npc._current_options; self.can_talk = False
                # If game is won, any key press exits
                elif self.game_won: self.running = False; continue # Stop processing this event
                # If dialogue box is active, handle dialogue input
                elif self.is_talking: self._handle_dialogue_input(event.key)
                # Otherwise (not talking, not won), handle interaction input
                else: self._handle_interaction_input(event.key)

    # Method to handle keyboard input specifically when the dialogue box is active.
    def _handle_dialogue_input(self, key):
        num_options = len(self.current_options_display) # How many options are there?
        if not num_options: return # Do nothing if no options
        # Handle navigation keys (Up/Down, W/S) to change selected_option_index
        if key in (pygame.K_UP, pygame.K_w): self.selected_option_index = (self.selected_option_index - 1) % num_options # Modulo wraps around
        elif key in (pygame.K_DOWN, pygame.K_s): self.selected_option_index = (self.selected_option_index + 1) % num_options
        # Handle number keys (1, 2, 3) to directly select an option
        elif key == pygame.K_1 and num_options >= 1: self._confirm_dialogue_choice(0)
        elif key == pygame.K_2 and num_options >= 2: self._confirm_dialogue_choice(1)
        elif key == pygame.K_3 and num_options >= 3: self._confirm_dialogue_choice(2)
        # Handle confirmation keys (Enter, Space, E) to choose the highlighted option
        elif key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_e): self._confirm_dialogue_choice(self.selected_option_index)

    # Method called when a dialogue option is confirmed. Contains core dialogue logic.
    def _confirm_dialogue_choice(self, index):
        # Basic error check for valid index
        if not self.current_options_display or index >= len(self.current_options_display):
            print(f"Warning: Invalid choice index {index} selected."); return
        # Get the text and state of the chosen option
        chosen_option_text, chosen_state = self.current_options_display[index]

        # --- Handle 'start' state (chosen from initial interaction) ---
        if chosen_state == 'start':
            print("Chose 'start' option. Initiating LLM conversation.")
            self.npc.start_conversation() # Tell NPC to make first AI call
            # Get the first AI response and update display
            self.current_npc_text_display, self.current_options_display = self.npc.get_dialogue()
            self.is_talking = True # Set game state to talking
            self.selected_option_index = 0 # Reset selection highlight
            # Check if the very first AI response immediately ended the conversation
            if not self.current_options_display or all(opt[1] == 'llm_end' for opt in self.current_options_display): print("LLM's first response seems to end the conversation or failed.")
            return # Finished handling 'start'

        # --- Handle 'end' state (chosen from initial interaction, means walk away) ---
        elif chosen_state == 'end':
            print("Chose 'end' option. Conversation ended by player choice.")
            self.is_talking = False; self.npc.reset_dialogue() # End talking, reset NPC
            # Reset displayed text to NPC default
            self.current_npc_text_display = self.npc._current_npc_response; self.current_options_display = self.npc._current_options; self.can_talk = False
            # Optionally reset clue flag if conversation ends without enough clues?
            # self.has_sufficient_clues = False # Uncomment if clues should be forgotten
            return # Finished handling 'end'

        # --- Handle states generated by LLM ('llm_continue', 'llm_end') ---
        elif chosen_state == 'llm_continue' or chosen_state == 'llm_end':
            # Tell the NPC to advance the dialogue (logs choice, gets next AI response if needed)
            conversation_continues = self.npc.advance_dialogue(index, self.current_options_display)

            # Check if conversation should end based on chosen state or NPC logic
            if chosen_state == 'llm_end' or not conversation_continues:
                print("Conversation ended based on chosen option state or advance_dialogue result.")
                self.is_talking = False; self.npc.reset_dialogue() # End talking, reset NPC
                # Reset displayed text to NPC default
                self.current_npc_text_display = self.npc._current_npc_response; self.current_options_display = self.npc._current_options; self.can_talk = False
                # Optionally reset clue flag?
                # self.has_sufficient_clues = False
            else: # Conversation CONTINUES
                self.is_talking = True # Stay in talking state
                # Get the new AI response/options from the NPC
                self.current_npc_text_display, self.current_options_display = self.npc.get_dialogue(); self.selected_option_index = 0 # Reset highlight

                # --- Set Clue Flag based on conversation depth ---
                clue_threshold = 4 # Number of turns needed to get clues (adjust as needed)
                # Check the turn count *within the current NPC conversation*
                if not self.has_sufficient_clues and self.npc.dialogue_count >= clue_threshold:
                    self.has_sufficient_clues = True # Set the flag!
                    print(f">>> Player has gained sufficient clues after {self.npc.dialogue_count} turns! Seed can now be found. <<<")
                # --- End Set Clue Flag ---

                # Safety check if AI failed to return options for the next turn
                if not self.current_options_display:
                    print("Warning: No options received for the next turn. Ending conversation."); self.is_talking = False; self.npc.reset_dialogue()
                    self.current_npc_text_display = self.npc._current_npc_response; self.current_options_display = self.npc._current_options; self.can_talk = False
                    # Optionally reset clue flag?
                    # self.has_sufficient_clues = False
            return # Finished handling llm states

        # --- Fallback for unknown states ---
        else:
             print(f"Warning: Unknown option state '{chosen_state}'. Ending conversation."); self.is_talking = False; self.npc.reset_dialogue()
             self.current_npc_text_display = self.npc._current_npc_response; self.current_options_display = self.npc._current_options; self.can_talk = False
             return # Finished handling unknown state

    # Method to handle keyboard input when NOT in dialogue.
    def _handle_interaction_input(self, key):
        # Check if player is close enough and pressed an interaction key
        if self.can_talk and key in (pygame.K_e, pygame.K_SPACE):
            print("Interaction key pressed near NPC.")
            self.is_talking = True; self.selected_option_index = 0 # Enter talking state
            # Display the initial non-AI options first
            self.current_npc_text_display = self.npc._current_npc_response
            self.current_options_display = self.npc._current_options
            print("Showing initial interaction options. Choose 'start' option to talk to AI.")

    # Method called every frame to update game state (movement, checks).
    def _update(self):
        # Don't update world state if talking or game is already won
        if self.is_talking or self.game_won: return
        # Get currently pressed keys
        keys = pygame.key.get_pressed()
        # Tell the player object to update its position based on keys
        self.player.update(keys)
        # Check distance between player and NPC to see if interaction is possible
        dist_sq = (self.player.rect.centerx - self.npc.rect.centerx)**2 + (self.player.rect.centery - self.npc.rect.centery)**2
        self.can_talk = dist_sq < INTERACTION_DISTANCE_SQ # Update can_talk flag

        # --- REVISED WIN CONDITION CHECK ---
        # Check for collision between player and goal's rectangle only if:
        # 1. Game isn't already won.
        # 2. Player has received sufficient clues.
        if not self.game_won and self.has_sufficient_clues and self.player.rect.colliderect(self.goal.rect):
            print(">>> Player found the seed location with sufficient clues! Game Won! <<<")
            self.game_won = True # Set win state
        # --- END REVISED CHECK ---

    # Method called every frame to draw everything onto the screen.
    def _draw(self):
        # Draw background first
        self.scenery.draw(self.screen)
        # Draw sprites (Player and NPC)
        self.all_sprites.draw(self.screen)

        # --- GOAL SPRITE IS NOT DRAWN HERE ---
        # The goal remains invisible until the win screen.

        # --- Draw UI Elements Conditionally ---
        # Draw interaction prompt if close to NPC, not talking, and game not won
        if self.can_talk and not self.is_talking and not self.game_won: self.ui_manager.draw_interaction_prompt(self.screen, (self.npc.rect.centerx, self.npc.rect.top - 20))
        # Draw dialogue box if currently talking
        if self.is_talking: self.ui_manager.draw_dialogue_box(self.screen, self.current_npc_text_display, self.current_options_display, self.selected_option_index)
        # Draw instructions if game not won
        if not self.game_won: self.ui_manager.draw_instructions(self.screen, self.is_talking)
        # Draw win screen if game is won (drawn last, on top)
        if self.game_won:
            self.ui_manager.draw_win_screen(self.screen, self.goal.image, self.goal.rect) # Pass goal image for display

        # Update the actual display to show the newly drawn frame
        pygame.display.flip()

    # Method containing the main game loop.
    def run(self):
        print("\nStarting main game loop...")
        # Loop continues as long as self.running is True
        while self.running:
            self._handle_events() # Check for input
            self._update()        # Update game state
            self._draw()          # Draw the current frame
            self.clock.tick(FPS)  # Pause briefly to control frame rate
        # After the loop ends (self.running is False)
        self._cleanup() # Clean up Pygame resources

    # Method to shut down Pygame cleanly.
    def _cleanup(self):
        print("Exiting game...")
        pygame.mixer.quit() # Quit sound mixer
        pygame.quit()       # Quit all Pygame modules

# --- Main Execution Block ---
# This code runs only when the script is executed directly.
if __name__ == "__main__":
    # Attempt to change the working directory to the script's location
    # This helps ensure relative paths for assets work correctly.
    try:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        os.chdir(script_dir)
        print(f"Changed CWD to: {script_dir}")
    # Handle cases where finding the script directory might fail (e.g., interactive mode)
    except NameError: print(f"Running interactively? Assets expected in CWD: {os.getcwd()}")
    except Exception as e: print(f"Warning: Could not change CWD: {e}. CWD is {os.getcwd()}")

    # Main execution block with error handling
    try:
        game = Game() # Create an instance of the Game class
        game.run()    # Start the main game loop
    # Catch any unexpected errors during game execution
    except Exception as e:
        print("\n" + "="*30 + " FATAL ERROR " + "="*30)
        traceback.print_exc() # Print detailed error information
        print("="*60)
        pygame.quit() # Attempt to clean up Pygame even after an error

    # Ensure the program exits
    sys.exit()