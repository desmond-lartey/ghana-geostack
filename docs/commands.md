# Command reference

Every control on the ribbon runs one command by id, and this is the list.
It is generated from the registry in `web/index.html` by
`python scripts/commands_doc.py`, so it cannot drift from what the
interface actually does.

**401 commands. 85 are built. 316 are open.**

An open slot is not a bug. The ribbon, the registry and the place each
command plugs into are finished; the function behind it is the work, and
it is deliberately left for the people who will use this platform. Each
one is a small, self-contained job: add a `run` to its entry in the
`COMMANDS` registry and the button, its icon, its tooltip and its place
on the tab are already there.

In the interface, an open slot carries a gold dot and pressing it says
what it is for and what it is called. **Ctrl K** searches every command
by name.

---

## Home

### Ghana Data

| Command | Does | Status |
| --- | --- | --- |
| `data.ghanaLibrary` | Every layer there is for Ghana, as cards: what it is, where it came  | Built |
| `data.ghanaAdmin` | Regions, districts, capitals and census geography. | Built |
| `data.ghanaPopulation` | The 100 m population grid, built-up surface, and the 2021 census. | Built |
| `data.ghanaHealth` | Facilities, and how long it takes to reach one. | Built |
| `data.ghanaEducation` | Schools, and the children beyond reach of one. | Built |
| `data.ghanaWater` | Water points, the Volta system, and 37 years of observed surface water. | Built |
| `data.ghanaTransport` | Roads, buildings, markets, and travel time to each. | Built |
| `data.ghanaAgriculture` | Land cover, tree cover and the cocoa belt, vegetation through the season. | Built |
| `data.ghanaClimate` | CHIRPS rainfall, land surface temperature, departure from the normal. | Built |
| `data.ghanaHazard` | Observed flooding, population exposed to it, fire detections and burned area. | Built |
| `data.ghanaEnergy` | Night lights, and electrification read from them. | Built |

### Navigate

| Command | Does | Status |
| --- | --- | --- |
| `map.pan` | Pan with the mouse, zoom with the wheel, click a feature for its attributes. | Built |
| `map.bookmarkList` | Go to a saved extent. | Built |
| `map.zoomIn` | Move one zoom level closer. | Built |
| `map.zoomOut` | Move one zoom level further out. | Built |
| `map.fullExtent` | Back to the whole of Ghana. | Built |
| `map.previous` | The view before this one. | Built |
| `map.next` | Forward again. | Built |
| `map.north` | Put north back at the top. | Built |
| `map.goToXY` | Jump to a coordinate. | Built |
| `map.bookmarkNew` | Save this extent under a name. | Built |

### Add Data

| Command | Does | Status |
| --- | --- | --- |
| `data.eeSearch` | Search the Earth Engine catalogue and draw any of it over Ghana. | Built |
| `data.liveHealth` | Hospitals, clinics and pharmacies, live from OpenStreetMap. | Built |
| `data.liveEducation` | Schools and colleges, live from OpenStreetMap. | Built |
| `data.liveWater` | Boreholes, wells and taps, live from OpenStreetMap. | Built |
| `data.liveMarket` | Markets and shops, live from OpenStreetMap. | Built |
| `data.liveRoad` | The road network, live from OpenStreetMap. | Built |
| `data.liveBuilding` | Building footprints, live from OpenStreetMap. | Built |
| `data.addFile` | Open a GeoJSON, CSV, GPX, KML or zipped Shapefile from this computer, or drop one on the map. | Built |
| `data.addUrl` | Fetch a GeoJSON or CSV from an address. | Built |
| `data.addWms` | Add a tile service. OGC WMS is not read yet; an XYZ template works today, under Basemap. | Built |
| `layer.addSample` | Add one of the bundled sample layers to the map. | Built |
| `ui.addDelimited` | Delimited Text…. | **Open** |
| `graphics.newLayer` | Graphics Layer. | **Open** |

### Selection

| Command | Does | Status |
| --- | --- | --- |
| `select.clip` | Confine every tool, fetch and summary to one boundary. | Built |
| `select.byRectangle` | Drag a rectangle to select features. | **Open** |
| `select.byAttributes` | Select with an expression. | **Open** |
| `select.byLocation` | Select features by where they are relative to another layer. | **Open** |
| `select.clear` | Drop the selection. | **Open** |
| `select.zoomTo` | Fit the map to what is selected. | **Open** |
| `select.selectByAttributes` | Select features with a SQL expression. | **Open** |
| `select.selectByLocation` | Select features that intersect another layer. | **Open** |
| `table.attributes` | Open the attribute table of the selected layer. | Built |

### Inspect

