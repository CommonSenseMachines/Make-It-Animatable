# Auto-Rig Pro - Minimal Retargeting Version

This is a minimal version of Auto-Rig Pro configured to only load what's needed for animation retargeting functionality.

## What Was Removed

### Files Removed (~20MB saved):
- **`armature_presets/`** - Armature preset .blend files (bird, dog, horse, human, master)
  - Only used for creating new rigs from scratch
  - Not needed for retargeting existing Mixamo animations
- **`00_LOG.txt`** - Changelog file (not needed for functionality)

### Modules Not Loaded:
The `__init__.py` has been modified to only import and register the essential modules:

**Loaded (Required for retargeting):**
- `auto_rig_prefs` - Addon preferences
- `rig_functions` - Core rig functions (dependency of auto_rig)
- `auto_rig` - Core functionality (required by auto_rig_remap)
- `auto_rig_remap` - **The actual retargeting functionality**
- `utils` - Utility functions

**Not Loaded (Saves memory/load time):**
- `auto_rig_smart` - Smart rig detection (not needed for retargeting)
- `auto_rig_ge` - Game Engine export features (not needed for retargeting)
- `export_fbx` / `export_fbx_old` - FBX export operators (not needed for retargeting)
- UI panels and icons (gracefully handled if missing)

## What's Still Included

### Essential Files:
- **`remap_presets/`** (248KB) - Bone mapping presets including Mixamo mappings
  - These define how to map bones between different rig types
  - **Critical for retargeting to work**

- **`src/`** (4.2MB) - Python source modules
  - Contains all the core functionality
  - Cannot easily remove individual files due to interdependencies

- **`__init__.py`** - Main addon file (now minimal version)
- **`LICENSE.txt`** - License information

## Size Comparison

- **Before:** ~24.5MB
- **After:** ~4.5MB
- **Savings:** ~20MB (82% reduction)

## How Retargeting Works

1. Code calls `blender_utils.retarget()` in `util/blender_utils.py:547-560`
2. This enables the auto_rig_pro addon via `enable_arp()`
3. The addon registers the retargeting operators:
   - `bpy.ops.arp.auto_scale()` - Auto-scale source to target
   - `bpy.ops.arp.build_bones_list()` - Build bone mappings
   - `bpy.ops.arp.retarget()` - Perform the actual retargeting
4. These operators use the `remap_presets/` to map Mixamo bones to the target rig

## Usage

The addon works exactly the same as before for retargeting purposes. The code in `job_handler.py` will continue to work without any changes.

## Notes

- The minimal `__init__.py` includes error handling to gracefully handle missing icons
- All core retargeting functionality is preserved
- UI panels may not work properly (but they're not used in the pipeline anyway)
- This is optimized for programmatic use via `bpy.ops.arp.retarget()`, not for interactive UI usage
