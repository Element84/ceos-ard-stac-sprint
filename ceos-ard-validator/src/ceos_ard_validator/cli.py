import json

import click
import pystac
from pystac_client import Client

from .constants import LANDSATLOOK_URL, CARD4L_EXTENSION
from .validate import validate as validate_href


@click.group()
def cli() -> None:
    """Validate STAC items against the CARD4L extension."""
    pass


@cli.command()
@click.argument("ITEM-ID")
def download_landsat_item(item_id: str) -> None:
    """Downloads a LANDSAT item from LandsatLook by ID and prints it to stdout."""
    client = Client.open(LANDSATLOOK_URL)
    result = client.search(ids=[item_id])
    item = next(result.get_items())
    print(json.dumps(item.to_dict(), indent=4))


@cli.command()
@click.argument("HREF")
def validate(href: str) -> None:
    """Validates an item."""
    validation_result = validate_href(href)
    if not validation_result:
        click.secho("OK", fg="green")
    else:
        for path, results in validation_result.items():
            click.echo(f"At '{path}': ")
            for result in results:
                if result.is_error:
                    click.secho("  - ERROR: ", fg="red", nl=False)
                elif result.is_warning:
                    click.secho("  - WARNING: ", fg="yellow", nl=False)
                click.echo(result.message)
                if result.suggestion:
                    click.echo(f"    SUGGESTION: {result.suggestion}")


@cli.command()
@click.argument("HREF")
def validate_jsonschema(href: str) -> None:
    """Validates an item's jsonschema.

    Injects the CARD4L schema.
    """
    stac_object = pystac.read_file(href)
    existing_card4l_url = next(
        (
            url
            for url in stac_object.stac_extensions
            if url.startswith("https://stac-extensions.github.io/card4l")
        ),
        None,
    )
    if existing_card4l_url:
        stac_object.stac_extensions.remove(existing_card4l_url)
    stac_object.stac_extensions.append(CARD4L_EXTENSION)
    stac_object.validate()


def main():
    cli()