| Command | Does | Status |
| --- | --- | --- |
| `map.identify` | Click a feature to read its attributes. | Built |
| `map.measure` | Distance and area on the map. | Built |
| `layer.table` | The selected layer's rows. | Built |
| `ui.query` | Query the data directly. | Built |
| `tool.zoomBox` | Drag a box to zoom into. | **Open** |
| `ui.pane.infographics` | Counts, totals and top categories of what's in view. | **Open** |

## Data

### Catalogue

| Command | Does | Status |
| --- | --- | --- |
| `data.eeSearch` | Search the Earth Engine catalogue and draw any of it over Ghana. | Built |
| `data.catalogue` | The curated datasets this platform publishes. | **Open** |
| `data.refresh` | Re-read the catalogue index. | **Open** |
| `data.sources` | Where each layer came from and what you may do with it. | **Open** |
| `data.rasterInformation` | Size, bands, statistics and coordinate system. | **Open** |

### Connect

| Command | Does | Status |
| --- | --- | --- |
| `data.connectPostgis` | Connect to a PostGIS database. | **Open** |
| `data.connectDuckdb` | Open a DuckDB file or a remote Parquet. | **Open** |
| `data.connectS3` | Open a cloud-native dataset by its address. | **Open** |
| `data.connectStac` | Search a SpatioTemporal Asset Catalog. | **Open** |

### Table

| Command | Does | Status |
| --- | --- | --- |
| `table.open` | The selected layer's attributes, in a table under the map. | Built |
| `table.addField` | A new column. | **Open** |
| `table.calculate` | Fill a column from an expression. | **Open** |
| `table.statistics` | Count, sum, mean and range for a column. | **Open** |
| `table.join` | Attach another table by a shared key. | **Open** |

### Definition Query

| Command | Does | Status |
| --- | --- | --- |
| `data.definitionQuery` | Show only the rows that match an expression. | **Open** |
| `data.clearQuery` | Show everything again. | **Open** |

### Export

| Command | Does | Status |
| --- | --- | --- |
| `data.downloadGeoJSON` | Download the drawn layer. | Built |
| `data.downloadCSV` | Download the query result. | Built |
| `data.exportGpkg` | Export as OGC GeoPackage. | **Open** |
| `data.exportParquet` | Export as GeoParquet. | **Open** |
| `data.exportShapefile` | Export as an ESRI Shapefile. | **Open** |
| `ui.exportRaster` | Save the raster as a GeoTIFF. | **Open** |
| `data.exportFeatures` | Export Features…. | **Open** |
| `data.exportFeaturesTool` | Export Features (tool). | **Open** |

### Offline

| Command | Does | Status |
| --- | --- | --- |
| `offline.download` | Cache the current extent for use without a network. | **Open** |
| `offline.sync` | Send local edits back and pull changes down. | **Open** |
| `offline.clear` | Free what has been cached. | **Open** |

### Feature Cache

| Command | Does | Status |
| --- | --- | --- |
| `cache.fill` | Prepare every layer's geometry for this projection. | **Open** |
| `cache.empty` | Free the prepared geometry. | **Open** |
| `cache.cancel` | Stop filling the cache. | **Open** |
| `cache.auto` | Fill the cache whenever the projection changes. | **Open** |

### Project

| Command | Does | Status |
| --- | --- | --- |
| `map.new` | Add a new map to the project. | **Open** |
| `data.toolbox` | Browse the geoprocessing toolbox. | **Open** |
| `ui.open` | Open a RustGIS project. | **Open** |
| `layout.new` | Add a page layout for printing and exporting the map. | **Open** |
| `ui.importLayout` | Import Layout…. | **Open** |
| `data.browser` | Browse the project's maps, tables and folders. | **Open** |
| `ui.addFolder` | Connect a folder to the Browser. | **Open** |
| `data.import` | Add the maps of a map file, map package, project or project package. | **Open** |
| `data.newCustomTemplate` | New Custom Template…. | **Open** |
| `data.openCustomTemplate` | Open Custom Template…. | **Open** |
| `task.task` | Tasks: guided steps that each run a command. | **Open** |
| `task.newTaskFromHistory` | New Task From History. | **Open** |
| `data.importTask` | Import Task…. | **Open** |
| `layer.layerTemplates` | Add an empty layer with a ready-made schema, to draw into. | **Open** |
| `layer.layerTemplate` | Start a layer from a saved template. | **Open** |

### Selection

| Command | Does | Status |
| --- | --- | --- |
| `select.all` | Select every feature. | **Open** |
| `select.switch` | Invert the selection. | **Open** |
| `select.layerFromSelection` | Make a new layer of the selected features. | **Open** |

