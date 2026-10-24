import os
import json
import re
import time
import urllib.request
import urllib.parse
from datetime import datetime, timezone

# ==========================================
# ENVIRONMENT CONFIGURATION
# ==========================================
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "").strip()
SITE_BASE_URL = os.environ.get("SITE_BASE_URL", "https://hanifsalman11.github.io/compressor-cfm-index").rstrip("/")
INDEXNOW_KEY = os.environ.get("INDEXNOW_KEY", "d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9").strip()
CUSTOM_TOOL = os.environ.get("CUSTOM_TOOL", "").strip()
PAGES_PER_RUN = int(os.environ.get("PAGES_PER_RUN", "3"))

DOCS_DIR = "docs"
DATA_DIR = "data"
PUBLISHED_FILE = os.path.join(DATA_DIR, "published_tools.json")
MONETIZATION_FILE = os.path.join(DATA_DIR, "monetization.json")

# Format: (Tool / Compressor Name, Continuous CFM @ 90 PSI, Tool Duty Cycle %, Working PSI, Rec Tank Gal, Rec HP)
SEED_TOOLS = [
    ("HVLP Automotive Paint Spray Gun", 13.5, 85, 40, 60, 5.0),
    ("6-Inch Dual-Action (DA) Orbital Air Sander", 16.0, 90, 90, 60, 5.0),
    ("Abrasive Media Sandblasting Cabinet (1/4 Nozzle)", 18.5, 95, 90, 80, 7.5),
    ("1/2-Inch Heavy-Duty Pneumatic Impact Wrench", 5.5, 25, 90, 26, 2.0),
    ("CNC & Handheld Air Plasma Cutter (45A–65A)", 6.5, 80, 90, 60, 3.5),
    ("1/4-Inch High-Speed Pneumatic Die Grinder", 14.0, 70, 90, 60, 5.0),
    ("3-Inch Pneumatic Cut-Off Wheel Tool", 13.0, 65, 90, 60, 5.0),
    ("Pneumatic Long-Board Inline Straight Sander", 14.5, 85, 90, 60, 5.0),
    ("LVLP (Low Volume Low Pressure) Paint Spray Gun", 7.5, 80, 30, 30, 2.5),
    ("3/4-Inch Semi-Truck Heavy Impact Wrench", 11.0, 30, 90, 60, 3.5),
    ("Pneumatic Air Hammer & Chisel Scaler", 8.5, 50, 90, 30, 3.0),
    ("Pneumatic Needle Scaler Rust Remover", 9.0, 75, 90, 40, 3.5),
    ("3/8-Inch Automotive Air Ratchet Wrench", 4.5, 25, 90, 20, 1.5),
    ("Framing & Roofing Pneumatic Nail Gun Set", 3.2, 35, 90, 10, 1.5),
    ("Pneumatic Drywall Texture Hopper Gun", 7.0, 75, 45, 30, 2.5),
    ("1-Inch Commercial Tire Shop Impact Wrench", 16.5, 35, 110, 80, 5.0),
    ("Pneumatic Air Belt Sander (3/8 x 13 Inch)", 11.5, 70, 90, 40, 3.5),
    ("Automotive Undercoating & Bedliner Spray Gun", 8.0, 70, 60, 30, 2.5),
    ("Tornador Car Detailing Interior Cleaning Gun", 6.5, 75, 85, 30, 2.5),
    ("Ingersoll Rand SS5L5 60-Gallon 5HP Compressor", 18.1, 100, 90, 60, 5.0),
    ("Ingersoll Rand 2475N7.5 80-Gallon 7.5HP Two-Stage", 24.0, 100, 90, 80, 7.5),
    ("Quincy QT-54 60-Gallon 5HP Two-Stage Compressor", 15.2, 100, 90, 60, 5.0),
    ("California Air Tools 8010A 8-Gallon Ultra-Quiet", 2.2, 70, 90, 8, 1.0),
    ("California Air Tools 20020AD 20-Gallon 2HP Quiet", 5.3, 80, 90, 20, 2.0),
    ("DeWalt DXCMV5048055 80-Gallon 5HP Two-Stage", 17.0, 100, 90, 80, 5.0),
    ("DeWalt DXCM601 60-Gallon 3.7HP Vertical Compressor", 11.5, 85, 90, 60, 3.7),
    ("Fortress 27-Gallon 200 PSI High-Performance Vertical", 5.1, 75, 90, 27, 1.6),
    ("McGraw 29-Gallon 2HP 165 PSI Oil-Lube Compressor", 5.9, 75, 90, 29, 2.0),
    ("Campbell Hausfeld XC802100 80-Gallon Two-Stage", 14.0, 90, 90, 80, 5.0),
    ("Eastwood Elite QST 30/60 Scroll Air Compressor", 12.7, 100, 90, 60, 4.0)
]


def load_json(filepath, default):
    if os.path.exists(filepath):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[WARN] Could not parse {filepath}: {e}")
    return default


def save_json(filepath, data):
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def slugify(text):
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9\s-]", "", text)
    return re.sub(r"[\s-]+", "-", text).strip("-")


def safe_float(val, default=10.0):
    try:
        cleaned = re.sub(r"[^0-9.]", "", str(val))
        return float(cleaned) if cleaned else float(default)
    except Exception:
        return float(default)


def build_amazon_url(search_keywords, mon_cfg):
    domain = mon_cfg.get("marketplace_domain", "www.amazon.com")
    tag = mon_cfg.get("amazon_associate_tag", "YOUR_AMAZON_TAG-20")
    encoded_q = urllib.parse.quote_plus(search_keywords)
    return f"https://{domain}/s?k={encoded_q}&tag={tag}"


def discover_google_compressor_queries():
    """Mengambil kueri kalkulator CFM alat angin & ukuran kompresor dari Google Autocomplete US."""
    discovered = []
    seeds = [
        "what size air compressor for ",
        "air compressor cfm calculator for ",
        "how many cfm for ",
        "ingersoll rand "
    ]
    for seed in seeds:
        try:
            url = f"http://suggestqueries.google.com/complete/search?client=firefox&hl=en&gl=us&q={urllib.parse.quote(seed)}"
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=8) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                for suggestion in data[1]:
                    cleaned = suggestion.lower()
                    for pref in seeds:
                        cleaned = cleaned.replace(pref, "")
                    cleaned = re.sub(
                        r"\b(calculator|size|sizing|cfm|requirements|for|how|many)\b",
                        "",
                        cleaned
                    ).strip()
                    if 5 <= len(cleaned) <= 42:
                        discovered.append((cleaned.title(), 11.5, 75, 90, 60, 3.7))
        except Exception as e:
            print(f"[WARN] Google Suggest notice: {e}")
    return discovered


