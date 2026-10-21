# PermitPulse Victoria dashboard user guide

[Open the public dashboard](https://permitpulse-melbourne-victoria.streamlit.app/)

## Purpose

PermitPulse Victoria helps users explore issued building-permit activity reported to Victoria's Building and Plumbing Commission (BPC). It is intended for market scanning, local-area comparison and early-stage business analysis.

The dashboard can help users understand where reported activity is concentrated, how the mix of work differs between locations, how reported project values are distributed and how selected indicators change over time. It does not identify individual sales leads or predict construction outcomes.

## Before you start

Three interpretation rules apply throughout the dashboard:

1. A **permit record** is one source row, not a proven unique permit. The public files have no permit identifier.
2. Time charts use the **BPC levy reporting period**, which can differ from the permit issue date due to delayed reporting or corrections.
3. **Reported cost** is an estimate. It is not realised expenditure, contract value, revenue or an inflation-adjusted market measure.

All sidebar filters apply to the headline metrics, map, profiles, charts, cost analysis and download. Start broadly, then narrow the data one question at a time.

## 1. Sidebar filters

### Business questions

- Which period, region or local market do I want to investigate?
- Am I interested in a particular project size, activity or building use?
- How does one municipality or suburb differ from the broader market?

### How to use the filters

| Filter | How to use it | Example question |
|---|---|---|
| BPC reporting period | Choose the start and end dates included in the analysis. | What activity was reported during 2024 and 2025? |
| Regions | Select one or more BPC regions. This also narrows the municipality list. | How does activity in a selected regional market compare with the statewide view? |
| Municipalities | Select one for a focused profile or several for a narrower comparison. | What is the activity and project mix in Greater Geelong? |
| Suburbs | Select suburbs available within the chosen region or municipality. | Which activities are most common in a selected suburb? |
| Reported-cost bands | Restrict the analysis to broad estimated-cost ranges. | Where are projects above $1 million being reported? |
| Nature of work | Select official categories such as new building, alteration or demolition. | Which areas have the most demolition activity? |
| Building use | Restrict the analysis to a reported building-use category. | Where is a selected building-use segment concentrated? |
| Search location or category | Search municipality, suburb, nature of work and building use using plain text. | Show records containing “Geelong” or “demolition”. |

If the dashboard reports that no records match, clear one filter at a time or broaden the reporting period. Avoid changing several filters at once when investigating an unexpected result; otherwise it is difficult to identify which condition removed the records.

## 2. Headline metrics

The top row summarises the currently filtered population.

### Business questions

- How large is the selected market in record volume and reported value?
- What does a typical positive-cost record look like?
- How geographically broad is the selected result?
- How many new dwellings are reported where the field is available?

### How to interpret the metrics

- **Permit records:** activity volume after applying the filters. Do not call this a unique-permit count.
- **Total reported cost:** the sum of reported estimated cost. Compare it with permit volume because individual large projects can dominate the total.
- **Median positive cost:** the middle positive reported cost. Use it to describe typical project scale without allowing a few very large records to dominate.
- **Municipalities:** number of municipality labels represented by the filtered records.
- **New dwellings:** sum of the comparable source field where available. The tooltip reports field coverage; 2018–2019 are unavailable.

A useful first check is to compare permit records, total cost and median cost together. Rising total cost with little change in volume can indicate a shift towards higher-value reported work, but the dashboard does not establish the cause.

## 3. Statewide permit hotspots map

### Business questions

- Where is permit activity concentrated?
- Which municipalities account for the greatest reported project value?
- Where are new dwellings concentrated in the available source data?

### How to use the view

Choose one map measure:

- **Permit records** for activity volume;
- **Reported cost** for estimated project-value concentration; or
- **New dwellings** for reported dwelling activity from 2020 onward.

Darker municipalities have higher values within the current filtered population. Hover over a municipality to view its figures. Use the region, cost, work-type and building-use filters to test whether the hotspot remains when the market segment changes.

The map is aggregated to official municipality boundaries. It is not an address heat map because the public statewide source does not provide point coordinates. A large municipality shaded strongly does not show where activity occurs within that municipality.

## 4. Municipality business profile

### Business questions

- Which municipalities have the greatest activity, value or dwelling impact?
- Has a municipality's permit-record volume increased or decreased between selected years?
- What types of work and building use define a selected municipality?
- Is activity dominated by projects above $10 million?

### How to use the view

Choose a **profile year** and a different **profile baseline**.

- With no municipality or several municipalities selected, the dashboard shows a comparison table for the leading municipalities in the filtered data.
- With exactly one municipality selected, it changes to a focused profile showing permit records, year comparison, total and median reported cost, new dwellings and the share of records above $10 million.
- The focused profile also shows the municipality's nature-of-work and building-use mix.

Use record change together with absolute volume. A large percentage increase from a small baseline may still represent limited market activity. The high-value threshold is an analytical segment, not an official BPC classification.

## 5. Monthly activity trend

### Business questions

- Is reported activity rising, falling or unusually volatile over the selected period?
- Do changes in reported cost move with permit-record volume?
- Are there months that warrant deeper investigation?

### How to use the view

Switch the trend measure between **Permit records** and **Reported cost**. Hover over the line to compare monthly values. Apply a municipality, activity or cost filter to see whether the pattern is statewide or associated with a particular segment.

Treat spikes as investigation prompts rather than conclusions. A reported-cost spike may be driven by a small number of large projects, and the reporting month does not necessarily represent the construction start month.

## 6. Location and activity mix charts

This row contains three views: top suburbs, official nature of work and building use.

### Business questions

- Which suburbs account for the greatest filtered permit-record volume?
- Is the selected market driven by new buildings, alterations, demolitions or another activity?
- Which building-use categories are most represented?

### How to use the views

Start with a region or municipality filter, then use the charts to identify the dominant suburbs and activities within that market. Add a nature-of-work or building-use filter to isolate a segment and observe how the location ranking changes.

The top-suburb chart shows only the leading 12 suburbs. The building-use field is unavailable in the 2018 workbook, so comparisons involving 2018 must retain that limitation.

## 7. Reported-cost analysis

### Business questions

- Is the selected market dominated by small, medium or high-value reported work?
- Which cost ranges gained or lost activity between two years?
- Did record volume and total reported value move in the same direction?
- Is an apparent market change broad-based or concentrated in a few value bands?

### How to use the view

1. Choose **Broad ranges** for a quick market overview or **Detailed ranges** for a narrower project-value breakdown.
2. Choose **Permit records** to compare activity volume or **Total reported cost** to compare estimated value.
3. Select a **focus year** and a different **baseline year**.
4. Compare the grouped bars, then use the table for exact record and cost changes.

If the sidebar reporting period includes only one year, this section displays a distribution rather than a year comparison.

Use both comparison measures before drawing a conclusion. For example, permit records may rise while total cost falls, indicating more reported activity but a lower-value mix. Conversely, total cost may rise while volume falls because a small number of large projects dominate the result. Cost bands are analytical groupings rather than official project classifications, and values are not inflation-adjusted.

## 8. Download aggregated results

### Business questions

- Can I perform further analysis or prepare a stakeholder briefing outside the dashboard?
- Can I retain the current municipality comparison as evidence for a report?

### How to use the feature

After setting the sidebar filters and profile years, select **Download municipality summary**. The CSV contains the current municipality-level aggregation rather than raw street-level source records.

Before using the file, record the filters, focus year and baseline year used to create it. The download is suitable for further spreadsheet or SQL analysis, but it does not remove the source limitations described in this guide.

## 9. Metric definitions and source quality

Open **Metric definitions and responsible use** when a term or formula is unclear. It explains the calculation and cautions for permit records, reported cost, medians, record change, new dwellings, hotspots and cost bands.

Open **Source and data quality** to review the publisher, licence, snapshot date, reporting years, record coverage and validation findings. Consult this section before presenting a result to a stakeholder. It makes missing fields, date differences, duplicate-looking rows and source-reconciliation checks visible.

The source panel links to the official DataVic dataset and BPC publisher page. The dashboard is
refreshed manually after a new annual BPC workbook is released and validated; the snapshot analysis
date shows when the current bundle was prepared.

## 10. Ask PermitPulse dashboard guide

### Business questions

- Which view should I use for a particular analysis?
- What does a dashboard term or calculation mean?
- What do the active sidebar filters currently contain?
- Can this dataset support the question I want to answer?

### How to use the assistant

Select **💬 Ask PermitPulse** at the top of the sidebar to open the assistant in a dialog from anywhere
in the dashboard. Select a suggested question or type a question of up to 500 characters. The
assistant uses the active sidebar filters and aggregate results. Changing a sidebar filter clears the
conversation so older answers are not confused with the new scope. On a narrow screen, open the
collapsed sidebar first to access the assistant button.

When a Groq API key is configured, up to five questions per browser session can receive
natural-language explanations from `openai/gpt-oss-20b`. Without a key, after the session limit, or
when Groq is unavailable, the built-in guide answers supported questions without an external API.

The assistant receives aggregate summaries only. It does not receive the complete dataset, source
record identifiers or raw permit rows. Do not enter personal, confidential or commercially sensitive
information. Treat AI wording as an explanation aid and confirm numerical claims against the
dashboard views.

The assistant will refuse questions outside the dataset's evidence, including refusal risk,
forecasts, realised construction costs, builder performance, property prices and exact-address
hotspots.

## Suggested analysis workflows

### Find an active local market

1. Select a recent reporting period.
2. View the hotspot map using permit records.
3. Select a region, then review the municipality table.
4. Select one municipality to inspect its median cost, dwelling activity and work mix.
5. Use the monthly trend to check whether activity is sustained or concentrated in a short period.

### Investigate a change in project value mix

1. Select the relevant region or municipality.
2. Open reported-cost analysis and choose detailed ranges.
3. Select the focus and baseline years.
4. Compare permit records first, then total reported cost.
5. Identify whether the change is broad-based or limited to one cost range.

### Explore reported dwelling activity

1. Restrict the period to 2020 onward.
2. Select new dwellings as the map measure.
3. Identify a municipality with higher reported dwelling activity.
4. Select that municipality and review its profile and activity mix.
5. Treat the result as planned activity in permit records, not completed housing supply.

## Questions this dashboard cannot answer

PermitPulse does not contain refused or not-granted applications, so it cannot calculate approval probability or refusal risk. It cannot establish unique permit counts, exact address hotspots, construction starts or completions, realised expenditure, cost overruns, builder performance, project profitability, property prices or future demand. Answering those questions requires additional authoritative datasets and a separate analytical design.