### Data Design

| Command | Does | Status |
| --- | --- | --- |
| `data.fields` | Add a field. | **Open** |
| `data.calculate` | Calculate field values. | **Open** |
| `data.subtypes` | Group features by an integer code, each with default values. | **Open** |
| `data.domains` | Limit a field to coded values or a range. | **Open** |
| `data.attributeRules` | Calculate fields and enforce conditions on every edit. | **Open** |
| `data.contingentValues` | Allow only certain combinations of values across fields. | **Open** |

### Archiving

| Command | Does | Status |
| --- | --- | --- |
| `data.archive` | Keep a history of every edit to the layer, to look back or restore. | **Open** |

### Relationship

| Command | Does | Status |
| --- | --- | --- |
| `data.relatedData` | Select the rows related to the selection. | **Open** |
| `data.dataRelated` | Open the tables related to this one. | **Open** |
| `data.newRelationship` | New Relationship…. | **Open** |

## Style

### Layer

| Command | Does | Status |
| --- | --- | --- |
| `style.symbology` | Single colour, graduated classes, or categories. | Built |
| `style.graduated` | Classes across a numeric column. | Built |
| `style.single` | One colour for the whole layer. | Built |
| `style.opacity` | How much of what is underneath shows through. | Built |
| `style.categorised` | A colour per distinct value. | **Open** |
| `layer.zoomTo` | Zoom to the layer's extent. | **Open** |
| `layer.visibility` | Show or hide the layer. | **Open** |
| `layer.remove` | Remove the layer from the map. | **Open** |
| `layer.symbology` | Choose how the layer is drawn. | **Open** |

### Classification

| Command | Does | Status |
| --- | --- | --- |
| `style.quantile` | The same number of features in each class. | Built |
| `style.equalInterval` | The range cut into equal widths. | Built |
| `style.palette` | Which colours the classes use. | Built |
| `style.naturalBreaks` | Jenks: breaks where the data has gaps. | **Open** |
| `style.classCount` | How many classes to cut the data into. | **Open** |

### Labels

| Command | Does | Status |
| --- | --- | --- |
| `labels.enable` | Draw a column as text on the map. | **Open** |
| `labels.field` | Which column to draw. | **Open** |
| `labels.placement` | Where the text sits relative to the feature. | **Open** |
| `labels.halo` | An outline so text reads over any basemap. | **Open** |
| `labels.scaleRange` | The zoom levels the labels appear at. | **Open** |
| `labels.lock` | Keep the labelled features fixed as the map moves. | **Open** |
| `labels.pause` | Stop drawing labels, for faster navigation. | **Open** |
| `labels.viewUnplaced` | Show the labels that don't fit, in red. | **Open** |
| `labels.convert` | Convert the selected layer's labels into an annotation layer. | **Open** |
| `labels.bold` | Bold label text. | **Open** |

### Effects

| Command | Does | Status |
| --- | --- | --- |
| `style.extrude` | Raise the shapes by a column, in 3D. | Built |
| `style.visibilityRange` | The zoom levels this layer draws at. | **Open** |
| `style.blend` | How this layer mixes with the ones below. | **Open** |
| `style.swipe` | Drag a line across the map to compare two layers. | **Open** |
| `layer.displayFilters` | Show different features at different scales. | **Open** |
| `layer.aggregation` | Draw points as bins coloured by how many fall in each. | **Open** |
| `layer.scaleRange` | Draw the layer at every scale. | **Open** |

### Raster

| Command | Does | Status |
| --- | --- | --- |
| `raster.stretch` | How pixel values map to the colour ramp. | **Open** |
| `raster.bands` | Which bands go to red, green and blue. | **Open** |
| `raster.resampling` | Nearest, bilinear or cubic. | **Open** |
| `raster.hillshade` | Shade the terrain by a light angle. | **Open** |
| `raster.symbology` | Choose how the raster is drawn. | **Open** |
| `raster.dra` | Dynamic range adjustment: stretch using the pixels in view. | **Open** |
| `layer.blend` | How the layer's colours combine with what's beneath. | **Open** |
| `raster.enhance` | Reset brightness, contrast and gamma. | **Open** |

### Styles

| Command | Does | Status |
| --- | --- | --- |
| `style.styles` | Saved symbology: apply it to the selected layer, or save the layer's. | **Open** |
| `style.new` | New Style From Layer. | **Open** |
| `style.addStyleFile` | Add Style File…. | **Open** |
| `style.importStylesFrom` | Import Styles From…. | **Open** |

### Extrusion

| Command | Does | Status |
| --- | --- | --- |
| `layer.extrusion` | Raise polygons by a height or a field. | **Open** |

