import bpy
import sys
import os

# Assumes render_utils is in the same directory, e.g., 'util/render_utils.py'
try:
    from . import render_utils
except ImportError:
    # Fallback for running the script directly
    import render_utils

def render_thumbnail(glb_path, output_image_path):
    """
    Renders a single thumbnail image from a GLB file's starting pose.
    """
    # --- Scene Setup ---
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete()

    # --- Import GLB ---
    if not os.path.exists(glb_path):
        raise FileNotFoundError(f"Error: GLB file not found at {glb_path}")
    
    bpy.ops.import_scene.gltf(filepath=glb_path)
    
    scene = bpy.context.scene

    # --- Set to Starting Frame ---
    scene.frame_set(scene.frame_start)
    
    # --- Camera Setup using Utilities ---
    render_utils.create_and_setup_camera(scene)
    render_utils.frame_all_objects(scene)
    
    # --- Configure Rendering ---
    scene.render.image_settings.file_format = 'PNG'
    scene.render.filepath = output_image_path
    # The thumbnail can have a transparent background, which is often desirable.
    scene.render.film_transparent = True
    scene.render.image_settings.color_mode = 'RGBA'
    scene.render.resolution_x = 512
    scene.render.resolution_y = 512
    
    # --- NEW: Performance Settings ---
    scene.render.threads_mode = 'FIXED'
    desired_threads = 20
    scene.render.threads = desired_threads
    print(f"Set render threads mode to FIXED with {desired_threads} threads.")
    # Reduce render samples for faster previews (default is 64 for Eevee)
    scene.eevee.taa_render_samples = 16
    print(f"Render samples set to {scene.eevee.taa_render_samples} for faster rendering.")
    # --- END of Performance Settings ---
    
    # --- Render a Single Frame ---
    print(f"Rendering thumbnail to {output_image_path}...")
    bpy.ops.render.render(write_still=True)
    print("Thumbnail rendering complete.")


if __name__ == "__main__":
    argv = sys.argv
    try:
        args = argv[argv.index("--") + 1:]
    except ValueError:
        args = []

    if len(args) != 2:
        print("Usage: blender --background --python render_thumbnail.py -- <path_to_glb> <output_image_path>", file=sys.stderr)
        sys.exit(1)

    input_glb, output_image = args
    
    try:
        render_thumbnail(input_glb, output_image)
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)