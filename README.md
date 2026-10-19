# Pacifica PHEV website 

## Tank update

1. Add a row to `tanks.csv`, preserving the existing column names and sequence of tank numbers.
2. Enter raw electric miles, gas miles, gasoline gallons, home/public kWh, and gas/home/public costs. **Do not enter totals or percentages.**
3. Enter the Twin Cities GasBuddy average price per gallon in `gasbuddy_avg_price`. For the six historical tanks, the `benchmark_cost_override` preserves the published 2018 comparison because the original unrounded GasBuddy averages are not available in this HTML. For future tanks, leave the override blank.
4. Optionally add a row to `narratives.csv` with a tank result comment and tank context. If the comment is blank, a numeric summary is generated.
5. Commit the CSV changes. The included GitHub Actions workflow regenerates `index.html` automatically. The workflow requires repository Actions write permission.

The build automatically calculates tank totals, electric percentages, cost per mile, 2018 benchmark cost (tank miles ÷ 22 MPG × GasBuddy price), savings, cumulative statistics, navigation, tank cards, and both chart lines. The chart widens for additional tanks and scrolls on mobile.

## Run locally

```bash
python -m pip install beautifulsoup4
python build_phev.py
```

`template.html` is the existing Tank 6 design. Do not replace it with the generated `index.html`; the builder uses it as the fixed layout reference. The first six tank narratives are intentionally preserved verbatim. A future rate change or methodology revision should be made deliberately in `template.html`.

**Important:** The GasBuddy price is the period-specific benchmark *you provide*; the script does not scrape GasBuddy. Existing benchmark overrides are historical display values, not newly verified gas prices. Published figures are rounded for display. The build stops if required numeric fields are absent or invalid.
