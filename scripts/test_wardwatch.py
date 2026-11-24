import json
import tempfile
import unittest
from pathlib import Path

from property_standards import normalize_property_standards
from wardwatch import changes_between, normalize, refresh


def feature(folder=101, address="100 TEST ST", category="Community planning", status="Under Review"):
    return {"attributes": {
        "OBJECTID": folder,
        "FOLDERRSN": folder,
        "REFERENCEFILE": f"A{folder}/26TEY" if category == "C of A" else None,
        "APPLICATION_NUMBER": f"26 {folder} WET 05 OZ",
        "FULL_ADDRESS": address,
        "FOLDERNAME": address,
        "FOLDERTYPE": "MV" if category == "C of A" else "OZ",
        "FOLDERTYPE_DESC": "Minor Variance" if category == "C of A" else "OPA / Rezoning",
        "APPLICATION_TYPE": category,
        "STATUS_DESC": status,
        "STATUS_GROUP": "Open",
        "SUBMIT_DATE": 1767225600000,
        "FOLDERDESCRIPTION": "Test proposal",
        "WARD_NUMBER": "05",
        "WARD_NAME": "York South-Weston",
        "AIC_URL": "https://example.test/application",
    }}


def property_data(investigation_id="9001", house="55", deficiency_status="Open"):
    return {
        "investigations": [{
            "INVESTIGATION_ID": investigation_id,
            "INVESTIGATION#": "26 123456 PRS 00 IV",
            "INVESTIGATION_TYPE": "Order Issued Property Standards",
            "IN_DATE": "Nov 17, 2026",
            "NOTICE_OR_ORDER_DATE": "Nov 20, 2026",
            "NEXT_INSPECTION": "Dec 22, 2026",
            "EXPIRY_DATE": "Dec 21, 2026",
            "ISSUE": "Order Issued Property Standards / Order to Comply",
            "CURRENT_STATUS": "Order Issued",
        }, {
            "INVESTIGATION_ID": "other-type",
            "INVESTIGATION#": "26 OTHER",
            "INVESTIGATION_TYPE": "Zoning",
            "IN_DATE": "Nov 17, 2026",
            "CURRENT_STATUS": "Open",
        }],
        "addresses": [{
            "INVESTIGATION_ID": investigation_id,
            "ASSESSED_OR_MAILING_ADDRESS": f"{house} EMMETT AVE",
            "PROPHOUSE": house,
            "PROPSTREET": "EMMETT",
            "PROPSTREETTYPE": "AVE",
            "PROPSTREETDIRECTION": "",
        }],
        "deficiencies": [{
            "INVESTIGATION_ID": investigation_id,
            "LOCATION": "Bedroom",
            "SUBLOCATION": "",
            "TEXT": "Wall not maintained.",
            "STATUS": deficiency_status,
        }],
        "address_points": [{
            "ADDRESS_NUMBER": house,
            "LINEAR_NAME": "Emmett",
            "LINEAR_NAME_TYPE": "Ave",
            "LINEAR_NAME_DIR": "None",
            "ADDRESS_FULL": f"{house} Emmett Ave",
            "WARD": "05",
            "WARD_NAME": "York South-Weston",
            "geometry": json.dumps({"type": "Point", "coordinates": [-79.5, 43.68]}),
        }],
    }


class NormalizationTests(unittest.TestCase):
    def test_addresses_are_consolidated(self):
        apps = normalize([feature(address="100 TEST ST"), feature(address="102 TEST ST")])
        self.assertEqual(len(apps), 1)
        self.assertEqual(len(apps[0]["addresses"]), 2)
        self.assertEqual(apps[0]["category"], "planning")

    def test_all_three_aic_categories_are_preserved(self):
        apps = normalize([
            feature(folder=1, category="Community planning"),
            feature(folder=2, category="C of A"),
            feature(folder=3, category="TLAB"),
        ])
        self.assertEqual({app["category"] for app in apps}, {"planning", "coa", "tlab"})

    def test_status_change_is_explicit(self):
        before = normalize([feature()])[0]
        after = normalize([feature(status="Closed")])[0]
        changes = changes_between(before, after)
        self.assertEqual(changes[0]["field"], "status")

    def test_source_html_entities_are_decoded(self):
        app = normalize([feature(address="9 HERTFORD AVE - PARTS 2, 3 &amp; 4")])[0]
        self.assertEqual(app["display_address"], "9 HERTFORD AVE - PARTS 2, 3 & 4")

    def test_property_investigation_join_and_deficiencies(self):
        apps, quality, _ = normalize_property_standards(property_data(), "05")
        self.assertEqual(len(apps), 1)
        app = apps[0]
        self.assertEqual(app["id"], "property:9001")
        self.assertEqual(app["category"], "property")
        self.assertEqual(app["submitted_date"], "2026-11-17")
        self.assertEqual(app["notice_or_order_date"], "2026-11-20")
        self.assertEqual(app["next_inspection"], "2026-12-22")
        self.assertEqual(app["deficiencies"][0]["text"], "Wall not maintained.")
        self.assertEqual(app["addresses"][0]["latitude"], 43.68)
        self.assertEqual(quality["matched_address_rows"], 1)

    def test_ambiguous_property_address_is_not_guessed(self):
        data = property_data()
        data["addresses"][0]["PROPSTREETTYPE"] = ""
        second = dict(data["address_points"][0])
        second["LINEAR_NAME_DIR"] = "W"
        second["ADDRESS_FULL"] = "55 Emmett Ave W"
        data["address_points"][0]["LINEAR_NAME_DIR"] = "E"
        data["address_points"][0]["ADDRESS_FULL"] = "55 Emmett Ave E"
        data["address_points"].append(second)
        with self.assertRaisesRegex(RuntimeError, "matched confidently"):
            normalize_property_standards(data, "05")


class RefreshTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.project = Path(self.temp.name)
        for directory in ["public/data", "public/digests", "public/exports", "data/snapshots", "digests", "exports"]:
            (self.project / directory).mkdir(parents=True)

    def tearDown(self):
        self.temp.cleanup()

    def write_input(self, features, name="input.json"):
        path = self.project / name
        path.write_text(json.dumps({"features": features}), encoding="utf-8")
        return path

    def write_property_input(self, data, name="property-input"):
        directory = self.project / name
        directory.mkdir(exist_ok=True)
        for key, rows in data.items():
            (directory / f"{key}.json").write_text(json.dumps(rows), encoding="utf-8")
        return directory

    def test_baseline_then_new_and_changed(self):
        first = self.write_input([feature(), feature(folder=2, category="TLAB")])
        baseline = refresh(self.project, "05", first, include_property=False)
        self.assertTrue(baseline["latest_digest"]["baseline"])
        self.assertEqual(baseline["stats"]["new"], 0)
        self.assertEqual(baseline["stats"]["open"], 2)

        second = self.write_input([
            feature(status="Approved"),
            feature(folder=2, category="TLAB"),
            feature(folder=3, category="C of A"),
        ], "second.json")
        current = refresh(self.project, "05", second, include_property=False)
        digest = current["latest_digest"]
        self.assertFalse(digest["baseline"])
        self.assertEqual(digest["counts"]["new"], 1)
        self.assertEqual(digest["new_applications"][0]["id"], "3")
        self.assertEqual(digest["counts"]["changed"], 1)
        self.assertEqual(current["stats"]["planning"], 1)
        self.assertEqual(current["stats"]["coa"], 1)
        self.assertEqual(current["stats"]["tlab"], 1)
        self.assertTrue((self.project / "public/data/latest.js").exists())
        self.assertTrue(list((self.project / "digests").glob("*.html")))

    def test_property_has_separate_baseline_then_tracks_new_and_changed(self):
        aic = self.write_input([feature()])
        refresh(self.project, "05", aic, include_property=False)
        first_property = self.write_property_input(property_data())
        current = refresh(self.project, "05", aic, first_property)
        self.assertTrue(current["latest_digest"]["property_baseline"])
        self.assertEqual(current["stats"]["new"], 0)
        self.assertEqual(current["stats"]["property"], 1)
        self.assertEqual(current["stats"]["property_records"], 1)

        second_data = property_data(deficiency_status="Rectified")
        new_data = property_data(investigation_id="9002", house="57")
        for key in second_data:
            if key != "address_points":
                second_data[key].extend(new_data[key])
        second_data["address_points"].append(new_data["address_points"][0])
        second_property = self.write_property_input(second_data, "property-input-2")
        following = refresh(self.project, "05", aic, second_property)
        self.assertFalse(following["latest_digest"]["property_baseline"])
        self.assertEqual(following["stats"]["new"], 1)
        self.assertEqual(following["stats"]["changed"], 1)
        changed_fields = {item["field"] for item in following["latest_digest"]["changes"][0]["changes"]}
        self.assertIn("deficiency_summary", changed_fields)
        self.assertTrue(list((self.project / "data/snapshots").glob("*-property-standards.json.gz")))

    def test_fresh_runner_restores_normalized_state_and_history(self):
        first_input = self.write_input([feature(), feature(folder=2, category="TLAB")])
        baseline = refresh(self.project, "05", first_input, include_property=False)
        original_first_seen = baseline["applications"][0]["first_seen"]
        state = (self.project / "data/state/ward-05.json").read_bytes()

        with tempfile.TemporaryDirectory() as cloud_directory:
            cloud = Path(cloud_directory)
            for directory in ["public/data", "public/digests", "public/exports", "data/state", "digests", "exports"]:
                (cloud / directory).mkdir(parents=True)
            (cloud / "data/state/ward-05.json").write_bytes(state)
            second_input = self.write_input([
                feature(status="Approved"),
                feature(folder=2, category="TLAB"),
                feature(folder=3, category="C of A"),
            ], "cloud-input.json")

            current = refresh(cloud, "05", second_input, include_property=False)

            self.assertEqual(current["latest_digest"]["previous_captured_at"], baseline["generated_at"])
            self.assertFalse(current["latest_digest"]["baseline"])
            self.assertEqual(current["stats"]["new"], 1)
            self.assertEqual(current["stats"]["changed"], 1)
            restored = next(app for app in current["applications"] if app["id"] == "101")
            self.assertEqual(restored["first_seen"], original_first_seen)

    def test_invalid_state_never_silently_starts_a_new_baseline(self):
        state_path = self.project / "data/state/ward-05.json"
        state_path.parent.mkdir(parents=True)
        state_path.write_text('{"schema_version": 1, "ward": "05"}', encoding="utf-8")
        source = self.write_input([feature()])

        with self.assertRaisesRegex(RuntimeError, "refusing to start a new baseline"):
            refresh(self.project, "05", source, include_property=False)
        self.assertFalse((self.project / "public/data/latest.json").exists())


if __name__ == "__main__":
    unittest.main()
