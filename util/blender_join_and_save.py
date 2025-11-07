# util/blender_join_and_save.py
import bpy
import sys
import os

def join_and_save_mesh(input_path, output_path):
    """
    Clears the Blender scene by deleting all objects, imports a mesh,
    removes non-essential objects, joins all mesh parts into a single object,
    cleans unused data, and exports it, preserving original positions.
    """
    # Clear existing objects without resetting scene settings
    if bpy.context.scene.objects:
        bpy.ops.object.select_all(action='SELECT')
        bpy.ops.object.delete(use_global=False)

    # Import the mesh
    if input_path.lower().endswith('.fbx'):
        bpy.ops.import_scene.fbx(filepath=input_path)
    elif input_path.lower().endswith(('.glb', '.gltf')):
        bpy.ops.import_scene.gltf(filepath=input_path)
    else:
        # Raise an exception for better error handling in the server
        raise ValueError(f"Unsupported file format for import: {input_path}")

    # Remove non-essential objects like lights and cameras
    bpy.ops.object.select_all(action='DESELECT')
    for obj in bpy.context.scene.objects:
        if obj.type not in ['MESH', 'ARMATURE']:
            obj.select_set(True)
    bpy.ops.object.delete()

    # Select all mesh objects in the scene
    bpy.ops.object.select_all(action='DESELECT')
    mesh_objects = [obj for obj in bpy.context.scene.objects if obj.type == 'MESH']
    
    if not mesh_objects:
        # Raise an exception if no meshes are found after import
        raise RuntimeError("No mesh objects found to join.")

    for obj in mesh_objects:
        obj.select_set(True)
    
    # The active object will be the one that remains after joining
    bpy.context.view_layer.objects.active = mesh_objects[0]

    # Join the selected mesh objects
    bpy.ops.object.join()

    # Ensure the newly joined object is selected for export
    joined_object = bpy.context.view_layer.objects.active
    bpy.ops.object.select_all(action='DESELECT')
    joined_object.select_set(True)

    # Also select any armatures to export them with the mesh
    for obj in bpy.context.scene.objects:
        if obj.type == 'ARMATURE':
            obj.select_set(True)

    # Purge orphan data to clean up the file
    bpy.ops.outliner.orphans_purge()

    # Export the joined mesh to the specified output path
    if output_path.lower().endswith('.fbx'):
        bpy.ops.export_scene.fbx(filepath=output_path, use_selection=True)
    elif output_path.lower().endswith(('.glb', '.gltf')):
        bpy.ops.export_scene.gltf(filepath=output_path, export_format='GLB', use_selection=True)
    else:
        # Raise an exception for better error handling
        raise ValueError(f"Unsupported file format for export: {output_path}")

    print(f"Successfully joined meshes and saved to {output_path}")

# This block allows the script to still be run from the command line if needed
if __name__ == "__main__":
    try:
        # Find arguments passed after '--'
        idx = sys.argv.index("--")
        args = sys.argv[idx + 1:]
    except ValueError:
        print("Error: No arguments provided after '--'.", file=sys.stderr)
        print("Usage: blender --background --python script.py -- <input_path> <output_path>", file=sys.stderr)
        sys.exit(1)

    if len(args) != 2:
        print("Error: Invalid number of arguments.", file=sys.stderr)
        print("Usage: blender --background --python script.py -- <input_path> <output_path>", file=sys.stderr)
        sys.exit(1)

    input_file, output_file = args

    if not os.path.exists(input_file):
        print(f"Error: Input file not found: {input_file}", file=sys.stderr)
        sys.exit(1)

    try:
        # Execute the main function
        join_and_save_mesh(input_file, output_file)
    except Exception as e:
        print(f"An error occurred: {e}", file=sys.stderr)
        sys.exit(1)