def build_deterministic_cfm_data(tool_tuple):
    """Mesin Fisika Termodinamika Udara Bertekanan & Hukum Boyle (100% bebas gagal)."""
    item_name, raw_cfm, duty_pct, work_psi, tank_gal, rec_hp = tool_tuple

    # Effective CFM dengan duty cycle + 25% safety headroom (agar pompa kompresor tidak overheat)
    effective_cfm = round(raw_cfm * (duty_pct / 100.0), 1)
    recommended_compressor_cfm = round(effective_cfm * 1.25, 1)

    # Boyle's Law Usable Air Volume (dalam Cubic Feet) saat tekanan turun dari 150 PSI (Cut-Out) ke 90 PSI (Cut-In):
    # 1 Galon AS = 0.133681 cu ft. Delta P = 60 PSI / 14.7 PSI atm = 4.0816 atm
    tank_cuft = tank_gal * 0.133681
    usable_reserve_cuft = round(tank_cuft * ((150.0 - 90.0) / 14.7), 1)
    # Waktu cadangan tangki murni sebelum motor kompresor menyala (detik)
    reserve_seconds = int(round((usable_reserve_cuft / max(1.0, raw_cfm)) * 60.0))

    hose_id = "1/2-Inch ID High-Flow" if raw_cfm >= 12.0 else "3/8-Inch ID Hybrid Polymer"

    return {
        "tool_name": item_name,
        "seo_title": f"{item_name} CFM @ 90 PSI, Tank Size & Compressor Calculator (2026)",
        "meta_description": f"Calculate exact continuous SCFM ({recommended_compressor_cfm} CFM recommended), tank drawdown reserve ({reserve_seconds}s on {tank_gal} Gal), and HP sizing for {item_name}.",
        "specs": {
            "continuous_cfm_90psi": raw_cfm,
            "tool_duty_cycle_pct": duty_pct,
            "working_psi": work_psi,
            "recommended_compressor_cfm": recommended_compressor_cfm,
            "recommended_tank_gallons": tank_gal,
            "recommended_motor_hp": rec_hp,
            "recommended_hose_id": hose_id,
            "tank_reserve_seconds": reserve_seconds
        },
        "thermodynamic_verdict": f"Operating at full trigger, the {item_name} consumes {raw_cfm} SCFM at {work_psi} PSI ({duty_pct}% typical duty cycle = {effective_cfm} average CFM). Applying the compressed-air engineering 1.25x safety margin so your pump does not exceed a 70% duty cycle, pair this setup with at least a {rec_hp} HP ({tank_gal}-Gallon) air compressor rated for {recommended_compressor_cfm}+ CFM @ 90 PSI and plumbed with {hose_id} air hose.",
        "hardware_bundle": [
            {
                "badge": f"{tank_gal}-Gal / {rec_hp} HP Compressor",
                "title": f"{tank_gal}-Gallon {rec_hp} HP High-CFM Shop Air Compressor ({recommended_compressor_cfm}+ CFM @ 90 PSI)",
                "price_range": "$399 - $1,899",
                "amazon_query": f"{tank_gal} Gallon {rec_hp} HP Air Compressor Two Stage Quiet",
                "air_note": f"Provides {usable_reserve_cuft} cubic feet of pressurized reserve air between 150 PSI cut-out and 90 PSI cut-in."
            },
            {
                "badge": "3-Stage Desiccant Dryer",
                "title": "1/2\" NPT 3-Stage Industrial Air Drying System (Water Separator, 0.01μm Coalescing & Desiccant Dryer)",
                "price_range": "$89 - $249",
                "amazon_query": "1/2 NPT 3 Stage Air Drying System Desiccant Dryer Regulator",
                "air_note": "High-CFM compression heats air and condenses gallons of water; a 3-stage dryer prevents moisture fisheyes in paint and internal tool rust."
            },
            {
                "badge": f"{hose_id} Reel",
                "title": f"50ft Auto-Rewind Retractable {hose_id} Air Hose Reel + Milton V-Style High-Flow Fittings",
                "price_range": "$74 - $169",
                "amazon_query": "50ft Retractable Air Hose Reel 3/8 1/2 Hybrid Milton V Style High Flow",
                "air_note": f"Standard 1/4\" hoses and M-style fittings choke flow by up to 18 PSI under a {raw_cfm} CFM load; V-style high-flow couplers eliminate pressure drop."
            },
            {
                "badge": "Pneumatic Tool & Lube",
                "title": f"Pro-Grade {item_name} & Pneumatic Air Tool Oil Maintenance Kit",
                "price_range": "$69 - $389",
                "amazon_query": f"{item_name} Pneumatic Air Tool",
                "air_note": f"Engineered for {work_psi} PSI dynamic dynamic pressure with low-vibration ergonomic housing."
            }
        ],
        "shop_checklist": [
            f"Measure dynamic pressure right at the tool inlet with the trigger pulled: a 50ft 1/4\" hose drops pressure by 15–22 PSI at {raw_cfm} CFM. Upgrade to {hose_id} hose and High-Flow V-Style couplers.",
            "Mount your coalescing water trap and desiccant dryer at least 20 to 25 feet downstream from the compressor pump (via copper or aluminum air piping) so hot compressed air cools and condenses before reaching the filter.",
            "Size your compressor's continuous CFM @ 90 PSI rating at 1.25x your tool's average CFM consumption; running a single-stage pump 100% continuously overheats reed valves and piston rings.",
            "Install an automatic electronic timed tank drain valve at the bottom of your receiver tank to purge condensed water every 30 minutes of operation."
        ],
        "faqs": [
            {
                "q": f"How many CFM and what size tank do I need for {item_name}?",
                "a": f"The {item_name} draws {raw_cfm} CFM continuously ({effective_cfm} CFM at a {duty_pct}% work cycle). To prevent waiting for the tank to pump up, use a {tank_gal}-gallon ({rec_hp} HP) compressor delivering at least {recommended_compressor_cfm} CFM at 90 PSI."
            },
            {
                "q": f"How long will a {tank_gal}-gallon tank run {item_name} before dropping below 90 PSI?",
                "a": f"By Boyle's Law, a {tank_gal}-gallon tank dropping from 150 PSI to 90 PSI releases {usable_reserve_cuft} cubic feet of free air. Without the motor running, that reserve alone powers a {raw_cfm} CFM load for {reserve_seconds} seconds—after which your compressor pump motor must keep pace with the {effective_cfm} CFM demand."
            },
            {
                "q": f"Why does my {item_name} lose power after 15 seconds even when the tank gauge reads 120 PSI?",
                "a": f"That is caused by restrictive 1/4-inch hoses and standard 1/4\" industrial M-style quick-disconnects, which bottleneck airflow to ~6–8 CFM. Switching to {hose_id} hose and 1/4\" High-Flow V-Style (or 3/8\" body) couplers restores full torque and RPM."
            }
        ]
    }


