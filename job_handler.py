from pathlib import Path
import subprocess
from typing import TYPE_CHECKING
import logging
import sys
import zipfile

from jobs.utils.azure import download_zip_from_azure_if_missing
from models.make_it_animatable.server.server import run_pipeline, init_models
from models.make_it_animatable.util import render_thumbnail, render_glb_frames

sys.path.append("/home/ray/csm")
from jobs.api_models import MakeItAnimatableJob, MakeItAnimatableJobUpdate
from jobs.job_handlers.job_handler import JobHandler

if TYPE_CHECKING:
    from jobs.managers.job_handler_manager import JobHandlerManager

logger = logging.getLogger(__name__)


class MakeItAnimatableJobHandler(
    JobHandler[MakeItAnimatableJob, MakeItAnimatableJobUpdate]
):
    def __init__(self, manager: "JobHandlerManager"):
        super().__init__(
            manager,
        )
        self.job_class = MakeItAnimatableJob
        self.job_update_class = MakeItAnimatableJobUpdate

        init_models()
 
    @classmethod
    def preload(cls, cache_path: Path = Path("/home/ray/csm/models/make_it_animatable/data")):
        data_path = Path("/home/ray/csm/models/make_it_animatable/data")
        if data_path.exists():
            logger.info("Data already downloaded")
            return
        logger.info("Downloading data")
        download_zip_from_azure_if_missing("make_it_animatable_data.zip", data_path)
        
        subprocess.run(
            ["mv", "/home/ray/csm/models/make_it_animatable/data/data", "/home/ray/csm/models/make_it_animatable/data"]
        )
        subprocess.run(
            ["chmod", "+x", "/home/ray/csm/models/make_it_animatable/data/FBX2glTF"]
        )
        logger.info("Data downloaded")

    def run_job(self, job):
        # download mesh
        mesh_extension = job.input_mesh_url.split(".")[-1].split("?")[0]
        mesh_path = self._scratch_dir() / f"mesh.{mesh_extension}"
        self._download_file(job.input_mesh_url, mesh_path)

        self._checkpoint("mesh_downloaded")

        with open(mesh_path, "rb") as f:
            mesh_bytes = f.read()

        db = run_pipeline(mesh_bytes, job.animation_name)

        self._checkpoint("animation_generated")

        glb_path = db.anim_vis_path

        # thumbnail_path = self._scratch_dir() / f"thumbnail.png"
        # render_thumbnail.render_thumbnail(glb_path, str(thumbnail_path))

        # frames_output_dir = self._scratch_dir() / "frames"
        # gif_path = Path(
        #     render_glb_frames.render_frames(glb_path, str(frames_output_dir))
        # )

        # upload files
        # thumbnail_url = self._upload_file(thumbnail_path, Path("thumbnail.png"))
        # gif_url = self._upload_file(gif_path, Path("animation.gif"))
        glb_url = self._upload_file(Path(glb_path), Path("animation.glb"))

        return MakeItAnimatableJobUpdate(
            status="complete",
            # output_thumbnail_url=thumbnail_url,
            # output_gif_url=gif_url,
            output_glb_url=glb_url,
        )
