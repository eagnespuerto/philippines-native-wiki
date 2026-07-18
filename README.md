# Philippines Native Wiki

A downsized wiki of ~60 plants and animals native to **Metro Manila**, **Region III (Central Luzon)**, and **CALABARZON**, packaged as a lightweight Tkinter app that runs on 32-bit Raspberry Pi OS.

- Text: Wikipedia (CC BY-SA 4.0 excerpts)
- Images: Wikimedia Commons (individual licenses recorded per species)
- Curated fields (region, habitat, colors, edibility) hand-tagged in `scripts/seed.py`

## Repository layout

```
philippines-native-wiki/
├── data/
│   ├── species.json        # built artifact (produced by build script)
│   └── images/             # compressed JPEGs, each <= 1 MB
├── scripts/
│   ├── seed.py             # curated 60-species master list
│   └── build_wiki.py       # fetches Wikipedia + Commons, writes species.json
├── app/
│   ├── main.py             # Tkinter entry point
│   ├── data.py             # load + filter species
│   └── ui.py               # list + detail views
├── requirements.txt
└── README.md
```

## Building the data (one-time, needs internet)

```bash
python -m pip install -r requirements.txt
python scripts/build_wiki.py
```

The builder writes `data/species.json` and downloads a lead image per species
into `data/images/`. Each image is re-encoded to JPEG and iteratively lowered
in quality until it fits under 1 MB.

## Running the app

```bash
python app/main.py
```

On Raspberry Pi OS (32-bit), the only runtime dependency beyond the Python
standard library is Pillow (for image display):

```bash
sudo apt install python3-pil python3-pil.imagetk
python3 app/main.py
```

## Filters

The app lets you filter by:

- **Kind** — animal / plant
- **Region** — NCR (Metro Manila) / Region III / CALABARZON
- **Habitat** — forest, wetland, coastal, urban, grassland, mountain, farmland
- **Edibility** — edible / not edible
- **Search** — free-text over common + scientific names

## Attribution

Every image records its Wikimedia Commons author and license in
`species.json.imageCredit`. Text summaries are quoted from English Wikipedia
under CC BY-SA 4.0.
