from pathlib import Path
from jobs.api_models import TestMakeItAnimatableJob
from jobs.utils.testing import LocalTester

tester = LocalTester(type="make_it_animatable", port=7778)

tester.run_test(
    TestMakeItAnimatableJob(
        _id="purpleguy",
        input_mesh_url=tester.local_url(Path("jobs/test_storage/purpleguy.glb")),
        animation_name="jumping",
    )
)
