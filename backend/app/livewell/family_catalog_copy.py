"""Plain-language words for the family catalog (Requests page, Score & plan).

One line per catalog code saying what the item does for the parent — not how it is
built. Ops keeps its own technical description; families see these. Codes not listed
fall back to the ops description.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

BLURBS: dict[str, str] = {
    # Kushalaya services
    "SVC-001": "We visit, check every room and give you a safety score and a clear report.",
    "SVC-002": "We make the bathroom safe in one go: grab bars, anti-slip floor and more.",
    "SVC-003": "We make the bedroom safer for getting in and out of bed at night.",
    "SVC-004": "A detailed follow-up check of the whole home, with a report for you.",
    "SVC-005": "We set up the alert device and add your numbers, so help reaches you fast.",
    # Bathroom
    "BTH-001": "A strong bar to hold while sitting down and standing up.",
    "BTH-002": "Steady support for standing up and stepping in and out of the shower.",
    "BTH-003": "A grab bar that folds away — good for small bathrooms and wheelchairs.",
    "BTH-004": "Floor-fixed support for walls that can't hold a normal grab bar.",
    "BTH-005": "Lets your parent sit while bathing, so there's no need to balance.",
    "BTH-006": "Raises the toilet seat so sitting down and getting up is easier.",
    "BTH-007": "Arms around the toilet to push up from and steady themselves.",
    "BTH-008": "Makes wet bathroom floors far less slippery.",
    "BTH-009": "Grip strips on wet spots for a quick, low-cost slip fix.",
    "BTH-010": "A shower on a hose so bathing seated is easy.",
    "BTH-011": "Stops water getting too hot, so there are no scalds.",
    "BTH-012": "Sit outside the shower and slide in safely.",
    "BTH-013": "Clears steam so floors and mirrors stay dry.",
    # Bedroom
    "BED-001": "A rail beside the bed to hold when getting up and to stop rolling out.",
    "BED-002": "A bed that raises the head and legs for comfort and easier getting up.",
    "BED-003": "Lifts the bed so sitting down and standing up take less effort.",
    "BED-004": "Lights the way automatically for night-time trips to the bathroom.",
    "BED-005": "A soft mat beside the bed that cushions a fall.",
    # Living room
    "LIV-001": "A table with rounded edges, so a fall against it hurts less.",
    "LIV-002": "Soft covers on sharp furniture corners.",
    "LIV-003": "Keeps rugs from sliding, so they don't cause trips.",
    "LIV-004": "A steady chair that helps your parent sit and stand with less effort.",
    # Entry and exterior
    "EXT-001": "A firm handrail for the front steps and stairs.",
    "EXT-002": "A gentle slope over steps for a walker or wheelchair.",
    "EXT-003": "Lights the entrance when someone walks up after dark.",
    "EXT-004": "A sun-powered light outside that works even in a power cut.",
    # Hallway
    "HAL-001": "Turns on by itself when your parent walks by at night.",
    "HAL-002": "Soft low lighting along the floor so the path is always visible.",
    "HAL-003": "A rail along the hallway to hold while walking.",
    # Kitchen
    "KIT-001": "Brings high shelves down to reach, so no climbing on stools.",
    "KIT-002": "A turntable that makes things at the back easy to reach.",
    "KIT-003": "Sounds an alarm if cooking gas leaks.",
    "KIT-004": "Sounds an early alarm if there's smoke.",
    "KIT-005": "A small extinguisher to put out a kitchen fire fast.",
    "KIT-006": "Warns of carbon monoxide, an invisible gas from stoves and heaters.",
    # Balcony
    "BAL-001": "Makes a wet balcony floor less slippery.",
    "BAL-002": "A higher, stronger balcony railing.",
    # Mobility
    "MOB-001": "A steady frame to lean on while walking.",
    "MOB-002": "A walker on wheels with brakes and a seat to rest.",
    "MOB-003": "For longer distances, outings and hospital visits.",
    "MOB-004": "A light chair for moving your parent safely between rooms.",
    "MOB-005": "A simple stick for a little extra balance.",
    "MOB-006": "A cane with four feet that stands on its own and grips better.",
    "MOB-007": "A ramp you can carry and place over steps when needed.",
    # Smart home
    "SMT-001": "See and talk to whoever is at the door from your phone.",
    "SMT-002": "Opens without a key, and lets help in during an emergency.",
    "SMT-003": "A camera so you can check in on your parent from your phone.",
    "SMT-004": "Notices movement at home and alerts you if all is quiet too long.",
    "SMT-005": "Tells you when a door is opened, for example at night.",
    "SMT-006": "A wrist band with an SOS button; a press or a fall alerts you at once.",
    "SMT-007": "Reminds your parent to take medicines on time.",
    "SMT-008": "Call family, set reminders and get help just by speaking.",
    "SMT-009": "Warns you early about a water leak before floors get slippery.",
    "SMT-010": "A smoke alarm that also alerts your phone.",
    "SMT-011": "A press-for-help button in the bathroom, bedroom or living room.",
    "SMT-012": "Shows where your parent is and alerts you if they wander off.",
    # Emergency
    "EMG-001": "Key phone numbers on the wall, for your parent and any helper.",
    "EMG-002": "A stocked kit for cuts, burns and small injuries.",
    "EMG-003": "A bright torch ready for power cuts.",
    "EMG-004": "Comes on by itself when the power goes.",
    "EMG-005": "Medical details in one folder, ready for doctors and ambulances.",
    "EMG-006": "A phone with big buttons and photo speed-dial for family.",
    # Health devices
    "HLT-001": "Check blood pressure at home with one button.",
    "HLT-002": "Clips on a finger to check oxygen and pulse.",
    "HLT-003": "Check blood sugar at home; starter strips included.",
    "HLT-004": "Morning, noon and night boxes for the week, so no dose is missed.",
    # Care and wellness
    "WEL-001": "A caregiver checks on your parent, helps with medicines and updates you.",
    "WEL-002": "Friendly company — a chat, a walk, a game — so your parent feels less alone.",
    "WEL-003": "We collect medicines from the pharmacy and bring them home.",
    "WEL-004": "Someone goes with your parent to the doctor and tells you what was said.",
    "WEL-005": "We do the grocery shopping and bring it home.",
    "WEL-006": "We set up video calls so your parent can see and talk to family.",
    "WEL-007": "Gentle help with bathing and personal care.",
    "WEL-008": "A caregiver at home for the day (10 hours).",
    "WEL-009": "A caregiver who lives in and helps day and night.",
    "WEL-010": "One Family Partner who plans and checks all of your parent's care.",
    "WEL-011": "An attendant for a few hours of help with daily tasks.",
    "WEL-012": "Help with insurance, pension and government schemes.",
    "WEL-013": "We set up your parent's phone and show them how to use it.",
    "WEL-014": "Alarms, sensors and alerts set up together, so you can relax.",
    # Home maintenance
    "HM-001": "An electrician checks wiring and switches for shocks and fire risks.",
    "HM-002": "A plumber checks for leaks and wet floors before they cause trouble.",
    "HM-003": "A handyman for small fixes around the house.",
    "HM-004": "A plumber to fix a leak or blockage.",
    "HM-005": "An electrician to fix a fault, light or socket.",
    "HM-006": "A carpenter for doors, cupboards and furniture.",
    "HM-007": "A technician to repair a fridge, washing machine or other appliance.",
    "HM-008": "Keeps the home free of pests.",
    "HM-009": "A thorough clean of the whole home.",
    "HM-010": "A cleaned, serviced AC that cools well.",
    # Nursing
    "NUR-001": "A nurse checks vitals and helps with medicines and ongoing conditions.",
    "NUR-002": "A nurse at home for the day (10 hours).",
    "NUR-003": "A nurse at home round the clock.",
    "NUR-004": "A nurse gives the injection at home — no trip to the clinic.",
    "NUR-005": "A nurse cleans and dresses wounds at home.",
    "NUR-006": "A nurse changes the catheter at home.",
    "NUR-007": "A nurse gives an IV drip at home.",
    # Physiotherapy
    "PHY-001": "A physiotherapist checks movement and plans the exercises.",
    "PHY-002": "Exercises at home for walking, balance and getting up safely.",
    "PHY-003": "Regular physiotherapy at home for a month.",
    # Doctor and diagnostics
    "DX-001": "A doctor comes home to see your parent.",
    "DX-002": "Blood is taken at home for lab tests — no waiting at the lab.",
    "DX-003": "A set of lab tests, sample taken at home.",
    "DX-004": "A heart check (ECG) done at home.",
    # Property management
    "PM-001": "A monthly walk-round of the home to catch problems early.",
    "PM-002": "We make sure electricity, water and other bills are paid on time.",
    "PM-003": "We watch over contractors so the work is done right.",
    "PM-004": "We manage a renovation from start to finish.",
    # Transport
    "TRN-001": "A safe ride to the hospital or clinic.",
    "TRN-002": "Someone goes with your parent to the hospital and stays with them.",
    "TRN-003": "Help at the airport, from the car to the gate.",
}


# The original products seeded without a catalog code.
NAME_BLURBS: dict[str, str] = {
    "Anti-slip bath mat": "A mat that grips the wet floor so feet don't slide.",
    "Bathroom emergency pull cord": "A cord to pull for help after a fall in the bathroom.",
}


def blurb_for(code: str | None, name: str, fallback: str) -> str:
    return BLURBS.get(code or "") or NAME_BLURBS.get(name) or fallback


@lru_cache(maxsize=1)
def _price_labels() -> dict[str, str]:
    raw = json.loads((Path(__file__).parent / "default_catalog.json").read_text(encoding="utf-8"))["products"]
    return {p["product_code"]: (p.get("price_label") or "").strip() for p in raw if p.get("product_code")}


def unit_for(code: str | None) -> str:
    """How a service is charged, in plain words: "per visit", "per day"... ("" for one-off items)."""
    label = _price_labels().get(code or "", "")
    if not label.lower().startswith("per "):
        return ""
    return label.split("(")[0].strip().lower()


def included_for(code: str | None, kind: str) -> str:
    """One honest line on what the price covers."""
    label = _price_labels().get(code or "", "").lower()
    if "parts" in label or "materials" in label:
        return "Visit charge only — any parts are quoted on the spot."
    if "tests" in label:
        return "Collection charge only — tests are priced separately."
    if kind == "product" or label.startswith("installed"):
        return "Supplied and fitted at home by our trained team."
    return "Arranged and checked by your KushAlaya care team."
