"""Build the linked three-pane WA prevalence visualization (Altair -> HTML).

Panes
  1. Choropleth of county estimates (hover = soft focus, click = strong focus)
  2. Ridgeline of posterior densities; under strong focus -> focus + bordering counties
  3. Ridgeline; under strong focus -> focus + 3 nearest lower + 3 nearest higher by estimate

Run:  uv run build_viz.py   ->  wa_prevalence.html
"""

from pathlib import Path

import altair as alt
import geopandas as gpd
import pandas as pd

ROOT = Path(__file__).parent
DATA = ROOT / "data"
RAW = DATA / "raw"
CB_ZIP = RAW / "cb_2023_us_county_500k.zip"  # cartographic (shoreline-clipped) shapes, for display
TL_ZIP = RAW / "tl_2023_us_county.zip"  # TIGER legal boundaries (extend into water), for adjacency
CB_URL = "https://www2.census.gov/geo/tiger/GENZ2023/shp/cb_2023_us_county_500k.zip"
TL_URL = "https://www2.census.gov/geo/tiger/TIGER2023/COUNTY/tl_2023_us_county.zip"
OUT = ROOT / "wa_prevalence.html"

WA_FIPS = "53"
N_RANK_NEIGHBORS = 3
PREV_STEP = 0.004  # thinned density grid step
RIDGE_PEAK_ROWS = 7.0  # tallest ridge in the dataset spans this many rows
COLOR_DOMAIN = [0.2, 0.55]  # shared color scale (clamped) so the map keeps contrast

BORDER_BLUE, BORDER_BG = "#2563eb", "#eef4fd"  # neighbors: map outline / middle-pane background
RANK_RED, RANK_BG = "#dc2626", "#fdf0ef"  # similar estimates: map outline / right-pane background

MAP_W, MAP_H = 520, 380
RIDGE_W, RIDGE_H = 300, 640


# --------------------------------------------------------------------------- data


def load_wa(zip_path: Path, url: str) -> gpd.GeoDataFrame:
    src = zip_path if zip_path.exists() else url
    gdf = gpd.read_file(src)
    gdf = gdf[gdf["STATEFP"] == WA_FIPS].rename(columns={"NAME": "county"})
    return gdf[["county", "geometry"]].reset_index(drop=True)


def adjacency(tl: gpd.GeoDataFrame) -> dict[str, list[str]]:
    tl = tl.set_index("county")
    joined = gpd.sjoin(tl.reset_index(), tl.reset_index(), predicate="intersects")
    joined = joined[joined["county_left"] != joined["county_right"]]
    return joined.groupby("county_left")["county_right"].apply(sorted).to_dict()


def membership_string(groups: dict[str, list[str]]) -> dict[str, str]:
    """Invert focus -> members into county -> '|F1|F2|...|' (the foci that show it)."""
    inv: dict[str, set[str]] = {}
    for focus, members in groups.items():
        for c in members:
            inv.setdefault(c, set()).add(focus)
    return {c: "|" + "|".join(sorted(f)) + "|" for c, f in inv.items()}


