import periodictable
import tc3tg


constants = []

for element in periodictable.elements:
    tc3_name = f"fDensity_{element}"
    constants.append(
        tc3tg.Constant(
            description=f"Elemental density of {element}",
            name=tc3_name,
            units=element.density_units,
            value=element.density,
            caveat=element.density_caveat,
        )
    )


fn = "GVL_ElementDensity.TcGVL"
gvl_source = tc3tg.generate_constant_table(fn.split(".")[0], constants)
with open(fn, "wt") as fp:
    print(gvl_source, file=fp)