def generate_cfm_data(tool_tuple):
    """Memanggil Gemini 2.5 Flash API; jika gagal otomatis memakai Deterministic Boyle's Law Engine."""
    if not GEMINI_API_KEY:
        return build_deterministic_cfm_data(tool_tuple)

    item_name, raw_cfm, duty_pct, work_psi, tank_gal, rec_hp = tool_tuple
    effective_cfm = round(raw_cfm * (duty_pct / 100.0), 1)
    rec_cfm = round(effective_cfm * 1.25, 1)
    usable_cuft = round((tank_gal * 0.133681) * ((150.0 - 90.0) / 14.7), 1)
    reserve_sec = int(round((usable_cuft / max(1.0, raw_cfm)) * 60.0))

    prompt = f"""
You are a Senior Compressed Air Systems & Pneumatic Mechanical Engineer (Compressed Air & Gas Institute - CAGI Specialist). Create an accurate 2026 CFM @ 90 PSI, tank drawdown, and compressor sizing guide for: "{item_name}".
Baseline reference specs: Continuous Draw={raw_cfm} CFM @ {work_psi} PSI, Duty Cycle={duty_pct}%, Recommended Compressor Output={rec_cfm} CFM @ 90 PSI, Tank={tank_gal} Gallons, Motor={rec_hp} HP, Tank Reserve Drawdown (150 to 90 PSI)={reserve_sec} seconds.
Return ONLY a valid JSON object matching this exact schema:
{{
  "tool_name": "{item_name}",
  "seo_title": "{item_name} CFM @ 90 PSI, Tank Size & Compressor Calculator (2026)",
  "meta_description": "Calculate exact continuous SCFM, Boyle's Law tank drawdown time, and air compressor HP/Gallon sizing for {item_name}.",
  "specs": {{
    "continuous_cfm_90psi": {raw_cfm},
    "tool_duty_cycle_pct": {duty_pct},
    "working_psi": {work_psi},
    "recommended_compressor_cfm": {rec_cfm},
    "recommended_tank_gallons": {tank_gal},
    "recommended_motor_hp": {rec_hp},
    "recommended_hose_id": "3/8-Inch or 1/2-Inch ID",
    "tank_reserve_seconds": {reserve_sec}
  }},
  "thermodynamic_verdict": "3-sentence technical summary stating continuous CFM, duty cycle, 1.25x safety buffer CFM, and recommended tank gallons/HP.",
  "hardware_bundle": [
    {{
      "badge": "Matched Air Compressor",
      "title": "Exact Gallon & HP Two-Stage or Ultra-Quiet Air Compressor recommendation",
      "price_range": "$429 - $1,899",
      "amazon_query": "{tank_gal} Gallon {rec_hp} HP Air Compressor",
      "air_note": "1-sentence CFM @ 90 PSI output note"
    }},
    {{
      "badge": "3-Stage Desiccant Dryer",
      "title": "1/2\" NPT 3-Stage Water Separator, Coalescing Filter & Desiccant Air Dryer",
      "price_range": "$89 - $249",
      "amazon_query": "1/2 NPT 3 Stage Air Dryer Water Separator Compressor",
      "air_note": "1-sentence moisture removal note"
    }},
    {{
      "badge": "High-Flow Hose & Couplers",
      "title": "50ft Retractable 3/8\" / 1/2\" Hybrid Air Hose Reel + Milton V-Style High-Flow Fittings",
      "price_range": "$74 - $169",
      "amazon_query": "50ft Retractable Air Hose Reel 3/8 Milton V Style",
      "air_note": "1-sentence pressure drop prevention note"
    }},
    {{
      "badge": "Pneumatic Tool Unit",
      "title": "Pro-Grade {item_name}",
      "price_range": "$79 - $389",
      "amazon_query": "{item_name}",
      "air_note": "1-sentence dynamic PSI performance note"
    }}
  ],
  "shop_checklist": [
    "Step 1 regarding dynamic PSI measurement at tool inlet and hose ID",
    "Step 2 regarding 25-foot cooling run before water separator/dryer",
    "Step 3 regarding 1.25x compressor CFM duty cycle headroom",
    "Step 4 regarding automatic electronic tank condensate drain valve"
  ],
  "faqs": [
    {{"q": "How many CFM and what size compressor do I need for {item_name}?", "a": "Exact continuous CFM, duty-cycle adjusted CFM, tank gallons, and HP."}},
    {{"q": "How long will a {tank_gal}-gallon air tank run {item_name} before refilling?", "a": "Exact Boyle's Law cubic feet reserve and seconds of runtime."}},
    {{"q": "What size air hose and fittings should I use for {item_name}?", "a": "Exact hose inner diameter and high-flow V-style coupler explanation."}}
  ]
}}
"""

    for model_id in ["gemini-2.5-flash", "gemini-2.0-flash"]:
        try:
            endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{model_id}:generateContent?key={GEMINI_API_KEY}"
            payload = {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {
                    "temperature": 0.2,
                    "responseMimeType": "application/json"
                }
            }
            req = urllib.request.Request(
                endpoint,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=35) as resp:
                result = json.loads(resp.read().decode("utf-8"))
                raw_text = result["candidates"][0]["content"]["parts"][0]["text"].strip()
                raw_text = re.sub(r"^```(?:json)?\s*", "", raw_text)
                raw_text = re.sub(r"\s*```$", "", raw_text)
                parsed = json.loads(raw_text)
                if "specs" in parsed and "hardware_bundle" in parsed:
                    return parsed
        except Exception as e:
            print(f"[WARN] Gemini ({model_id}) notice for '{item_name}': {e}")

    return build_deterministic_cfm_data(tool_tuple)


