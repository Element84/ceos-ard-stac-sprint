from abc import ABC, abstractmethod
from collections import defaultdict
from typing import List, Optional, Dict, Any, Sequence

import pystac
from pystac.validation.stac_validator import JsonSchemaSTACValidator
from pystac.extensions.eo import EOExtension
from pystac.extensions.projection import ProjectionExtension
from pystac.extensions.raster import RasterExtension
from pystac.extensions.view import ViewExtension
from pystac import Item, STACValidationError

from .constants import CARD4L_EXTENSION


class Result(ABC):
    message: str
    suggestion: Optional[str]

    def __init__(self, message: str, suggestion: Optional[str] = None):
        self.message = message
        self.suggestion = suggestion

    @abstractmethod
    def is_error(self) -> bool:
        raise NotImplementedError


class Error(Result):
    def is_error(self) -> bool:
        return True


class Warning(Result):
    def is_error(self) -> bool:
        return False


def validate(href: str, recurse: bool = False) -> Dict[str, List[Result]]:

    if recurse:
        raise NotImplementedError
    item = pystac.read_file(href)
    if not isinstance(item, Item):
        raise NotImplementedError

    extensions: List[Any] = [
        EOExtension,
        ProjectionExtension,
        RasterExtension,
        ViewExtension,
    ]
    result_dict: defaultdict[str, List[Result]] = defaultdict(list)
    for Extension in extensions:
        result = check_required_extension(item, Extension.get_schema_uri())
        if result:
            result_dict["stac_extensions"].append(result)
    result = validate_extension(item, CARD4L_EXTENSION)
    if result:
        result_dict["stac_extensions"].append(result)

    return result_dict


def check_required_extension(item: Item, extension: str) -> Optional[Result]:
    if extension not in item.stac_extensions:
        return Error(f"missing required extension: {extension}")
    return validate_extension(item, extension)


def validate_extension(item: Item, extension: str) -> Optional[Result]:
    validator = JsonSchemaSTACValidator()
    try:
        validator.validate_extension(
            item.to_dict(),
            item.STAC_OBJECT_TYPE,
            pystac.get_stac_version(),
            extension,
        )
    except STACValidationError as e:
        return Error(
            f"object does not pass validation against {extension}",
            suggestion=f"Run `ceos-ard validate-jsonschema {item.self_href}` to see the validation error",
        )

    return None
