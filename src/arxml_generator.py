r"""
arxml_generator.py
------------------
FOLDER : D:\Auto\claude-autosar-integration\src\
FILE   : src\arxml_generator.py

Layer 2 — Converts a validated SWCSpec into three AUTOSAR
R22-11 ARXML files using autosarfactory.

Output files (written to output_dir):
    datatypes.arxml   — ImplementationDataType per data_type used
    interfaces.arxml  — SenderReceiverInterface per port
    component.arxml   — ApplicationSwComponentType with ports + runnables

Usage:
    from pathlib import Path
    from src.models import SWCSpec
    from src.arxml_generator import ARXMLGenerator

    spec = SWCSpec(...)
    gen  = ARXMLGenerator(spec, output_dir=Path("output"))
    paths = gen.generate_all()
"""

import logging
from pathlib import Path

# ── IMPORTANT: the real API lives in the submodule, not the top-level package
import autosarfactory.autosarfactory as af

from src.models import SWCSpec, PortSpec, RunnableSpec

logger = logging.getLogger(__name__)


class ARXMLGenerator:
    """
    Generates AUTOSAR Classic R22-11 ARXML files from a SWCSpec.

    Three files are produced in dependency order:
        1. datatypes.arxml   — base types + implementation data types
        2. interfaces.arxml  — SenderReceiver interfaces (one per port)
        3. component.arxml   — SWC with ports, internal behavior, runnables
    """

    def __init__(self, spec: SWCSpec, output_dir: Path):
        self.spec = spec
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.dt_path   = self.output_dir / "datatypes.arxml"
        self.if_path   = self.output_dir / "interfaces.arxml"
        self.comp_path = self.output_dir / "component.arxml"

    # ── Public ────────────────────────────────────────────────────────
    def generate_all(self) -> list[Path]:
        """
        Generate all three ARXML files.
        Returns [datatypes.arxml, interfaces.arxml, component.arxml]
        """
        logger.info("Generating ARXML for SWC: %s", self.spec.swc_name)

        # reinit clears autosarfactory's internal state between runs
        af.reinit()

        self._gen_datatypes()
        self._gen_interfaces()
        self._gen_component()

        logger.info("ARXML generation complete -> %s", self.output_dir)
        return [self.dt_path, self.if_path, self.comp_path]

    # ── datatypes.arxml ───────────────────────────────────────────────
    def _gen_datatypes(self):
        logger.info("  Generating datatypes.arxml ...")
        unique_types = sorted({p.data_type for p in self.spec.ports})
        BASE_TYPE_ENCODING = {
            "uint8":   ("uint8",   8,  "2C"),
            "uint16":  ("uint16",  16, "2C"),
            "uint32":  ("uint32",  32, "2C"),
            "sint8":   ("sint8",   8,  "2C"),
            "sint16":  ("sint16",  16, "2C"),
            "float32": ("float32", 32, "IEEE754"),
        }
        xml = [
            "<?xml version='1.0' encoding='UTF-8'?>",
            '<AUTOSAR xmlns="http://autosar.org/schema/r4.0"',
            '  xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"',
            '  xsi:schemaLocation="http://autosar.org/schema/r4.0 AUTOSAR_00051.xsd">',
            "  <AR-PACKAGES><AR-PACKAGE><SHORT-NAME>DataTypes</SHORT-NAME><AR-PACKAGES>",
            "    <AR-PACKAGE><SHORT-NAME>BaseTypes</SHORT-NAME><ELEMENTS>",
        ]
        for dt in unique_types:
            name, size, enc = BASE_TYPE_ENCODING[dt]
            xml.append(f"      <SW-BASE-TYPE><SHORT-NAME>{name}</SHORT-NAME>")
            xml.append(f"        <CATEGORY>FIXED_LENGTH</CATEGORY>")
            xml.append(f"        <BASE-TYPE-SIZE>{size}</BASE-TYPE-SIZE>")
            xml.append(f"        <BASE-TYPE-ENCODING>{enc}</BASE-TYPE-ENCODING>")
            xml.append(f"      </SW-BASE-TYPE>")
        xml.append("    </ELEMENTS></AR-PACKAGE>")
        xml.append("    <AR-PACKAGE><SHORT-NAME>ImplementationDataTypes</SHORT-NAME><ELEMENTS>")
        for dt in unique_types:
            name, size, enc = BASE_TYPE_ENCODING[dt]
            xml.append(f"      <IMPLEMENTATION-DATA-TYPE>")
            xml.append(f"        <SHORT-NAME>{name}_T</SHORT-NAME>")
            xml.append(f"        <CATEGORY>VALUE</CATEGORY>")
            xml.append(f"        <SW-DATA-DEF-PROPS><SW-DATA-DEF-PROPS-VARIANTS>")
            xml.append(f"          <SW-DATA-DEF-PROPS-CONDITIONAL>")
            xml.append(f'            <BASE-TYPE-REF DEST="SW-BASE-TYPE">/DataTypes/BaseTypes/{name}</BASE-TYPE-REF>')
            xml.append(f"          </SW-DATA-DEF-PROPS-CONDITIONAL>")
            xml.append(f"        </SW-DATA-DEF-PROPS-VARIANTS></SW-DATA-DEF-PROPS>")
            xml.append(f"      </IMPLEMENTATION-DATA-TYPE>")
            logger.debug("    %s -> %s_T", dt, dt)
        xml += [
            "    </ELEMENTS></AR-PACKAGE>",
            "  </AR-PACKAGES></AR-PACKAGE></AR-PACKAGES>",
            "</AUTOSAR>",
        ]
        self.dt_path.write_text("\n".join(xml), encoding="utf-8")
        logger.info("    Saved: %s (%d bytes)", self.dt_path.name, self.dt_path.stat().st_size)


    # ── interfaces.arxml ──────────────────────────────────────────────
    def _gen_interfaces(self):
        logger.info("  Generating interfaces.arxml ...")

        # Read datatypes into memory so we can pass node objects
        af.read([str(self.dt_path)])

        root_pack = af.new_file(
            str(self.if_path),
            defaultArPackage="Interfaces",
            overWrite=True,
        )

        for port in self.spec.ports:
            iface = root_pack.new_SenderReceiverInterface(port.interface_name)
            bvvp = af.BooleanValueVariationPoint()
            bvvp.set('false')
            iface.set_isService(bvvp)  # Required by MATLAB arxml.importer
            de = iface.new_DataElement(port.data_element)
            impl_type = af.get_node(
                f"/DataTypes/ImplementationDataTypes/{port.data_type}_T"
            )
            de.set_type(impl_type)
            logger.debug("    %s.%s -> %s_T",
                         port.interface_name, port.data_element, port.data_type)

        af.save([str(self.if_path)])
        self._fix_schema_version(self.if_path)
        logger.info("    Saved: %s (%d bytes)", self.if_path.name,
                    self.if_path.stat().st_size)

    # ── component.arxml ───────────────────────────────────────────────
    def _gen_component(self):
        logger.info("  Generating component.arxml ...")

        # Read interfaces (and datatypes) into memory for node references
        af.read([str(self.dt_path), str(self.if_path)])

        root_pack = af.new_file(
            str(self.comp_path),
            defaultArPackage="Components",
            overWrite=True,
        )

        swc = root_pack.new_ApplicationSwComponentType(self.spec.swc_name)
        logger.debug("    SWC: %s", self.spec.swc_name)

        for port in self.spec.ports:
            self._add_port(swc, port)

        ib = swc.new_InternalBehavior(f"{self.spec.swc_name}_IB")
        logger.debug("    InternalBehavior: %s_IB", self.spec.swc_name)

        for runnable in self.spec.runnables:
            self._add_runnable(ib, runnable, swc)

        af.save([str(self.comp_path)])
        self._fix_schema_version(self.comp_path)
        logger.info("    Saved: %s (%d bytes)", self.comp_path.name,
                    self.comp_path.stat().st_size)

    # ── Port helpers ──────────────────────────────────────────────────
    def _add_port(self, swc, port: PortSpec):
        # Fetch the actual SenderReceiverInterface node from memory
        iface_node = af.get_node(f"/Interfaces/{port.interface_name}")
        if port.direction == "P":
            p = swc.new_PPortPrototype(port.name)
            p.set_providedInterface(iface_node)
            logger.debug("    P-Port: %s", port.name)
        else:
            p = swc.new_RPortPrototype(port.name)
            p.set_requiredInterface(iface_node)
            logger.debug("    R-Port: %s", port.name)

    # ── Runnable helpers ──────────────────────────────────────────────
    def _add_runnable(self, ib, runnable: RunnableSpec, swc):
        # new_Runnable is the correct method name (not new_RunnableEntity)
        rbl = ib.new_Runnable(runnable.name)
        logger.debug("    Runnable: %s (period_ms=%d)",
                     runnable.name, runnable.period_ms)

        # Add data access elements for each port access
        for access in runnable.accesses:
            # Find the port in the SWC
            port = next((p for p in self.spec.ports if p.name == access.port), None)
            if port is None:
                logger.warning("Runnable %s accesses unknown port %s", runnable.name, access.port)
                continue

            # Debug: print available methods on runnable
            logger.debug("Runnable methods: %s", [m for m in dir(rbl) if 'new' in m][:5])

            # Try to create data access
            try:
                if access.mode == "read":
                    va = rbl.new_DataReadAcces(f"VA_{runnable.name}_{access.port}")
                else:
                    va = rbl.new_DataWriteAcces(f"VA_{runnable.name}_{access.port}")
                logger.debug("      Created DataAccess: %s", f"VA_{runnable.name}_{access.port}")
            except AttributeError as e:
                logger.warning("DataAccess creation failed: %s", e)
                continue

            # Set the accessed variable reference
            try:
                # Find the port in the SWC - need to get the VariableDataPrototype
                port = next((p for p in self.spec.ports if p.name == access.port), None)
                if port is None:
                    logger.warning("Runnable %s accesses unknown port %s", runnable.name, access.port)
                    continue
                
                # Create an AutosarVariable reference to the data element
                # Need to create a VariableInAtomicSWCTypeInstanceRef that references the port and data element
                var_ref = va.new_AccessedVariable()
                
                # Get the actual port object from the SWC
                port_obj = None
                for p in swc.get_ports():
                    if p.name == access.port:
                        port_obj = p
                        break
                
                if port_obj is None:
                    logger.warning("Could not find port object for %s", access.port)
                    continue
                
                # Get the data element from the interface
                data_elem_obj = af.get_node(f"/Interfaces/{port.interface_name}/{port.data_element}")
                
                # Create the variable reference
                var_instance_ref = af.VariableInAtomicSWCTypeInstanceRef()
                var_instance_ref.set_portPrototype(port_obj)
                var_instance_ref.set_targetDataPrototype(data_elem_obj)
                
                # Set the autosar variable to the instance reference
                var_ref.set_autosarVariable(var_instance_ref)
                logger.debug("      DataAccess: %s -> %s (%s)",
                             access.port, port.data_element, access.mode)
            except Exception as e:
                logger.warning("DataAccess setup failed: %s", e)

        if runnable.period_ms == -1:
            event = ib.new_InitEvent(f"IE_{runnable.name}")
            event.set_startOnEvent(rbl)
            logger.debug("      -> InitEvent")

        elif runnable.period_ms == 0:
            event = ib.new_BackgroundEvent(f"BGE_{runnable.name}")
            event.set_startOnEvent(rbl)
            logger.debug("      -> BackgroundEvent")

        else:
            period_s = runnable.period_ms / 1000.0
            event = ib.new_TimingEvent(f"TE_{runnable.name}")
            event.set_period(period_s)
            event.set_startOnEvent(rbl)
            logger.debug("      -> TimingEvent (%.3fs)", period_s)


    def _fix_schema_version(self, filepath: Path):
        """
        Downgrade ARXML schema version from 00053 to 00051 (R22-11).
        MATLAB R2025a supports up to 00051 / R23-11.
        autosarfactory latest defaults to 00053 which MATLAB rejects.
        """
        text = filepath.read_text(encoding='utf-8')
        text = text.replace('AUTOSAR_00053.xsd', 'AUTOSAR_00051.xsd')
        text = text.replace('AUTOSAR_00052.xsd', 'AUTOSAR_00051.xsd')
        filepath.write_text(text, encoding='utf-8')
        logger.debug('    Schema version fixed -> 00051: %s', filepath.name)

