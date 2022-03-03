# ceos-ard-validator

Validate STAC objects against the CARD4L extension.

There is a Python API in `ceos_ard_validator.validate` and a command line interface at `ceos-ard`.

## Installing

Clone the repo and install:

```shell
pip install .
```

## CLI

To see a list of commands:

```shell
ceos-ard --help
```

### Download an item

If you'd like, you can download a Landsat STAC item to test validation on a local file:

```shell
ceos-ard download-landsat-item LC09_L2SP_092067_20220228_20220302_02_T1_SR > LC09_L2SP_092067_20220228_20220302_02_T1_SR.json
```

### Validate

The validation work steps through the required extensions, including the CARD4L extension (even if it doesn't exist in the `stac_extensions` attribute of the Item):

```shell
ceos-ard validate LC09_L2SP_092067_20220228_20220302_02_T1_SR.json
```

This should display some output, e.g.:

```text
At 'stac_extensions': 
  - ERROR: missing required extension: https://stac-extensions.github.io/raster/v1.0.0/schema.json
  - ERROR: object does not pass validation against https://raw.githubusercontent.com/stac-extensions/card4l/4e62c51a8fc40cce7f0a6dd7dbc6f2c33ff1b704/optical/json-schema/schema.json
    SUGGESTION: Run `ceos-ard validate-jsonschema https://landsatlook.usgs.gov/stac-server/collections/landsat-c2l2-sr/items/LC09_L2SP_092067_20220228_20220302_02_T1_SR` to see the validation error
```

### Validate JSONSchema

To run jsonschema validation after injecting the CARD4L schema into `stac_extensions`:

```shell
ceos-ard validate-jsonschema LC09_L2SP_092067_20220228_20220302_02_T1_SR.json
```

This should display the validation errors.
