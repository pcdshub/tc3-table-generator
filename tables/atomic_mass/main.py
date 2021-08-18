import periodictable
import tc3tg


constants = []

for element in periodictable.elements:
    tc3_name = f"fMass_{element}"
    constants.append(
        tc3tg.Constant(
            description=f"Atomic mass of {element} ({element.name})",
            name=tc3_name,
            key=element,
            units=None,
            value=element.mass,
        )
    )


fn = "GVL_AtomicMass.TcGVL"
gvl_source = tc3tg.generate_constant_table(fn.split(".")[0], constants)
with open(fn, "wt") as fp:
    print(gvl_source, file=fp)


fn = "FB_AtomicMass.TcPOU"
fb_source = tc3tg.generate_constant_table(
    fn.split(".")[0], constants, lookup_by_key=True
)
with open(fn, "wt") as fp:
    print(fb_source, file=fp)
