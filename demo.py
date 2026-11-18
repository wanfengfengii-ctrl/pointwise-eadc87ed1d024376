from fractions import Fraction as F
import json
from pathlib import Path
import tempfile

from spectral.archive.catalog import Catalog
from spectral.archive.codec import encode_payload, decode_payload
from spectral.archive.reading import read
from spectral.archive.export import export
from spectral.dictionary.revisions import save_dictionary
from spectral.measurements.intake import save_batch
from spectral.measurements.revisions import append_measurement_revision
from spectral.measurements.cohorts import freeze
from spectral.unmixing.jobs import unmix
from spectral.response.requests import direction


def main():
    source = Path(__file__).resolve().parent / "fixtures" / "day_shift.json"
    fixture = json.loads(source.read_text(encoding="utf-8"))
    with tempfile.TemporaryDirectory(prefix="spectral-demo-") as directory:
        database = Path(directory) / "lab.sqlite"
        destination = Path(directory) / "quality.json"
        c = Catalog(database)
        try:
            dictionary = save_dictionary(c, fixture["channels"], fixture["components"],
                                         fixture["channel_units"], fixture["component_units"],
                                         fixture["matrix"])
            batch = save_batch(c, fixture["channels"], fixture["channel_units"], fixture["records"])
            revisions = c.read_record(batch, "batch")["data"]["revision_ids"]
            cohort = freeze(c, dictionary, revisions)
            parent = unmix(c, cohort)
            positive = direction(c, parent, fixture["positive"])
            negative = direction(c, parent, fixture["negative"])
            parent_saved = read(c, parent)
            response_saved = read(c, positive)
            x = parent_saved["data"]["rows"][0]["coefficients"]
            plus = response_saved["data"]["rows"][0]["coefficients"]
            minus = read(c, negative)["data"]["rows"][0]["coefficients"]
            assert x == [F(1, 2), F(1, 2), F(0)]
            assert plus == [F(0), F(0), F(1)]
            assert minus == [F(0), F(0), F(0)]
            newer = save_dictionary(c, fixture["channels"], fixture["components"],
                                    fixture["channel_units"], fixture["component_units"],
                                    [[2, 2, 0], [0, 0, 2]], previous=dictionary)
            corrected = append_measurement_revision(c, revisions[0], [3, 0])
            new_parent = unmix(c, freeze(c, newer, [corrected]))
            self_check = read(c, new_parent)["data"]["rows"][0]["coefficients"]
            assert self_check == [F(3, 4), F(3, 4), F(0)]
            export(c, positive, destination)
        finally:
            c.close()
        c = Catalog(database)
        try:
            c.initialize()
            assert read(c, parent) == parent_saved
            assert read(c, positive) == response_saved
            package = decode_payload(destination.read_text(encoding="utf-8"))
            artifacts = {item["id"]: item for item in package["chain"]["artifacts"]}
            assert artifacts[parent] == parent_saved
            assert artifacts[positive] == response_saved
            print("POINTWISE_SCENARIO " + encode_payload({
                "case_id": "V3.joint_handoff",
                "input": {"A": fixture["matrix"], "y": fixture["records"][0]["values"],
                          "positive_d": fixture["positive"], "negative_d": fixture["negative"]},
                "expected": [F(1, 2), F(1, 2), F(0)], "actual": x,
                "downstream_expected": {"positive": [0, 0, 1], "negative": [0, 0, 0],
                                        "new_parent": [F(3, 4), F(3, 4), F(0)]},
                "downstream_actual": {"positive": plus, "negative": minus, "new_parent": self_check},
                "code_paths": ["spectral/dictionary/revisions.py", "spectral/measurements/cohorts.py",
                               "spectral/unmixing/jobs.py", "spectral/response/requests.py",
                               "spectral/archive/export.py"],
                "oracle": "equal-column hand split, one-sided max(0,y2), frozen reopen and export identity"}))
            print(encode_payload({"old_parent": parent_saved, "positive": response_saved,
                                  "negative": read(c, negative), "new_parent": read(c, new_parent),
                                  "export_record_count": len(package["chain"]["records"])}))
        finally:
            c.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
