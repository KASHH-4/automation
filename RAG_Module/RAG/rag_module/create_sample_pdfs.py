"""
create_sample_pdfs.py  (v2 — 10 industrial quotations)
-------------------------------------------------------
Generates 10 realistic industrial engineering quotation PDFs for pipeline testing.

Products covered:
  1. Pressure Vessel          6. Pipe Assembly
  2. Boiler                   7. Compressor
  3. Heat Exchanger           8. Reactor
  4. Storage Tank             9. Condenser
  5. Industrial Valve        10. Pump

Usage:
    python create_sample_pdfs.py

Output:
    data/quote_001_pressure_vessel.pdf
    data/quote_002_boiler.pdf
    ...  (10 files total)
"""

import os
from fpdf import FPDF
from config import DATA_DIR


# ── 10 Realistic industrial quotations ───────────────────────────────────────
QUOTATIONS = [
    {
        "filename"      : "quote_001_pressure_vessel.pdf",
        "quote_no"      : "QT-2024-0101",
        "date"          : "2024-01-10",
        "supplier"      : "Allied Fabricators Pvt. Ltd.",
        "customer"      : "Reliance Petrochemicals Ltd.",
        "contact"       : "Mr. Arjun Mehta",
        "email"         : "arjun.mehta@reliance-petro.com",
        "product"       : "Pressure Vessel (Vertical, ASME Sec VIII Div.1)",
        "material"      : "SA-516 Grade 70 Carbon Steel, 25mm shell thickness",
        "quantity"      : "2 units",
        "currency"      : "USD",
        "unit_price"    : "$38,500.00",
        "base_cost"     : "$77,000.00",
        "labour_cost"   : "$12,000.00",
        "total_cost"    : "$89,000.00",
        "delivery_time" : "18 weeks from order confirmation",
        "remarks"       : (
            "Design pressure: 15 bar (g) at 250°C operating temperature. "
            "ASME U-stamp certification included. NDT: 100% radiographic + UT weld inspection. "
            "Post Weld Heat Treatment (PWHT) required. Nozzle schedule per customer P&ID. "
            "Third-party inspection by Lloyd's Register. 2-year warranty on fabrication defects. "
            "Hydrostatic test at 1.5× design pressure. Painting: epoxy primer + polyurethane topcoat."
        ),
    },
    {
        "filename"      : "quote_002_boiler.pdf",
        "quote_no"      : "QT-2024-0102",
        "date"          : "2024-01-22",
        "supplier"      : "Thermax Industrial Systems",
        "customer"      : "Gujarat Cement Works",
        "contact"       : "Ms. Kavya Nair",
        "email"         : "kavya.nair@gcw-cement.com",
        "product"       : "Fire Tube Boiler (3-Pass, Scotch Marine Type)",
        "material"      : "IS 2002 Grade 2 Carbon Steel; seamless boiler tubes SA-192",
        "quantity"      : "1 unit",
        "currency"      : "INR",
        "unit_price"    : "₹42,00,000",
        "base_cost"     : "₹42,00,000",
        "labour_cost"   : "₹6,50,000",
        "total_cost"    : "₹48,50,000",
        "delivery_time" : "14 weeks (ex-works Pune)",
        "remarks"       : (
            "Steam output: 5 TPH at 10.5 kg/cm² saturated steam. "
            "Fuel: Natural gas (dual-fuel burner included). "
            "IBR certification mandatory — included in scope. "
            "Efficiency: ≥ 88% (NCV basis). Controls: Fully automatic PLC panel. "
            "Includes economiser, safety valves (×2), steam pressure gauge, water level gauge. "
            "Erection & commissioning charges extra at ₹1,20,000 lump sum."
        ),
    },
    {
        "filename"      : "quote_003_heat_exchanger.pdf",
        "quote_no"      : "QT-2024-0103",
        "date"          : "2024-02-05",
        "supplier"      : "HeatTech Engineering Solutions",
        "customer"      : "IOCL Mathura Refinery",
        "contact"       : "Dr. Sanjay Verma",
        "email"         : "s.verma@iocl-mathura.com",
        "product"       : "Shell & Tube Heat Exchanger (TEMA Type AES)",
        "material"      : "Shell: SA-106 Gr.B Carbon Steel; Tubes: SS304 (19mm OD, 16BWG)",
        "quantity"      : "3 units",
        "currency"      : "USD",
        "unit_price"    : "$22,400.00",
        "base_cost"     : "$67,200.00",
        "labour_cost"   : "$8,100.00",
        "total_cost"    : "$75,300.00",
        "delivery_time" : "16 weeks from PO and approved drawings",
        "remarks"       : (
            "Heat duty: 1.8 MW per unit. Shell-side fluid: crude oil at 180°C/12 bar. "
            "Tube-side fluid: cooling water at 32°C/6 bar. TEMA Class R construction. "
            "Tube bundle removable. Baffle cut: 25%. "
            "Hydrotest: Shell at 18 bar, tube-side at 9 bar. "
            "Nace MR0175 compliance for H2S service. "
            "Data book with drawings, MTCs, hydro test reports included."
        ),
    },
    {
        "filename"      : "quote_004_storage_tank.pdf",
        "quote_no"      : "QT-2024-0104",
        "date"          : "2024-02-18",
        "supplier"      : "EuroBuild Tank Fabricators",
        "customer"      : "Hindustan Oil Storage Corp.",
        "contact"       : "Mr. Ramesh Pillai",
        "email"         : "r.pillai@hosc.co.in",
        "product"       : "Atmospheric Fixed-Roof Storage Tank (API 650)",
        "material"      : "SA-283 Grade C Carbon Steel; bottom plate 8mm; shell 10mm",
        "quantity"      : "4 units",
        "currency"      : "USD",
        "unit_price"    : "$54,000.00",
        "base_cost"     : "$216,000.00",
        "labour_cost"   : "$28,500.00",
        "total_cost"    : "$244,500.00",
        "delivery_time" : "24 weeks (fabrication) + 6 weeks (site erection)",
        "remarks"       : (
            "Capacity: 5,000 KL per tank. Diameter: 20m, Height: 16m. "
            "Product: Diesel storage. API 650 Annex S (seismic zone II). "
            "Floating suction assembly included. Internal epoxy coating 250 microns DFT. "
            "External painting: zinc primer + epoxy + polyurethane (RAL 7035). "
            "Includes: vents, manhole (×2), staircase, roof platform, earthing bosses. "
            "Cathodic protection system extra at $3,200 per tank."
        ),
    },
    {
        "filename"      : "quote_005_industrial_valve.pdf",
        "quote_no"      : "QT-2024-0105",
        "date"          : "2024-03-01",
        "supplier"      : "FlowMaster Valve Industries",
        "customer"      : "ONGC Hazira Gas Plant",
        "contact"       : "Ms. Deepa Krishnamurthy",
        "email"         : "deepa.k@ongc-hazira.com",
        "product"       : "Gate Valve, Full Bore, Rising Stem (Class 600, RF Flanged)",
        "material"      : "Body: ASTM A216 WCB Carbon Steel; Trim: SS410; Seat: Stellite",
        "quantity"      : "50 units (assorted sizes: 2\" to 12\")",
        "currency"      : "USD",
        "unit_price"    : "$1,450.00 (average across sizes)",
        "base_cost"     : "$72,500.00",
        "labour_cost"   : "$3,200.00",
        "total_cost"    : "$75,700.00",
        "delivery_time" : "10 weeks from PO",
        "remarks"       : (
            "API 600 / API 6D design. Fire-safe per API 607. "
            "Pressure test: shell 1.5× CWP, seat 1.1× CWP per API 598. "
            "Fugitive emission test: ISO 15848 Class BH. "
            "Colour coding as per OISD-118. CE/PED marked (Directive 2014/68/EU). "
            "Certificates: EN 10204 3.1 MTCs, dimensional report, test certificates. "
            "Spare parts: gland packing (×3 sets per valve) included."
        ),
    },
    {
        "filename"      : "quote_006_pipe_assembly.pdf",
        "quote_no"      : "QT-2024-0106",
        "date"          : "2024-03-14",
        "supplier"      : "PipeTech Fabrication Works",
        "customer"      : "Tata Steel Processing Division",
        "contact"       : "Mr. Vikram Singh",
        "email"         : "v.singh@tata-steel-proc.com",
        "product"       : "Pre-Fabricated Pipe Spools (Carbon Steel, Various Schedules)",
        "material"      : "ASTM A106 Gr.B seamless; fittings: ASTM A234 WPB; flanges: ASTM A105",
        "quantity"      : "180 spool pieces (approx. 2,400 linear meters)",
        "currency"      : "INR",
        "unit_price"    : "₹4,800 per linear meter",
        "base_cost"     : "₹1,15,20,000",
        "labour_cost"   : "₹18,00,000",
        "total_cost"    : "₹1,33,20,000",
        "delivery_time" : "12 weeks in 3 batches (4 weeks per batch)",
        "remarks"       : (
            "Diameter range: 2\" NPS to 24\" NPS. Schedules: Sch 40, 80, 160. "
            "Welding: GTAW root + SMAW fill/cap. WPS/PQR as per ASME IX. "
            "NDT: 100% RT for sizes > 2\", PT/MT for fillet welds. "
            "Dimensional tolerance: ±1.5mm on spool lengths. "
            "Painting: 1 coat red-oxide primer shop-applied. "
            "Isometric drawings to be supplied by client; as-built spools provided."
        ),
    },
    {
        "filename"      : "quote_007_compressor.pdf",
        "quote_no"      : "QT-2024-0107",
        "date"          : "2024-04-02",
        "supplier"      : "Atlas Copco India Ltd.",
        "customer"      : "Bharat Heavy Electricals Ltd. (BHEL)",
        "contact"       : "Engr. Pradeep Rajan",
        "email"         : "p.rajan@bhel-turbine.com",
        "product"       : "Reciprocating Air Compressor (2-Stage, Water-Cooled)",
        "material"      : "Cast Iron cylinder block; Forged Steel crankshaft; SS valves",
        "quantity"      : "6 units",
        "currency"      : "USD",
        "unit_price"    : "$18,750.00",
        "base_cost"     : "$112,500.00",
        "labour_cost"   : "$9,600.00",
        "total_cost"    : "$122,100.00",
        "delivery_time" : "20 weeks from confirmed PO",
        "remarks"       : (
            "Free Air Delivery (FAD): 12 m³/min at 7 bar(g). Motor: 75 kW, IE3 efficiency class. "
            "Intercooler & aftercooler: SS tube bundles. "
            "Vibration mounts and baseframe included. "
            "ATEX Zone 2 certified option available at +8% cost. "
            "Spare parts kit (piston rings, valves, gaskets) included for 2-year operation. "
            "Annual maintenance contract available at $3,400/year per unit."
        ),
    },
    {
        "filename"      : "quote_008_reactor.pdf",
        "quote_no"      : "QT-2024-0108",
        "date"          : "2024-04-19",
        "supplier"      : "ChemFab Process Equipment Ltd.",
        "customer"      : "UPL Limited (Agrochemicals)",
        "contact"       : "Dr. Nilesh Patil",
        "email"         : "n.patil@upl-agro.com",
        "product"       : "Glass-Lined Stirred Reactor (Batch, 5000L)",
        "material"      : "CS shell with 2mm DIN 12116 borosilicate glass lining; SS316L agitator",
        "quantity"      : "2 units",
        "currency"      : "EUR",
        "unit_price"    : "€95,000.00",
        "base_cost"     : "€190,000.00",
        "labour_cost"   : "€22,000.00",
        "total_cost"    : "€212,000.00",
        "delivery_time" : "28 weeks from PO",
        "remarks"       : (
            "Design pressure: FV to 6 bar(g). Jacket design: 3 bar(g) at 150°C. "
            "Glass lining porosity test per DIN 12116 to be performed. "
            "Agitator: anchor type, 55 kW gearbox-driven. Seal: double mechanical, SS316L. "
            "Nozzle connections: GL flanges per DIN 2501. "
            "Includes: rupture disc, safety valve, sight glass, dip pipe, sample valve. "
            "CE-PED marked. Documentation: DIN 12116 lining test cert, pressure test cert, GA drawing."
        ),
    },
    {
        "filename"      : "quote_009_condenser.pdf",
        "quote_no"      : "QT-2024-0109",
        "date"          : "2024-05-06",
        "supplier"      : "CoolTech Heat Transfer Pvt. Ltd.",
        "customer"      : "NTPC Vindhyachal Super Thermal Power Station",
        "contact"       : "Mr. Ashok Kumar",
        "email"         : "ashok.k@ntpc-vindhya.com",
        "product"       : "Surface Condenser (Steam Turbine Exhaust Condenser)",
        "material"      : "Shell: SA-285 Gr.C Carbon Steel; Tubes: Titanium Grade 2 (25mm OD, 18BWG)",
        "quantity"      : "1 unit",
        "currency"      : "USD",
        "unit_price"    : "$380,000.00",
        "base_cost"     : "$380,000.00",
        "labour_cost"   : "$42,000.00",
        "total_cost"    : "$422,000.00",
        "delivery_time" : "36 weeks from approved GA drawing",
        "remarks"       : (
            "Steam load: 280 TPH. Absolute pressure: 0.1 bar. Heat duty: 195 MW. "
            "Cooling water flow: 22,000 m³/hr at 28°C inlet. "
            "Tube material titanium for seawater/brackish cooling water service. "
            "HEI standards for steam surface condensers. "
            "Includes: hotwell, air-ejector connections, expansion joint. "
            "Delivery to site in 3 modules; site assembly and hydro test by OEM team."
        ),
    },
    {
        "filename"      : "quote_010_pump.pdf",
        "quote_no"      : "QT-2024-0110",
        "date"          : "2024-05-20",
        "supplier"      : "Kirloskar Brothers Ltd.",
        "customer"      : "Mahanagar Gas Ltd.",
        "contact"       : "Ms. Anita Desai",
        "email"         : "a.desai@mahanagar-gas.com",
        "product"       : "Horizontal Centrifugal Pump (BB2 Type, API 610 11th Edition)",
        "material"      : "Casing: ASTM A216 WCB; Impeller: CD4MCu Duplex SS; Shaft: AISI 4140",
        "quantity"      : "4 units (2 operating + 2 standby)",
        "currency"      : "USD",
        "unit_price"    : "$28,200.00",
        "base_cost"     : "$112,800.00",
        "labour_cost"   : "$11,500.00",
        "total_cost"    : "$124,300.00",
        "delivery_time" : "22 weeks from PO and approved datasheet",
        "remarks"       : (
            "Flow: 450 m³/hr. Head: 180m. Fluid: LPG condensate at -10°C. "
            "API 610 BB2 single-stage between-bearing design. "
            "Seal: API Plan 53B dual pressurised mechanical seal. "
            "Driver: 315 kW, 2-pole induction motor, Ex-d ATEX Zone 1. "
            "Coupling: API 671 flexible disc type. Baseplate: API 686 grouted type. "
            "Performance test at OEM works per API 610 Annex H. Factory acceptance test (FAT) included."
        ),
    },
]


