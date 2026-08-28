import importlib
import importlib.metadata
import socket
import threading
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.ai.symbol_detection import model_loader
from app.ai.symbol_detection.model_loader import (
    ERROR_CODES,
    MAXIMUM_CACHED_MODELS,
    SAFE_ERROR_MESSAGE,
    LoadedSymbolDetectionModel,
    SymbolClassMetadata,
    YOLOModelLoaderError,
    load_symbol_detection_model,
    reset_symbol_detection_model_cache,
)
from app.core.config import Settings


class FakeModel:
    def __init__(self, names=None, task="detect") -> None:
        self.names = names if names is not None else {0: "outlet", 1: "switch"}
        self.task = task
        self.predict = MagicMock(side_effect=AssertionError("prediction executed"))

    def __call__(self, *args, **kwargs):
        raise AssertionError("inference executed")


class YOLOModelLoaderTests(unittest.TestCase):
    def setUp(self) -> None:
        reset_symbol_detection_model_cache()
        self.temporary_directory = TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        self.model_path = self.root / "electrical-symbols.pt"
        self.model_path.write_bytes(b"test-only-fake-model")

    def tearDown(self) -> None:
        reset_symbol_detection_model_cache()
        self.temporary_directory.cleanup()

    def settings(self, path) -> Settings:
        return Settings(_env_file=None, yolo_model_path=path)

    def assert_error(self, code: str, operation) -> YOLOModelLoaderError:
        with self.assertRaises(YOLOModelLoaderError) as caught:
            operation()
        self.assertEqual(caught.exception.code, code)
        self.assertEqual(str(caught.exception), SAFE_ERROR_MESSAGE)
        self.assertIn(code, ERROR_CODES)
        return caught.exception

    def test_relative_configuration_resolves_from_repository_root(self) -> None:
        relative = Path("models") / "electrical-symbols.pt"
        target = self.root / relative
        target.parent.mkdir()
        target.write_bytes(b"relative-test-model")
        factory = MagicMock(return_value=FakeModel())
        with patch.object(model_loader, "REPOSITORY_ROOT", self.root):
            loaded = load_symbol_detection_model(
                settings=self.settings(relative),
                model_factory=factory,
            )
        self.assertEqual(loaded._resolved_path, target.resolve())
        factory.assert_called_once_with(str(target.resolve()))

    def test_absolute_local_path_is_supported_and_result_is_immutable(self) -> None:
        loaded = load_symbol_detection_model(
            settings=self.settings(self.model_path.resolve()),
            model_factory=lambda _: FakeModel(),
        )
        self.assertIsInstance(loaded, LoadedSymbolDetectionModel)
        self.assertEqual(loaded._resolved_path, self.model_path.resolve())
        with self.assertRaises(AttributeError):
            loaded.task = "segment"

    def test_missing_configuration_fails_safely(self) -> None:
        self.assert_error(
            "model_path_not_configured",
            lambda: load_symbol_detection_model(
                settings=self.settings(None),
                model_factory=lambda _: FakeModel(),
            ),
        )

    def test_missing_file_directory_wrong_extension_url_and_malformed_path_fail(self) -> None:
        directory = self.root / "directory.pt"
        directory.mkdir()
        wrong_extension = self.root / "model.onnx"
        wrong_extension.write_bytes(b"unsupported")
        cases = (
            ("model_file_missing", self.root / "missing.pt"),
            ("model_path_invalid", directory),
            ("model_file_unsupported", wrong_extension),
            ("model_path_invalid", Path("https:/example.test/model.pt")),
            ("model_path_invalid", SimpleNamespace(yolo_model_path="bad\x00.pt")),
        )
        for code, configured in cases:
            with self.subTest(code=code, configured=str(configured)):
                settings = (
                    configured
                    if isinstance(configured, SimpleNamespace)
                    else self.settings(configured)
                )
                self.assert_error(
                    code,
                    lambda value=settings: load_symbol_detection_model(
                        settings=value,
                        model_factory=lambda _: FakeModel(),
                    ),
                )

    def test_unreadable_file_fails_before_factory(self) -> None:
        factory = MagicMock(return_value=FakeModel())
        with patch.object(Path, "open", side_effect=PermissionError("private path")):
            error = self.assert_error(
                "model_path_invalid",
                lambda: load_symbol_detection_model(
                    settings=self.settings(self.model_path),
                    model_factory=factory,
                ),
            )
        factory.assert_not_called()
        self.assertNotIn(str(self.model_path), str(error))

    def test_factory_receives_canonical_path_and_prediction_is_never_called(self) -> None:
        fake_model = FakeModel()
        factory = MagicMock(return_value=fake_model)
        loaded = load_symbol_detection_model(
            settings=self.settings(self.model_path),
            model_factory=factory,
        )
        factory.assert_called_once_with(str(self.model_path.resolve()))
        self.assertIs(loaded.model, fake_model)
        fake_model.predict.assert_not_called()

    def test_default_factory_uses_lazy_official_yolo_api(self) -> None:
        yolo = MagicMock(return_value=FakeModel())
        fake_module = SimpleNamespace(YOLO=yolo)
        with patch.dict("sys.modules", {"ultralytics": fake_module}):
            loaded = load_symbol_detection_model(settings=self.settings(self.model_path))
        yolo.assert_called_once_with(str(self.model_path.resolve()))
        self.assertEqual(loaded.task, "detect")

    def test_same_path_loads_once_and_returns_same_result(self) -> None:
        factory = MagicMock(return_value=FakeModel())
        first = load_symbol_detection_model(
            settings=self.settings(self.model_path), model_factory=factory
        )
        second = load_symbol_detection_model(
            settings=self.settings(self.model_path), model_factory=factory
        )
        self.assertIs(first, second)
        self.assertIs(first.model, second.model)
        factory.assert_called_once()

    def test_concurrent_first_calls_load_exactly_once(self) -> None:
        call_count = 0
        count_lock = threading.Lock()

        def factory(_):
            nonlocal call_count
            with count_lock:
                call_count += 1
            time.sleep(0.05)
            return FakeModel()

        with ThreadPoolExecutor(max_workers=8) as executor:
            results = tuple(
                executor.map(
                    lambda _: load_symbol_detection_model(
                        settings=self.settings(self.model_path),
                        model_factory=factory,
                    ),
                    range(16),
                )
            )
        self.assertEqual(call_count, 1)
        self.assertTrue(all(result is results[0] for result in results))

    def test_different_paths_do_not_share_instances(self) -> None:
        second_path = self.root / "second.pt"
        second_path.write_bytes(b"second-test-model")
        first = load_symbol_detection_model(
            settings=self.settings(self.model_path),
            model_factory=lambda _: FakeModel({0: "first"}),
        )
        second = load_symbol_detection_model(
            settings=self.settings(second_path),
            model_factory=lambda _: FakeModel({0: "second"}),
        )
        self.assertIsNot(first, second)
        self.assertIsNot(first.model, second.model)
        self.assertNotEqual(first.classes, second.classes)

    def test_failed_load_is_not_cached_and_can_be_retried(self) -> None:
        factory = MagicMock(
            side_effect=(RuntimeError(f"failed at {self.model_path}"), FakeModel())
        )
        error = self.assert_error(
            "model_load_failed",
            lambda: load_symbol_detection_model(
                settings=self.settings(self.model_path), model_factory=factory
            ),
        )
        loaded = load_symbol_detection_model(
            settings=self.settings(self.model_path), model_factory=factory
        )
        self.assertEqual(factory.call_count, 2)
        self.assertEqual(loaded.task, "detect")
        self.assertNotIn(str(self.model_path), str(error))

    def test_cache_reset_forces_a_new_load(self) -> None:
        factory = MagicMock(side_effect=(FakeModel(), FakeModel()))
        first = load_symbol_detection_model(
            settings=self.settings(self.model_path), model_factory=factory
        )
        reset_symbol_detection_model_cache()
        second = load_symbol_detection_model(
            settings=self.settings(self.model_path), model_factory=factory
        )
        self.assertIsNot(first, second)
        self.assertEqual(factory.call_count, 2)

    def test_cache_is_bounded(self) -> None:
        paths = []
        for index in range(MAXIMUM_CACHED_MODELS + 1):
            path = self.root / f"model-{index}.pt"
            path.write_bytes(f"model-{index}".encode())
            paths.append(path)
            load_symbol_detection_model(
                settings=self.settings(path),
                model_factory=lambda _, item=index: FakeModel({0: f"class-{item}"}),
            )
        self.assertEqual(len(model_loader._model_cache), MAXIMUM_CACHED_MODELS)
        self.assertNotIn(paths[0].resolve(), model_loader._model_cache)

    def test_list_and_dictionary_class_names_are_normalized_deterministically(self) -> None:
        for names in ([" outlet ", "switch"], {1: "switch", 0: " outlet "}):
            with self.subTest(shape=type(names).__name__):
                reset_symbol_detection_model_cache()
                loaded = load_symbol_detection_model(
                    settings=self.settings(self.model_path),
                    model_factory=lambda _, value=names: FakeModel(value),
                )
                self.assertEqual(
                    loaded.classes,
                    (
                        SymbolClassMetadata(0, "outlet"),
                        SymbolClassMetadata(1, "switch"),
                    ),
                )

    def test_empty_malformed_duplicate_and_non_string_metadata_is_rejected(self) -> None:
        cases = (
            [],
            {},
            ("outlet",),
            {1: "outlet"},
            {True: "outlet"},
            {0: 123},
            {0: "outlet", 1: " outlet "},
            {0: ""},
        )
        for names in cases:
            with self.subTest(names=repr(names)):
                reset_symbol_detection_model_cache()
                self.assert_error(
                    "model_metadata_invalid",
                    lambda value=names: load_symbol_detection_model(
                        settings=self.settings(self.model_path),
                        model_factory=lambda _: FakeModel(value),
                    ),
                )

    def test_classes_are_discovered_without_electrical_class_assumptions(self) -> None:
        loaded = load_symbol_detection_model(
            settings=self.settings(self.model_path),
            model_factory=lambda _: FakeModel({0: "custom-a", 1: "custom-b"}),
        )
        self.assertEqual(tuple(item.name for item in loaded.classes), ("custom-a", "custom-b"))

    def test_missing_task_is_allowed_but_unsupported_task_is_rejected(self) -> None:
        loaded = load_symbol_detection_model(
            settings=self.settings(self.model_path),
            model_factory=lambda _: FakeModel(task=None),
        )
        self.assertIsNone(loaded.task)
        for task in ("segment", "classify", 123, ""):
            with self.subTest(task=task):
                reset_symbol_detection_model_cache()
                self.assert_error(
                    "model_task_unsupported",
                    lambda value=task: load_symbol_detection_model(
                        settings=self.settings(self.model_path),
                        model_factory=lambda _: FakeModel(task=value),
                    ),
                )

    def test_fastapi_import_does_not_load_model(self) -> None:
        with patch.object(
            model_loader,
            "_default_model_factory",
            side_effect=AssertionError("model loaded during app import"),
        ):
            import app.main

            importlib.reload(app.main)
        self.assertEqual(len(model_loader._model_cache), 0)

    def test_fake_factory_path_performs_no_network_or_download(self) -> None:
        with patch.object(socket, "create_connection", side_effect=AssertionError("network used")), patch(
            "urllib.request.urlopen", side_effect=AssertionError("download used")
        ):
            loaded = load_symbol_detection_model(
                settings=self.settings(self.model_path),
                model_factory=lambda _: FakeModel(),
            )
        self.assertEqual(loaded.classes[0].name, "outlet")

    def test_installed_headless_package_imports_at_pinned_version(self) -> None:
        package = importlib.import_module("ultralytics")
        self.assertEqual(package.__version__, "8.4.131")
        self.assertEqual(
            importlib.metadata.version("ultralytics-opencv-headless"),
            "8.4.131",
        )

    def test_exactly_one_headless_opencv_provider_is_installed(self) -> None:
        providers = {
            distribution.metadata["Name"].casefold(): distribution.version
            for distribution in importlib.metadata.distributions()
            if distribution.metadata["Name"].casefold()
            in {
                "opencv-python",
                "opencv-python-headless",
                "opencv-contrib-python",
                "opencv-contrib-python-headless",
            }
        }
        self.assertEqual(providers, {"opencv-python-headless": "4.14.0.94"})


if __name__ == "__main__":
    unittest.main()
