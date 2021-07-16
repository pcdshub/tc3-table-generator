import periodictable
import tc3tg


constants = []

for element in periodictable.elements:
    tc3_name = f"fMass_{element}"
    constants.append(
        tc3tg.Constant(
            description=f"Atomic mass of {element} ({element.name})",
            name=tc3_name,
            units=None,
            value=element.mass,
        )
    )


fn = "GVL_AtomicMass.TcGVL"
gvl_source = tc3tg.generate_constant_table(fn.split(".")[0], constants)
with open(fn, "wt") as fp:
    print(gvl_source, file=fp)