class QuotationPDF(FPDF):
    """Custom FPDF subclass with branded header and footer."""

    def header(self):
        self.set_fill_color(15, 23, 42)          # slate-900
        self.rect(0, 0, 210, 20, style="F")
        self.set_font("Helvetica", "B", 12)
        self.set_text_color(248, 250, 252)
        self.set_xy(10, 5)
        self.cell(130, 10, "AI PROPOSAL INTELLIGENCE SYSTEM", align="L")
        self.set_font("Helvetica", "", 9)
        self.set_text_color(148, 163, 184)
        self.set_xy(140, 5)
        self.cell(0, 10, "Industrial Equipment Quotation", align="R")
        self.set_text_color(0, 0, 0)
        self.ln(18)

    def footer(self):
        self.set_y(-14)
        self.set_font("Helvetica", "I", 7.5)
        self.set_text_color(120, 120, 120)
        self.cell(0, 10,
                  f"Page {self.page_no()}  |  Confidential & Proprietary  |  AI Proposal Intelligence System",
                  align="C")


def _section(pdf: QuotationPDF, title: str) -> None:
    pdf.set_fill_color(30, 58, 138)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "B", 9)
    pdf.cell(0, 7, f"  {title}", fill=True, ln=True)
    pdf.set_text_color(0, 0, 0)
    pdf.ln(1)