def build_tables():
    ests = pd.read_parquet(DATA / "ests.parquet")
    dens = pd.read_parquet(DATA / "densities.parquet")

    cb = load_wa(CB_ZIP, CB_URL)
    tl = load_wa(TL_ZIP, TL_URL)
    assert set(cb.county) == set(ests.county), set(cb.county) ^ set(ests.county)

    # unique 0..n-1 order by estimate (ties broken by name)
    ests = ests.sort_values(["estimate", "county"]).reset_index(drop=True)
    ests["order"] = range(len(ests))
    names = ests["county"].tolist()

    # pane 2 groups: focus + bordering counties
    nbrs = adjacency(tl)
    border_groups = {c: [c, *nbrs.get(c, [])] for c in names}

    # pane 3 groups: focus + 3 nearest lower + 3 nearest higher by estimate
    rank_groups = {
        c: names[max(0, i - N_RANK_NEIGHBORS) : i + N_RANK_NEIGHBORS + 1]
        for i, c in enumerate(names)
    }

    ests["border_of"] = ests["county"].map(membership_string(border_groups))
    ests["rank_of"] = ests["county"].map(membership_string(rank_groups))
    ests["label"] = ests["estimate"].map(lambda v: f"{v:.1%}")

    print("Neighbor counts:")
    for c in names:
        print(f"  {c:<13} {len(nbrs.get(c, [])):>2}  {', '.join(nbrs.get(c, []))}")

    # ridge data: trim to where any county has mass, thin the grid, scale to row units
    peak = dens.groupby("county")["density"].transform("max")
    live = dens.loc[dens["density"] > 1e-3 * peak, "prev"]
    lo, hi = live.min() - PREV_STEP, live.max() + PREV_STEP
    grid = (dens["prev"] / PREV_STEP).round(6) % 1 == 0
    ridge = dens[grid & dens["prev"].between(lo, hi)].copy()
    ridge["h"] = ridge["density"] * RIDGE_PEAK_ROWS / dens["density"].max()
    ridge["prev2"] = ridge["prev"] + PREV_STEP
    ridge = ridge.merge(ests[["county", "estimate", "order", "border_of", "rank_of"]], on="county")
    ridge = ridge[["county", "prev", "prev2", "h", "estimate", "order", "border_of", "rank_of"]]

    # map data: display geometry + estimates + label anchor
    cb = cb.merge(ests, on="county")
    cb["geometry"] = cb.geometry.simplify(0.002, preserve_topology=True)
    pts = cb.to_crs(32610).geometry.representative_point().to_crs(4326)
    cb["lon"], cb["lat"] = pts.x, pts.y

    return cb, ridge, ests, (lo, hi)


# --------------------------------------------------------------------------- chart

STRONG_COUNTY = "(length(data('strong_store')) ? data('strong_store')[0].values[0] : null)"


def color_scale():
    return alt.Scale(scheme="viridis", reverse=True, domain=COLOR_DOMAIN, clamp=True)


def map_pane(cb: gpd.GeoDataFrame, soft, strong):
    base = alt.Chart(cb).properties(width=MAP_W, height=MAP_H).project(type="mercator")
    tooltip = [alt.Tooltip("county:N", title="County"), alt.Tooltip("estimate:Q", title="Estimate", format=".1%")]

    fill = (
        base.mark_geoshape(stroke="#4a4a4a", strokeWidth=0.6)
        .encode(
            color=alt.Color("estimate:Q", scale=color_scale(), title="Prevalence",
                            legend=alt.Legend(format=".0%", orient="bottom", gradientLength=260)),
            fillOpacity=alt.when(soft).then(alt.value(1.0)).otherwise(alt.value(0.5)),
            tooltip=tooltip,
        )
        .add_params(soft, strong)
    )

    def group_outline(member_col: str, color: str, width: float):
        """Thin border around the focused county's group members (excluding the focus itself)."""
        s = STRONG_COUNTY
        return base.mark_geoshape(filled=False, stroke=color, strokeWidth=width).transform_filter(
            f"{s} !== null && datum.county !== {s} && indexof(datum.{member_col}, '|' + {s} + '|') >= 0"
        )

    # blue (wider) under red (narrower): a county in both groups shows a two-tone edge
    border_outline = group_outline("border_of", BORDER_BLUE, 2.4)
    rank_outline = group_outline("rank_of", RANK_RED, 1.2)
    outline = (
        base.mark_geoshape(filled=False, stroke="black", strokeWidth=2.6)
        .transform_filter(alt.param(strong.name, empty=False))
    )
    label = (
        alt.Chart(cb[["county", "lon", "lat", "label"]])
        .mark_text(fontSize=13, fontWeight="bold", color="white", stroke="black",
                   strokeWidth=0.4, cursor="pointer")
        .encode(longitude="lon:Q", latitude="lat:Q", text="label:N")
        .transform_filter(alt.param(soft.name, empty=False))
    )
    return alt.layer(fill, border_outline, rank_outline, outline, label).properties(
        title=alt.Title(
            "Estimated prevalence",
            subtitle=["Hover to highlight · click to focus · click background to clear",
                      "Focused: black · bordering: blue · similar estimate: red"],
        )
    )