### Faces

| Command | Does | Status |
| --- | --- | --- |
| `layer.faceCulling` | Hide walls facing away from you. | **Open** |
| `layer.lighting` | Shade walls by the way they face the light. | **Open** |

### Light and Shadow

| Command | Does | Status |
| --- | --- | --- |
| `layer.enableLighting` | Light the extruded shapes from the north-west. | **Open** |
| `layer.castShadow` | Extruded shapes cast shadows on the map. | **Open** |

## Edit

### Manage Edits

| Command | Does | Status |
| --- | --- | --- |
| `edit.enable` | Turn editing on for the map. | **Open** |
| `edit.save` | Commit what has changed. | **Open** |
| `edit.discard` | Throw away what has changed. | **Open** |
| `edit.undo` | Step back. | **Open** |
| `edit.redo` | Step forward again. | **Open** |
| `ui.save` | Save the project with your edits. | **Open** |
| `edit.status` | Edits since the project was saved. | **Open** |
| `edit.settings` | Editing settings. | **Open** |
| `edit.topology` | Topology rules and the errors they find. | **Open** |
| `edit.topologyOptions` | Topology Options…. | **Open** |

### Features

| Command | Does | Status |
| --- | --- | --- |
| `edit.create` | Draw a new feature. | **Open** |
| `edit.modify` | Move a vertex or a whole feature. | **Open** |
| `edit.delete` | Remove the selected features. | **Open** |
| `edit.split` | Cut a feature in two. | **Open** |
| `edit.merge` | Join the selected features into one. | **Open** |
| `edit.createFeatures` | Draw new features in the selected layer. Double-click to finish lines and polygons. | **Open** |
| `edit.groundToGrid` | Scale and rotate entered distances and directions to the grid. | **Open** |

### Draw

| Command | Does | Status |
| --- | --- | --- |
| `edit.drawPolygon` | Draw an area - also usable as a clip boundary. | **Open** |
| `edit.drawLine` | Draw a line. | **Open** |
| `edit.drawPoint` | Place a point. | **Open** |
| `edit.drawText` | Place a label on the map. | **Open** |

### Snapping

| Command | Does | Status |
| --- | --- | --- |
| `edit.snapping` | Snap new geometry to what is already there. | **Open** |
| `edit.snapVertex` | Snap to existing vertices. | **Open** |
| `edit.snapEdge` | Snap to existing edges. | **Open** |

### Clipboard

| Command | Does | Status |
| --- | --- | --- |
| `edit.copy` | Copy the selected features. | **Open** |
| `edit.paste` | Paste features into the selected layer. | **Open** |
| `edit.cut` | Copy the selection and delete it. | **Open** |
| `edit.pasteSpecial` | Paste Special (as a new layer). | **Open** |
| `ui.copyPath` | Copy the selected layer's data source path. | **Open** |

### Tools

| Command | Does | Status |
| --- | --- | --- |
| `edit.moveRotateScale` | Move, Rotate, Scale…. | **Open** |

### Elevation

| Command | Does | Status |
| --- | --- | --- |
| `edit.elevation` | Where new features get their elevation - the z field. | **Open** |
| `edit.constant` | Constant…. | **Open** |

## Analyze

### Geoprocessing

| Command | Does | Status |
| --- | --- | --- |
| `gp.toolbox` | Every tool, searchable, with its parameters. | Built |
| `gp.clip` | Keep only what falls inside a boundary. | Built |
| `gp.buffer` | A zone of the given radius around each feature. | Built |
| `gp.dissolve` | Merge every feature into one. | Built |
| `gp.overlay` | Clip, dissolve and the rest. | Built |
| `gp.history` | What has been run in this session. | **Open** |
| `gp.tools` | Find and run geoprocessing tools. | **Open** |
| `gp.modelBuilder` | Chain tools into a model; build one from your history. | **Open** |
| `ui.pane.script` | Run commands from text, one per line. | **Open** |
| `gp.environments` | Limit where tools work, and the cell size of new rasters. | **Open** |
| `gp.readyToUse` | Everyday tools. | **Open** |

### Vector

| Command | Does | Status |
| --- | --- | --- |
| `gp.centroid` | One point per feature, at its centre of mass. | Built |
| `gp.convex` | The tightest convex polygon around the input. | Built |
| `gp.envelope` | One rectangle around the whole input. | Built |
| `gp.simplify` | Remove vertices while keeping the shape. | Built |
| `gp.voronoi` | The area closest to each input point. | Built |
| `gp.nearest` | How far each feature is from the closest of another layer. | Built |

### Raster

