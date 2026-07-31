"""Enhetstester för datadrivna DoD91-regler."""
import unittest

from pipeline.conversion_records import validate_skill_merges
from pipeline.conversion_rules import (Catalog, convert_fv, convert_modifier,
                                       load_profile)


class TestConversionRules(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.profile = load_profile("dod-t100", "dod91")
        cls.catalog = Catalog("dod91")

    def test_fv_examples_and_clamp(self):
        self.assertEqual(convert_fv(15, self.profile), 3)
        self.assertEqual(convert_fv(35, self.profile), 7)
        self.assertEqual(convert_fv(50, self.profile), 10)
        self.assertEqual(convert_fv(70, self.profile), 14)
        self.assertEqual(convert_fv(100, self.profile), 18)
        self.assertEqual(convert_fv(1, self.profile), 3)
        self.assertEqual(convert_fv(200, self.profile), 18)

    def test_authoritative_bfv_table(self):
        expected = {
            0: 0, 1: 1, 5: 1, 6: 2, 10: 2, 11: 3, 15: 3,
            16: 4, 19: 4, 20: 5,
        }
        for fv, bfv in expected.items():
            self.assertEqual(self.catalog.bfv(fv), bfv)

    def test_resistance_table_is_in_snapshot(self):
        table = self.catalog.tables_data["resistance_table"]
        self.assertEqual(len(table["rows"]), 21)
        self.assertEqual(table["rows"][0]["chances"][0], 10)
        self.assertEqual(
            table["rows"][0]["chances"][10], "automatic_success")
        self.assertEqual(
            table["rows"][10]["chances"][0], "automatic_failure")

    def test_alias_must_resolve_to_catalog(self):
        self.assertEqual(
            self.catalog.skill("Finna dolda",
                               self.profile["skill_aliases"])["name"],
            "Finna dolda ting")
        self.assertIsNone(self.catalog.skill(
            "Påhittad", {"Påhittad": "Finns inte"}))
        for alias in self.profile["skill_aliases"]:
            self.assertIsNotNone(self.catalog.skill(
                alias, self.profile["skill_aliases"]))
        for alias in self.profile["weapon_aliases"]:
            self.assertIsNotNone(self.catalog.weapon(
                alias, self.profile["weapon_aliases"]))
        for alias in self.profile["armor_aliases"]:
            self.assertIsNotNone(self.catalog.armor_item(
                alias, self.profile["armor_aliases"]))

    def test_weapon_uses_canonical_values(self):
        weapon = self.catalog.weapon(
            "Kort svärd", self.profile["weapon_aliases"])
        self.assertEqual(weapon["name"], "Kortsvärd")
        self.assertIn("damage", weapon)
        self.assertEqual(weapon["weaponGroup"], "enhandssward")
        self.assertEqual(
            self.catalog.weapon(
                "Korstvärd", self.profile["weapon_aliases"])["name"],
            "Kortsvärd")

    def test_modifier_is_not_clamped_to_fv_range(self):
        """En modifikator är ett delta och ska inte klampas till [3, 18]."""
        self.assertEqual(convert_modifier(-20, self.profile), -4)
        self.assertEqual(convert_modifier(-5, self.profile), -1)
        self.assertEqual(convert_modifier(10, self.profile), 2)
        self.assertEqual(convert_fv(-20, self.profile), 3)


class TestSkillMergeGuard(unittest.TestCase):
    """Spärren mot tyst dataförlust när färdigheter slås ihop."""

    def test_lower_value_overwriting_higher_is_rejected(self):
        with self.assertRaises(ValueError) as caught:
            validate_skill_merges(
                "p009_e15",
                {"Enhandssvärd": [("Bredsvärd", "80%", 16),
                                  ("Korstvärd", "70%", 14)]},
                {"Enhandssvärd": 14})
        self.assertIn("gått förlorad", str(caught.exception))

    def test_highest_value_surviving_is_accepted(self):
        validate_skill_merges(
            "p009_e15",
            {"Enhandssvärd": [("Bredsvärd", "80%", 16),
                              ("Korstvärd", "70%", 14)]},
            {"Enhandssvärd": 16})


if __name__ == "__main__":
    unittest.main()
