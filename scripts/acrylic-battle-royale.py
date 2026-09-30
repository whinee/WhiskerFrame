"""
Acrylic sheet price comparator — "battle royale" edition.

Compares multiple acrylic sheet listings on price-per-area, then applies
a thickness correction so thicker sheets get credit for being
disproportionately stiffer, not just linearly "more material."

Physics rationale:
    Plate bending stiffness (flexural rigidity) is:
        D = E * t^3 / (12 * (1 - v^2))
    where t = thickness. Notice it scales with thickness CUBED, not
    linearly. So a 3mm sheet isn't "50% stronger" than a 2mm sheet —
    it resists bending/deflection roughly (3/2)^3 ≈ 3.4x more.

    This matters for something like a case panel that needs to resist
    bowing/cracking under screw pressure or being pressed on.

    Caveat: this cubic scaling models BENDING STIFFNESS specifically.
    If your actual failure mode is impact/drop toughness or edge
    chip-out resistance instead, the relationship with thickness is
    messier and N=3 may overcorrect. Adjust N if that's your concern.
"""

from abc import ABC, abstractmethod
from typing import Annotated, Literal, Union

from pydantic import BaseModel, ConfigDict, Field


class Dimension(BaseModel, ABC):
    model_config = ConfigDict(extra="forbid")

    value: float
    unit: str

    @abstractmethod
    def to_millimeters(self) -> float:
        """Every subclass must know how to convert itself to mm."""
        ...

    def to_centimeters(self) -> float:
        return self.to_millimeters() / 10


class Millimeter(Dimension):
    unit: Literal["mm"] = Field(
        default="mm", frozen=True
    )  # pyright: ignore[reportIncompatibleVariableOverride]

    def to_millimeters(self) -> float:
        return self.value


class Centimeter(Dimension):
    unit: Literal["cm"] = Field(
        default="cm", frozen=True
    )  # pyright: ignore[reportIncompatibleVariableOverride]

    def to_millimeters(self) -> float:
        return self.value * 10


class Inch(Dimension):
    unit: Literal["in"] = Field(
        default="in", frozen=True
    )  # pyright: ignore[reportIncompatibleVariableOverride]

    def to_millimeters(self) -> float:
        return self.value * 25.4


AnyDimension = Annotated[
    Union[Centimeter, Inch, Millimeter], Field(discriminator="unit")
]

DimensionClass = type[Millimeter] | type[Centimeter] | type[Inch]


