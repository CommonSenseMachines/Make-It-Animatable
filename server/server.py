import os
import sys
import tempfile
import base64
import shutil
import logging
import pickle
from pathlib import Path
from contextlib import asynccontextmanager
from typing import List, Optional, Literal

# Third-party imports
import httpx
import anthropic
from aiocache import cached, Cache
from pydantic import BaseModel, Field
from fastapi import FastAPI, HTTPException, Header, Depends
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from azure.storage.blob import BlobServiceClient, BlobClient

SERVER_ROOT = Path(__file__).parent  # This is now /project/server/
AZURE_CONNECTION_STRING = (
    "DefaultEndpointsProtocol=https;AccountName=meshanimation;"
    f"AccountKey={os.getenv('MESH_ANIMATION_BUCKET_KEY')}"
    "EndpointSuffix=core.windows.net"
)
ANTHROPIC_API_KEY = "xxxxxx"
AZURE_CONTAINER_NAME = "fbx-animation-files"

# ---- import the core Make-It-Animatable code --------------------
# PARENT_DIR will be /project/
PARENT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.append(PARENT_DIR)
import app as mia  # our Gradio-based pipeline functions

from app import (
    DB,
    init_models,
    prepare_input,
    preprocess,
    infer,
    vis,
    vis_blender,
)

# ---- NEW: Import the blender utility directly -------------------
from util import blender_join_and_save, render_glb_frames, render_thumbnail

# -----------------------------------------------------------------


# ensure the module attributes don't shadow our placeholders
for _name in [
    "state",
    "output_joints_coarse",
    "output_normed_input",
    "output_sample",
    "output_joints",
    "output_bw",
    "output_rest_vis",
    "output_rest_lbs",
    "output_anim",
    "output_anim_vis",
]:
    setattr(mia, _name, _name)

# -----------------------------------------------------------------
#  Global animation lookup
# -----------------------------------------------------------------
ANIMATION_DB = {}


# -----------------------------------------------------------------
#  Lifespan: initialise models once at startup
# -----------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    # load or scan animation DB
    animation_pkl = "animation.pkl"
    loaded = False
    if os.path.exists(animation_pkl):
        try:
            with open(animation_pkl, "rb") as f:
                ANIMATION_DB.update(pickle.load(f))
            loaded = True
            print(f"✅ Loaded {len(ANIMATION_DB)} animations from {animation_pkl}")
        except Exception as e:
            print(f"❌ Failed to load pickle DB: {e}")

    if not loaded and os.path.isdir("./data"):
        for idx, fname in enumerate(os.listdir("./data")):
            if fname.lower().endswith(".fbx"):
                ANIMATION_DB[f"motion_{idx}"] = {
                    "file_path": os.path.join("./data", fname),
                    "name": Path(fname).stem,
                }
        print(f"✅ Scanned {len(ANIMATION_DB)} .fbx files in ./data")

    if not ANIMATION_DB and os.path.exists("./data/Standard Run.fbx"):
        ANIMATION_DB["default"] = {
            "file_path": "./data/Standard Run.fbx",
            "name": "Standard Run",
        }
        print("✅ Added default Standard Run animation")

    init_models()
    print("✅ Make-It-Animatable models initialised")
    yield


