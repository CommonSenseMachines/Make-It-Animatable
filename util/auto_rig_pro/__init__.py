# ***** BEGIN GPL LICENSE BLOCK *****
#
# Minimal version of Auto-Rig Pro for retargeting only
# Only loads what's needed for animation retargeting (remap functionality)
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software Foundation,
# Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
#
# ***** END GPL LICENCE BLOCK *****

import os

bl_info = {
    "name": "Auto-Rig Pro (Minimal - Retargeting Only)",
    "author": "Artell",
    "version": (3, 70, 36),
    "blender": (2, 80, 0),
    "location": "3D View > Properties> Auto-Rig Pro",
    "description": "Minimal version for animation retargeting only",
    "tracker_url": "http://lucky3d.fr/auto-rig-pro/doc/bug_report.html",
    "doc_url": "http://lucky3d.fr/auto-rig-pro/doc/",
    "category": "Animation",
}

import bpy

# Only import what's needed for retargeting
# Note: auto_rig and auto_rig_remap have dependencies on these modules
from .src import auto_rig_prefs
from .src import rig_functions  # Required by auto_rig
from .src import auto_rig
from .src import auto_rig_remap
from .src import utils


def cleanse_modules():
    """Clean up imported modules on unregister"""
    import sys
    all_modules = sys.modules
    all_modules = dict(sorted(all_modules.items(), key=lambda x: x[0]))
    for k in all_modules:
        if k.startswith(__name__):
            del sys.modules[k]


def register():
    """Register only the modules needed for retargeting"""
    try:
        # Register preferences first (needed by other modules)
        auto_rig_prefs.register()
    except Exception as e:
        print(f"Warning: Failed to register auto_rig_prefs: {e}")

    try:
        # Register rig_functions (required by auto_rig)
        rig_functions.register()
    except Exception as e:
        print(f"Warning: Failed to register rig_functions: {e}")

    try:
        # Register auto_rig (required by auto_rig_remap)
        # Note: This may try to load icons but will work without them
        auto_rig.register()
    except Exception as e:
        print(f"Warning: Failed to register auto_rig: {e}")

    try:
        # Register remap functionality (core retargeting feature)
        auto_rig_remap.register()
    except Exception as e:
        print(f"Warning: Failed to register auto_rig_remap: {e}")
        raise  # This one is critical


def unregister():
    """Unregister modules in reverse order"""
    try:
        auto_rig_remap.unregister()
    except Exception as e:
        print(f"Warning: Failed to unregister auto_rig_remap: {e}")

    try:
        auto_rig.unregister()
    except Exception as e:
        print(f"Warning: Failed to unregister auto_rig: {e}")

    try:
        rig_functions.unregister()
    except Exception as e:
        print(f"Warning: Failed to unregister rig_functions: {e}")

    try:
        auto_rig_prefs.unregister()
    except Exception as e:
        print(f"Warning: Failed to unregister auto_rig_prefs: {e}")

    cleanse_modules()


if __name__ == "__main__":
    register()
