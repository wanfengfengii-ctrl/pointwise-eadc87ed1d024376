from fractions import Fraction as F
from pathlib import Path
import tempfile
import unittest

from spectral.archive.catalog import Catalog
from spectral.archive.codec import encode_payload, decode_payload, parse_rational
from spectral.archive.reading import read, read_parent_chain
from spectral.archive.export import export
from spectral.measurements.cohorts import freeze
from spectral.unmixing.jobs import unmix
from spectral.response.requests import direction
from tests.test_unmix import publish, scenario


class TestArchive(unittest.TestCase):
    def test_publish_failure_retry(self):
        c = Catalog(":memory:")
        try:
            d, revisions, _, old = publish(c, [[1]], [[1]])
            for stage in ("after_payload", "after_index"):
                q = freeze(c, d, revisions)
                before = c.counts()
                saved = read(c, old)
                with self.assertRaises(RuntimeError):
                    unmix(c, q, fail_at=stage)
                self.assertEqual(c.counts(), before)
                self.assertEqual(read(c, old), saved)
                result = unmix(c, q)
                self.assertEqual(unmix(c, q), result)
                self.assertEqual(c.counts()["payloads"], before["payloads"] + 1)
                self.assertEqual(c.counts()["artifacts"], before["artifacts"] + 1)
                self.assertEqual(read(c, result)["data"]["rows"][0]["coefficients"], [F(1)])
            for index, stage in enumerate(("after_payload", "after_index")):
                before = c.counts()
                values = [index + 2]
                with self.assertRaises(RuntimeError):
                    direction(c, old, values, fail_at=stage)
                self.assertEqual(c.counts(), before)
                result = direction(c, old, values)
                self.assertEqual(direction(c, old, values), result)
                self.assertEqual(c.counts()["artifacts"], before["artifacts"] + 1)
                self.assertEqual(read(c, result)["data"]["rows"][0]["coefficients"], [F(index + 2)])
            self.assertEqual(c.counts()["payloads"], c.counts()["artifacts"])
        finally:
            c.close()

    def test_export_failure_preserves_results(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            c = Catalog(root / "catalog.sqlite")
            _, _, _, parent = publish(c, [["1/3"]], [["1/7"]])
            child = direction(c, parent, [1])
            # Keep newer, unrelated analysis visible while exporting the old one.
            publish(c, [[7]], [[5]])
            saved_parent, saved_child = read(c, parent), read(c, child)
            count = c.counts()
            target = root / "report.json"
            target.write_text("previous complete report", encoding="utf-8")
            # An unencodable destination is rejected before replacing its old bytes.
            with self.assertRaises(ValueError):
                export(c, parent, target)
            self.assertEqual(target.read_text(encoding="utf-8"), "previous complete report")
            blocked = root / "occupied"
            blocked.mkdir()
            (blocked / "keep").write_text("retain", encoding="utf-8")
            with self.assertRaises(OSError):
                export(c, child, blocked)
            self.assertEqual((blocked / "keep").read_text(encoding="utf-8"), "retain")
            self.assertEqual(list(root.glob(".spectral-*")), [])
            with self.assertRaises(OSError):
                export(c, child, root / "absent" / "report.json")
            self.assertEqual(c.counts(), count)
            self.assertEqual(read(c, parent), saved_parent)
            self.assertEqual(read(c, child), saved_child)
            export(c, child, target)
            c.close()
            # The remainder reads the exported bytes only.
            package = decode_payload(target.read_text(encoding="utf-8"))
            self.assertEqual(package["format_version"], 1)
            self.assertEqual(package["direction_id"], child)
            chain = package["chain"]
            artifacts = {a["id"]: a for a in chain["artifacts"]}
            records = {r["id"]: r for r in chain["records"]}
            self.assertEqual(artifacts[parent], saved_parent)
            self.assertEqual(artifacts[child], saved_child)
            data = artifacts[parent]["data"]
            snapshot = data["input"]
            dictionary = snapshot["dictionary"]
            self.assertEqual(dictionary["matrix"], [[F(1, 3)]])
            self.assertEqual(dictionary["channels"], ["c0"])
            self.assertEqual(dictionary["component_units"], ["mg/L"])
            self.assertEqual(records[dictionary["revision_id"]]["data"]["matrix"], [[F(1, 3)]])
            self.assertEqual(records[data["cohort_id"]]["data"], snapshot)
            for artifact in chain["artifacts"]:
                for ref in artifact["parents"]:
                    self.assertIn(ref["id"], artifacts if ref["type"] == "artifact" else records)
            row = data["rows"][0]
            y = snapshot["measurements"][0]["values"][0]
            x = row["coefficients"][0]
            h = artifacts[child]["data"]["rows"][0]["coefficients"][0]
            self.assertEqual(F(1, 3) * x, y)
            self.assertEqual(row["residual_squared"], 0)
            self.assertEqual(F(1, 3) * h, F(1))
            self.assertEqual(artifacts[child]["data"]["rows"][0]["reconstruction"], [F(1)])
            scenario("V8.self_contained", {"direction_id": child},
                     {"x": [F(3, 7)], "h": [F(3)]}, {"x": row["coefficients"], "h": [h]},
                     [F(1)], artifacts[child]["data"]["rows"][0]["reconstruction"],
                     ["spectral/archive/export.py", "spectral/archive/reading.py",
                      "spectral/archive/codec.py"], "read only export after catalog close; one-channel hand identities")

    def test_codec_and_fixed_read(self):
        c = Catalog(":memory:")
        try:
            _, _, _, parent = publish(c, [[1]], [[1]])
            child = direction(c, parent, [1])
            chain = read_parent_chain(c, child)
            self.assertEqual([a["id"] for a in chain["artifacts"]], [child, parent])
            self.assertEqual(len({r["id"] for r in chain["records"]}), len(chain["records"]))
            for bad in (True, None, 0.5, "", "nan", "1/0", " 1"):
                with self.assertRaises(ValueError):
                    parse_rational(bad)
            for bad in ('{"$fraction":[2,4]}', '{"$fraction":[1,0]}',
                        '{"$fraction":[true,2]}', '{"x":0.1}'):
                with self.assertRaises(ValueError):
                    decode_payload(bad)
            with self.assertRaises(KeyError):
                read(c, "missing")
            self.assertEqual(decode_payload(encode_payload({"x": F(1, 7)})), {"x": F(1, 7)})
        finally:
            c.close()
