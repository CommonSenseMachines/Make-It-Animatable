# test_client.py
import os
import sys
import json
import base64
import requests
from typing import Literal, Optional # Import Optional

# --- CONFIG ---
API_URL = "http://localhost:8000/animate"
API_KEY = "F3b5CDFb5ED2A306D1E7814528bD3224" # <--- IMPORTANT: Replace with a valid API key
MESH_PATH = "./mesh2.glb"                 # <--- Path to your input mesh file (e.g., .glb or .fbx)

# --- Define output paths for all three files ---
OUTPUT_GLB = "./animated_mesh.glb"
OUTPUT_GIF = "./animation.gif"
OUTPUT_THUMBNAIL = "./thumbnail.png"

# Choose an animation from the supported literals
# "running", "jumping", "punching", "walking", "waving"
ANIMATION_NAME: Literal["running", "jumping", "punching", "walking", "waving"] = "running"

# --- HELPERS ---
def b64_file(path: str) -> str:
    """Read a file and return its base-64 encoded contents as a UTF-8 string."""
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")

# --- BUILD PAYLOAD ---
if not os.path.isfile(MESH_PATH):
    print(f"Error: mesh file not found: {MESH_PATH}", file=sys.stderr)
    sys.exit(1)

mesh_b64 = b64_file(MESH_PATH)

payload = {
    "mesh_b64_str": mesh_b64,
    "animation_name": ANIMATION_NAME,
    "animation_file": None, # <--- FIXED: Explicitly send None
}

# --- SEND REQUEST ---
headers = {
    "Content-Type": "application/json",
    "x-api-key": API_KEY, # Required by _verify_api_key dependency
}

print(f"Sending request to {API_URL} with animation: '{ANIMATION_NAME}'")
# The server now returns a JSON response, so stream=True is not needed.
resp = requests.post(API_URL, headers=headers, json=payload)

# --- PROCESS RESPONSE ---
if resp.status_code == 200:
    print("✅ Request successful. Processing JSON response...")
    # The server now returns a JSON object.
    response_data = resp.json()

    # 1. Save the animated GLB mesh
    mesh_b64 = response_data.get("mesh_base64")
    if mesh_b64:
        with open(OUTPUT_GLB, "wb") as f:
            f.write(base64.b64decode(mesh_b64))
        print(f"✅ Saved animated GLB file → {OUTPUT_GLB}")
    else:
        print("❌ No mesh data ('mesh_base64') found in the response.")

    # 2. Save the animation GIF
    gif_b64 = response_data.get("gif_base64")
    if gif_b64:
        with open(OUTPUT_GIF, "wb") as f:
            f.write(base64.b64decode(gif_b64))
        print(f"✅ Saved animation GIF → {OUTPUT_GIF}")
    else:
        print("⚠️ No GIF data ('gif_base64') found. Rendering on server may have failed.")

    # 3. Save the thumbnail image
    thumbnail_b64 = response_data.get("thumbnail_base64")
    if thumbnail_b64:
        with open(OUTPUT_THUMBNAIL, "wb") as f:
            f.write(base64.b64decode(thumbnail_b64))
        print(f"✅ Saved thumbnail image → {OUTPUT_THUMBNAIL}")
    else:
        print("⚠️ No thumbnail data ('thumbnail_base64') found. Rendering on server may have failed.")

else:
    print(f"❌ Request failed [{resp.status_code}]: {resp.text}", file=sys.stderr)
    sys.exit(1)