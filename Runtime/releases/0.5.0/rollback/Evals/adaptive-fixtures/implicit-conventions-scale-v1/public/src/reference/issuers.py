"""Issuer universe: canonical issuer tokens, aliases and parent chains.

This is the DEFINED TRADABLE UNIVERSE for exposure attribution: small,
stable, reviewed quarterly with the desks. The MATCHING is automated (see
core/resolve.py); only the universe itself is curated. An issuer token
missing here does not error - resolution returns unresolved and the exposure
stays in the venue bucket, so nothing is ever mis-attributed to a public
ticker just because the universe lagged a listing.

Curation notes:
* canonical tokens are the uppercase issuer names as they appear in venue
  notices, not legal names;
* ALIASES cover feed-specific spellings observed in captures;
* PARENTS map subsidiary and shell tokens to the canonical issuer whose
  ticker carries the exposure (the crosswalk the resolution ladder consults
  after exact/alias/containment/fuzzy all miss).
"""

# canonical issuer token -> ticker
ISSUER_TICKERS = {
    "GLX": "GLXN",  # data infrastructure
    "MERIDIAN": "MRDN",  # diversified industrials
    "HALVORSEN": "HLVR",  # shipping and logistics
    "KESTREL": "KSTL",  # avionics
    "OKUDA": "OKDA",  # precision machinery
    "BRANNOCK": "BRNK",  # footwear and apparel
    "TALWEG": "TLWG",  # hydro engineering
    "VIREO": "VIRO",  # agricultural biotech
    "QUILLON": "QLLN",  # specialty steel
    "SANDPIPER": "SNDP",  # asset management
    "COBALTWORKS": "CBLT",  # battery materials
    "FENWICK": "FNWK",  # consumer credit
    "LARKSPUR": "LKSP",  # hospitality
    "MARROWGATE": "MRWG",  # medical devices
    "NIMBUSDATA": "NMBS",  # cloud storage
    "OSPREYTECH": "OSPT",  # defense electronics
    "PELLUCID": "PLCD",  # optical components
    "RAVENSCROFT": "RVNC",  # private banking
    "STELLARIS": "STLR",  # satellite services
    "THORNFIELD": "THRN",  # agrochemicals
    "UMBERLINE": "UMBR",  # paints and coatings
    "VANTAGEPOINT": "VNTG",  # market data
    "WYCLIFFE": "WYCL",  # publishing
    "YARROWBANK": "YRRW",  # regional banking
    "ZEPHYRINE": "ZPHR",  # wind energy
    "ALDERSHOTT": "ALDS",  # brewing
    "BASSWOOD": "BSWD",  # timber and pulp
    "CARDAMINE": "CRDM",  # specialty pharma
    "DELVAUXITE": "DLVX",  # mining
    "EBBTIDE": "EBTD",  # port operations
    "FALKLINE": "FLKL",  # subsea cables
    "GRISWOLDE": "GRSW",  # insurance
    "HELIOTROPE": "HLTR",  # solar inverters
    "INKWELLS": "INKW",  # industrial printing
    "JUNIPERRIDGE": "JNPR2",  # vineyards
    "KILNCROFT": "KLNC",  # ceramics
    "LODESTONE": "LDST",  # magnetics
    "MOORCOCK": "MRCK",  # gas distribution
    "NARWHALINE": "NRWL",  # cold-chain freight
    "OXBOWDALE": "OXBD",  # river logistics
    "PARSECDYNE": "PRSC",  # propulsion
    "QUINTARELLE": "QNTR",  # luxury goods
    "ROOKHAVEN": "RKHV",  # student housing
    "SILVERTHREAD": "SLVT",  # textiles
    "TANAGERWORKS": "TNGR",  # robotics
    "UNDERCLIFF": "UNDC",  # tunneling
    "VERMILIONBAY": "VRMB",  # offshore drilling
    "WHITLOCKE": "WHTL",  # auctions
    "XANTHICLABS": "XNTH",  # pigments
    "YELLOWKEEL": "YLWK",  # ferries
    "ZINCFORGE": "ZNCF",  # galvanizing
    "AMBERGRIS": "AMBG",  # fragrances
    "BLACKDAMP": "BLKD",  # mine safety
    "CINDERHOLM": "CNDH",  # district heating
    "DRIFTWELL": "DRFW",  # bottled water
    "EIDERDOWNE": "EIDR",  # bedding
    "FLINTMERE": "FLNT",  # glass
    "GORSEHILL": "GRSH",  # landscaping
    "HARROWGATE": "HRWG",  # rail maintenance
    "IRONQUAY": "IRNQ",  # crane leasing
}

# alias token -> canonical issuer token
ALIASES = {
    "GALAXIA": "GLX",
    "GALAXIADATA": "GLX",
    "MERIDIANCO": "MERIDIAN",
    "HALVORSENGRP": "HALVORSEN",
    "KESTRELSYS": "KESTREL",
    "OKUDAHD": "OKUDA",
    "BRANNOCKIND": "BRANNOCK",
    "VIREOLABS": "VIREO",
    "SANDPIPERAM": "SANDPIPER",
    "COBALT": "COBALTWORKS",
    "FENWICKLTD": "FENWICK",
    "NIMBUS": "NIMBUSDATA",
    "OSPREY": "OSPREYTECH",
    "STELLARISPLC": "STELLARIS",
    "VPOINT": "VANTAGEPOINT",
    "ALDERSHOTTBRW": "ALDERSHOTT",
    "BASSWOODPULP": "BASSWOOD",
    "CARDAMINERX": "CARDAMINE",
    "EBBTIDEPORTS": "EBBTIDE",
    "GRISWOLDERE": "GRISWOLDE",
    "HELIOTROPESOL": "HELIOTROPE",
    "LODESTONEMAG": "LODESTONE",
    "PARSEC": "PARSECDYNE",
    "QUINTA": "QUINTARELLE",
    "SILVERTHREADTX": "SILVERTHREAD",
    "TANAGER": "TANAGERWORKS",
    "VERMILION": "VERMILIONBAY",
    "WHITLOCKEAUC": "WHITLOCKE",
    "YELLOWKEELFER": "YELLOWKEEL",
    "ZINC": "ZINCFORGE",
}

# subsidiary / shell token -> parent canonical issuer token
PARENTS = {
    "GLXVENTURES": "GLX",
    "MERIDIANRE": "MERIDIAN",
    "KESTRELFIN": "KESTREL",
    "OKUDACAP": "OKUDA",
    "TALWEGHOLD": "TALWEG",
    "QUILLONSUB": "QUILLON",
    "LARKSPURTWO": "LARKSPUR",
    "THORNFIELDRE": "THORNFIELD",
    "WYCLIFFEHOLD": "WYCLIFFE",
    "ZEPHYRINEKK": "ZEPHYRINE",
    "ALDERSHOTTFIN": "ALDERSHOTT",
    "EBBTIDETWO": "EBBTIDE",
    "FALKLINESUB": "FALKLINE",
    "HELIOTROPEJV": "HELIOTROPE",
    "MOORCOCKPIPE": "MOORCOCK",
    "PARSECDYNELAB": "PARSECDYNE",
    "ROOKHAVENRE": "ROOKHAVEN",
    "UNDERCLIFFJV": "UNDERCLIFF",
    "VERMILIONSUB": "VERMILIONBAY",
    "IRONQUAYLEASE": "IRONQUAY",
}
