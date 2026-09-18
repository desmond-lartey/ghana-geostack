# Notebooks

Exploratory work lives here. Anything that becomes a repeatable step should
move into `pipelines/` or `db/analysis/` — a notebook is a place to figure
something out, not a place to keep it.

Register the kernel after creating the environment:

```bash
python -m ipykernel install --user --name ghana-geostack --display-name "Ghana GeoStack"
```

Strip outputs before committing. `nbstripout --install` does it automatically.
