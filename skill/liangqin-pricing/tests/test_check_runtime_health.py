import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "check_runtime_health.py"
SPEC = importlib.util.spec_from_file_location("check_runtime_health", SCRIPT_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


def write_runtime_files(
    root: Path,
    *,
    release_payload: dict | None = None,
    price_index_payload: dict | None = None,
) -> None:
    current_dir = root / "data" / "current"
    current_dir.mkdir(parents=True, exist_ok=True)
    if release_payload is not None:
        (current_dir / "release.json").write_text(json.dumps(release_payload, ensure_ascii=False), encoding="utf-8")
    if price_index_payload is not None:
        (current_dir / "price-index.json").write_text(json.dumps(price_index_payload, ensure_ascii=False), encoding="utf-8")


class CheckRuntimeHealthTests(unittest.TestCase):
    def test_inspect_runtime_health_reports_ok_for_complete_runtime(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            write_runtime_files(
                root,
                release_payload={
                    "version": "2026-04-07",
                    "status": "active",
                    "price_index_file": "price-index.json",
                },
                price_index_payload={
                    "record_count": 2,
                    "queryable_record_count": 1,
                    "records": [
                        {"product_code": "A-01", "name": "衣柜", "pricing_mode": "projection_area", "is_queryable": True, "record_kind": "price"},
                        {"product_code": "A-02", "name": "备注", "pricing_mode": "note", "is_queryable": False, "record_kind": "guidance_note"},
                    ],
                },
            )

            payload = MODULE.inspect_runtime_health(root)

        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["counts"]["record_count_actual"], 2)
        self.assertEqual(payload["counts"]["queryable_record_count_actual"], 1)
        self.assertEqual(payload["sample_queryable_record"]["product_code"], "A-01")

    def test_inspect_runtime_health_reports_missing_release(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            write_runtime_files(
                root,
                price_index_payload={"record_count": 1, "queryable_record_count": 1, "records": [{"is_queryable": True, "record_kind": "price"}]},
            )

            payload = MODULE.inspect_runtime_health(root)

        self.assertEqual(payload["status"], "error")
        self.assertTrue(any("release.json" in item for item in payload["errors"]))

    def test_inspect_runtime_health_reports_missing_price_index(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            write_runtime_files(
                root,
                release_payload={
                    "version": "2026-04-07",
                    "status": "active",
                    "price_index_file": "price-index.json",
                },
            )

            payload = MODULE.inspect_runtime_health(root)

        self.assertEqual(payload["status"], "error")
        self.assertTrue(any("缺少价格索引文件" in item for item in payload["errors"]))

    def test_inspect_runtime_health_reports_empty_records_as_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            write_runtime_files(
                root,
                release_payload={
                    "version": "2026-04-07",
                    "status": "active",
                    "price_index_file": "price-index.json",
                },
                price_index_payload={"record_count": 0, "queryable_record_count": 0, "records": []},
            )

            payload = MODULE.inspect_runtime_health(root)

        self.assertEqual(payload["status"], "error")
        self.assertTrue(any("records[] 为空" in item for item in payload["errors"]))

    def test_render_text_report_highlights_filter_mismatch_hint_when_ok(self) -> None:
        payload = {
            "status": "ok",
            "summary": "当前运行环境数据完整，可正常用于报价。",
            "skill_dir": "/tmp/skill",
            "release": {"version": "2026-04-07", "status": "active"},
            "price_index_path": "/tmp/skill/data/current/price-index.json",
            "counts": {
                "record_count_actual": 10,
                "queryable_record_count_actual": 8,
                "price_record_count_actual": 6,
            },
            "sample_queryable_record": {"product_code": "A-01", "name": "衣柜", "pricing_mode": "projection_area"},
            "warnings": [],
            "errors": [],
            "recommended_actions": ["如果这里显示数据正常，但机器人仍说“价格索引为空”，优先排查它是否把“筛选没命中”误判成了“整份数据为空”。"],
        }

        rendered = MODULE.render_text_report(payload)

        self.assertIn("运行环境诊断：ok", rendered)
        self.assertIn("更可能是它的筛选条件没命中", rendered)


if __name__ == "__main__":
    unittest.main()