def _row(pdf: QuotationPDF, label: str, value: str, alt: bool = False) -> None:
    fill_color = (241, 245, 249) if alt else (255, 255, 255)
    pdf.set_fill_color(*fill_color)
    pdf.set_font("Helvetica", "B", 8.5)
    pdf.cell(52, 7, f"  {label}", fill=True, border="B")
    pdf.set_font("Helvetica", "", 8.5)
    pdf.multi_cell(0, 7, value, fill=True, border="B")


def create_pdf(q: dict, output_dir: str) -> str:
    pdf = QuotationPDF()
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.add_page()
    pdf.set_margins(12, 24, 12)

    # Title
    pdf.set_font("Helvetica", "B", 15)
    pdf.set_text_color(15, 23, 42)
    pdf.cell(0, 9, "COMMERCIAL QUOTATION", ln=True, align="C")
    pdf.set_font("Helvetica", "", 8.5)
    pdf.set_text_color(71, 85, 105)
    pdf.cell(0, 5,
             f"Quote No: {q['quote_no']}    |    Date: {q['date']}    |    Supplier: {q['supplier']}",
             ln=True, align="C")
    pdf.set_text_color(0, 0, 0)
    pdf.ln(5)

    # Customer
    _section(pdf, "1.  CUSTOMER INFORMATION")
    _row(pdf, "Customer Name",  q["customer"],  alt=True)
    _row(pdf, "Contact Person", q["contact"],   alt=False)
    _row(pdf, "Email Address",  q["email"],     alt=True)
    pdf.ln(4)

    # Product
    _section(pdf, "2.  PRODUCT DETAILS")
    _row(pdf, "Product / Equipment", q["product"],   alt=True)
    _row(pdf, "Material of Construction", q["material"], alt=False)
    _row(pdf, "Quantity",           q["quantity"],  alt=True)
    pdf.ln(4)

    # Pricing
    _section(pdf, "3.  PRICING BREAKDOWN")
    _row(pdf, "Currency",       q["currency"],      alt=True)
    _row(pdf, "Unit Price",     q["unit_price"],    alt=False)
    _row(pdf, "Base / Material Cost", q["base_cost"], alt=True)
    _row(pdf, "Labour Cost",    q["labour_cost"],   alt=False)
    _row(pdf, "TOTAL COST",     q["total_cost"],    alt=True)
    _row(pdf, "Delivery Time",  q["delivery_time"], alt=False)
    pdf.ln(4)

    # Remarks
    _section(pdf, "4.  TECHNICAL REMARKS & TERMS")
    pdf.set_font("Helvetica", "", 8.5)
    pdf.multi_cell(0, 6, q["remarks"])
    pdf.ln(6)

    # Signature
    pdf.set_font("Helvetica", "I", 8)
    pdf.set_text_color(100, 100, 100)
    pdf.cell(0, 5,
             "Authorised Signatory: _______________________    Date: ________________    Seal:",
             ln=True)

    out = os.path.join(output_dir, q["filename"])
    pdf.output(out)
    return out


def main() -> None:
    os.makedirs(DATA_DIR, exist_ok=True)
    print(f"\nGenerating {len(QUOTATIONS)} industrial quotation PDFs → {DATA_DIR}\n")
    for q in QUOTATIONS:
        path = create_pdf(q, DATA_DIR)
        print(f"  ✔  {q['filename']}")
    print(f"\nDone. Run  python build_index.py  to index these documents.\n")


if __name__ == "__main__":
    main()
