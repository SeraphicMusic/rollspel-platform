"""Systemadaptrar: laddar regelsystemskunskap från system/<id>/ (ren data).

Varje adapter består av:
    system.json           — attribut, intervall, härledda formler, utgåvor
    lexicon.json          — kanoniska termer/ord + kända variantmappningar
    dice.json             — tärningsgrammatik + OCR-förväxlingar
    statblock.schema.json — fältkrav för statblock
    detection.json        — fingeravtryck för systemidentifiering
"""
import json
import unicodedata
from pathlib import Path

SYSTEM_ROOT = Path(__file__).resolve().parent.parent / "system"

_FILES = {
    "system": "system.json",
    "lexicon": "lexicon.json",
    "dice": "dice.json",
    "statblock": "statblock.schema.json",
    "detection": "detection.json",
}


def normalize(text):
    """Matchningsnormalisering (DoD-repots standard): gemener, å/ä->a, ö->o."""
    text = text.lower()
    text = text.replace("å", "a").replace("ä", "a").replace("ö", "o")
    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode("ascii")
    return " ".join(text.split())


class Adapter:
    def __init__(self, system_id, root=None):
        self.id = system_id
        self.root = Path(root or SYSTEM_ROOT) / system_id
        if not self.root.is_dir():
            raise KeyError("okänt system: %s (finns ej i %s)" %
                           (system_id, self.root.parent))
        for attr, fname in _FILES.items():
            path = self.root / fname
            data = {}
            if path.is_file():
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            setattr(self, attr, data)
        self._word_index = None
        self._alias_index = None

    # -- uppslagsstrukturer (lata) ----------------------------------------

    @property
    def words(self):
        """normaliserat ord -> lista av kanoniska former (>1 = tvetydigt)."""
        if self._word_index is None:
            idx = {}
            lex = self.lexicon

            def add(word):
                key = normalize(word)
                if key and word not in idx.setdefault(key, []):
                    idx[key].append(word)

            for word in lex.get("words", []):
                add(word)
            for term, label in lex.get("terms", {}).items():
                add(term)
                add(label)
            for cat in lex.get("categories", {}).values():
                for word in cat:
                    add(word)
            self._word_index = idx
        return self._word_index

    @property
    def aliases(self):
        """normaliserad känd variant -> kanonisk form."""
        if self._alias_index is None:
            self._alias_index = {normalize(k): v for k, v in
                                 self.lexicon.get("aliases", {}).items()}
        return self._alias_index

    @property
    def attribute_names(self):
        return self.system.get("attributes", {}).get("names", [])

    @property
    def dice_sides(self):
        return set(self.dice.get("sides", []))

    def attr_range(self):
        r = self.system.get("attributes", {}).get("range", {})
        return r.get("min", 1), r.get("max", 100)


def available_systems(root=None):
    root = Path(root or SYSTEM_ROOT)
    if not root.is_dir():
        return []
    return sorted(d.name for d in root.iterdir()
                  if d.is_dir() and not d.name.startswith("_")
                  and (d / "system.json").is_file())


def resolve_system_id(name, root=None):
    """Slå upp system via id eller alias ('mutant' -> 'mutant2089')."""
    name_n = normalize(name)
    for sid in available_systems(root):
        if sid == name_n:
            return sid
    for sid in available_systems(root):
        adapter = Adapter(sid, root=root)
        if name_n in [normalize(a) for a in adapter.system.get("aliases", [])]:
            return sid
    raise KeyError("okänt system: %r (tillgängliga: %s)" %
                   (name, ", ".join(available_systems(root))))


def load(name, root=None):
    return Adapter(resolve_system_id(name, root=root), root=root)
