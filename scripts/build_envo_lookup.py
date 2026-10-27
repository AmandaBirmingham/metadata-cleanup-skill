"""Build the skill's ENVO lookup table from an ENVO release.

Maintainer tool; not used during metadata cleanup sessions.

Combines the repository's ENVO term list (TSV) with the hierarchy and synonyms
in an ENVO OWL release, and writes one TSV row per term with its label,
synonyms, obsolete status, direct parents, flags for which MIxS environment
field the term suits, and the ENVO release it came from.

Parents are the named targets of rdfs:subClassOf plus the named genus class of
each owl:equivalentClass/owl:intersectionOf definition.

Usage:
    python3 build_envo_lookup.py ENVO_OWL ENVO_TERMS_TSV OUTPUT_TSV
"""

from __future__ import annotations

import argparse
import csv
import sys
from collections import defaultdict
from pathlib import Path
from xml.etree import ElementTree as ET

OWL = "{http://www.w3.org/2002/07/owl#}"
RDF = "{http://www.w3.org/1999/02/22-rdf-syntax-ns#}"
RDFS = "{http://www.w3.org/2000/01/rdf-schema#}"
OBO_IN_OWL = "{http://www.geneontology.org/formats/oboInOwl#}"

SYNONYM_TAGS = (
    "hasExactSynonym",
    "hasRelatedSynonym",
    "hasNarrowSynonym",
    "hasBroadSynonym",
)

# Root classes whose descendants suit each MIxS environment field.
FIELD_ROOTS = {
    "is_biome": "ENVO:00000428",  # biome
    "is_env_system": "ENVO:01000254",  # environmental system
    "is_env_material": "ENVO:00010483",  # environmental material
}

OUTPUT_COLUMNS = [
    "term_id",
    "label",
    "synonyms",
    "is_obsolete",
    "replaced_by_term_id",
    "parent_ids",
    "parent_labels",
    *FIELD_ROOTS,
    "envo_release",
]


def curie(iri: str) -> str:
    """Convert an OBO IRI such as .../obo/ENVO_00000428 to ENVO:00000428."""
    return iri.rsplit("/", 1)[-1].replace("_", ":", 1)


def single_line(text: str) -> str:
    """Replace tabs and line breaks so a value fits in one TSV cell."""
    return " ".join(text.split())


class OwlData:
    """Labels, synonyms and direct parents read from an OWL file."""

    def __init__(self, owl_path: Path) -> None:
        """Parse the OWL file."""
        root = ET.parse(owl_path).getroot()
        version = root.find(f"{OWL}Ontology/{OWL}versionIRI")
        if version is None:
            msg = f"No owl:versionIRI found in {owl_path}"
            raise ValueError(msg)
        self.release = version.get(f"{RDF}resource", "").split("/")[-2]
        self.parents: dict[str, set[str]] = defaultdict(set)
        self.synonyms: dict[str, list[str]] = defaultdict(list)
        self.labels: dict[str, str] = {}
        for owl_class in root.findall(f"{OWL}Class"):
            about = owl_class.get(f"{RDF}about")
            if about:
                self._read_class(curie(about), owl_class)

    def _read_class(self, term_id: str, owl_class: ET.Element) -> None:
        for sub in owl_class.findall(f"{RDFS}subClassOf"):
            target = sub.get(f"{RDF}resource")
            if target:
                self.parents[term_id].add(curie(target))
        genus_path = f"{OWL}equivalentClass/{OWL}Class/{OWL}intersectionOf/{OWL}Class"
        for genus in owl_class.findall(genus_path):
            target = genus.get(f"{RDF}about")
            if target:
                self.parents[term_id].add(curie(target))
        label = owl_class.find(f"{RDFS}label")
        if label is not None and label.text:
            self.labels[term_id] = label.text
        for tag in SYNONYM_TAGS:
            for synonym in owl_class.findall(f"{OBO_IN_OWL}{tag}"):
                text = single_line(synonym.text or "")
                if text and text not in self.synonyms[term_id]:
                    self.synonyms[term_id].append(text)

    def descendants_and_self(self, root_id: str) -> set[str]:
        """Return root_id and every class below it in the hierarchy."""
        children: dict[str, set[str]] = defaultdict(set)
        for child, parents in self.parents.items():
            for parent in parents:
                children[parent].add(child)
        found = {root_id}
        stack = [root_id]
        while stack:
            for child in children[stack.pop()]:
                if child not in found:
                    found.add(child)
                    stack.append(child)
        return found


def build(owl_path: Path, terms_path: Path, out_path: Path) -> None:
    """Write the lookup table and print a short summary."""
    owl = OwlData(owl_path)
    field_members = {
        flag: owl.descendants_and_self(root_id) for flag, root_id in FIELD_ROOTS.items()
    }
    with terms_path.open(newline="", encoding="utf-8") as f:
        terms = list(csv.DictReader(f, delimiter="\t"))

    label_mismatches = 0
    with out_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, delimiter="\t", lineterminator="\n")
        writer.writerow(OUTPUT_COLUMNS)
        for term in terms:
            term_id = term["term_id"]
            owl_label = owl.labels.get(term_id, "")
            if term["label"] and owl_label and owl_label != term["label"]:
                label_mismatches += 1
            parent_ids = sorted(owl.parents.get(term_id, ()))
            writer.writerow(
                [
                    term_id,
                    term["label"] or owl_label,
                    "|".join(owl.synonyms.get(term_id, [])),
                    term["is_obsolete"],
                    term["replaced_by_term_id"],
                    "|".join(parent_ids),
                    "|".join(owl.labels.get(p, "") for p in parent_ids),
                    *(
                        str(term_id in field_members[flag]).lower()
                        for flag in FIELD_ROOTS
                    ),
                    owl.release,
                ]
            )

    print(f"ENVO release {owl.release}: {len(terms)} terms written to {out_path}")
    print(f"Label mismatches between TSV and OWL: {label_mismatches}")
    for flag, members in field_members.items():
        current = sum(
            1 for t in terms if t["term_id"] in members and t["is_obsolete"] == "false"
        )
        print(f"{flag}: {current} current terms")


def main(argv: list[str] | None = None) -> int:
    """Parse arguments and build the lookup table."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("owl", type=Path, help="ENVO release in OWL/RDF-XML format")
    parser.add_argument("terms", type=Path, help="repository ENVO term list (TSV)")
    parser.add_argument("output", type=Path, help="lookup table to write (TSV)")
    args = parser.parse_args(argv)
    if args.output.exists():
        parser.error(f"{args.output} already exists; choose a new name")
    build(args.owl, args.terms, args.output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
