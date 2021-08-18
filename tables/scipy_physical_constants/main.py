import re

import inflection
import scipy.constants
import tc3tg

valid_identifier_chars = re.compile("[^a-z0-9_]", re.IGNORECASE)

constants = []

for item in scipy.constants.physical_constants.items():
    description, (value, units, uncertainty) = item

    # Start off with the description and go from there
    tc3_name = description

    # abbreviations
    tc3_name = tc3_name.replace("gyromagn.", "Gyromagnetic")
    tc3_name = tc3_name.replace("magn.", "Magnetic")

    tc3_name = inflection.camelize(tc3_name.replace(" ", "_"))
    if units:
        unit_desc = units.replace(" ", "_")
        tc3_name = f"{tc3_name}_in_{unit_desc}"

    # other abbreviations
    tc3_name = tc3_name.replace(". ", "")

    # e.g., volt-amps
    def replace_dash(match):
        letter1, letter2 = match.groups()
        return letter1 + letter2.upper()

    tc3_name = re.sub("([a-z])-([a-z])", replace_dash, tc3_name, re.IGNORECASE)

    # non identifier chars -> _
    tc3_name = valid_identifier_chars.sub("_", f"f{tc3_name}")

    # multiple _ to one _
    tc3_name = re.sub("_+", "_", tc3_name)

    # no ending _
    tc3_name = tc3_name.rstrip("_")
    constants.append(
        tc3tg.Constant(
            description=description,
            name=tc3_name,
            key=description,
            units=units,
            value=value,
            uncertainty=uncertainty,
        )
    )


short_name = "GVL_PhysicalConstants"
with open(f"{short_name}.TcGVL", "wt") as fp:
    print(tc3tg.generate_constant_table(short_name, constants), file=fp)


short_name = "FB_PhysicalConstants"
with open(f"{short_name}.TcPOU", "wt") as fp:
    print(tc3tg.generate_constant_table(short_name, constants, lookup_by_key=True), file=fp)