def ridge_pane(ridge: pd.DataFrame, ests: pd.DataFrame, xdom, member_col: str,
               title_all: str, title_focus: str, soft, bg: str, accent: str):
    """Ridgeline as a single unit (no facet): rows are re-ranked after the strong-focus filter."""
    flt = (
        f"{STRONG_COUNTY} === null || "
        f"indexof(datum.{member_col}, '|' + {STRONG_COUNTY} + '|') >= 0"
    )
    rank = alt.WindowFieldDef(op="dense_rank", field="order", **{"as": "row"})

    def staged(chart):
        return chart.transform_filter(flt).transform_window(window=[rank], sort=[alt.SortField("order")])

    x = alt.X("prev:Q", title="Prevalence", scale=alt.Scale(domain=list(xdom), nice=False),
              axis=alt.Axis(format=".0%", grid=True, tickCount=6))
    y_axis = alt.Axis(labels=False, ticks=False, domain=False, grid=False, title=None)
    opacity = alt.when(soft).then(alt.value(1.0)).otherwise(alt.value(0.18))
    z = alt.Order("order:Q", sort="descending")  # lower rows drawn over upper rows
    tooltip = [alt.Tooltip("county:N", title="County"), alt.Tooltip("estimate:Q", title="Estimate", format=".1%")]

    base = alt.Chart(ridge)
    fill = staged(base).transform_calculate(top="datum.row + datum.h").mark_rect(strokeWidth=0.6).encode(
        x=x, x2="prev2:Q",
        y=alt.Y("row:Q", axis=y_axis, scale=alt.Scale(zero=False, nice=False, padding=8)),
        y2="top:Q",
        color=alt.Color("prev:Q", scale=color_scale(), legend=None),
        stroke=alt.Stroke("prev:Q", scale=color_scale(), legend=None),  # hides seams between rects
        opacity=opacity, order=z, tooltip=tooltip,
    ).add_params(soft)
    line = staged(base).transform_calculate(top="datum.row + datum.h").mark_line(
        color="black", strokeWidth=0.9
    ).encode(
        x="prev:Q", y="top:Q", detail="county:N", order="prev:Q",
        opacity=alt.when(soft).then(alt.value(1.0)).otherwise(alt.value(0.25)),
    )
    baseline = staged(alt.Chart(ests)).mark_rule(color="#bdbdbd", strokeWidth=0.6).encode(
        y="row:Q", x=alt.value(0), x2=alt.value(RIDGE_W),
    )
    labels = staged(alt.Chart(ests)).mark_text(align="right", baseline="bottom", dx=-6, dy=-1, fontSize=11).encode(
        y="row:Q", x=alt.value(0), text="county:N",
        opacity=alt.when(soft).then(alt.value(1.0)).otherwise(alt.value(0.35)),
    )
    title_expr = f"{STRONG_COUNTY} === null ? '{title_all}' : {STRONG_COUNTY} + '{title_focus}'"
    return alt.layer(baseline, fill, line, labels).properties(
        width=RIDGE_W, height=RIDGE_H,
        view=alt.ViewBackground(fill=bg, stroke=None),
        title=alt.Title(alt.ExprRef(title_expr), subtitle="Posterior density of prevalence",
                        color=accent),
    )


def build_chart():
    cb, ridge, ests, xdom = build_tables()
    soft = alt.selection_point(name="soft", on="pointerover", clear="pointerout", fields=["county"])
    strong = alt.selection_point(name="strong", on="click", fields=["county"], toggle=False, clear="dblclick")

    mid = ridge_pane(ridge, ests, xdom, "border_of", "All counties", " and bordering counties", soft,
                     bg=BORDER_BG, accent=BORDER_BLUE)
    right = ridge_pane(ridge, ests, xdom, "rank_of", "All counties", " and nearest by estimate", soft,
                       bg=RANK_BG, accent=RANK_RED)
    chart = (
        alt.hconcat(map_pane(cb, soft, strong), mid, right, spacing=90)
        .resolve_scale(color="shared", stroke="independent")
        .resolve_legend(stroke="independent")
        .configure_view(stroke=None)
        .configure_title(anchor="start", fontSize=15, subtitleColor="#666")
        .configure_axis(labelColor="#444", titleColor="#444", gridColor="#e6e6e6")
    )
    return chart


if __name__ == "__main__":
    alt.data_transformers.disable_max_rows()
    build_chart().save(OUT)
    print(f"Wrote {OUT}")
