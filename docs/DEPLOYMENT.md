# Streamlit Community Cloud Deployment

PermitPulse is prepared for a public Streamlit Community Cloud deployment but has not been published.

## Runtime bundle

The public application needs only:

- `app.py` and the `src/permitpulse` package;
- `requirements.txt` and `pyproject.toml`;
- `data/processed/analytic_permits.parquet`;
- `data/processed/data_quality_results.parquet`; and
- `data/processed/source_metadata.json`; and
- `data/reference/victoria_lga_simplified.geojson`.

The raw BPC annual workbooks, legacy City of Melbourne build artefacts, DuckDB database, intermediate tables and quarantine records remain ignored. They are build inputs or audit artefacts rather than application runtime requirements.

The processed data comes from public CC BY sources. Even so, review every tracked file before publishing. The generated public metadata records source filenames, checksums and URLs without local computer paths.

## Deployment settings

Use the following Streamlit Community Cloud settings:

| Setting | Value |
|---|---|
| Repository | Public GitHub repository created for PermitPulse |
| Branch | `main` |
| Entrypoint | `app.py` |
| Python | 3.12 |
| Secrets | None required |

## Deployment workflow

1. Run the local verification commands.
2. Review `git status` and confirm that no raw data, credentials, local paths or unrelated files are staged.
3. Create the initial Git commit.
4. Create a public GitHub repository and push the `main` branch.
5. Sign in to [Streamlit Community Cloud](https://share.streamlit.io/), create an app and select the settings above.
6. Verify the hosted default view, municipality and suburb filters, Vicmap hotspot view, year controls, detailed cost ranges, aggregate CSV export, glossary and source panel.
7. Add the verified `streamlit.app` URL to the README, portfolio and LinkedIn material.

## Local verification

```bash
python -m pip install -r requirements.txt
ruff check .
pytest
streamlit run app.py
```

## Data refresh

Refresh and validate the source data locally. Commit only the regenerated runtime files listed above after checking their counts, checksums, metadata and dashboard behaviour. Streamlit Community Cloud redeploys after the GitHub update.

## Hosting limitations

Community Cloud applications can sleep after inactivity and are subject to shared resource limits. PermitPulse is a portfolio prototype and should not be described as a continuously available production service.
