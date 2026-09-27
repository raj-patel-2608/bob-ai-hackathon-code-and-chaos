# Problem Statement

**Track 4 (AI & Predictive), PS10: FIR Intelligence & Crime Pattern Detector** (IBM × NFSU Bob Hackathon)

## Background
A First Information Report (FIR) is written as free text at the police station where the complainant walks in.
UP Police's CCTNS alone holds **3+ crore digitised FIRs with no NLP layer**, and pattern analysis is manual.

Organised offenders exploit this. A Jamtara-style call centre uses the **same phone numbers and "mule" bank
accounts** against victims in many districts. Each victim files at their own police station, each FIR is written
differently (`98765 43210`, `+91-9876543210`, `09876543210`), and nobody connects them. Serial offenders evaded
detection for years because **inter-district FIR connections were never surfaced**.

## Who experiences it
- **Investigating officers**: cannot see that "their" case is the sixth of a ring spread across three districts.
- **Station House Officers (SHOs)**: have no timely picture of what is rising in their area, which gangs are
  active, or which linked FIRs sit at other stations.
- **Victims**: cyber-fraud money moves through mule accounts within hours. The window to freeze it closes before
  anyone links the complaints.

## Why existing approaches fall short
- **CCTNS is a records system, not an intelligence layer.** Crime type and method (the NCRB Crime Details Form,
  I.I.F.-II: Major/Minor Head and Method) are filled in by hand, later, by the investigating officer. A real FIR
  (I.I.F.-I) has no crime-type field at all.
- **Keyword search misses variants.** Identifiers are written in many formats and names appear as aliases
  ("Salim alias Pappu").
- **Generic LLM chat on raw FIRs is unsafe for policing.** It can invent links or names, cannot show evidence, and
  sending every FIR to a large model is slow and costly. Accusations must be explainable and verifiable.

## Quantified pain (public figures, sources in `src/dataset/SOURCES.md`)
- Digital-arrest scams alone: reported losses of ₹2,140 crore and 92,000+ complaints in 2024.
- Busts routinely trace one mule account to complaints in several jurisdictions. In one Delhi Police Telegram
  task-scam case, a single account was linked to **5 complaints in different jurisdictions**.

## What PS10 asks for, and what we deliver
| PS10 requirement | CrimeFIR |
|---|---|
| Ingest a batch of mock FIR text samples | Upload `.txt` / `.jsonl` / `.json` / `.csv`, processed asynchronously in micro-batches |
| Categorise each by crime type | Auto-drafted NCRB **Major / Minor Head** (4 major, 17 minor) by Laya, with an IBM Granite second opinion |
| Extract named entities: accused, location, MO, victim profile | Hard evidence (phones, accounts, UPI, IMEI, vehicles, handles), accused + aliases, 24 MO flags, victim age group / gender / occupation, loss, place |
| Detect repeat-offender signatures across FIRs | Evidence links + **NetworkX clusters** across stations and districts |
| Station-level crime trend summary + flagged repeat-offender list | Station facts vs previous period + **Granite-written brief with every number verified**, plus a risk-ranked **flagged cluster list** |
| Bob-powered | **IBM Bob** queries everything through our MCP server ("FIR Analyst" mode) and writes weekly briefs headlessly (`bob run`) |

## Why now
Cyber-enabled fraud is the fastest-growing crime category, it is inherently inter-district, and India is moving
FIR records to BNS/BNSS-era digital systems. An explainable intelligence layer can sit on top of existing FIR
text without changing how FIRs are written.
