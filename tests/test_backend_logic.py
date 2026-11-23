import io
import json
import math
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from PIL import Image

BACKEND = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND))

import script_official as analysis  # noqa: E402
import server  # noqa: E402


class GeometryAndHeuristicTests(unittest.TestCase):
    def test_ellipse_area_proxy_uses_semi_axes(self):
        self.assertAlmostEqual(analysis.ellipse_area_proxy(10, 20), math.pi * 5 * 10)

    def test_non_positive_boxes_have_zero_proxy(self):
        self.assertEqual(analysis.ellipse_area_proxy(0, 20), 0.0)
        self.assertEqual(analysis.ellipse_area_proxy(10, -1), 0.0)

    def test_maturity_thresholds_are_explicit_and_stable(self):
        self.assertEqual(analysis.classify_olive_by_gray_intensity(140)[0], "Ripe")
        self.assertEqual(analysis.classify_olive_by_gray_intensity(141)[0], "Unripe")
        self.assertEqual(analysis.classify_olive_by_gray_intensity(180)[0], "Partially ripe")

    def test_yolo_inference_is_delegated_to_the_model(self):
        model = Mock()
        analysis.run_yolo_inference(model, "olive.jpg", conf=0.5)
        model.predict.assert_called_once_with(source="olive.jpg", conf=0.5)

    def test_progress_is_not_completed_until_explicitly_finalized(self):
        with tempfile.TemporaryDirectory() as tmp:
            progress_file = Path(tmp) / "progress.json"
            analysis.update_progress(progress_file, 1, 1)
            self.assertEqual(json.loads(progress_file.read_text())["status"], "running")
            self.assertEqual(json.loads(progress_file.read_text())["percentage"], 95)
            analysis.update_progress(progress_file, 1, 1, completed=True)
            self.assertEqual(json.loads(progress_file.read_text())["status"], "completed")
            self.assertEqual(json.loads(progress_file.read_text())["percentage"], 100)

    def test_progress_marks_worker_errors_as_failed(self):
        with tempfile.TemporaryDirectory() as tmp:
            progress_file = Path(tmp) / "progress.json"
            analysis.update_progress(progress_file, 0, 1, error="inference failed")
            progress = json.loads(progress_file.read_text())
            self.assertEqual(progress["status"], "failed")
            self.assertEqual(progress["error"], "inference failed")


class ApiBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.original_config = {
            key: server.app.config[key]
            for key in ("UPLOAD_FOLDER", "RESULTS_FOLDER", "MAX_CONTENT_LENGTH")
        }
        server.app.config.update(
            TESTING=True,
            UPLOAD_FOLDER=str(root / "upload"),
            RESULTS_FOLDER=str(root / "results"),
            MAX_CONTENT_LENGTH=20 * 1024 * 1024,
        )
        Path(server.app.config["UPLOAD_FOLDER"]).mkdir()
        Path(server.app.config["RESULTS_FOLDER"]).mkdir()
        server.JOB_RUNNING = False
        if server.JOB_LOCK.locked():
            self.fail("A previous test did not release the analysis lock")
        self.client = server.app.test_client()

    def tearDown(self):
        server.JOB_RUNNING = False
        if server.JOB_LOCK.locked():
            server.JOB_LOCK.release()
        server.app.config.update(self.original_config)
        self.tmp.cleanup()

    @staticmethod
    def image_upload(name="olive.png"):
        payload = io.BytesIO()
        Image.new("RGB", (4, 4), color="green").save(payload, format="PNG")
        payload.seek(0)
        return payload, name

    def test_upload_rejects_an_unsupported_extension(self):
        response = self.client.post("/upload", data={"files": (io.BytesIO(b"x"), "notes.txt")})
        self.assertEqual(response.status_code, 400)

    def test_upload_rejects_a_corrupt_image(self):
        response = self.client.post("/upload", data={"files": (io.BytesIO(b"not an image"), "olive.png")})
        self.assertEqual(response.status_code, 400)

    def test_upload_rejects_a_request_over_the_configured_limit(self):
        server.app.config["MAX_CONTENT_LENGTH"] = 64
        response = self.client.post("/upload", data={"files": self.image_upload()})
        self.assertEqual(response.status_code, 413)

    def test_clean_rejects_when_a_worker_owns_the_lock(self):
        server.JOB_RUNNING = True
        server.JOB_LOCK.acquire()
        response = self.client.post("/clean_folders")
        self.assertEqual(response.status_code, 409)

    def test_second_upload_is_rejected_while_the_first_job_runs(self):
        entered = threading.Event()
        release = threading.Event()

        def controlled_worker():
            entered.set()
            try:
                release.wait(timeout=2)
            finally:
                server.JOB_RUNNING = False
                server.JOB_LOCK.release()

        with patch.object(server, "process_images_thread", side_effect=controlled_worker):
            first = self.client.post("/upload", data={"files": self.image_upload("first.png")})
            self.assertEqual(first.status_code, 200)
            self.assertTrue(entered.wait(timeout=1))
            second = self.client.post("/upload", data={"files": self.image_upload("second.png")})
            self.assertEqual(second.status_code, 409)
            release.set()
            deadline = time.monotonic() + 1
            while server.JOB_LOCK.locked() and time.monotonic() < deadline:
                time.sleep(0.01)
            self.assertFalse(server.JOB_LOCK.locked())

    def test_worker_releases_lock_when_processing_raises(self):
        server.JOB_RUNNING = True
        server.JOB_LOCK.acquire()
        with patch.object(server, "process_and_save_results", side_effect=RuntimeError("inference failed")), \
             patch.object(server, "update_progress") as update_progress:
            server.process_images_thread()
        self.assertFalse(server.JOB_RUNNING)
        self.assertFalse(server.JOB_LOCK.locked())
        self.assertTrue(any(call.kwargs.get("error") == "inference failed" for call in update_progress.call_args_list))

    def test_result_endpoints_wait_for_a_terminal_job_state(self):
        results = Path(server.app.config["RESULTS_FOLDER"])
        (results / "olive_pipeline.jpg").write_bytes(b"not inspected by this endpoint")
        (results / "summary_results.json").write_text(json.dumps({"total_olives": 1}))
        server.JOB_RUNNING = True
        self.assertEqual(self.client.get("/get_results").status_code, 409)
        self.assertEqual(self.client.get("/get_summary_results").status_code, 409)
        server.JOB_RUNNING = False
        with patch.object(server, "get_analysis_status", return_value="completed"):
            self.assertEqual(self.client.get("/get_results").status_code, 200)
            self.assertEqual(self.client.get("/get_summary_results").status_code, 200)

    def test_download_and_file_serving_wait_for_completion(self):
        results = Path(server.app.config["RESULTS_FOLDER"])
        (results / "summary_results.json").write_text("{}")
        (results / "olive_pipeline.jpg").write_bytes(b"image")
        server.JOB_RUNNING = True
        self.assertEqual(self.client.get("/download_results").status_code, 409)
        self.assertEqual(self.client.get("/results/olive_pipeline.jpg").status_code, 409)

    def test_failed_jobs_do_not_expose_partial_artifacts(self):
        results = Path(server.app.config["RESULTS_FOLDER"])
        (results / "summary_results.json").write_text("{}")
        (results / "olive_pipeline.jpg").write_bytes(b"partial image")
        with patch.object(server, "get_analysis_status", return_value="failed"):
            self.assertEqual(self.client.get("/download_results").status_code, 409)
            self.assertEqual(self.client.get("/results/olive_pipeline.jpg").status_code, 409)

    def test_completed_jobs_can_download_and_serve_artifacts(self):
        results = Path(server.app.config["RESULTS_FOLDER"])
        (results / "summary_results.json").write_text("{}")
        (results / "olive_pipeline.jpg").write_bytes(b"completed image")
        with patch.object(server, "get_analysis_status", return_value="completed"):
            self.assertEqual(self.client.get("/download_results").status_code, 200)
            self.assertEqual(self.client.get("/results/olive_pipeline.jpg").status_code, 200)

    def test_previous_results_require_an_explicit_reset(self):
        Path(server.app.config["RESULTS_FOLDER"], "summary_results.json").write_text("{}")
        response = self.client.post("/upload", data={"files": self.image_upload()})
        self.assertEqual(response.status_code, 409)
        self.assertIn(b"Clear the completed", response.data)


if __name__ == "__main__":
    unittest.main()