class TwoDimensions(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str | None = None
    width: AnyDimension
    height: AnyDimension


def width_height_fn(
    width_height: float | tuple[float, float],
    unit: DimensionClass,
    label: str | None = None,
) -> TwoDimensions:
    match width_height:
        case float() | int():
            w, h = (width_height, width_height)
        case (w, h):
            pass
        case _:
            raise TypeError(
                f"Expected float or tuple[float, float], got {type(width_height)}"
            )

    return TwoDimensions(label=label, width=unit(value=w), height=unit(value=h))


A4 = width_height_fn((21, 29.7), Centimeter, "A4")


class Dimensions(BaseModel):
    model_config = ConfigDict(extra="forbid")

    width_height: TwoDimensions
    thickness: AnyDimension


class Variation(BaseModel):
    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    price: int
    dimensions: Dimensions
    cons: str = ""
    notes: str = ""


class FullVariation(Variation):
    label: str | None = None
    url: str


class Candidate(BaseModel):
    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    label: str | None = None
    variations: list[Variation]
    url: str
    cons: str = ""
    notes: str = ""


candidates = [
    Candidate(
        variations=[
            Variation(
                price=209,
                dimensions=Dimensions(
                    width_height=width_height_fn(30, Centimeter),
                    thickness=Millimeter(value=3),
                ),
            ),
            Variation(
                price=289,
                dimensions=Dimensions(
                    width_height=width_height_fn(40, Centimeter),
                    thickness=Millimeter(value=2),
                ),
            ),
            Variation(
                price=299,
                dimensions=Dimensions(
                    width_height=width_height_fn(30, Centimeter),
                    thickness=Millimeter(value=4.5),
                ),
            ),
            Variation(
                price=399,
                dimensions=Dimensions(
                    width_height=width_height_fn(40, Centimeter),
                    thickness=Millimeter(value=3),
                ),
            ),
            Variation(
                price=529,
                dimensions=Dimensions(
                    width_height=width_height_fn(40, Centimeter),
                    thickness=Millimeter(value=4.5),
                ),
            ),
        ],
        url=r"https://shopee.ph/Black-Acrylic-sheet-LASER-CUT-pre-cut-plastic-Sheet-i.263573334.8846820765",
    ),
    Candidate(
        variations=[
            Variation(
                price=209,
                dimensions=Dimensions(
                    width_height=width_height_fn((30, 60), Centimeter),
                    thickness=Millimeter(value=3),
                ),
            ),
        ],
        url=r"https://shopee.ph/Transparent-Colored-Acrylic-3mm-Thickness-i.263573334.22531460010",
        cons="Clear; poor laser cutting",
    ),
    Candidate(
        variations=[
            Variation(
                price=88,
                dimensions=Dimensions(
                    width_height=width_height_fn(8, Inch), thickness=Millimeter(value=3)
                ),
            ),
        ],
        url=r"https://shopee.ph/Acrylic-Square-Box-Blanks-DIY-2-to-8-Square-Box-Clear-Colored-Pre-Cut-Sheets-Customized-Size-Glass-i.116150007.25171120610",
    ),
    Candidate(
        variations=[
            Variation(
                price=227,
                dimensions=Dimensions(
                    width_height=width_height_fn((10, 12), Inch),
                    thickness=Millimeter(value=3),
                ),
            ),
        ],
        url=r"https://shopee.ph/Black-Opaque-Glossy-Acrylic-Sheet-Pre-Cut-Sizes-1.5mm-2mm-3mm-Laser-Cut-Acrylic-BK-03--i.1788514251.50910201381",
        cons="None sold",
    ),
    Candidate(
        variations=[
            Variation(
                price=315,
                dimensions=Dimensions(width_height=A4, thickness=Millimeter(value=3)),
            ),
        ],
        url=r"https://shopee.ph/Black-White-Acrylic-Sheet-A4*-Size-2mm-to-10mm-thick-%E2%80%93-solid-cast-acrylic-for-signage-laser-cutting-display-i.1619959161.40467810169",
    ),
]

THICKNESS_EXPONENT = 3
REFERENCE_THICKNESS = Millimeter(value=3).to_millimeters()


def area_cm2(sheet: FullVariation):
    """Simple rectangular area in cm^2."""
    dimensions = sheet.dimensions.width_height
    return dimensions.width.to_centimeters() * dimensions.height.to_centimeters()


def raw_rate(sheet: FullVariation):
    """Plain price per cm^2 — ignores thickness entirely."""
    return sheet.price / area_cm2(sheet)


def strength_factor(sheet: FullVariation):
    """How much stiffer this sheet is vs. the reference thickness."""
    return (
        sheet.dimensions.thickness.to_millimeters() / REFERENCE_THICKNESS
    ) ** THICKNESS_EXPONENT


def adjusted_rate(sheet: FullVariation):
    """Price per cm^2, corrected for thickness. Dividing by the strength factor gives thicker sheets credit for disproportionate stiffness instead of just linearly 'more material'."""

    return sheet.price / (area_cm2(sheet) * strength_factor(sheet))


# ── 3. Rank everyone and build the markdown table ───────────────────
def build_markdown_table(candidates: list[Candidate]):
    variations: list[FullVariation] = []
    for candidate in candidates:
        candidate_data = candidate.model_dump()
        candidate_data.pop("variations")
        for variation in candidate.variations:
            variations.append(
                FullVariation(**(candidate_data | variation.model_dump()))
            )
    ranked = sorted(variations, key=adjusted_rate)
    header = [
        "| Rank (Adj.) | Item | Price (PHP) | Dimensions (cm) | Thickness (mm) | Raw PHP/cm² | Adj. PHP/cm² (t³) | Link |",
        "|:---:|:---|:---:|:---:|:---:|:---:|:---:|:---:|",
    ]
    rows = []
    for rank, variation in enumerate(ranked, start=1):
        dimensions = variation.dimensions
        width_height = dimensions.width_height
        rows.append(
            f"| {rank} | {variation.label} | {variation.price} "
            f"| {width_height.width.to_centimeters():g}x{width_height.height.to_centimeters():g}cm | {dimensions.thickness.to_millimeters():g} "
            f"| {raw_rate(variation):.3f} | {adjusted_rate(variation):.4f} "
            f"| [link]({variation.url}) |",
        )
    return "\n".join(header + rows)


if __name__ == "__main__":
    print(build_markdown_table(candidates))
