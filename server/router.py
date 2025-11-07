# router.py
import httpx
import itertools
from typing import List, Optional, Literal
import argparse
import sys

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
import uvicorn

# Timeout for requests to worker servers (in seconds).
WORKER_TIMEOUT = 300.0

# --- Pydantic Model ---
# This model MUST exactly match the AnimationRequest model in server.py
# to ensure proper validation and serialization.
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
    animation_file: Optional[str] = None
    retarget: bool = True
    inplace: bool = True

def create_app(env: str):
    """
    Factory function to create and configure the FastAPI application.
    This allows dynamic configuration based on the environment.
    """
    app = FastAPI(
        title="Animation Request Router",
        description="A FastAPI server that acts as a load balancer, routing animation requests to a pool of worker servers.",
        version="1.0.0",
    )

    # Define worker ports based on the environment
    if env == "dev":
        worker_ports = [8001, 8002, 8003]
    else: # prod
        worker_ports = [9001, 9002, 9003]

    # Populate the list of worker servers
    worker_servers_list = [f"http://localhost:{p}" for p in worker_ports]
    
    if not worker_servers_list:
        print("❌ Error: Worker server list is empty. Exiting.")
        # In a real FastAPI app, you might raise an exception or configure a fallback
        sys.exit(1) 

    # Store necessary state on the app instance
    app.state.worker_servers = worker_servers_list
    app.state.server_cycle = itertools.cycle(worker_servers_list)

    print(f"🚀 Configuring Animation Router for '{env.upper()}' environment...")
    print(f"   - Routing requests to: {app.state.worker_servers}")

    @app.post("/animate")
    async def route_animation_request(payload: AnimationRequest, request: Request):
        """
        Receives an animation request, forwards it to the next available worker
        server using a round-robin strategy, and streams the worker's response back.
        """
        # Access the server_cycle from app.state
        worker_url = next(app.state.server_cycle)
        forward_url = f"{worker_url}/animate"

        print(f"Routing request to worker: {forward_url}")

        # Extract relevant headers to forward for authentication.
        headers_to_forward = {
            "Content-Type": "application/json",
        }
        if "authorization" in request.headers:
            headers_to_forward["Authorization"] = request.headers["authorization"]
        if "x-api-key" in request.headers:
            headers_to_forward["x-api-key"] = request.headers["x-api-key"]

        # Asynchronously forward the request to the selected worker
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    url=forward_url,
                    json=payload.model_dump(),
                    headers=headers_to_forward,
                    timeout=WORKER_TIMEOUT,
                )
                response.raise_for_status()
            except httpx.ConnectError as e:
                error_message = f"Could not connect to worker server at {worker_url}. The service may be down. Error: {e}"
                print(error_message)
                raise HTTPException(status_code=503, detail=error_message)
            except httpx.ReadTimeout as e:
                error_message = f"Request to worker server at {worker_url} timed out after {WORKER_TIMEOUT} seconds. Error: {e}"
                print(error_message)
                raise HTTPException(status_code=504, detail=error_message)
            except httpx.HTTPStatusError as e:
                worker_response_body = e.response.json()
                raise HTTPException(
                    status_code=e.response.status_code,
                    detail=worker_response_body.get("detail", "An unknown error occurred on the worker server."),
                )

        return JSONResponse(content=response.json(), status_code=response.status_code)

    @app.get("/health", summary="Health Check")
    def health_check():
        """A simple endpoint to verify that the router is running and view its configuration."""
        return {
            "status": "ok",
            "message": "Router is active.",
            "configured_workers": app.state.worker_servers # Access from app.state
        }
    
    return app


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the Animation Router.")
    parser.add_argument("--port", type=int, required=True, help="Port to run the router on.")
    parser.add_argument("--env", type=str, choices=["dev", "prod"], required=True, help="Environment to configure for ('dev' or 'prod').")
    args = parser.parse_args()
    
    # Create the app instance with the specified environment
    # The 'app_instance' object here is the one that Uvicorn will run
    app_instance = create_app(args.env)

    print(f"   - Listening on http://0.0.0.0:{args.port}")
    uvicorn.run(app_instance, host="0.0.0.0", port=args.port, reload=False)