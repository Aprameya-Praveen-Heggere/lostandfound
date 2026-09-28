# V2 Matching Engine

1. Hard filters select only the authenticated institution, exact category, open availability, and non-archived records.
2. Structured scoring compares names, colors, brands/types, descriptions, locations, and dates.
3. Semantic scoring compares normalized text embeddings. The local provider maps synonyms and hashes terms into a normalized vector; configured-provider failure falls back deterministically.
4. If both records have private images, an image histogram embedding adds a bounded optional signal. No face detection or sensitive inference occurs.

The weighted score is 55% structured, 35% semantic, and up to 10% image. Confidence bands are low below 45, medium from 45–74, and high at 75+. Stable found-item IDs break ties. Explanations expose contributing public factors, never private ownership evidence. Scores never alter claim state or approve ownership.
