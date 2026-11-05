I want to plan an altair data visualization which pulls in data on the estimates    
  and distribution of uncertainty regarding the estimates and produces a              
  visualization with three panes. The panes are as follows:                           
                                                                                      
  1) On the far left is a map of Washington State with each county shown. Estimates   
  from  "ests.parquet" are used and will create a map like the examples/map.png but   
  the map has the estimates from the parequet file instead and the map is of          
  Washington State. When a user clicks on a given county, the "strong focus" shifts   
  to the given county. Mousing over a given county will shift the "soft focus" to     
  that county.  Having a strong focus will outline the given county in black. Having  
  a soft focus will highligh the given county and grey out the other counties.        
  Additionally when a county has the soft focus the estimated prevalence will be      
  shown in the middle of the county.                                                  
  2) In the middle pane when there is no hard focus, it will display a ridgeline plot 
  like the one shown in examples/ridgeline.png... (more text coming, wait to          
  respond).                                                                           

⏺ Got it. I'll wait for the rest of the description before I explore the files or
  write the plan.

  So far I have:
  - Pane 1: A choropleth of Washington counties colored by the estimates in
    ests.parquet, styled like examples/map.png.
    - Hover (soft focus): highlights that county, greys out the others and shows its
      estimated prevalence in the middle of the county.
    - Click (strong focus): outlines that county in black.
  - Pane 2: With no strong focus selected, it shows a ridgeline plot like
    examples/ridgeline.png. I'm waiting on the rest of this.

  Send the rest whenever you're ready.

✻ Cooked for 4s · done 12:13 PM

❯ 2) In the middle pane when there is no hard focus, it will display a ridgeline plot 
                                                                                      
       like the one shown in examples/ridgeline.png with all the counties in          
  Washington state. Like the pane on the left, when soft focus is on a given county,  
  all the other counties will dimmed slighly to heighlight the county with a soft     
  focus. Importantly, even if the mouse is on the left pane, the soft focus will      
  apply across all three panes. When strong focus is applied to a given county, the   
  ridgeline plot will only display counties that are immediately bordering the county 
  with the strong focus.                                                              
  3) In the far right pane, there will be another ridge plot the same as the middle   
  pane.  However, when hard focus is placed on a given county, this pane will filter  
  the counties displayed down to the county with strong focus, the three counties     
  closest to the focused county with lower estimate values and the three counties     
       closest to the focused county with higher values.                              

  Read 3 files, listed 1 directory (ctrl+o to expand)

⏺ Bash(which python3 uv; python3 -c "
      import pandas as pd…)
  ⎿  /Users/adamelder/.local/bin/python3
     /Users/adamelder/.local/bin/uv
     Traceback (most recent call last):
     … +5 lines (ctrl+o to expand)

⏺ Bash(uv run --no-project --with pandas --with pyarrow python -c "
      import pandas as pd…)
  ⎿  Downloading pandas (10.7MiB)
     Downloading numpy (5.2MiB)
     Downloading pyarrow (35.6MiB)
     … +56 lines (ctrl+o to expand)
  ⎿  Allowed by auto mode

⏺ User answered Claude's questions:
  ⎿  · When a county has strong focus, should the middle pane (bordering counties) 
     also show the focused county itself? Note that San Juan has no land neighbors. → 
     Include focused county (Recommended)
     · Should two counties separated only by water (e.g. San Juan–Whatcom, 
     Kitsap–King) count as bordering? → Legal boundaries (Recommended)
     · Which color palette should the map and ridgelines share? → Viridis 
     (Recommended)
     · What should the output be? → What about using Altair?
 
⏺ Updated plan
  ⎿  /plan to preview

❯ How reasonable is it to make the described plot with Altair, or do you have         
  thoughts about better app creating options?                                         

⏺ User answered Claude's questions:
  ⎿  · Altair can do this, and every interaction you described can be done in the 
     browser with a single HTML file and no server. The rough spots: overlapping 
     ridgelines take a facet workaround, and titles that change with the clicked 
     county are awkward. Neighbor and nearest-rank filtering are fine if those lists 
     are computed in Python beforehand. Which tool should I plan for? → Altair 
     (Recommended)

──────────────────────────────────────────────────────────────────────────────────────
 Ready to code?
    
 Here is Claude's plan:
╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌
 Interactive WA prevalence dashboard (Altair)

 Context

 We want one interactive Altair chart with three linked panes for county prevalence
 estimates in Washington and the uncertainty around them:
 - a choropleth map,
 - an "uncertainty neighborhood" ridgeline, filtered to the counties that border the
   focused county,
 - a "rank neighborhood" ridgeline, filtered to the counties closest in estimate.

 There are two kinds of focus, and both apply across all three panes:
 - Soft focus: follows hover.
 - Strong focus: set by clicking a county on the map.

 The whole thing is built with Altair. A Python script (build_viz.py) builds it and
 saves a standalone wa_prevalence.html that opens in any browser. The same chart
 object also renders inline in Jupyter if you prefer that.

 Data (already present)

 - data/ests.parquet: 39 rows, county, estimate (range 0.23–0.50).
 - data/densities.parquet: 39×1001 rows, county, prev (0–1 grid, step 0.001),
   density. These are precomputed, so no KDE is needed.
 - No geometry exists yet, so the script adds it (see step 1).

 Files to create

 - pyproject.toml: a uv project with altair>=5, pandas, pyarrow, geopandas, shapely
   and requests.
 - build_viz.py: does the data prep and builds the chart.
 - data/wa_counties.geojson: cached display geometry, generated once.
 - wa_prevalence.html: the output.

 Steps

 1. Geometry and adjacency (build_viz.py, cached on first run)

 - Display shapes: Census cartographic boundary file cb_2023_us_county_500k.
   - Filter to STATEFP == "53" and keep NAME as county.
   - Simplify the shapes (~0.002°) and write them to data/wa_counties.geojson.
   - Assert that the 39 names match ests.county exactly.
 - Adjacency: TIGER/Line tl_2023_us_county, whose county lines extend into water, so
   maritime neighbors count as bordering.
   - Compute the pairs from geom.touches | geom.intersects on the WA subset.
   - Sanity check: San Juan should have ≥1 neighbor.
 - Label points: representative_point() lon/lat for each county, used for the hover
   label.

 2. Derived tables (pandas)

 - Ridge data:
   - Trim densities to the prev range where any county's density is above a tiny
     epsilon (about 0.1–0.8).
   - Thin the grid to a 0.004 step.
   - Join each row's estimate and an order rank (by estimate).
 - Middle-pane membership: a long table with columns focus, county.
   - For every county F, add rows for F itself and each of F's neighbors (user
     choice: include the focused county).
   - Add the sentinel rows focus = "__all__", one for each county.
 - Right-pane membership: the same shape.
   - For every F, add F itself, the 3 next-lower counties by estimate and the 3
     next-higher counties by estimate.
   - Near the ends of the ranking this is truncated, e.g. the lowest county gets F
     plus 3 higher.
   - Add the same __all__ sentinel rows.
 - Join each membership table to the ridge data, so each pane gets its own
   pre-expanded dataset (tens of thousands of rows, which is fine inline).
       pre-expanded dataset (tens of thousands of rows, which is fine inline).

     3. Shared params

     - soft = alt.selection_point(name="soft", on="pointerover", fields=["county"],
       clear="pointerout", empty=False)
     - strong = alt.selection_point(name="strong", on="click", fields=["county"],
       toggle=False, empty=False)
       - Clicking the same county again, or clicking empty map space, clears it.
       - The click is added only to the map, so only the map sets strong focus.
     - The soft param is added to all three views. Because the field name (county) is
       the same everywhere, hovering a ridge also highlights the map, and the other
       way round.
     - Ridgeline filter, given a scalar for the clicked county:
       - datum.focus == (strong.county ? strong.county[0] : "__all__")
       - This needs to be checked in the browser: the shape of the point-selection
         signal varies by Vega-Lite version. The fallback is vlSelectionTest /
         length(data("strong_store")).

     4. Pane 1: map

     - Layer A: mark_geoshape with fill = estimate.
       - Color scale: scheme="viridis", reverse=True, so dark means higher, matching
         examples/map.png.
       - The domain is shared with both ridgelines.
       - Fill condition: soft selected, or soft empty → color; otherwise lightgray.
       - Stroke condition: strong → black, width 2.5; otherwise a thin dark gray.
       - Projection: albersUsa, or mercator fitted to WA.
     - Layer B: mark_text at the label lon/lat showing format(estimate, ".1%"), made
       visible by opacity only when soft-selected.
     - Tooltip: county and estimate.

     5. Panes 2 and 3: ridgelines (one shared builder function, ridgeline(df, title))

     - Faceted by row=county, sorted by order descending so the highest county is at
       the top, like the screenshot.
     - Each facet is a layered chart:
       - Gradient fill: mark_rect from prev to prev + step, with y from 0 to density
         and color prev on the same viridis scale. This reproduces the left-to-right
         gradient in examples/ridgeline.png.
       - Outline: mark_line in black.
     - Row overlap: spacing=-(overlap) plus y.scale.domain clipped to roughly 60% of
       the max density, with clip=False so the peaks overlap the row above.
     - Opacity condition: soft selected, or soft empty → 1; otherwise 0.25.
     - transform_filter uses the focus expression above. When strong focus is set, the
       facet rows collapse to just the filtered counties.
     - Titles are dynamic where possible: "All counties" or "Bordering <county>", and
       "All counties" or "Nearest by estimate".

     6. Compose and save

     - alt.hconcat(map, middle, right).resolve_scale(color="shared"), with one color
       legend.
     - .save("wa_prevalence.html")
     - Set alt.data_transformers.disable_max_rows().

     Verification

     1. uv run build_viz.py. It should finish and print the neighbor count per county
        as a sanity check, e.g. King has about 5–6 neighbors and San Juan has more
        than 0.
     2. Open wa_prevalence.html and check the interactions, using claude-in-chrome
        screenshots if available:
        - Hover a county on the map: it is highlighted, the other counties go gray,
          the % label appears, and the same ridge is highlighted in both ridgelines.
        - Hover a ridge: the map responds.
        - Click King: King gets a black outline, the middle pane shows King and its
          neighbors, and the right pane shows King ±3 by rank.
        - Click Whitman (the lowest): the right pane shows Whitman plus 3 higher.
        - Click Wahkiakum (the highest): the right pane shows Wahkiakum plus 3 lower.
        - Click King again, or the background: all panes reset.
     3. Visually compare with examples/map.png and examples/ridgeline.png.