| Command | Does | Status |
| --- | --- | --- |
| `ee.summarise` | Reduce a raster onto regions or districts, as a queryable table. | Built |
| `ee.classAreas` | Square kilometres of each class per zone. | Built |
| `gp.elevation` | The height at a point. | Built |
| `raster.calculator` | An expression across bands. | **Open** |
| `raster.reclassify` | Map pixel values onto new ones. | **Open** |
| `gp.rasterFunctions` | Slope, aspect, hillshade, NDVI, band math, thresholds. | **Open** |
| `gp.functionEditor` | Chain raster functions. | **Open** |

### Statistics

| Command | Does | Status |
| --- | --- | --- |
| `gp.sql` | Run SQL against everything loaded, in the browser. | Built |
| `stats.summary` | Count, sum, mean and range by group. | **Open** |
| `stats.hotspot` | Clusters, after the hotspots notebook: DBSCAN and Shannon entropy. | **Open** |
| `stats.correlation` | How two columns move together. | **Open** |

### Assistant

| Command | Does | Status |
| --- | --- | --- |
| `ui.assistant` | Ask in plain English; it drives the map and the data. | Built |
| `ai.explainLayer` | What the selected layer holds and where it came from. | **Open** |
| `ai.suggest` | What this data could answer. | **Open** |

### Notebook

| Command | Does | Status |
| --- | --- | --- |
| `ui.newNotebook` | A notebook of text and command cells. | **Open** |
| `notebook.addAndOpen` | Open a RustGIS or Jupyter notebook. | **Open** |
| `ui.pane.notebook` | Edit and run the notebook. | **Open** |

### Portal

| Command | Does | Status |
| --- | --- | --- |
| `gp.uiPaneWorkflows` | Open the workflow pane. | **Open** |

### Workflows

| Command | Does | Status |
| --- | --- | --- |
| `task.workflows` | Guided analysis: suitability, visibility, networks, interpolation and more. | **Open** |
| `task.uiPaneWorkflows` | Step through a saved workflow. | **Open** |

### Ortho Mapping

| Command | Does | Status |
| --- | --- | --- |
| `gp.newWorkspace` | Mosaic the visible rasters into an orthomosaic. | **Open** |
| `gp.options` | Workspace cell size and blending. | **Open** |

### Alignment

| Command | Does | Status |
| --- | --- | --- |
| `gp.georeference` | Place a raster on the map from control points or the view. | **Open** |

### Image Analysis

| Command | Does | Status |
| --- | --- | --- |
| `gp.changeDetection` | Difference, ratio or percent change between two rasters. | **Open** |
| `gp.spectralAnalysis` | Every band's value at a pixel. | **Open** |
| `gp.process` | Clip a raster to the view, or resample it. | **Open** |
| `gp.indices` | NDVI, NDWI, SAVI, NBR, NDBI, EVI. | **Open** |
| `gp.pixelEditor` | Set the pixels inside a polygon. | **Open** |

### Image Classification

| Command | Does | Status |
| --- | --- | --- |
| `gp.classificationWizard` | Unsupervised classes (k-means). | **Open** |
| `gp.classificationTools` | Classes from training polygons. | **Open** |
| `gp.deepLearningTools` | Train a neural network on training polygons and classify every pixel. | **Open** |

### Imagery Sharing

| Command | Does | Status |
| --- | --- | --- |
| `gp.createHostedImagery` | Cut a raster into web map tiles (XYZ PNG) with a viewer page. | **Open** |

### Mensuration

| Command | Does | Status |
| --- | --- | --- |
| `gp.mensuration` | Distances along the surface, heights, areas and volumes. | **Open** |
| `gp.results` | Measurements so far. | **Open** |

## View

### Panels

| Command | Does | Status |
| --- | --- | --- |
| `ui.layers` | The layer stack. | Built |
| `ui.style` | Symbology for the selected layer. | Built |
| `ui.catalogue` | The Earth observation catalogue. | Built |
| `ui.query` | Query the data directly. | Built |
| `ui.assistant` | Ask in plain English; it drives the map and the data. | Built |
| `ui.log` | Everything this session has done. | Built |

### Map

| Command | Does | Status |
| --- | --- | --- |
| `map.basemap` | Which backdrop the data sits on. | Built |
| `map.projection` | Switch between the globe and web mercator. | Built |
| `map.terrain` | 3D terrain and hillshade. | Built |
| `map.theme` | Switch the interface theme. | Built |
| `map.locate` | Centre on this device's position. | Built |
| `map.fullscreen` | Give the map the whole display. | Built |

### Display