def build_cfm_html_page(data, slug, mon_cfg):
    tool_name = data.get("tool_name", "Pneumatic Air Tool")
    sp = data.get("specs", {})
    raw_cfm = round(safe_float(sp.get("continuous_cfm_90psi", 12.0), 12.0), 1)
    duty_pct = int(safe_float(sp.get("tool_duty_cycle_pct", 75), 75))
    work_psi = int(safe_float(sp.get("working_psi", 90), 90))
    rec_cfm = round(safe_float(sp.get("recommended_compressor_cfm", round(raw_cfm * 0.9, 1)), 12.0), 1)
    tank_gal = int(safe_float(sp.get("recommended_tank_gallons", 60), 60))
    rec_hp = round(safe_float(sp.get("recommended_motor_hp", 5.0), 5.0), 1)
    hose_id = sp.get("recommended_hose_id", "3/8-Inch ID")

    header_cta = mon_cfg.get("header_cta", {})
    header_cta_url = build_amazon_url(header_cta.get("search_query", "Two+Stage+Air+Compressor+60+Gallon"), mon_cfg)

    schema_graph = {
        "@context": "https://schema.org",
        "@graph": [
            {
                "@type": "SoftwareApplication",
                "name": f"{tool_name} Air Compressor CFM & Tank Sizing Calculator",
                "applicationCategory": "UtilitiesApplication",
                "operatingSystem": "Web Browser",
                "offers": {"@type": "Offer", "price": "0", "priceCurrency": "USD"}
            },
            {
                "@type": "FAQPage",
                "mainEntity": [
                    {
                        "@type": "Question",
                        "name": f.get("q", ""),
                        "acceptedAnswer": {"@type": "Answer", "text": f.get("a", "")}
                    } for f in data.get("faqs", [])
                ]
            }
        ]
    }

    bundle_html = ""
    for item in data.get("hardware_bundle", []):
        amz_url = build_amazon_url(item.get("amazon_query", item.get("title", "60 Gallon Air Compressor")), mon_cfg)
        bundle_html += f"""
        <div class="bg-slate-900 border border-slate-800 rounded-xl p-5 flex flex-col justify-between hover:border-yellow-500/60 transition">
          <div>
            <div class="flex items-center justify-between gap-2 mb-2">
              <span class="text-xs font-bold uppercase tracking-wider bg-yellow-500/10 text-yellow-400 border border-yellow-500/20 px-2.5 py-0.5 rounded">{item.get('badge', 'Pneumatic Gear')}</span>
              <span class="text-sm font-bold text-emerald-400">{item.get('price_range', '$79+')}</span>
            </div>
            <h3 class="text-base font-bold text-white mt-2">{item.get('title', '')}</h3>
            <p class="text-xs text-slate-400 mt-2 leading-relaxed">💨 {item.get('air_note', '')}</p>
          </div>
          <a href="{amz_url}" target="_blank" rel="nofollow sponsored" class="mt-5 block text-center bg-yellow-500 hover:bg-yellow-400 text-slate-950 font-extrabold py-2.5 px-4 rounded-lg text-sm transition shadow-lg">
            Check Price on Amazon →
          </a>
        </div>"""

    # Build Tank Size vs Boyle's Law Drawdown Matrix (8, 20, 30, 60, 80, 120 Gallons)
    matrix_rows_html = ""
    for t_gal, t_hp, typ_cfm in [(8, 1.0, 2.5), (20, 2.0, 5.3), (30, 3.0, 9.5), (60, 5.0, 16.5), (80, 7.5, 24.0), (120, 10.0, 35.0)]:
        cuft_res = round((t_gal * 0.133681) * (60.0 / 14.7), 1)
        sec_res = int(round((cuft_res / max(1.0, raw_cfm)) * 60.0))
        can_continuous = "✅ Continuous Run OK" if typ_cfm >= (raw_cfm * (duty_pct / 100.0)) else f"⚠️ Pauses Every ~{sec_res}s"
        matrix_rows_html += f"""
        <tr class="border-b border-slate-800 hover:bg-slate-800/40">
          <td class="py-3 px-4 font-bold text-white">{t_gal} Gallon ({t_hp} HP)</td>
          <td class="py-3 px-4 text-slate-300">~{typ_cfm} CFM @ 90 PSI</td>
          <td class="py-3 px-4 font-bold text-yellow-400">{cuft_res} cu. ft. Reserve</td>
          <td class="py-3 px-4 text-emerald-400 font-semibold">{sec_res} sec Buffer</td>
          <td class="py-3 px-4 text-xs text-slate-300">{can_continuous}</td>
        </tr>"""

    checklist_html = ""
    for idx, step_text in enumerate(data.get("shop_checklist", []), start=1):
        checklist_html += f"""
        <label class="flex items-start gap-3.5 bg-slate-900 border border-slate-800 rounded-xl p-4 cursor-pointer hover:border-slate-700 transition">
          <input type="checkbox" class="mt-1 w-5 h-5 accent-yellow-500 rounded cursor-pointer cfm-check">
          <span class="text-sm text-slate-200 leading-relaxed"><strong>CAGI Step {idx}:</strong> {step_text}</span>
        </label>"""

    faqs_html = "".join([
        f"<div class='bg-slate-900 border border-slate-800 rounded-xl p-5'><h3 class='font-bold text-white text-base mb-2'>{f.get('q', '')}</h3><p class='text-sm text-slate-300 leading-relaxed'>{f.get('a', '')}</p></div>"
        for f in data.get("faqs", [])
    ])

    canonical_url = f"{SITE_BASE_URL}/{slug}.html"
    amz_domain = mon_cfg.get("marketplace_domain", "www.amazon.com")
    amz_tag = mon_cfg.get("amazon_associate_tag", "YOUR_AMAZON_TAG-20")

    html = f"""<!DOCTYPE html>
<html lang="en" class="dark">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{data.get('seo_title', tool_name)}</title>
  <meta name="description" content="{data.get('meta_description', '')}">
  <link rel="canonical" href="{canonical_url}">
  <meta property="og:title" content="{data.get('seo_title', tool_name)}">
  <meta property="og:description" content="{data.get('meta_description', '')}">
  <meta property="og:type" content="article">
  <meta property="og:url" content="{canonical_url}">
  <script src="https://cdn.tailwindcss.com"></script>
  <script type="application/ld+json">{json.dumps(schema_graph)}</script>
</head>
<body class="bg-slate-950 text-slate-100 antialiased min-h-screen flex flex-col">
  <header class="border-b border-slate-800 bg-slate-900/80 backdrop-blur sticky top-0 z-30">
    <div class="max-w-5xl mx-auto px-4 py-3.5 flex items-center justify-between">
      <a href="index.html" class="text-lg font-black tracking-tight text-white flex items-center gap-2">
        <span class="bg-yellow-500 text-slate-950 px-2 py-0.5 rounded font-black">CFM</span>CompressorIndex
      </a>
      <a href="{header_cta_url}" target="_blank" rel="nofollow sponsored" class="text-xs sm:text-sm bg-yellow-500 hover:bg-yellow-400 text-slate-950 font-extrabold px-3.5 py-2 rounded-lg transition">
        {header_cta.get('cta_text', 'Shop High-CFM Air Compressors →')}
      </a>
    </div>
  </header>

  <main class="max-w-5xl mx-auto px-4 py-10 flex-1 w-full">
    <div class="mb-8">
      <div class="flex flex-wrap items-center gap-2.5 mb-3">
        <span class="text-xs font-extrabold uppercase tracking-widest bg-yellow-500 text-slate-950 px-3 py-1 rounded-full">{raw_cfm} CFM @ {work_psi} PSI</span>
        <span class="text-xs font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 px-3 py-1 rounded-full">Min Compressor: {rec_cfm} CFM ({rec_hp} HP)</span>
        <span class="text-xs font-semibold bg-slate-800 text-slate-300 px-3 py-1 rounded-full">Tank: {tank_gal} Gal | Hose: {hose_id}</span>
      </div>
      <h1 class="text-3xl sm:text-4xl font-black text-white leading-tight">{data.get('seo_title', tool_name)}</h1>
      <div class="mt-4 bg-slate-900 border-l-4 border-yellow-500 p-4 rounded-r-xl text-sm text-slate-200 leading-relaxed">
        <strong>CAGI Pneumatic Engineering Verdict:</strong> {data.get('thermodynamic_verdict', '')}
      </div>
    </div>

    <!-- INTERACTIVE CFM, BOYLE'S LAW TANK DRAWDOWN & HP SIZING CALCULATOR -->
    <section class="bg-slate-900 border border-slate-800 rounded-2xl p-6 sm:p-8 mb-12 shadow-2xl">
      <h2 class="text-xl font-extrabold text-white mb-2">Interactive {tool_name} CFM & Tank Drawdown Calculator</h2>
      <p class="text-xs text-slate-400 mb-6">Adjust your tool's continuous CFM draw, trigger duty cycle, tank size (gallons), and cut-out pressure to compute required compressor SCFM and Boyle's Law tank reserve time.</p>

      <div class="grid md:grid-cols-2 gap-8 items-center">
        <div class="space-y-5">
          <div>
            <div class="flex justify-between text-sm font-medium mb-1.5">
              <label for="cfmSlider" class="text-slate-300">Tool Continuous Air Consumption (CFM @ 90 PSI)</label>
              <span class="text-yellow-400 font-bold"><span id="cfmVal">{raw_cfm}</span> CFM</span>
            </div>
            <input id="cfmSlider" type="range" min="1.5" max="30.0" step="0.5" value="{raw_cfm}" class="w-full accent-yellow-500 cursor-pointer">
          </div>

          <div>
            <div class="flex justify-between text-sm font-medium mb-1.5">
              <label for="dutySlider" class="text-slate-300">Trigger Duty Cycle (% Active Spraying/Grinding)</label>
              <span class="text-yellow-400 font-bold"><span id="dutyVal">{duty_pct}</span>%</span>
            </div>
            <input id="dutySlider" type="range" min="15" max="100" step="5" value="{duty_pct}" class="w-full accent-yellow-500 cursor-pointer">
          </div>

          <div class="grid grid-cols-2 gap-3">
            <div>
              <label for="tankSelect" class="block text-xs font-medium text-slate-400 mb-1">Receiver Tank Size</label>
              <select id="tankSelect" class="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-xs text-white focus:outline-none focus:border-yellow-500">
                <option value="8" {"selected" if tank_gal <= 10 else ""}>8 Gallon Portable</option>
                <option value="20" {"selected" if 10 < tank_gal <= 22 else ""}>20 Gallon Vertical</option>
                <option value="30" {"selected" if 22 < tank_gal <= 35 else ""}>30 Gallon Shop</option>
                <option value="60" {"selected" if 35 < tank_gal <= 65 else ""}>60 Gallon Stationary</option>
                <option value="80" {"selected" if tank_gal > 65 else ""}>80 Gallon Two-Stage</option>
              </select>
            </div>
            <div>
              <label for="psiSelect" class="block text-xs font-medium text-slate-400 mb-1">Max Tank Cut-Out PSI</label>
              <select id="psiSelect" class="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-xs text-white focus:outline-none focus:border-yellow-500">
                <option value="135">135 PSI (Single-Stage)</option>
                <option value="155" selected>155 PSI (Pro Single-Stage)</option>
                <option value="175">175 PSI (Two-Stage Cast Iron)</option>
              </select>
            </div>
          </div>
        </div>

        <div class="grid grid-cols-2 gap-4">
          <div class="bg-slate-950 border border-yellow-500/30 rounded-xl p-4">
            <span class="text-xs uppercase text-yellow-400 font-bold">Min Compressor Rating</span>
            <div class="text-2xl sm:text-3xl font-black text-white mt-1"><span id="reqCfmOut">{rec_cfm}</span> <span class="text-sm font-normal text-slate-400">CFM</span></div>
            <p id="hpOut" class="text-xs text-yellow-400 font-semibold mt-1">Need {rec_hp} HP Compressor</p>
          </div>

          <div class="bg-slate-950 border border-emerald-500/30 rounded-xl p-4">
            <span class="text-xs uppercase text-emerald-400 font-bold">Tank Reserve Buffer</span>
            <div class="text-2xl sm:text-3xl font-black text-emerald-400 mt-1"><span id="drawdownSecOut">45</span> <span class="text-sm font-normal text-slate-400">sec</span></div>
            <p id="cuftOut" class="text-xs text-slate-400 mt-1">Before Dropping Below 90 PSI</p>
          </div>
        </div>
      </div>

      <div class="mt-6 bg-yellow-950/40 border border-yellow-500/30 rounded-xl p-4 flex flex-col sm:flex-row items-center justify-between gap-4">
        <div id="cfmAdviceBanner" class="text-sm text-yellow-100 font-medium"></div>
        <a id="dynamicCompBtn" href="{header_cta_url}" target="_blank" rel="nofollow sponsored" class="shrink-0 bg-yellow-500 hover:bg-yellow-400 text-slate-950 font-extrabold px-4 py-2.5 rounded-lg text-xs uppercase tracking-wider transition">
          Shop Matched Air Compressor on Amazon →
        </a>
      </div>
    </section>

    <!-- 4-CARD HARDWARE BUNDLE -->
    <section class="mb-12">
      <div class="flex items-center justify-between mb-4">
        <h2 class="text-2xl font-extrabold text-white">Recommended Compressor, Air Dryer & Hose Setup for {tool_name}</h2>
        <span class="text-xs text-slate-400">CAGI & ASME Tank Rated</span>
      </div>
      <div class="grid sm:grid-cols-2 lg:grid-cols-4 gap-4">{bundle_html}</div>
    </section>

    <!-- TANK SIZE & DRAWDOWN MATRIX TABLE -->
    <section class="mb-12">
      <h2 class="text-2xl font-extrabold text-white mb-4">{tool_name} Tank Gallon Reserve & Continuous Run Matrix</h2>
      <div class="overflow-x-auto bg-slate-900 border border-slate-800 rounded-xl">
        <table class="w-full text-left border-collapse text-sm">
          <thead>
            <tr class="border-b border-slate-800 bg-slate-950/60 text-slate-400 uppercase text-xs">
              <th class="py-3.5 px-4">Compressor Tank & HP</th>
              <th class="py-3.5 px-4">Typical Output (@90 PSI)</th>
              <th class="py-3.5 px-4 text-yellow-400">Usable Air (150→90 PSI)</th>
              <th class="py-3.5 px-4 text-emerald-400">Tank-Only Buffer Time</th>
              <th class="py-3.5 px-4">Shop Workflow Verdict</th>
            </tr>
          </thead>
          <tbody>{matrix_rows_html}</tbody>
        </table>
      </div>
    </section>

    <!-- SHOP CHECKLIST -->
    <section class="mb-12">
      <div class="flex items-center justify-between mb-4">
        <h2 class="text-2xl font-extrabold text-white">High-Flow Pneumatic Plumbing & Moisture Checklist</h2>
        <span id="cfmBadge" class="text-xs font-bold bg-slate-800 text-yellow-400 px-3 py-1 rounded-full">0 / 4 Completed</span>
      </div>
      <div class="space-y-3">{checklist_html}</div>
    </section>

    <!-- FAQ -->
    <section class="mb-12">
      <h2 class="text-2xl font-extrabold text-white mb-5">Frequently Asked Questions ({tool_name})</h2>
      <div class="space-y-4">{faqs_html}</div>
    </section>
  </main>

  <footer class="border-t border-slate-800 py-8 text-center text-xs text-slate-500 px-4">
    <p>© {datetime.now(timezone.utc).year} CFMCompressorIndex. Independent Compressed Air & Pneumatic Sizing Database. As an Amazon Associate, we earn from qualifying purchases.</p>
  </footer>

  <script>
    const amzDomain = "{amz_domain}";
    const amzTag = "{amz_tag}";

    const cfmSlider = document.getElementById('cfmSlider');
    const dutySlider = document.getElementById('dutySlider');
    const tankSelect = document.getElementById('tankSelect');
    const psiSelect = document.getElementById('psiSelect');
    const cfmVal = document.getElementById('cfmVal');
    const dutyVal = document.getElementById('dutyVal');
    const reqCfmOut = document.getElementById('reqCfmOut');
    const hpOut = document.getElementById('hpOut');
    const drawdownSecOut = document.getElementById('drawdownSecOut');
    const cuftOut = document.getElementById('cuftOut');
    const cfmAdviceBanner = document.getElementById('cfmAdviceBanner');
    const dynamicCompBtn = document.getElementById('dynamicCompBtn');

    function recalculateCfm() {{
      const toolCfm = parseFloat(cfmSlider.value);
      const duty = parseInt(dutySlider.value, 10) / 100.0;
      const gals = parseInt(tankSelect.value, 10);
      const maxPsi = parseInt(psiSelect.value, 10);

      cfmVal.textContent = toolCfm.toFixed(1);
      dutyVal.textContent = Math.round(duty * 100);

      const avgCfm = toolCfm * duty;
      const safeCompressorCfm = avgCfm * 1.25;

      const tankCuFt = gals * 0.133681;
      const usableCuFt = tankCuFt * ((maxPsi - 90.0) / 14.7);
      const bufferSecs = Math.round((usableCuFt / Math.max(0.5, toolCfm)) * 60.0);

      let estHp = "1.5 HP";
      let recTankTier = "20 Gallon";
      if (safeCompressorCfm <= 4.0) {{
        estHp = "1.5 HP";
        recTankTier = "20 Gallon";
      }} else if (safeCompressorCfm <= 6.5) {{
        estHp = "2.0 HP";
        recTankTier = "30 Gallon";
      }} else if (safeCompressorCfm <= 11.5) {{
        estHp = "3.7 HP";
        recTankTier = "60 Gallon";
      }} else if (safeCompressorCfm <= 17.5) {{
        estHp = "5.0 HP Two-Stage";
        recTankTier = "60 Gallon";
      }} else {{
        estHp = "7.5 HP Two-Stage";
        recTankTier = "80 Gallon";
      }}

      reqCfmOut.textContent = safeCompressorCfm.toFixed(1);
      hpOut.textContent = `Match: ${{estHp}} (${{recTankTier}})`;
      drawdownSecOut.textContent = bufferSecs;
      cuftOut.textContent = `${{usableCuFt.toFixed(1)}} cu. ft. Reserve (${{maxPsi}}→90 PSI)`;

      cfmAdviceBanner.innerHTML = `💨 <strong>CAGI Sizing Spec:</strong> With a 1.25x duty-cycle safety factor, you need <strong>${{safeCompressorCfm.toFixed(1)}} SCFM @ 90 PSI</strong>. Install a <strong>${{recTankTier}} ${{estHp}} Air Compressor</strong> with a 3-stage desiccant dryer.`;
      dynamicCompBtn.href = `https://${{amzDomain}}/s?k=${{encodeURIComponent(recTankTier)}}+${{encodeURIComponent(estHp)}}+Air+Compressor&tag=${{amzTag}}`;
    }}

    cfmSlider.addEventListener('input', recalculateCfm);
    dutySlider.addEventListener('input', recalculateCfm);
    tankSelect.addEventListener('change', recalculateCfm);
    psiSelect.addEventListener('change', recalculateCfm);
    recalculateCfm();

    const checks = document.querySelectorAll('.cfm-check');
    const badge = document.getElementById('cfmBadge');
    checks.forEach(ch => {{
      ch.addEventListener('change', () => {{
        const done = Array.from(checks).filter(c => c.checked).length;
        badge.textContent = `${{done}} / ${{checks.length}} Completed`;
      }});
    }});
  </script>
</body>
</html>"""

    os.makedirs(DOCS_DIR, exist_ok=True)
    with open(os.path.join(DOCS_DIR, f"{slug}.html"), "w", encoding="utf-8") as f:
        f.write(html)


