import bpy
import sys
import os
from pathlib import Path

# Pillow is now required for GIF creation
try:
    from PIL import Image
except ImportError:
    print("Error: The 'Pillow' library is required to create a GIF. Please install it.", file=sys.stderr)
    print("Example: /path/to/blender/python/bin/python -m pip install Pillow", file=sys.stderr)
    sys.exit(1)

# Assumes render_utils is in the same directory, e.g., 'util/render_utils.py'
try:
    from . import render_utils
except ImportError:
    import render_utils


def render_frames(glb_path, output_dir):
    """
    Renders an animated GLB file to a sequence of PNG frames and assembles them
    into a single animated GIF.
    """
    # --- Scene Setup ---
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete()

    # --- Import GLB ---
    if not os.path.exists(glb_path):
        raise FileNotFoundError(f"Error: GLB file not found at {glb_path}")

    bpy.ops.import_scene.gltf(filepath=glb_path)
    scene = bpy.context.scene

    # --- Camera Setup using Utilities ---
    render_utils.create_and_setup_camera(scene)
    render_utils.frame_all_objects(scene)

    # --- Set Frame Range from Animation ---
    anim_data_objects = [obj for obj in scene.objects if obj.animation_data and obj.animation_data.action]
    if not anim_data_objects:
        raise RuntimeError("No animation data found in the imported GLB.")
    min_frame, max_frame = float('inf'), float('-inf')
    for obj in anim_data_objects:
        action = obj.animation_data.action
        if action and action.frame_range:
            min_frame = min(min_frame, action.frame_range[0])
            max_frame = max(max_frame, action.frame_range[1])
    if min_frame == float('inf') or max_frame == float('-inf'):
         raise RuntimeError("Could not determine frame range from animation.")
    scene.frame_start = int(min_frame)
    scene.frame_end = int(max_frame)

    # --- Configure Rendering ---
    scene.render.image_settings.file_format = 'PNG'
    scene.render.image_settings.color_mode = 'RGB'
    scene.render.film_transparent = False
    
    # Set the World background to pure white
    world = scene.world
    if world is None:
        world = bpy.data.worlds.new("World")
        scene.world = world
    world.use_nodes = True
    bg_node = world.node_tree.nodes.get('Background')
    if bg_node:
        bg_node.inputs['Color'].default_value = (1.0, 1.0, 1.0, 1.0)
        # Set strength to 1.0 for a pure white background
        bg_node.inputs['Strength'].default_value = 0.3

    # --- Performance Settings ---
    scene.render.threads_mode = 'FIXED'
    desired_threads = 20
    scene.render.threads = desired_threads
    print(f"Set render threads mode to FIXED with {desired_threads} threads.")
    scene.eevee.taa_render_samples = 16
    print(f"Render samples set to {scene.eevee.taa_render_samples} for faster rendering.")
    
    # --- Render Animation Manually ---
    print(f"Rendering frames {scene.frame_start} to {scene.frame_end} manually...")
    for frame in range(scene.frame_start, scene.frame_end + 1):
        scene.frame_set(frame)
        scene.render.filepath = os.path.join(output_dir, f"frame_{frame:04d}")
        print(f"Rendering frame {frame} of {scene.frame_end}...")
        bpy.ops.render.render(write_still=True)
    print("Frame rendering complete.")

    # --- GIF Construction Logic ---
    print("Assembling animated GIF...")
    frame_files = sorted(
        [os.path.join(output_dir, f) for f in os.listdir(output_dir) if f.endswith(".png")]
    )
    if not frame_files:
        raise RuntimeError("Blender did not produce any output frames. Cannot create GIF.")
    
    images = [Image.open(f) for f in frame_files]
    output_parent_dir = Path(output_dir).parent
    gif_path = output_parent_dir / f"{Path(glb_path).stem}_animated.gif"
    
    images[0].save(
        str(gif_path),
        save_all=True,
        append_images=images[1:],
        duration=40,
        loop=0,
        disposal=2
    )

    print(f"Animated GIF successfully saved to: {gif_path}")
    return str(gif_path)


if __name__ == "__main__":
    argv = sys.argv
    try:
        args = argv[argv.index("--") + 1:]
    except ValueError:
        args = []
    if len(args) != 2:
        print("Usage: blender --background --python render_glb_frames.py -- <path_to_glb> <frame_output_directory>", file=sys.stderr)
        sys.exit(1)
    input_glb, frame_output_dir = args
    os.makedirs(frame_output_dir, exist_ok=True)
    try:
        final_gif_path = render_frames(input_glb, frame_output_dir)
        print(f"\nFinal output path: {final_gif_path}")
    except (FileNotFoundError, RuntimeError, ImportError) as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)