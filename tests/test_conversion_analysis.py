"""Tester för kandidatidentifiering i text, tabeller och statblock."""
import unittest

from pipeline.conversion_analysis import analyze_and_convert
from pipeline.conversion_rules import Catalog, load_profile


def book_with(elements):
    return {
        "source": {"path": "/tmp/test.pdf", "metadata": {"title": "Test"}},
        "system": {"id": "dod"},
        "stats": {"missing_pages": [], "needs_review": 0},
        "pages": [{"page": 1, "elements": elements}],
    }


class TestConversionAnalysis(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.profile = load_profile("dod-t100", "dod91")
        cls.catalog = Catalog("dod91")

    def convert(self, elements):
        return analyze_and_convert(
            book_with(elements), self.profile, self.catalog)

    def test_fv_in_prose_but_not_plain_number(self):
        converted, analysis = self.convert([{
            "id": "p001_e01", "type": "paragraph",
            "text": "Simma 50% krävs. Rummet är 50 meter långt.",
            "source": {"page": 1, "region": "kolumn 1"},
        }])
        text = converted["pages"][0]["elements"][0]["text"]
        self.assertEqual(
            text, "Simma FV 10 krävs. Rummet är 50 meter långt.")
        self.assertEqual(analysis["counts"]["applied"], 1)

    def test_bfv_is_recomputed_from_converted_fv(self):
        converted, analysis = self.convert([{
            "id": "p001_e01", "type": "paragraph",
            "text": "Simma 75% (B4)",
        }])
        self.assertEqual(analysis["counts"]["applied"], 1)
        self.assertEqual(analysis["counts"]["needs_review"], 0)
        self.assertEqual(
            converted["pages"][0]["elements"][0]["text"],
            "Simma FV 15 (B3)")

    def test_standalone_bfv_is_valid_target_notation(self):
        converted, analysis = self.convert([{
            "id": "p001_e01", "type": "paragraph",
            "text": "Det krävs minst FV B4 för att lyckas.",
        }])
        self.assertEqual(
            converted["pages"][0]["elements"][0]["text"],
            "Det krävs minst FV B4 för att lyckas.")
        self.assertEqual(analysis["counts"]["needs_review"], 0)
        self.assertEqual(analysis["candidates"][0]["rule"],
                         "bfv.target-native")

    def test_table_cells_are_scanned(self):
        converted, analysis = self.convert([{
            "id": "p001_e01", "type": "table", "text": "",
            "data": {"headers": ["Prov"], "rows": [["Klättra 70%"]]},
        }])
        self.assertEqual(
            converted["pages"][0]["elements"][0]["data"]["rows"][0][0],
            "Klättra FV 14")
        self.assertEqual(analysis["counts"]["applied"], 1)

    def test_labeled_weapon_and_armor_use_catalog_values(self):
        converted, analysis = self.convert([{
            "id": "p001_e01", "type": "paragraph",
            "text": "Vapen: Kort svärd 1T6, Rustning: Ringbrynja ABS 3.",
        }])
        self.assertEqual(
            converted["pages"][0]["elements"][0]["text"],
            "Vapen: Kortsvärd skada 1T6+1, "
            "Rustning: Ringbrynja ABS 5.")
        self.assertEqual(analysis["counts"]["applied"], 2)

    def test_weapon_skill_uses_catalog_group(self):
        converted, analysis = self.convert([{
            "id": "p001_e01", "type": "paragraph",
            "text": "Kortsvärd 77%",
        }])
        self.assertEqual(
            converted["pages"][0]["elements"][0]["text"],
            "Enhandssvärd FV 15")
        self.assertEqual(
            analysis["candidates"][0]["rule"], "fv.weapon-group")

    def test_printed_korstvard_aliases_to_kortsvard_group(self):
        converted, analysis = self.convert([{
            "id": "p001_e01", "type": "statblock", "text": "",
            "data": {
                "name": "Erwin",
                "stats": {"FYS": 15, "STO": 17},
                "skills": {"Korstvärd": "70%"},
            },
        }])
        skills = converted["pages"][0]["elements"][0]["data"]["skills"]
        self.assertEqual(skills, {"Enhandssvärd": 14})
        self.assertEqual(analysis["counts"]["needs_review"], 0)

    def test_printed_korstvard_is_normalized_in_prose(self):
        converted, analysis = self.convert([{
            "id": "p001_e01", "type": "paragraph",
            "text": "Han är skicklig på att hantera dolk och korstvärd.",
        }])
        self.assertEqual(
            converted["pages"][0]["elements"][0]["text"],
            "Han är skicklig på att hantera dolk och kortsvärd.")
        self.assertEqual(analysis["candidates"][0]["rule"], "weapon.alias")
        self.assertEqual(analysis["counts"]["needs_review"], 0)

    def test_list_items_are_scanned(self):
        converted, _ = self.convert([{
            "id": "p001_e01", "type": "list", "text": "",
            "data": {"items": ["Klättra 70%", "vanligt tal 70"]},
        }])
        self.assertEqual(
            converted["pages"][0]["elements"][0]["data"]["items"],
            ["Klättra FV 14", "vanligt tal 70"])

    def test_statblock_skills_kp_weapon_and_unknown(self):
        converted, analysis = self.convert([{
            "id": "p001_e01", "type": "statblock", "text": "",
            "data": {
                "name": "Vakt",
                "stats": {"FYS": 11, "STO": 12, "KP": 10},
                "skills": {"Simma": 50},
                "weapons": [{"name": "Kort svärd", "damage": "1T6"},
                            {"name": "Okänd klinga", "damage": "1T8"}],
            },
        }])
        data = converted["pages"][0]["elements"][0]["data"]
        self.assertEqual(data["skills"]["Simma"], 10)
        self.assertEqual(data["stats"]["KP"], 12)
        self.assertEqual(data["weapons"][0]["name"], "Kortsvärd")
        self.assertEqual(data["weapons"][0]["weaponGroup"],
                         "enhandssward")
        self.assertTrue(any(r["rule"] == "weapon.unmatched"
                            for r in analysis["candidates"]))
        self.assertEqual(
            len([r for r in analysis["candidates"] if r["applied"]]), 3)

    def test_zero_fys_does_not_overwrite_kp(self):
        converted, analysis = self.convert([{
            "id": "p001_e01", "type": "statblock", "text": "",
            "data": {"name": "Odöd",
                     "stats": {"FYS": 0, "STO": 12, "KP": 8}},
        }])
        data = converted["pages"][0]["elements"][0]["data"]
        self.assertEqual(data["stats"]["KP"], 8)
        self.assertEqual(analysis["counts"]["needs_review"], 1)

    def test_named_undead_exception_does_not_overwrite_kp(self):
        converted, analysis = self.convert([{
            "id": "p001_e01", "type": "statblock", "text": "",
            "data": {"name": "Skelettkrigare",
                     "stats": {"FYS": 10, "STO": 10, "KP": 14}},
        }])
        data = converted["pages"][0]["elements"][0]["data"]
        self.assertEqual(data["stats"]["KP"], 14)
        self.assertEqual(analysis["counts"]["needs_review"], 1)

    def test_equipment_mapping_and_scalar_are_supported(self):
        converted, _ = self.convert([{
            "id": "p001_e01", "type": "statblock", "text": "",
            "data": {
                "name": "Vakt",
                "stats": {"FYS": 10, "STO": 10},
                "weapons": {"Kort svärd": "1T6"},
                "armor": "Ringbrynja",
            },
        }])
        data = converted["pages"][0]["elements"][0]["data"]
        self.assertIn("Kortsvärd", data["weapons"])
        self.assertEqual(data["weapons"]["Kortsvärd"]["damage"], "1T6+1")
        self.assertEqual(data["armor"]["name"], "Ringbrynja")
        self.assertEqual(data["armor"]["absorption"], 5)

    def test_source_rules_reference_requires_review(self):
        _, analysis = self.convert([{
            "id": "p001_e01", "type": "paragraph",
            "text": "Slå 1T100.",
        }])
        self.assertEqual(analysis["counts"]["applied"], 0)
        self.assertEqual(analysis["counts"]["needs_review"], 1)

    def test_attribute_times_five_percent_becomes_fv_modifier(self):
        converted, analysis = self.convert([{
            "id": "p001_e01", "type": "paragraph",
            "text": ("Dra av Steinars PSY x 5% från RPns "
                     "färdighetsslag."),
        }])
        self.assertEqual(
            converted["pages"][0]["elements"][0]["text"],
            "Dra av Steinars aktuella PSY från RPns färdighetsslag.")
        self.assertEqual(analysis["counts"]["applied"], 1)
        self.assertEqual(analysis["counts"]["needs_review"], 0)
        self.assertEqual(
            analysis["candidates"][0]["rule"],
            "modifier.attribute-times-five-percent")

    def test_named_languages_merge_into_house_rule_skill(self):
        converted, analysis = self.convert([{
            "id": "p001_e01", "type": "statblock", "text": "",
            "data": {
                "name": "Erbolsus",
                "skills": {
                    "Tala Zorakiska": "50%",
                    "Tala Kardiska": "50%",
                },
            },
        }])
        skills = converted["pages"][0]["elements"][0]["data"]["skills"]
        self.assertEqual(skills, {"Språkkunskap": 10})
        # Två mappningsposter plus den post som redovisar sammanslagningen.
        self.assertEqual(analysis["counts"]["applied"], 3)
        self.assertEqual(analysis["counts"]["needs_review"], 0)
        self.assertEqual(
            [item["rule"] for item in analysis["candidates"]],
            ["skill.language-unified", "skill.language-unified",
             "skill.merged-target"])

    def test_weapon_group_collision_keeps_highest_fv(self):
        """Två vapen i samma DoD91-grupp får inte skriva över varandra."""
        converted, analysis = self.convert([{
            "id": "p001_e01", "type": "statblock", "text": "",
            "data": {
                "name": "Erwin",
                "skills": {
                    "Bredsvärd": "80%",
                    "Gatuslagsmål": "80%",
                    "Korstvärd": "70%",
                    "Upptäcka fara": "60%",
                },
            },
        }])
        skills = converted["pages"][0]["elements"][0]["data"]["skills"]
        self.assertEqual(skills, {
            "Enhandssvärd": 16, "Slagsmål": 16, "Upptäcka fara": 12})
        merge = [item for item in analysis["candidates"]
                 if item["rule"] == "skill.merged-target"]
        self.assertEqual(len(merge), 1)
        self.assertEqual(merge[0]["original"], "Bredsvärd 80% + Korstvärd 70%")
        self.assertEqual(merge[0]["converted"], "Enhandssvärd 16")
        self.assertIn("FV 14", merge[0]["reason"])
        self.assertEqual(analysis["counts"]["needs_review"], 0)

    def test_weapon_group_collision_is_order_independent(self):
        converted, _ = self.convert([{
            "id": "p001_e01", "type": "statblock", "text": "",
            "data": {
                "name": "Erwin",
                "skills": {"Korstvärd": "70%", "Bredsvärd": "80%"},
            },
        }])
        skills = converted["pages"][0]["elements"][0]["data"]["skills"]
        self.assertEqual(skills, {"Enhandssvärd": 16})

    def test_percent_point_modifier_becomes_fv_step(self):
        converted, analysis = self.convert([{
            "id": "p001_e01", "type": "paragraph",
            "text": "En RP som lyckas med Finna Dolda Ting (med –20 "
                    "på slaget) finner luckan.",
        }])
        self.assertEqual(
            converted["pages"][0]["elements"][0]["text"],
            "En RP som lyckas med Finna Dolda Ting (med –4 på slaget) "
            "finner luckan.")
        self.assertEqual(
            analysis["candidates"][0]["rule"],
            "modifier.percent-points-to-fv")
        self.assertEqual(analysis["counts"]["needs_review"], 0)

    def test_modifier_within_fv_range_is_flagged_not_converted(self):
        converted, analysis = self.convert([{
            "id": "p001_e01", "type": "paragraph",
            "text": "Gör ett Övertala-slag med -2 på slaget.",
        }])
        self.assertEqual(
            converted["pages"][0]["elements"][0]["text"],
            "Gör ett Övertala-slag med -2 på slaget.")
        self.assertEqual(
            analysis["candidates"][0]["rule"], "modifier.ambiguous-scale")
        self.assertEqual(analysis["counts"]["needs_review"], 1)
        self.assertEqual(analysis["counts"]["applied"], 0)

    def test_cl_percent_threshold_with_bfv_becomes_fv(self):
        """B-nivån räknas om ur det konverterade FV:t, inte ur källans egen
        B-uppgift: trycket skriver B3 medan DoD91:s tabell ger B2 för FV 10."""
        converted, analysis = self.convert([{
            "id": "p001_e01", "type": "paragraph",
            "text": "Alla som har 50% CL (FV B3) eller mer klarar det.",
        }])
        self.assertEqual(
            converted["pages"][0]["elements"][0]["text"],
            "Alla som har FV 10 (B2) eller mer klarar det.")
        self.assertEqual(
            analysis["candidates"][0]["rule"], "fv.divide-by-five")
        self.assertEqual(analysis["counts"]["needs_review"], 0)

    def test_combined_music_skill_splits_into_dod91_skills(self):
        converted, analysis = self.convert([{
            "id": "p001_e01", "type": "statblock", "text": "",
            "data": {
                "name": "Torolv",
                "skills": {"Spela och sjunga": 75},
            },
        }])
        skills = converted["pages"][0]["elements"][0]["data"]["skills"]
        self.assertEqual(skills, {
            "Spela stränginstrument": 15,
            "Sjunga": 15,
        })
        self.assertEqual(analysis["counts"]["applied"], 1)
        self.assertEqual(analysis["counts"]["needs_review"], 0)
        self.assertEqual(analysis["candidates"][0]["rule"], "skill.split")

    def test_slagsvard_maps_to_matching_dod91_bastardsvard(self):
        converted, analysis = self.convert([{
            "id": "p001_e01", "type": "statblock", "text": "",
            "data": {
                "name": "Viking",
                "weapons": [{
                    "name": "Slagsvärd",
                    "attack": "80%",
                    "damage": "1T10+1",
                }],
            },
        }])
        weapon = converted["pages"][0]["elements"][0]["data"]["weapons"][0]
        self.assertEqual(weapon["name"], "Bastardsvärd")
        self.assertEqual(weapon["damage"], "1T10+1")
        self.assertEqual(analysis["counts"]["needs_review"], 0)

    def test_language_chance_in_prose_uses_house_rule_skill(self):
        converted, analysis = self.convert([{
            "id": "p001_e01", "type": "paragraph",
            "text": "Han har CL 90%+ (FV B5) i Erebosiska.",
        }])
        self.assertEqual(
            converted["pages"][0]["elements"][0]["text"],
            "Han har Språkkunskap FV 10.")
        self.assertEqual(analysis["counts"]["applied"], 1)
        self.assertEqual(analysis["counts"]["needs_review"], 0)
        self.assertEqual(
            analysis["candidates"][0]["rule"], "skill.language-unified")

    def test_language_list_in_prose_collapses_to_house_rule_skill(self):
        converted, analysis = self.convert([{
            "id": "p001_e01", "type": "paragraph",
            "text": "alla som har 50% CL (FV B3) eller mer på Läsa/\n"
                    "Skriva Zorakiska, Kardiska eller Trakoriska\n"
                    "märker det.",
        }])
        self.assertEqual(
            converted["pages"][0]["elements"][0]["text"],
            "alla som har FV 10 (B2) eller mer på Språkkunskap\nmärker det.")
        self.assertEqual(analysis["counts"]["needs_review"], 0)

    def test_language_as_a_verb_is_left_alone(self):
        """'kan tala zorakiska' är inte ett färdighetsomnämnande."""
        text = ("En vakt som kan tala Zorakiska släpper in dem, och de kan "
                "läsa och skriva Kardiska.")
        converted, analysis = self.convert([{
            "id": "p001_e01", "type": "paragraph", "text": text,
        }])
        self.assertEqual(converted["pages"][0]["elements"][0]["text"], text)
        self.assertEqual(analysis["counts"]["applied"], 0)

    def _viking(self, **data):
        base = {"name": "Ulf", "stats": {"FYS": 15, "STO": 7}}
        base.update(data)
        return [{"id": "p001_e01", "type": "statblock", "text": "",
                 "data": base}]

    def test_printed_weapon_values_survive_the_catalog(self):
        """Trycket vinner över katalogen — spelvärden rättas aldrig (Regel 8a)."""
        converted, analysis = self.convert(self._viking(weapons=[
            {"name": "Stridsyxa", "attack": "85%", "damage": "1T10+2",
             "bv": 11}]))
        weapon = converted["pages"][0]["elements"][0]["data"]["weapons"][0]
        self.assertEqual(weapon["damage"], "1T10+2")
        self.assertEqual(weapon["bv"], 11)
        # Katalogen fyller i det boken inte anger.
        self.assertEqual(weapon["weaponGroup"], "enhandsyxor")
        self.assertIn("weight", weapon)
        # ...och avvikelsen mot katalogen flaggas i stället för att döljas.
        flagged = [c for c in analysis["candidates"]
                   if c["rule"] == "weapon.printed-value-differs"]
        self.assertEqual(len(flagged), 1)
        self.assertIn("1T10+2", flagged[0]["original"])
        self.assertTrue(flagged[0]["needs_review"])
        self.assertFalse(flagged[0]["applied"])

    def test_weapon_attack_percent_becomes_fv(self):
        """Angreppsvärdet är bärarens färdighet och får inte kastas."""
        converted, analysis = self.convert(self._viking(weapons=[
            {"name": "Stridsyxa", "attack": "85%"}]))
        weapon = converted["pages"][0]["elements"][0]["data"]["weapons"][0]
        self.assertEqual(weapon["attack"], 17)
        self.assertTrue(any(
            c["rule"] == "fv.divide-by-five" and c["category"] == "weapon_skill"
            for c in analysis["candidates"]))

    def test_printed_range_is_not_replaced_by_generic(self):
        converted, _ = self.convert(self._viking(weapons=[
            {"name": "Kastspjut", "rackvidd": "18 rutor"}]))
        weapon = converted["pages"][0]["elements"][0]["data"]["weapons"][0]
        self.assertEqual(weapon["rackvidd"], "18 rutor")
        self.assertNotIn("range", weapon)

    def test_statblock_other_fields_are_scanned(self):
        """Skydd/Förflyttning m.fl. var en blind fläck — inget scannades där."""
        converted, analysis = self.convert(self._viking(
            other={"Skydd": "Ringbrynja (abs 4), Stor sköld (85%, abs 16)"}))
        other = converted["pages"][0]["elements"][0]["data"]["other"]
        # Sköldens abs blir katalogens BV; rustningens abs 4 lämnas orörd.
        self.assertEqual(
            other["Skydd"],
            "Ringbrynja (abs 4), Rundsköld, stor (FV 17, BV 11)")
        rules = [c["rule"] for c in analysis["candidates"]]
        self.assertIn("shield.absorption-to-bv", rules)
        self.assertNotIn("term.unmatched", rules)
        self.assertEqual(analysis["counts"]["blocking"], 0)

    def test_unknown_parenthesised_term_is_flagged(self):
        converted, analysis = self.convert(self._viking(
            other={"Special": "Hednisk pryl (60%)"}))
        other = converted["pages"][0]["elements"][0]["data"]["other"]
        self.assertEqual(other["Special"], "Hednisk pryl (FV 12)")
        self.assertIn("term.unmatched",
                      [c["rule"] for c in analysis["candidates"]])

    def test_resistance_table_is_target_native(self):
        converted, analysis = self.convert([{
            "id": "p001_e01", "type": "paragraph",
            "text": "Slå på motståndstabellen.",
        }])
        self.assertEqual(
            converted["pages"][0]["elements"][0]["text"],
            "Slå på motståndstabellen.")
        self.assertEqual(analysis["counts"]["needs_review"], 0)
        self.assertEqual(analysis["candidates"][0]["rule"],
                         "rules-reference.target-native")


if __name__ == "__main__":
    unittest.main()