def rebuild_portal_sitemap_and_rss(published, mon_cfg):
    header_cta = mon_cfg.get("header_cta", {})
    header_cta_url = build_amazon_url(header_cta.get("search_query", "Two+Stage+Air+Compressor+60+Gallon"), mon_cfg)

    cards_html = ""
    for item in reversed(published):
        cards_html += f"""
        <a href="{item['slug']}.html" class="block bg-slate-900 border border-slate-800 hover:border-yellow-500/60 rounded-xl p-5 transition group">
          <div class="flex items-center justify-between mb-2">
            <span class="text-xs font-black uppercase bg-yellow-500 text-slate-950 px-2.5 py-0.5 rounded">{item.get('cfm', 12.0)} CFM @ 90 PSI</span>
            <span class="text-xs text-slate-400">Min: {item.get('tank_gal', 60)} Gal ({item.get('hp', 5.0)} HP)</span>
          </div>
          <h2 class="text-base font-bold text-white group-hover:text-yellow-400 transition">{item['tool_name']} CFM & Tank Calculator</h2>
          <p class="text-xs text-slate-400 mt-2 line-clamp-2">{item['description']}</p>
          <span class="inline-block mt-4 text-xs font-extrabold text-yellow-400">Calculate SCFM & Tank Drawdown →</span>
        </a>"""

    index_html = f"""<!DOCTYPE html>
<html lang="en" class="dark">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>CFMCompressorIndex — Air Compressor CFM @ 90 PSI, Tank Size & Tool Calculator (2026)</title>
  <meta name="description" content="Calculate exact air compressor SCFM @ 90 PSI, Boyle's Law tank drawdown time, and HP sizing for HVLP paint guns, DA sanders, impact wrenches, sandblasters, and plasma cutters.">
  <link rel="canonical" href="{SITE_BASE_URL}/">
  <link rel="alternate" type="application/rss+xml" title="CFMCompressorIndex RSS Feed" href="{SITE_BASE_URL}/rss.xml">
  <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-slate-950 text-slate-100 min-h-screen flex flex-col">
  <header class="border-b border-slate-800 bg-slate-900/80 sticky top-0 z-30 backdrop-blur">
    <div class="max-w-5xl mx-auto px-4 py-3.5 flex items-center justify-between">
      <div class="text-lg font-black text-white flex items-center gap-2">
        <span class="bg-yellow-500 text-slate-950 px-2 py-0.5 rounded font-black">CFM</span>CompressorIndex
      </div>
      <a href="{header_cta_url}" target="_blank" rel="nofollow sponsored" class="text-xs sm:text-sm bg-yellow-500 hover:bg-yellow-400 text-slate-950 font-extrabold px-3.5 py-2 rounded-lg transition">
        {header_cta.get('cta_text', 'Shop High-CFM Air Compressors →')}
      </a>
    </div>
  </header>

  <main class="max-w-5xl mx-auto px-4 py-12 flex-1 w-full">
    <div class="text-center max-w-2xl mx-auto mb-10">
      <h1 class="text-3xl sm:text-5xl font-black text-white tracking-tight">Air Compressor CFM, Tank Gallon & Pneumatic Tool Database</h1>
      <p class="text-slate-400 mt-3 text-base sm:text-lg">Select any pneumatic air tool or compressor model below to calculate continuous SCFM @ 90 PSI, Boyle's Law tank reserve drawdown time, and required hose diameter.</p>
      <div class="mt-6">
        <input id="filterInput" type="text" placeholder="Search air tool or compressor (e.g. HVLP Paint Gun, DA Sander, Sandblaster, Impact Wrench, Ingersoll Rand 60 Gal...)" class="w-full bg-slate-900 border border-slate-700 rounded-xl px-4 py-3.5 text-sm text-white focus:outline-none focus:border-yellow-500">
      </div>
    </div>

    <div id="cfmGrid" class="grid sm:grid-cols-2 lg:grid-cols-3 gap-5">{cards_html}</div>
  </main>

  <footer class="border-t border-slate-800 py-8 text-center text-xs text-slate-500">
    <p>© {datetime.now(timezone.utc).year} CFMCompressorIndex. As an Amazon Associate, we earn from qualifying purchases.</p>
  </footer>

  <script>
    const filterInput = document.getElementById('filterInput');
    const cards = Array.from(document.getElementById('cfmGrid').children);
    filterInput.addEventListener('input', (e) => {{
      const q = e.target.value.toLowerCase();
      cards.forEach(c => {{
        c.style.display = c.textContent.toLowerCase().includes(q) ? 'block' : 'none';
      }});
    }});
  </script>
</body>
</html>"""

    os.makedirs(DOCS_DIR, exist_ok=True)
    with open(os.path.join(DOCS_DIR, "index.html"), "w", encoding="utf-8") as f:
        f.write(index_html)

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    urls_xml = f"""  <url>
    <loc>{SITE_BASE_URL}/</loc>
    <lastmod>{today}</lastmod>
    <changefreq>daily</changefreq>
    <priority>1.0</priority>
  </url>\n"""

    for item in published:
        urls_xml += f"""  <url>
    <loc>{SITE_BASE_URL}/{item['slug']}.html</loc>
    <lastmod>{item.get('date', today)}</lastmod>
    <changefreq>monthly</changefreq>
    <priority>0.9</priority>
  </url>\n"""

    with open(os.path.join(DOCS_DIR, "sitemap.xml"), "w", encoding="utf-8") as f:
        f.write(f"""<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n{urls_xml}</urlset>""")

    rss_items = ""
    for item in list(reversed(published))[:30]:
        rss_items += f"""    <item>
      <title>{item['title']}</title>
      <link>{SITE_BASE_URL}/{item['slug']}.html</link>
      <guid>{SITE_BASE_URL}/{item['slug']}.html</guid>
      <description>{item['description']}</description>
    </item>\n"""

    rss_xml = f"""<?xml version="1.0" encoding="UTF-8" ?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">
  <channel>
    <title>CFMCompressorIndex Pneumatic & Air Compressor Sizing Database</title>
    <link>{SITE_BASE_URL}/</link>
    <description>Interactive Air Compressor CFM @ 90 PSI, Tank Drawdown & Pneumatic Tool Calculators</description>
    <atom:link href="{SITE_BASE_URL}/rss.xml" rel="self" type="application/rss+xml" />
    <atom:link href="https://pubsubhubbub.appspot.com/" rel="hub" />
{rss_items}  </channel>
</rss>"""

    with open(os.path.join(DOCS_DIR, "rss.xml"), "w", encoding="utf-8") as f:
        f.write(rss_xml)

    with open(os.path.join(DOCS_DIR, "robots.txt"), "w", encoding="utf-8") as f:
        f.write(f"User-agent: *\nAllow: /\nSitemap: {SITE_BASE_URL}/sitemap.xml\n")

    with open(os.path.join(DOCS_DIR, f"{INDEXNOW_KEY}.txt"), "w", encoding="utf-8") as f:
        f.write(INDEXNOW_KEY)