| Command | Does | Status |
| --- | --- | --- |
| `view.grid` | Latitude and longitude lines. | **Open** |
| `view.scalebar` | Show or hide the scale. | **Open** |
| `view.northArrow` | Show or hide the compass on the map. | **Open** |
| `view.legend` | Show or hide the legend card. | **Open** |
| `ui.theme` | Switch between light and dark themes. | **Open** |
| `map.globe` | Show the map as a 3D globe, or as a flat map again. | **Open** |
| `map.global` | A globe scene. | **Open** |
| `map.local` | A flat scene centred on the view (azimuthal equidistant). | **Open** |
| `ui.pane.profile` | Elevation profiles along lines, cross sections and more. | **Open** |

### Windows

| Command | Does | Status |
| --- | --- | --- |
| `ui.commands` | Find any command by name. | Built |
| `ui.splitView` | Two map frames side by side. | **Open** |
| `ui.sync` | Pan and zoom the frames together. | **Open** |
| `view.browserPane` | Show or hide the Browser pane. | **Open** |
| `view.toolsPane` | Show or hide the Tools pane. | **Open** |
| `view.details` | Details of the selected layer. | **Open** |

### Effects

| Command | Does | Status |
| --- | --- | --- |
| `map.illumination` | Day and night shading for a time. | **Open** |
| `map.weather` | Haze, fog, rain or snow over the map. | **Open** |
| `map.visualEffect` | Vignette and edge outlines. | **Open** |
| `map.cameraEffect` | Tilt-shift blur and film grain. | **Open** |
| `map.postprocessing` | Brightness, contrast, saturation and sepia for the whole map. | **Open** |
| `map.colorVision` | See the map as people with colour vision deficiencies do. | **Open** |

### Scene

| Command | Does | Status |
| --- | --- | --- |
| `map.drawingMode` | Draw polygons as outlines only. | **Open** |
| `layer.raisePriority` | Draw the selected layer above others. | **Open** |
| `layer.lowerPriority` | Draw the selected layer below others. | **Open** |
| `map.clipping` | Hide features far from the view's centre. | **Open** |
| `map.displayType` | Faster drawing: no antialiasing. | **Open** |

### Navigation

| Command | Does | Status |
| --- | --- | --- |
| `map.zoomWorld` | Zoom to the whole world. | **Open** |
| `map.navigator` | On-screen compass, zoom slider and pan pad. | **Open** |
| `view.camera` | See and set the camera's position and scale. | **Open** |
| `ui.magnifier` | A magnifying lens that follows the pointer. | **Open** |

### Link

| Command | Does | Status |
| --- | --- | --- |
| `ui.linkCursors` | Show the pointer's place on the other map. | **Open** |

### Workspace

| Command | Does | Status |
| --- | --- | --- |
| `ui.catalogView` | The project's items in place of the map. | **Open** |
| `ui.pane.tasks` | Step through a task. | **Open** |
| `ui.pane.jobs` | Track jobs and their status. | **Open** |
| `ui.paneSet` | Save the panes you have open, and switch back to them. | **Open** |
| `ui.itemPopups` | Show details when hovering items in the Browser view. | **Open** |

### Animation

| Command | Does | Status |
| --- | --- | --- |
| `animation.add` | Add a keyframe at the current view. | **Open** |
| `animation.remove` | Remove the last keyframe. | **Open** |
| `ui.animationPlay` | Play the animation. | **Open** |
| `ui.exportAnimation` | Export the animation as PNG frames (zip). | **Open** |

## Publish

### Map Image

| Command | Does | Status |
| --- | --- | --- |
| `layout.export` | A print layout: frame, title, north arrow, scale bar, legend and credits. | Built |
| `layout.page` | Size, orientation and margins. | **Open** |
| `layout.title` | What the map is called. | **Open** |
| `layout.elements` | Which of the legend, scale and arrow to draw. | **Open** |

### Export Data