app = FastAPI(
    lifespan=lifespan,
    title="Make-It-Animatable API",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class AnimationRequest(BaseModel):
    mesh_b64_str: str
    animation_name: Literal["running", "jumping", "punching", "walking", "waving"]
    is_gs: bool = False
    opacity_threshold: float = 0.0
    no_fingers: bool = False
    rest_pose_type: Optional[str] = None
    ignore_pose_parts: List[str] = Field(default_factory=list)
    input_normal: bool = False
    bw_fix: bool = True
    bw_vis_bone: str = "LeftArm"
    reset_to_rest: bool = True
    animation_file: Optional[str] = (
        None  # <-- FIXED: Changed from 'str = None' to 'Optional[str] = None'
    )
    retarget: bool = True
    inplace: bool = True


# This function remains unchanged
def download_blob_to_temp_file(blob_url: str) -> str:
    blob_name = blob_url.split(f"{AZURE_CONTAINER_NAME}/")[-1]
    blob_client = BlobClient.from_connection_string(
        conn_str=AZURE_CONNECTION_STRING,
        container_name=AZURE_CONTAINER_NAME,
        blob_name=blob_name,
    )
    temp_f = tempfile.NamedTemporaryFile(suffix=".fbx", delete=False)
    with temp_f as f:
        download_stream = blob_client.download_blob()
        f.write(download_stream.readall())
    return temp_f.name


# This function remains unchanged
def find_best_motion_match(text_prompt: str) -> str:
    # (Function content is unchanged)
    try:
        blob_service_client = BlobServiceClient.from_connection_string(
            AZURE_CONNECTION_STRING
        )
        container_client = blob_service_client.get_container_client(
            AZURE_CONTAINER_NAME
        )
        blob_list = container_client.list_blobs()
        animation_files = [b.name for b in blob_list if b.name.lower().endswith(".fbx")]
        if not animation_files:
            raise HTTPException(500, "No animation files in Azure.")

        animation_db = {Path(n).stem: n for n in animation_files}

        def fallback(prompt):
            p = prompt.lower()
            mapping = [
                (["run", "jog", "sprint"], "run"),
                (["walk", "stroll"], "walk"),
                (["jump", "hop"], "jump"),
                (["dance", "boogie"], "dance"),
                (["idle", "stand"], "idle"),
            ]
            for keys, key in mapping:
                if any(k in p for k in keys):
                    for name in animation_db:
                        if key in name.lower():
                            return animation_db[name]
            return animation_files[0]

        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        prompt = f"""
User wants an animation: "{text_prompt}"

Choose the BEST match from:
{', '.join(animation_db.keys())}

Only reply with the name (no extension).
"""
        msg = client.messages.create(
            model="claude-3-haiku-20240307",
            max_tokens=100,
            messages=[{"role": "user", "content": prompt}],
        )
        resp = getattr(msg, "content", "")
        name = str(resp).strip()
        if name in animation_db:
            chosen = animation_db[name]
        else:
            chosen = next(
                (animation_db[n] for n in animation_db if name.lower() in n.lower()),
                fallback(text_prompt),
            )
        local_dir = Path("./data")
        local_dir.mkdir(exist_ok=True)
        local_path = local_dir / Path(chosen).name
        if not local_path.exists():
            blob_client = container_client.get_blob_client(chosen)
            with open(local_path, "wb") as f:
                f.write(blob_client.download_blob().readall())
        return str(local_path)
    except Exception as e:
        print(f"Error in find_best_motion_match: {e}")
        return "./data/Standard Run.fbx"


# This function remains unchanged
@cached(ttl=300, cache=Cache.MEMORY)
async def _fetch_user_data_from_api(header_name: str, header_value: str) -> dict:
    # (Function content is unchanged)
    endpoints = [
        "https://api.csm.ai/user/userdata",
        "https://devapi.csm.ai/user/userdata",
    ]
    async with httpx.AsyncClient() as client:
        for url in endpoints:
            try:
                resp = await client.get(url, headers={header_name: header_value})
                if resp.status_code == 200:
                    return resp.json()
            except httpx.RequestError:
                continue
    raise HTTPException(status_code=403, detail="Invalid credentials")


# This function remains unchanged
async def _verify_api_key(
    x_api_key: Optional[str] = Header(None),
    authorization: Optional[str] = Header(None, alias="Authorization"),
) -> dict:
    # (Function content is unchanged)
    if x_api_key:
        name, value = "x-api-key", x_api_key
    elif authorization:
        name, value = "Authorization", authorization
    else:
        raise HTTPException(status_code=401, detail="Missing auth header")
    try:
        return await _fetch_user_data_from_api(name, value)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Auth check failed: {e}")


# This function remains unchanged
def _prepare_input_memory(mesh_bytes: bytes, db: DB):
    """
    Decodes mesh bytes, saves to a temp file, and then calls the core prepare_input function.
    """
    if not mesh_bytes:
        raise HTTPException(
            status_code=400,
            detail="Received empty mesh data. The 'mesh_b64_str' field in the request payload cannot be empty.",
        )
    # Detect file extension from mesh byte data
    if mesh_bytes[:4] == b"glTF":
        ext = ".glb"
    elif mesh_bytes.startswith(b"Kaydara FBX"):
        ext = ".fbx"
    else:
        raise HTTPException(400, "Unsupported mesh format. Supported: .glb or .fbx")

    input_filepath = None
    try:
        # Create temporary input and output paths
        with tempfile.NamedTemporaryFile(
            suffix=ext, dir="/dev/shm", delete=False
        ) as tmp_input:
            tmp_input.write(mesh_bytes)
            tmp_input.flush()
            input_filepath = tmp_input.name

        # Now, call the core `prepare_input` with the Blender-processed file
        prepare_input(
            input_path=input_filepath,
            is_gs=False,
            opacity_threshold=0.0,
            db=db,
            export_temp=False,
        )
    except Exception as e:
        # Catch any exception from the direct call (e.g., ValueError, RuntimeError)
        error_message = f"Mesh preparation failed: {e}"
        logging.error(error_message, exc_info=True)
        raise HTTPException(status_code=500, detail=error_message) from e
    finally:
        # Clean up temporary files
        if input_filepath and os.path.exists(input_filepath):
            os.unlink(input_filepath)


# This function remains unchanged
def run_pipeline(mesh_bytes: bytes, animation_name: str) -> DB:
    # (Function content is unchanged)
    db = DB()
    _prepare_input_memory(mesh_bytes, db)
    preprocess(db)
    infer(False, db)
    vis(True, "LeftArm", False, db)
    vis_blender(
        reset_to_rest=True,
        remove_fingers=False,
        rest_pose_type="",
        ignore_pose_parts=[],
        animation_file=str(
            Path("/home/ray/csm/models/make_it_animatable/data")
            / f"{animation_name}.fbx"
        ),
        retarget=True,
        inplace=True,
        db=db,
    )
    return db


@app.post("/animate")
async def animate(
    payload: AnimationRequest,
    _: dict = Depends(_verify_api_key),
):
    # Use PARENT_DIR to construct the path to animation-fbx-files
    animation_file_path = os.path.join(
        PARENT_DIR, "animation-fbx-files", f"{payload.animation_name}.fbx"
    )
    if not os.path.exists(animation_file_path):
        raise HTTPException(
            status_code=404, detail=f"Animation file not found: {animation_file_path}"
        )

    # Assign the resolved path back to the payload field
    # Pydantic will now see a string, not None
    payload.animation_file = animation_file_path

    # Define paths that will be created, initialize to None
    glb_path = None
    output_dir = None
    gif_path = None
    thumbnail_output_path = None

    try:
        try:
            db = run_pipeline(
                base64.b64decode(payload.mesh_b64_str), payload.animation_name
            )
        except HTTPException:
            raise
        except Exception as e:
            import traceback

            logging.error("Pipeline failed\n%s", traceback.format_exc())
            raise HTTPException(status_code=500, detail=f"Pipeline failed: {e}")

        glb_path = db.anim_vis_path
        if not glb_path or not os.path.isfile(glb_path):
            raise HTTPException(status_code=500, detail="No GLB file was produced.")

        # --- Direct calls to rendering scripts for GIF and Thumbnail ---
        try:
            # 1. Define output paths for the render artifacts
            base_path = Path(glb_path)
            output_dir = base_path.parent / f"{base_path.stem}_render_output"
            frames_output_dir = output_dir / "frames"
            thumbnail_output_path = output_dir / f"{base_path.stem}_thumbnail.png"
            os.makedirs(frames_output_dir, exist_ok=True)

            # 2. Directly call the thumbnail rendering function
            logging.info(f"Starting thumbnail rendering for {glb_path}")
            render_thumbnail.render_thumbnail(glb_path, str(thumbnail_output_path))
            logging.info(f"Thumbnail successfully rendered to {thumbnail_output_path}")

            # 3. Directly call the frame rendering function to get the GIF
            logging.info(f"Starting frame rendering and GIF creation for {glb_path}")
            gif_path = render_glb_frames.render_frames(glb_path, str(frames_output_dir))
            if gif_path:
                logging.info(f"Frames and GIF successfully created. GIF at: {gif_path}")
            else:
                logging.warning(
                    "render_frames completed but did not return a GIF path."
                )

        except Exception as e:
            # Log rendering errors but don't block the response
            error_message = f"An unexpected error occurred during rendering: {e}"
            logging.error(error_message, exc_info=True)
            print(f"Non-critical rendering error: {error_message}")

        # --- Base64 encode all three files for the JSON response ---
        glb_base64 = None
        if glb_path and os.path.isfile(glb_path):
            with open(glb_path, "rb") as f:
                glb_base64 = base64.b64encode(f.read()).decode("utf-8")

        gif_base64 = None
        if gif_path and os.path.isfile(gif_path):
            with open(gif_path, "rb") as f:
                gif_base64 = base64.b64encode(f.read()).decode("utf-8")

        thumb_base64 = None
        if thumbnail_output_path and os.path.isfile(thumbnail_output_path):
            with open(thumbnail_output_path, "rb") as f:
                thumb_base64 = base64.b64encode(f.read()).decode("utf-8")

        response_data = {
            "mesh_base64": glb_base64,
            "gif_base64": gif_base64,
            "thumbnail_base64": thumb_base64,
        }

        return JSONResponse(content=response_data)

    finally:
        # --- Cleanup ---
        # Clean up the temporary directory created for rendering artifacts
        if output_dir and os.path.isdir(output_dir):
            try:
                shutil.rmtree(output_dir)
                logging.info(f"Successfully cleaned up render directory: {output_dir}")
            except Exception as e:
                logging.error(f"Failed to clean up render directory {output_dir}: {e}")


if __name__ == "__main__":
    import uvicorn
    import argparse

    parser = argparse.ArgumentParser(
        description="Run the Make-It-Animatable FastAPI server."
    )

    parser.add_argument(
        "--port", type=int, default=8000, help="Port to run the server on."
    )

    args = parser.parse_args()

    print(f"Starting server on http://0.0.0.0:{args.port}")
    uvicorn.run(
        "server:app", host="0.0.0.0", port=args.port, reload=False, log_level="info"
    )
