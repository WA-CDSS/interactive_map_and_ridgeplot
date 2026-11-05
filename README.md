# Washington County Prevalence Explorer

An interactive [Altair](https://altair-viz.github.io/) visualization of county-level prevalence estimates for Washington State, and of the uncertainty around each estimate. A Python script builds it and writes one standalone HTML file. No server is needed: open `wa_prevalence.html` in a browser.

## The three panes

| Pane | Shows | When a county is focused (clicked) |
|---|---|---|
| **Map** (left) | A choropleth of each county's point estimate | The focused county is outlined in **black**, its neighbors in **blue** and counties with similar estimates in **red** |
| **Bordering** (middle, blue) | A ridgeline of every county's posterior density, ordered by estimate | Only the focused county and the counties that border it |
| **Nearest by estimate** (right, red) | The same ridgeline | The focused county plus the 3 counties just below it and the 3 just above it by estimate |

### Interactions

- **Hover (soft focus):** hover a county on the map or a ridge in either ridgeline.
  - The county is highlighted in all three panes; on the map, every other county fades to 50% opacity.
  - The county's estimated prevalence appears as a label in the middle of the county, and a tooltip shows the county name and estimate.
- **Click a county on the map (strong focus):** sets the focus that filters the two ridgelines and draws the colored outlines. The ridgeline titles update to name the focused county.
- **Clear the focus:** click empty space on the map, or double-click.

## Quick start

You need [uv](https://docs.astral.sh/uv/) and Python 3.11 or newer.

```bash
uv sync                 # install dependencies
uv run build_viz.py     # writes wa_prevalence.html
open wa_prevalence.html # or open it in any browser
```

The build prints each county's neighbor list as a sanity check.

> The HTML page loads Vega, Vega-Lite and Vega-Embed from the jsDelivr CDN, so viewing it needs an internet connection. The data is embedded in the file.

## Input data

| File | Columns | Notes |
|---|---|---|
| `data/ests.parquet` | `county` (str), `estimate` (float) | One row per county (39 rows). Values are proportions, e.g. `0.26` = 26%. |
| `data/densities.parquet` | `county` (str), `prev` (float), `density` (float) | Posterior density of each county's prevalence on a 0–1 grid with a step of 0.001. |
| `data/raw/cb_2023_us_county_500k.zip` | Census cartographic county boundaries | Used to draw the map. |
| `data/raw/tl_2023_us_county.zip` | Census TIGER/Line county boundaries | Used to work out which counties border each other. |

County names must exactly match the Census `NAME` field (e.g. `Grays Harbor`, `Walla Walla`); the build stops with an error if they don't.

If either Census zip is missing, the script reads it straight from census.gov. To keep a local copy:

```bash
mkdir -p data/raw && cd data/raw
curl -LO https://www2.census.gov/geo/tiger/GENZ2023/shp/cb_2023_us_county_500k.zip
curl -LO https://www2.census.gov/geo/tiger/TIGER2023/COUNTY/tl_2023_us_county.zip
```

## How the groups are defined

- **Bordering counties:** two counties border each other if their **legal** boundaries (TIGER/Line) touch. Legal county lines run into Puget Sound and the Columbia River, so counties separated only by water count as neighbors; San Juan, for example, borders Clallam, Island, Jefferson, Skagit and Whatcom. Counties that meet only at a corner also count. The map itself uses the shoreline-clipped shapes, so it looks right.
- **Similar estimates:** counties are ranked by `estimate`, with ties broken alphabetically. The group is the focused county plus the 3 counties immediately below it and the 3 immediately above it. At the ends of the ranking the group is smaller; for example, the lowest county shows only the 3 counties above it.

Both groups are computed in Python. The resulting membership lists are embedded in the chart, and the browser uses them to filter.

## Customizing

All settings are constants at the top of `build_viz.py`:

| Constant | Default | Controls |
|---|---|---|
| `N_RANK_NEIGHBORS` | `3` | How many counties above and below the focused one appear in the right pane |
| `COLOR_DOMAIN` | `[0.2, 0.55]` | The range of the shared viridis color scale. Values outside it get the end colors. |
| `RIDGE_PEAK_ROWS` | `7.0` | How many rows the tallest ridge spans. All ridges share one scale, so their heights can be compared. |
| `PREV_STEP` | `0.004` | Spacing of the grid used to draw the ridges (coarser means a smaller HTML file) |
| `BORDER_BLUE`, `BORDER_BG` | blue / pale blue | Neighbor outline color on the map and the middle pane's background |
| `RANK_RED`, `RANK_BG` | red / pale red | Similar-estimate outline color on the map and the right pane's background |
| `MAP_W`, `MAP_H`, `RIDGE_W`, `RIDGE_H` | sizes in pixels | Pane dimensions |

## Project layout

```
.
├── build_viz.py          # data prep + chart definition; run to rebuild the HTML
├── pyproject.toml        # dependencies (altair, pandas, pyarrow, geopandas, shapely)
├── wa_prevalence.html    # generated output
├── data/
│   ├── ests.parquet
│   ├── densities.parquet
│   └── raw/              # Census boundary shapefiles (zipped)
└── examples/             # reference images the design was based on
```

### How `build_viz.py` is organized

1. **`build_tables()`** loads the estimates, densities and boundaries. It computes each county's neighbors and its similar-estimate group, and stores, for each county, the list of focused counties whose views include it. It also trims and thins the density grid and finds a point inside each county to anchor the map label.
2. **`map_pane()`** builds the map in layers: the colored counties, then the blue, red and black outlines, then the hover label.
3. **`ridge_pane()`** builds a ridgeline as a single chart. Rows are re-ranked after filtering, so the remaining ridges spread out to fill the pane when a county is focused. Fills are drawn as narrow rectangles colored by prevalence, which gives the left-to-right gradient; a black line traces each ridge on top.
4. **`build_chart()`** sets up the two selections: hover (`soft`, shared by all three panes) and click (`strong`, set only from the map). It then places the panes side by side.

## Known behavior

- Clicking the already-focused county doesn't clear the focus; click empty map space or double-click instead.
- Only the map sets strong focus. Clicking a ridge does nothing beyond the hover highlight.
- The browser console shows a harmless Vega-Lite warning (`Conflicting legend property "disable"`). It comes from the hidden stroke legend used to cover the seams between the ridge rectangles.
