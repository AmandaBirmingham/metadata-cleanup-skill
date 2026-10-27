# ENA requirements, lookups and null values

## Fields every ENA sample needs

- **Sample taxon ID** — the NCBI taxon of the *sample*, not the host. For most
  microbiome samples this is a "… metagenome" taxon (for example, human gut
  metagenome, 408170). Look in `assets/metagenome_taxa.tsv` first.
- **ENA checklist** — for example ERC000011 (the default checklist) or
  ERC000014; usually a MIxS-based checklist chosen from the host and sample
  type.

Most checklists also require:

- collection date;
- geographic location (country and/or sea), from ENA's fixed list;
- latitude and longitude, in decimal degrees;
- broad_scale_environmental_context, preferably an ENVO biome;
- local_environmental_context, preferably an ENVO term;
- environmental_medium, preferably an ENVO environmental material.

Check the required fields of the chosen checklist on the ENA website when the
network is available. *(Planned: a bundled snapshot of the common checklists'
required fields, for when it isn't.)*

## When ENA fields are out of scope

These fields are optional for this work in two cases:

- the scientist says the data will never be made public through ENA; or
- the data will reach ENA through a separate route that brings its own
  fields (for example, an older submission process whose required columns
  the file already holds).

Ask which applies; don't assume. Record the scientist's statement in the
decision log. Host taxon ID and sample type are still required for every
sample in both cases.

## Taxon IDs

- Search `assets/ncbi_taxonomy.tsv.gz` (columns: term_id, label,
  alternate_label, is_obsolete, replaced_by_term_id, obsoletion_kind). It is
  compressed and large: search it with a streaming command, never load it
  whole. For partial names, search the whole line
  (`gzip -dc … | grep -i 'macaca'`) and then narrow down.
- If a taxon ID already in the scientist's file is obsolete, propose the
  replacement from replaced_by_term_id.
- If the network is available, confirm with ENA's taxonomy service that the
  taxon is submittable. If not, record the taxon as unconfirmed in the
  decision log.
- Host taxon ID special values: free-living samples → `not applicable`; most
  controls → `missing: control sample`.

## ENVO terms

`assets/envo_lookup.tsv` holds every term in the repository's ENVO term list
(4,321 ENVO terms, current and obsolete), with hierarchy from ENVO release
2026-06-26. Columns:

| Column | Meaning |
|---|---|
| term_id, label, synonyms | identity and search text (synonyms separated by `|`) |
| is_obsolete, replaced_by_term_id | obsolete terms and their replacements |
| parent_ids, parent_labels | direct parents in ENVO |
| is_biome | a biome (under ENVO:00000428) — suits broad_scale_environmental_context |
| is_env_system | an environmental system (under ENVO:01000254) — suits local_environmental_context |
| is_env_material | an environmental material (under ENVO:00010483) — suits environmental_medium |
| envo_release | the ENVO release it was built from |

Biomes are themselves environmental systems in ENVO, so a biome also has
is_env_system = true. *(To confirm against current MIxS guidance: which ENVO
branches each field should draw from.)*

Never suggest an obsolete term. If the scientist's file contains one, propose
its replacement.

## ENA null values

Use only after a real effort to get actual values. Explain each in plain words
and let the scientist choose:

| Term | Plain meaning |
|---|---|
| `not applicable` | This field doesn't make sense for this sample (host body site for a soil sample). |
| `not collected` | The information was never recorded. |
| `not provided` | The information was asked for but not supplied. |
| `restricted access` | It exists but can't be shared (for example, for privacy). |
| `missing: control sample` | The sample is a control, so the field has no real value. |

*(To confirm against ENA's current list: the full set of accepted missing-value
terms and their exact wording.)*
