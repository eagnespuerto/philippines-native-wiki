# Philippines Native Wiki

[![license](https://img.shields.io/badge/license-MIT-blue)](LICENSE)
[![release](https://img.shields.io/github/v/release/eagnespuerto/philippines-native-wiki?include_prereleases&sort=semver)](https://github.com/eagnespuerto/philippines-native-wiki/releases/latest)
[![made with](https://img.shields.io/badge/made%20with-Python-3776AB?logo=python&logoColor=white)](https://github.com/eagnespuerto/philippines-native-wiki)
[![platform](https://img.shields.io/badge/platform-Raspberry%20Pi-A22846?logo=raspberrypi&logoColor=white)](https://github.com/eagnespuerto/philippines-native-wiki#readme)
[![Ko-fi](https://img.shields.io/badge/Ko--fi-support%20me-FF5E5B?logo=kofi&logoColor=white)](https://ko-fi.com/eagnespuerto)
[![Linktree](https://img.shields.io/badge/Linktree-soitsagnes-43E55E?logo=linktree&logoColor=white)](https://linktr.ee/soitsagnes)

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
├── packaging/
│   ├── philippines-native-wiki.desktop   # menu entry template
│   └── install-desktop-entry.sh          # installer for the menu entry
├── requirements.txt
└── README.md
```

## Quickstart on Raspberry Pi OS (32-bit)

Everything below assumes a fresh Raspberry Pi OS install. All commands
run on the Pi itself.

```bash
# 1. system dependencies (git + Pillow for image display)
sudo apt update
sudo apt install -y git python3-pil python3-pil.imagetk

# 2. clone the repo (~13 MB, mostly compressed images)
git clone https://github.com/eagnespuerto/philippines-native-wiki.git
cd philippines-native-wiki

# 3. run the app
python3 app/main.py

# 4. (optional) add "Philippines Native Wiki" to the Science menu
./packaging/install-desktop-entry.sh
```

The data bundle is already committed (`data/species.json` and
`data/images/`), so no network access is required after `git clone`.
Rebuild only if you edit `scripts/seed.py` (see below).

To remove the menu entry later: `./packaging/install-desktop-entry.sh --uninstall`.

## Menu category

The launcher registers under **Categories=Science;Education;Biology;**
so it appears in the Science submenu on LXDE (Raspberry Pi OS default),
XFCE, GNOME, and KDE. The `install-desktop-entry.sh` script writes
`~/.local/share/applications/philippines-native-wiki.desktop` with the
`Exec` path rewritten to your clone location, then reloads the LXDE
panel so the entry shows up immediately.

## Running the app on other platforms

```bash
python -m pip install -r requirements.txt
python app/main.py
```

Tested on Python 3.10+; only `Pillow` is needed at runtime.

## Rebuilding the data (only if you edit `seed.py`)

The repo ships with a prebuilt `data/species.json` and image set, so most
users never need to run the fetcher. To refresh from Wikipedia:

```bash
python -m pip install -r requirements.txt
python scripts/build_wiki.py            # refetches only missing entries
python scripts/build_wiki.py --force    # refetch everything
python scripts/build_wiki.py --only narra,molave   # rebuild specific ids
```

The builder writes `data/species.json` and downloads a lead image per
species into `data/images/`. Each image is re-encoded to JPEG and
iteratively lowered in quality until it fits under 1 MB.

## Filters in the app

- **Kind** — animal / plant
- **Region** — NCR (Metro Manila) / Region III / CALABARZON
- **Habitat** — forest, wetland, coastal, urban, grassland, mountain, farmland
- **Edibility** — edible / not edible
- **Search** — free-text over common + scientific names

## Species card

Each entry lives in a scrolling detail pane (mouse wheel, trackpad, or
scrollbar) so long Wikipedia excerpts and long regional notes don't get
clipped. The card shows: image, common + scientific name, region and
habitat chips, colour swatches, edibility flag, Wikipedia summary,
regional notes, and a **Sources** block with:

- Text source: the source Wikipedia article and its licence (CC BY-SA 4.0)
- Image source: the Commons author + licence string
- Buttons to open the Wikipedia article and the Commons image page

The `Help → About / Sources` menu also shows the global attribution.

## Attribution

Every image records its Wikimedia Commons author and license in
`species.json.imageCredit`; the same string appears in the app's
Sources block. Text summaries are quoted from English Wikipedia under
CC BY-SA 4.0. The `applications-science` icon is supplied by the
desktop environment's icon theme (freedesktop.org standard name).
