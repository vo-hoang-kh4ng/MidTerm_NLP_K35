import os
from dotenv import load_dotenv

print("Current dir:", os.getcwd())

loaded = load_dotenv()
print("Dotenv loaded:", loaded)