| Command | Does | Status |
| --- | --- | --- |
| `data.downloadGeoJSON` | Download the drawn layer. | Built |
| `data.downloadCSV` | Download the query result. | Built |
| `publish.pdf` | The layout as a PDF. | **Open** |
| `publish.geotiff` | The current view as a georeferenced raster. | **Open** |
| `ui.exportMap` | Export the map view as a PNG image (with labels and a scale bar). | **Open** |
| `publish.exportFeatures` | Export the selected layer to GeoJSON or CSV. | **Open** |
| `ui.printMap` | Print the map view (through the system's PDF viewer). | **Open** |
| `ui.captureMap` | Copy an image of the map to the clipboard. | **Open** |
| `publish.report` | Export the report, or save it as a report file or template. | **Open** |
| `publish.exportReport` | Export Report…. | **Open** |
| `publish.saveAsReportFile` | Save As Report File…. | **Open** |
| `publish.saveAsReportTemplate` | Save As Report Template…. | **Open** |
| `publish.presentation` | Export the presentation as a slideshow or PDF, or save it as a file. | **Open** |
| `publish.exportPresentation` | Export Presentation…. | **Open** |
| `publish.saveAsPresentationFile` | Save As Presentation File…. | **Open** |
| `publish.exportTo3d` | Export the selected layer as a 3D model (OBJ), polygons extruded. | **Open** |
| `publish.export` | Export the layout as PDF or PNG. | **Open** |
| `publish.print` | Print the layout. | **Open** |
| `publish.saveLayoutFile` | Save the layout as a layout file. | **Open** |
| `layout.close` | Close the layout and show the map. | **Open** |

### Share

| Command | Does | Status |
| --- | --- | --- |
| `publish.link` | A URL that opens this exact view and these layers. | **Open** |
| `publish.embed` | An iframe snippet for a website. | **Open** |
| `publish.webmap` | Push this map to the project's public site. | **Open** |
| `publish.webMap` | Share the map as a web page that needs no server. | **Open** |
| `publish.webLayer` | Share the selected layer as an OGC API Features collection with its style. | **Open** |
| `publish.webStyle` | Share the selected layer's symbology as a MapLibre style. | **Open** |
| `publish.locator` | Share the selected layer's names as a place-search locator. | **Open** |
| `publish.geodataService` | Share every layer and table as OGC API Features collections. | **Open** |
| `publish.webTool` | Share the last model as a tool file. | **Open** |
| `publish.webScene` | Share the map in 3D (glTF), polygons extruded. | **Open** |
| `publish.webLinkChart` | Share the map's relationships as a link chart page. | **Open** |
| `ui.pane.shares` | Shares made, with Manage tools to update them. | **Open** |
| `publish.deepLearning` | Package a trained deep learning model. | **Open** |

### Report

| Command | Does | Status |
| --- | --- | --- |
| `report.new` | A document built from the current map and tables. | **Open** |
| `report.template` | Start from a layout someone has already made. | **Open** |
| `report.reportSection` | Add pages, layouts, related reports and related records to the report. | **Open** |
| `report.supplementalPage` | Supplemental Page. | **Open** |
| `report.supplementalPageAfter` | Supplemental Page After. | **Open** |
| `report.newTemplate` | New Template (a layout page). | **Open** |
| `report.existingTemplate` | Build a report from an existing template. | **Open** |
| `ui.reportLayoutFile` | Layout File…. | **Open** |
| `report.relatedReport` | A report on the rows related to this one. | **Open** |
| `report.subreport` | Embed one report inside another. | **Open** |
| `report.autofill` | Autofill Fields. | **Open** |
| `report.statistics` | Totals and summaries on a report section. | **Open** |
| `ui.pane.report` | Preview and set up the report. | **Open** |
| `report.importReport` | Add a report file, or a report template for the selected layer. | **Open** |

### Presentation

| Command | Does | Status |
| --- | --- | --- |
| `ui.newPresentation` | Pages of maps, text, images and videos, shown one after another. | **Open** |
| `presentation.page` | Add a page to the presentation. | **Open** |
| `presentation.mapTheCurrentView` | Map (the current view). | **Open** |
| `presentation.blankPage` | Add an empty page to the presentation. | **Open** |
| `ui.presentationPicture` | Image…. | **Open** |
| `ui.presentationVideo` | Video…. | **Open** |
| `presentation.importPresentation` | Add a presentation file. | **Open** |
| `ui.pane.presentation` | Preview, edit and play the presentation. | **Open** |

### Thumbnail

| Command | Does | Status |
| --- | --- | --- |
| `project.thumbnail` | The project's thumbnail, from the map view. | **Open** |
| `publish.importThumbnail` | The project's thumbnail, from an image. | **Open** |
| `map.thumbnail` | This map's thumbnail, from the view. | **Open** |
| `publish.import` | This map's thumbnail, from an image. | **Open** |

### Package

| Command | Does | Status |
| --- | --- | --- |
| `publish.projectPackage` | Bundle the project and its data into one file to share. | **Open** |
| `publish.map` | Bundle the active map and its data. | **Open** |
| `publish.mobileMap` | Bundle the visible layers, with simplified geometry for phones and tablets. | **Open** |
| `publish.results` | Bundle the geoprocessing history with the layers it made. | **Open** |

### Layout

| Command | Does | Status |
| --- | --- | --- |
| `layout.exportLayout` | Export the open layout as PDF or PNG. | **Open** |
| `layout.printLayout` | Print the open layout (through the system's PDF viewer). | **Open** |

### Save As

| Command | Does | Status |
| --- | --- | --- |
| `ui.saveAs` | Save the project under a new name. | **Open** |
| `publish.layoutFile` | Save the open layout as a layout file. | **Open** |
| `publish.mapFile` | Save the active map (with its data) as a map file. | **Open** |
| `publish.layerFile` | Save the selected layer with its symbology as a layer file. | **Open** |
| `publish.styleItems` | Save the project's styles to a style file. | **Open** |
| `publish.projectTemplate` | Save the project's setup, without its features, as a template. | **Open** |
| `publish.taskItem` | Save the last task as a task file. | **Open** |

### Map Frames

| Command | Does | Status |
| --- | --- | --- |
| `layout.addFrame` | Add a map frame showing a map of the project. | **Open** |
| `layout.grid` | Draw a labelled latitude/longitude grid over the map frame. | **Open** |
| `layout.extentIndicator` | Outline another frame's extent in this map frame. | **Open** |
| `layout.series` | One page per feature of an index layer. | **Open** |
| `layout.previousPage` | Show the previous map series page. | **Open** |
| `layout.nextPage` | Show the next map series page. | **Open** |

### Map Surrounds

| Command | Does | Status |
| --- | --- | --- |
| `layout.tableFrame` | Add the attribute table of a layer in the map frame. | **Open** |
| `layout.chartFrame` | Add a bar chart of a layer's numeric field. | **Open** |
| `layout.more` | Additional surrounds. | **Open** |

### Text

| Command | Does | Status |
| --- | --- | --- |
| `layout.dynamicText` | Add text that updates: page, date, scale, map and more. | **Open** |
| `ui.layoutPicture` | Add a PNG or JPEG picture to the page. | **Open** |

## Plugins

### Plugins

| Command | Does | Status |
| --- | --- | --- |
| `plugins.manage` | Turn community plugins on and off. | **Open** |
| `plugins.browse` | Plugins published by the Ghana GIS community. | **Open** |
| `plugins.install` | Load a plugin from a file. | **Open** |
| `plugins.develop` | How to add a tab, a tool or a data source. | **Open** |
| `plugins.pluginManager` | Browse, install, update and remove plugins. | **Open** |
| `plugins.browsePlugins` | Find plugins in the RustGIS plugin registry. | **Open** |

### Automation

| Command | Does | Status |
| --- | --- | --- |
| `task.record` | Capture a sequence of commands to replay. | **Open** |
| `task.run` | Replay a saved sequence. | **Open** |
| `task.schedule` | Run a task on a timetable. | **Open** |

## Settings

### Interface

| Command | Does | Status |
| --- | --- | --- |
| `ui.settings` | Basemap, projection, terrain and the model. | Built |
| `map.theme` | Switch the interface theme. | Built |
| `settings.language` | English, Twi, Ewe, Ga, Dagbani, Hausa. | **Open** |
| `settings.units` | Metric or imperial, and the coordinate format. | **Open** |

### Data

| Command | Does | Status |
| --- | --- | --- |
| `settings.crs` | The CRS the map draws and reports in. | **Open** |
| `settings.cache` | How much is held locally. | **Open** |
| `settings.privacy` | What leaves this browser, and what never does. | **Open** |

## Help

### Learn

| Command | Does | Status |
| --- | --- | --- |
| `ui.tour` | A guided walk through the map. | Built |
| `ui.docs` | The full guide. | Built |
| `ui.commands` | Find any command by name. | Built |
| `ui.shortcuts` | What the keys do. | **Open** |
| `ui.learn` | Open the RustGIS user guide. | **Open** |

### Community

| Command | Does | Status |
| --- | --- | --- |
| `ui.contribute` | How to add a command, a tool or a dataset. | Built |
| `ui.issues` | Tell us what broke. | Built |
| `ui.about` | Sources, licences and attribution. | Built |
| `ui.checkUpdate` | See whether a newer RustGIS has been released. | **Open** |

### Customize

| Command | Does | Status |
| --- | --- | --- |
| `ui.customizeRibbon` | Choose which tabs the ribbon shows. | **Open** |
| `ui.quickAccess` | Choose extra buttons for the Quick Access Toolbar. | **Open** |

### Performance

| Command | Does | Status |
| --- | --- | --- |
| `ui.pane.diagnostics` | Frame rate, draw time, data size and memory. | **Open** |

## Not on a tab

Commands the registry holds that no ribbon control names. They run
from command search and from the assistant.

| Command | Does | Status |
| --- | --- | --- |
| `gp.pointon` | One point per feature, guaranteed to sit on it. | Built |
| `gp.measure` | Area in km² and perimeter in km per feature. | Built |
