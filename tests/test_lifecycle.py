from fractions import Fraction as F
from pathlib import Path
import tempfile
import unittest

from spectral.archive.catalog import Catalog
from spectral.archive.reading import read
from spectral.dictionary.revisions import save_dictionary, get_dictionary_revision
from spectral.measurements.intake import save_batch
from spectral.measurements.revisions import append_measurement_revision, get_measurement_revision
from spectral.measurements.cohorts import freeze, get_cohort
from spectral.unmixing.jobs import unmix
from spectral.response.requests import direction
from tests.test_unmix import publish, scenario


class TestLifecycle(unittest.TestCase):
    def test_correction_reopen(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "lab.sqlite"
            c = Catalog(path)
            try:
                d1, measurements, q1, p1 = publish(c, [[1]], [[1]])
                # A second old queue is frozen before any correction and run afterwards.
                q_delayed = freeze(c, d1, measurements)
                d2 = save_dictionary(c, ["c0"], ["k0"], ["signal"], ["mg/L"], [[2]], previous=d1)
                m2 = append_measurement_revision(c, measurements[0], [3])
                r1 = direction(c, p1, [1])
                delayed = unmix(c, q_delayed)
                q2 = freeze(c, d2, [m2])
                p2 = unmix(c, q2)
                r2 = direction(c, p2, [1])
                self.assertEqual(read(c, delayed)["data"]["rows"][0]["coefficients"], [F(1)])
                self.assertEqual(read(c, p2)["data"]["rows"][0]["coefficients"], [F(3, 2)])
                self.assertEqual(read(c, r1)["data"]["rows"][0]["coefficients"], [F(1)])
                self.assertEqual(read(c, r2)["data"]["rows"][0]["coefficients"], [F(1, 2)])
                saved_parent, saved_response = read(c, p1), read(c, r1)
                altered = read(c, p1)
                altered["data"]["input"]["dictionary"]["matrix"][0][0] = F(99)
                altered["data"]["input"]["measurements"][0]["values"][0] = F(99)
                altered["data"]["rows"][0]["coefficients"][0] = F(99)
                altered_response = read(c, r1)
                altered_response["data"]["rows"][0]["coefficients"][0] = F(99)
                self.assertEqual(read(c, p1), saved_parent)
                self.assertEqual(read(c, r1), saved_response)
                frozen = get_cohort(c, q1)
                frozen.snapshot["dictionary"]["matrix"][0][0] = F(99)
                self.assertEqual(get_cohort(c, q1).snapshot["dictionary"]["matrix"], [[F(1)]])
                c.initialize()
                source = get_dictionary_revision(c, d1).source_id
                self.assertEqual(c.resolve_head("dictionary", source), d2)
                self.assertEqual(c.resolve_head("measurement",
                                               get_measurement_revision(c, m2).batch_id + ":s0"), m2)
            finally:
                c.close()
            c = Catalog(path)
            try:
                c.initialize()
                self.assertEqual(read(c, p1), saved_parent)
                self.assertEqual(read(c, r1), saved_response)
                self.assertEqual(c.resolve_head("dictionary", source), d2)
                self.assertEqual(read(c, p2)["data"]["rows"][0]["coefficients"], [F(3, 2)])
                scenario("V4.frozen_sources", {"old_A": [[1]], "old_y": [1],
                                              "new_A": [[2]], "new_y": [3]},
                         [F(1)], read(c, p1)["data"]["rows"][0]["coefficients"],
                         {"old_h": [F(1)], "new_h": [F(1, 2)]},
                         {"old_h": read(c, r1)["data"]["rows"][0]["coefficients"],
                          "new_h": read(c, r2)["data"]["rows"][0]["coefficients"]},
                         ["spectral/measurements/snapshots.py", "spectral/measurements/cohorts.py",
                          "spectral/unmixing/jobs.py", "spectral/archive/reading.py"],
                         "one channel hand division, frozen-before-correction execution and SQLite reopen")
            finally:
                c.close()

    def test_channel_mismatch(self):
        c = Catalog(":memory:")
        try:
            d = save_dictionary(c, ["c1", "c2"], ["a"], ["u", "v"], ["mg"], [[1], [2]])
            for channels, units, values in ((["c1"], ["u"], [1]),
                                            (["c2", "c1"], ["v", "u"], [2, 1]),
                                            (["c1", "c2"], ["u", "u"], [1, 2])):
                b = save_batch(c, channels, units, [{"sample_id": "sample", "values": values}])
                revisions = c.read_record(b)["data"]["revision_ids"]
                before = c.counts()
                with self.assertRaises(ValueError):
                    freeze(c, d, revisions)
                self.assertEqual(c.counts(), before)
            before = c.counts()
            with self.assertRaises(KeyError):
                freeze(c, "missing", revisions)
            with self.assertRaises(KeyError):
                freeze(c, d, ["missing"])
            with self.assertRaises(KeyError):
                unmix(c, "missing")
            self.assertEqual(c.counts(), before)
        finally:
            c.close()

    def test_invalid_intake_is_atomic(self):
        c = Catalog(":memory:")
        try:
            d, revisions, _, _ = publish(c, [[1]], [[1]])
            source = get_dictionary_revision(c, d).source_id
            for channels, matrix in ((["c0", "c0"], [[1], [1]]),
                                     (["c0"], [[-1]]), (["c0"], [[None]]),
                                     (["c0"], [[True]]), (["c0"], [[0.5]]),
                                     (["c0"], [["1/0"]]), (["c0"], [[1, 2]]),
                                     (["c0"], None)):
                before = c.counts()
                with self.assertRaises(ValueError):
                    save_dictionary(c, channels, ["k0"], ["signal"] * len(channels),
                                    ["mg/L"], matrix, previous=d)
                self.assertEqual(c.counts(), before)
                self.assertEqual(c.resolve_head("dictionary", source), d)
            for records in ([], [{"sample_id": "x", "values": [1]},
                                 {"sample_id": "bad", "values": [None]}],
                            [{"sample_id": "x", "values": [1]}, {"sample_id": "x", "values": [2]}],
                            [{"sample_id": "", "values": [1]}],
                            [{"sample_id": "x", "values": []}],
                            [{"sample_id": "x", "values": [1.0]}]):
                before = c.counts()
                with self.assertRaises(ValueError):
                    save_batch(c, ["c0"], ["signal"], records)
                self.assertEqual(c.counts(), before)
            before = c.counts()
            with self.assertRaises(ValueError):
                append_measurement_revision(c, revisions[0], [None])
            with self.assertRaises(KeyError):
                append_measurement_revision(c, "missing", [1])
            with self.assertRaises(KeyError):
                save_dictionary(c, ["c0"], ["k0"], ["signal"], ["mg/L"], [[1]], previous="missing")
            self.assertEqual(c.counts(), before)
            with self.assertRaises(ValueError):
                freeze(c, d, [revisions[0], revisions[0]])
        finally:
            c.close()

    def test_exact_fraction_reopen_and_version(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "lab.sqlite"
            c = Catalog(path)
            _, _, _, parent = publish(c, [["1/3"]], [["1/7"]])
            response = direction(c, parent, ["1/7"])
            saved = read(c, parent)
            self.assertEqual(saved["data"]["rows"][0]["coefficients"], [F(3, 7)])
            self.assertEqual(saved["data"]["rows"][0]["residual_squared"], F(0))
            c.close()
            c = Catalog(path)
            self.assertEqual(read(c, parent), saved)
            self.assertEqual(read(c, response)["data"]["rows"][0]["coefficients"], [F(3, 7)])
            c.initialize()
            c.connection.execute("PRAGMA user_version=2")
            with self.assertRaises(ValueError):
                c.initialize()
            c.close()