# ── Quick self-test (offline — no Claude API needed) ──────────────────
if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    print("\n== ARXMLGenerator self-test ==\n")

    from src.models import SWCSpec

    test_spec = SWCSpec(**{
        "swc_name": "SpeedSensor",
        "category": "APPLICATION",
        "ports": [
            {
                "name": "SpeedPort",
                "direction": "R",
                "interface_name": "SpeedSensorInterface",
                "data_element": "VehicleSpeed",
                "data_type": "uint16",
            }
        ],
        "runnables": [
            {
                "name": "Run10ms",
                "period_ms": 10,
                "accesses": [{"port": "SpeedPort", "mode": "read"}],
            },
            {
                "name": "InitSpeedSensor",
                "period_ms": -1,
                "accesses": [],
            },
        ],
        "init_runnable": "InitSpeedSensor",
    })

    out = Path("output") / "CanGateway"
    gen = ARXMLGenerator(test_spec, out)

    try:
        paths = gen.generate_all()
        print("\n[OK] Files generated:")
        for p in paths:
            print(f"     {p}  ({p.stat().st_size} bytes)")
        print("\nRESULT: PASSED")
        print(f"\nInspect the files:")
        for p in paths:
            print(f"  code {p}")
    except Exception as e:
        import traceback
        print(f"\n[FAIL] {type(e).__name__}: {e}")
        traceback.print_exc()
