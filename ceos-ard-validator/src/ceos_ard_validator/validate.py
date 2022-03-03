from abc import ABC, abstractmethod
from collections import defaultdict
from typing import List, Optional, Dict, Any, Sequence, Type

import pystac
from pystac.validation.stac_validator import JsonSchemaSTACValidator
from pystac import Item, STACValidationError, Asset

from .constants import SPECIFICATION_VERSION, SPECIFICATIONS, REQUIRED_EXTENSIONS


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

    validator = Validator(item)
    return validator.validate()


class Validator:
    def __init__(self, item: Item):
        self.item = item
        self.results: defaultdict[str, List[Result]] = defaultdict(list)

    def property(self, name: str) -> Any:
        return self.item.properties.get(name)

    def validate(self) -> Dict[str, List[Result]]:
        self.validate_extensions()
        self.validate_stac_items()
        self.validate_item_properties()
        self.validate_links()
        self.validate_assets()
        return self.results

    def is_st(self) -> bool:
        return self.property("card4l:specification") == "ST"

    def is_sr(self) -> bool:
        return self.property("card4l:specification") == "SR"

    def validate_extensions(self):
        for extension in REQUIRED_EXTENSIONS:
            result = self.validate_extension(extension)
            if result:
                self.add_result("extension", result)

    def validate_extension(self, extension: str) -> Optional[Result]:
        if extension in self.item.stac_extensions:
            validator = JsonSchemaSTACValidator()
            try:
                validator.validate_extension(
                    self.item.to_dict(),
                    self.item.STAC_OBJECT_TYPE,
                    pystac.get_stac_version(),
                    extension,
                )
            except STACValidationError as e:
                return Error(
                    f"object does not pass validation against {extension}",
                    suggestion=f"Run `ceos-ard validate-jsonschema {self.item.self_href}` to see the validation error",
                )
            else:
                return None
        else:
            return Error(f"missing required extension: {extension}")

    def validate_stac_items(self):
        if not self.item.geometry:
            self.add_result("geometry", Error("geometry cannot be null"))
        if not self.item.bbox:
            self.add_result("bbox", Error("bbox cannot be null"))

    def validate_item_properties(self):
        self.check_property_in("card4l:specification", SPECIFICATIONS)
        self.check_property_equal("card4l:specification_version", SPECIFICATION_VERSION)
        self.check_property_is_geometric_accuracy("card4l:northern_geometric_accuacy")
        self.check_property_is_geometric_accuracy("card4l:eastern_geometric_accuacy")
        if not self.item.datetime:
            self.add_result("datetime", Error("datetime cannot be null"))
        if not self.item.common_metadata.instruments:
            self.add_result("instruments", Error("instruments are required"))
        self.check_lowercase("constellation")
        epsg = self.property("proj:epsg")
        if not epsg and not (
            self.property("proj:wkt2") or self.property("proj:projjson")
        ):
            self.add_result(
                "proj",
                Error("proj:wkt2 or proj:projjson is required if proj:epsg is null"),
            )
        self.check_required_property("view:off_nadir")
        self.check_required_property("view:azimuth")
        self.check_required_property("view:sun_azimuth")
        self.check_required_property("view:sun_elevation")

    def validate_links(self):
        self.check_link(
            "card4l-document",
            media_types=[
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                "application/pdf",
            ],
        )
        self.validate_algorithms()
        self.check_link("access", result_type=Warning)
        if self.is_st():
            self.check_link("atmosphere-emissivity")
        elif self.is_sr():
            self.check_link("measurement-normalization")
            self.check_link("atmospheric-scattering")
            self.check_link("water-vapor")
            self.check_link("ozone")

    def check_property_in(self, name: str, values: Sequence[Any]):
        value = self.property(name)
        if value not in values:
            self.add_result(
                name,
                Error(
                    f"{name} is not an expected value: value={value}, expected={values}",
                ),
            )

    def check_property_equal(self, name: str, expected: Any):
        value = self.property(name)
        if value != expected:
            self.add_result(
                name,
                Error(
                    f"{name} is not the expected value: value={value}, expected={expected}",
                ),
            )

    def check_property_is_geometric_accuracy(self, name: str):
        self.check_member_is_number(name, "bias")
        self.check_member_is_number(name, "stddev")

    def check_member_is_number(self, p: str, name: str):
        d = self.property(p)
        if not d:
            self.add_result(f"{p}", Error(f"expected property is missing: {p}.{name}"))
        else:
            value = d.get(name)
            try:
                float(value)
            except ValueError:
                self.add_result(f"{p}.{name}", Error(f"value is not a number: {value}"))

    def add_result(self, name: str, result: Result):
        self.results[name].append(result)

    def check_lowercase(self, name: str):
        value = self.property(name)
        if value and any(c.isupper() for c in value):
            self.add_result(
                name,
                Error(f"{name} must be lowercase: {value}"),
            )

    def check_required_property(self, name: str):
        value = self.property(name)
        if not value:
            self.add_result(name, Error(f"missing required property: {name}"))

    def check_link(
        self, rel: str, media_types: List[str] = [], result_type: Type[Result] = Error
    ):
        link = self.item.get_single_link(rel)
        if not link:
            self.add_result(f"links[rel={rel}]", result_type("missing link"))
        elif media_types and link.media_type not in media_types:
            self.add_result(
                f"links[rel={rel}]",
                result_type(
                    f"invalid media type: actual={link.media_type}, expected={media_types}"
                ),
            )

    def validate_algorithms(self):
        if not self.property("processing:software") and not self.item.get_single_link(
            "about"
        ):
            self.add_result(
                "about",
                Error(
                    f"item must have either property `processing:software` or a link with with a relation type `about`"
                ),
            )

    def validate_assets(self):
        seen_required_roles = []
        for asset in self.item.assets.values():
            seen_required_roles = self.validate_asset(asset, seen_required_roles)
        if "data" not in seen_required_roles:
            self.add_result(
                "assets[role=data]",
                Error("missing asset with roles: (reflectance or temperature), data"),
            )

        def check_required_metadata_role(role: str):

            if role not in seen_required_roles:
                self.add_result(
                    f"assets[role={role}]",
                    Error(f"missing asset with roles: {role}, metadata"),
                )

        check_required_metadata_role("incomplete-testing")
        check_required_metadata_role("saturation")
        check_required_metadata_role("cloud")
        check_required_metadata_role("cloud-shadow")

    def validate_asset(self, asset: Asset, seen_required_roles: List[str]):
        roles = asset.roles
        if not roles:
            return

        if ("reflectance" in roles or "temperature" in roles) and "data" in roles:
            self.validate_data_asset(asset)
            seen_required_roles.append("data")
        elif "metadata" in roles:
            if "date" in roles:
                self.validate_date_asset(asset)
            elif "incomplete-testing" in roles:
                self.validate_incomplete_testing_asset(asset)
                seen_required_roles.append("incomplete-testing")
            elif "saturation" in roles:
                self.validate_saturation_asset(asset)
                seen_required_roles.append("saturation")
            elif "cloud" in roles:
                self.validate_cloud_asset(asset)
                seen_required_roles.append("cloud")
            elif "cloud-shadow" in roles:
                self.validate_cloud_shadow_asset(asset)
                seen_required_roles.append("cloud-shadow")
            elif "snow-ice" in roles:
                self.validate_snow_ice_asset(asset)
            elif "land-water" in roles:
                self.validate_land_water_asset(asset)
            elif "incidence-angle" in roles:
                self.validate_incidence_angle_asset(asset)
            elif "azimuth" in roles:
                self.validate_azimuth_asset(asset)
            elif "sun-azimuth" in roles:
                self.validate_sun_azimuth_asset(asset)
            elif "sun-elevation" in roles:
                self.validate_sun_elevation_asset(asset)
            elif "terrain-shadow" in roles:
                self.validate_terrain_shadow_asset(asset)
            elif "terrain-occlusion" in roles:
                self.validate_terrain_occlusion_asset(asset)
            elif "terrain-illumination" in roles:
                self.validate_terrain_illumination_asset(asset)

        return seen_required_roles

    def validate_data_asset(self, asset: Asset):
        pass

    def validate_date_asset(self, asset: Asset):
        pass

    def validate_incomplete_testing_asset(self, asset: Asset):
        pass

    def validate_saturation_asset(self, asset: Asset):
        pass

    def validate_cloud_asset(self, asset: Asset):
        pass

    def validate_cloud_shadow_asset(self, asset: Asset):
        pass

    def validate_snow_ice_asset(self, asset: Asset):
        pass

    def validate_land_water_asset(self, asset: Asset):
        pass

    def validate_incidence_angle_asset(self, asset: Asset):
        pass

    def validate_azimuth_asset(self, asset: Asset):
        pass

    def validate_sun_azimuth_asset(self, asset: Asset):
        pass

    def validate_sun_elevation_asset(self, asset: Asset):
        pass

    def validate_terrain_shadow_asset(self, asset: Asset):
        pass

    def validate_terrain_occlusion_asset(self, asset: Asset):
        pass

    def validate_terrain_illumination_asset(self, asset: Asset):
        pass
