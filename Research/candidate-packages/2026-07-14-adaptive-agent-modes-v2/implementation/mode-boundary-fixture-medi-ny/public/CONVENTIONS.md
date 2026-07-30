# NYRx PDL feed — drug-name conventions (discoverable in-workspace)

The task is underspecified by design: it asks for "bare drug names" without
enumerating every case. These are the house conventions the rest of the pipeline
already relies on. They are discoverable here and in the parser's own docstrings;
each maps to one graded dimension.

- The parser emits one NyPdlRow per drug per column, with status preferred or non_preferred and the therapeutic class taken from the section header.
- A drug name must not carry a dosage strength; strip trailing strength tails such as 20 mg, 30 mg, 60 mg so that duloxetine 20 mg becomes duloxetine.
- Drop the generic-equivalent annotation in parentheses so that Cymbalta (gen duloxetine) becomes Cymbalta.
- Strip trailing dosage-form and packaging words so that Buphenyl powder, tablet becomes Buphenyl.
- Strip a device or form word that bled in from an adjacent column so that Diskus Depakote becomes Depakote.
- Preserve a trailing delivery device that is genuinely part of the brand: keep Advair Diskus, Trelegy Ellipta and Proventil HFA intact.
- A drug name must never contain an unbalanced parenthesis or a stray trailing bracket left by line wrapping.
- Drop any footnote URL that bled into a cell so that aspirin https://newyork.fhsc.com/x becomes aspirin.