def notify_search_engines(new_urls):
    if not SITE_BASE_URL or not new_urls:
        return
    parsed_host = urllib.parse.urlparse(SITE_BASE_URL).netloc
    payload = {
        "host": parsed_host,
        "key": INDEXNOW_KEY,
        "keyLocation": f"{SITE_BASE_URL}/{INDEXNOW_KEY}.txt",
        "urlList": new_urls
    }
    try:
        req = urllib.request.Request(
            "https://api.indexnow.org/indexnow",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json; charset=utf-8"},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            print(f"[INDEXNOW] Pushed {len(new_urls)} URLs (HTTP {resp.status})")
    except Exception as e:
        print(f"[WARN] IndexNow ping notice: {e}")

    try:
        hub_data = urllib.parse.urlencode({
            "hub.mode": "publish",
            "hub.url": f"{SITE_BASE_URL}/rss.xml"
        }).encode("utf-8")
        req_hub = urllib.request.Request(
            "https://pubsubhubbub.appspot.com/",
            data=hub_data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            method="POST"
        )
        with urllib.request.urlopen(req_hub, timeout=15) as resp_hub:
            print(f"[WEBSUB] Google PubSubHubbub ping status: {resp_hub.status}")
    except Exception as e:
        print(f"[WARN] WebSub ping notice: {e}")


def main():
    published = load_json(PUBLISHED_FILE, [])
    mon_cfg = load_json(MONETIZATION_FILE, {})
    published_slugs = {item["slug"] for item in published}

    candidates = []
    if CUSTOM_TOOL:
        candidates.append((CUSTOM_TOOL.strip(), 12.0, 75, 90, 60, 5.0))
    candidates.extend(SEED_TOOLS)
    candidates.extend(discover_google_compressor_queries())

    new_urls = []
    count = 0

    for tool_tuple in candidates:
        if count >= PAGES_PER_RUN:
            break
        t_name = tool_tuple[0]
        slug = slugify(f"{t_name}-cfm-compressor-size-calculator")
        if slug in published_slugs:
            continue

        print(f"[ENGINE] Generating pneumatic CFM & tank drawdown calculator for: {t_name}...")
        try:
            data = generate_cfm_data(tool_tuple)
            build_cfm_html_page(data, slug, mon_cfg)
            today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            sp = data.get("specs", {})

            published.append({
                "tool_name": data.get("tool_name", t_name),
                "slug": slug,
                "title": data.get("seo_title", f"{t_name} CFM Calculator"),
                "description": data.get("meta_description", ""),
                "cfm": round(safe_float(sp.get("continuous_cfm_90psi", tool_tuple[1]), tool_tuple[1]), 1),
                "tank_gal": int(safe_float(sp.get("recommended_tank_gallons", tool_tuple[4]), tool_tuple[4])),
                "hp": round(safe_float(sp.get("recommended_motor_hp", tool_tuple[5]), tool_tuple[5]), 1),
                "date": today
            })
            published_slugs.add(slug)
            if SITE_BASE_URL:
                new_urls.append(f"{SITE_BASE_URL}/{slug}.html")
            count += 1
            time.sleep(2)
        except Exception as e:
            print(f"[ERROR] Failed building {t_name}: {e}")

    save_json(PUBLISHED_FILE, published)
    rebuild_portal_sitemap_and_rss(published, mon_cfg)
    if new_urls and SITE_BASE_URL:
        new_urls.append(f"{SITE_BASE_URL}/")
        notify_search_engines(new_urls)
    print(f"[DONE] Published {count} new air compressor CFM calculator pages.")


if __name__ == "__main__":
    main()
