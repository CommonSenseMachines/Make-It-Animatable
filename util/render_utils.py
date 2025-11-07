import bpy
from mathutils import Vector

def create_and_setup_camera(scene):
    """
    Creates and sets up a camera and a three-point light system.
    Returns the created camera object.
    """
    # --- Create Camera ---
    bpy.ops.object.camera_add()
    camera = bpy.context.object
    scene.camera = camera
    camera.data.lens = 50  # Set focal length

    # --- Create a Softer, more Natural Three-Point Light System ---
    
    # 1. Key Light (Main light source, slightly warm)
    bpy.ops.object.light_add(type='AREA', location=(-4, -4, 5))
    key_light = bpy.context.object
    key_light.data.energy = 1000      # Reduced energy for softer light
    key_light.data.size = 10          # Increased size for softer shadows
    key_light.data.color = (1.0, 0.95, 0.8) # Add a warm tint
    key_light.rotation_euler = (0, 0.7, -0.7)

    # 2. Fill Light (Softens shadows, slightly cool)
    bpy.ops.object.light_add(type='AREA', location=(4, -2, 2))
    fill_light = bpy.context.object
    fill_light.data.energy = 500       # Lower energy for less contrast
    fill_light.data.size = 12          # Greatly increased size for very soft fill
    fill_light.data.color = (0.8, 0.9, 1.0) # Add a cool tint
    fill_light.rotation_euler = (0, 0.5, 0.7)

    # 3. Back Light (Rim light, neutral)
    bpy.ops.object.light_add(type='AREA', location=(2, 4, 3))
    back_light = bpy.context.object
    back_light.data.energy = 700      # Reduced energy for a subtler rim effect
    back_light.data.size = 10         # Increased size
    back_light.rotation_euler = (0.8, 0, 2.3)

    print("Created camera and a softer, more natural three-point lighting system.")
    return camera


def frame_all_objects(scene):
    """
    Calculates a bounding box encompassing all mesh objects across the entire
    animation range and adjusts the camera to frame this box.
    """
    mesh_objects = [obj for obj in scene.objects if obj.type == 'MESH']
    if not mesh_objects:
        print("No mesh objects found to frame.")
        return

    min_corner = Vector((float('inf'), float('inf'), float('inf')))
    max_corner = Vector((float('-inf'), float('-inf'), float('-inf')))

    original_frame = scene.frame_current
    depsgraph = bpy.context.evaluated_depsgraph_get()

    for frame in range(scene.frame_start, scene.frame_end + 1):
        scene.frame_set(frame)
        for obj in mesh_objects:
            obj_eval = obj.evaluated_get(depsgraph)
            world_bbox_corners = [obj_eval.matrix_world @ Vector(corner) for corner in obj_eval.bound_box]
            
            for corner in world_bbox_corners:
                min_corner.x = min(min_corner.x, corner.x)
                min_corner.y = min(min_corner.y, corner.y)
                min_corner.z = min(min_corner.z, corner.z)
                max_corner.x = max(max_corner.x, corner.x)
                max_corner.y = max(max_corner.y, corner.y)
                max_corner.z = max(max_corner.z, corner.z)

    scene.frame_set(original_frame)

    if min_corner.x == float('inf'):
        print("Could not determine the bounding box of the objects.")
        return

    # --- 2. Use the bounding box to determine camera placement ---
    center = (min_corner + max_corner) / 2.0
    bbox_size = (max_corner - min_corner).length
    
    if bbox_size == 0:
        bbox_size = 1.0

    camera_direction = Vector((-2, -2, 1)).normalized()
    
    # --- 3. Position and point the camera ---
    camera = scene.camera
    if not camera:
        print("No active camera in the scene to position.")
        return
        
    # Position camera based on original center
    camera.location = center + camera_direction * bbox_size * 1.0
    
    # Adjust the target point to be lower, making the subject appear higher
    target_point = center.copy()
    bbox_height = max_corner.z - min_corner.z
    target_point.z += bbox_height * 0.15  # Shift target down by 15% of mesh height

    # Point the camera to the new adjusted target
    direction_to_target = target_point - camera.location
    camera.rotation_euler = direction_to_target.to_track_quat('-Z', 'Y').to_euler()

    print("Camera framed all objects across the entire animation.")