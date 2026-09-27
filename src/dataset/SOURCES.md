# Real-world grounding of the synthetic dataset

PS10 asks for **mock** FIR text samples. No public FIR text dataset exists that could be used responsibly:
- The ICDAR-2023 FIR dataset is scanned images with 4 annotated fields and real names.
- Scraping state FIR portals would publish real victims' and accused persons' personal data.

So every FIR here is **synthetic**. Every **crime pattern (modus operandi)** is taken from publicly reported cases and advisories listed below. **All people, phone numbers, bank accounts, UPI IDs, IMEIs and vehicle numbers are randomly generated and fictional.** Police station and area names are used only as geography.

## FIR format
The layout follows the official NCRB Integrated Investigation Form I.I.F.-I (First Information Report). Crime type and MO are **not** part of an FIR; they belong to I.I.F.-II (Crime Details Form: Major/Minor Head, Method), which CrimeFIR drafts automatically.
- NCRB I.I.F. forms: https://shillongpolice.gov.in/Police_Acts_Manual/07_Integrated_Investigation_Forms_NCRB_I.I.F._ITOVII.pdf
- Form IF-1: https://police.py.gov.in/Police%20manual/Forms%20pdf/FORM%20IF%201.pdf

Acts & Sections use the Bharatiya Nyaya Sanhita (BNS) 2023 and the IT Act 2000. They are indicative and not legal advice.

## Crime patterns and their sources
| Cluster / pattern | What the real cases describe | Sources |
|---|---|---|
| C01 card-reward / KYC calls | Jamtara/Deoghar callers posing as bank staff, taking OTPs; mule accounts reused across complaints | https://theprint.in/india/from-mewat-to-jamtara-cybercrime-trail-drains-rs-30-cr-in-2-5-years-in-southwest-delhi/2741179/ · https://www.newsonair.gov.in/jharkhand-police-arrest-6-cyber-criminals-from-jamtara/ · https://organiser.org/2024/03/13/227206/bharat/jamtara-model-cybercrime-hubs-flourish-in-north-indian-towns-kolkata-police-unveils-alarming-trends/ |
| C02 fake customer care | Fake helpline numbers, remote-access apps, fake customer care (listed in the same busts) | https://theprint.in/india/from-mewat-to-jamtara-cybercrime-trail-drains-rs-30-cr-in-2-5-years-in-southwest-delhi/2741179/ · https://www.indiatvnews.com/technology/news/jamtara-like-cybercrime-hub-discovered-in-mewat-by-rajasthan-police-2024-06-19-937772 |
| C03 digital arrest | Courier/customs parcel call, transfer to fake CBI officer, Skype video "custody", money to "safe account" | https://www.niti.gov.in/node/1642 · https://en.wikipedia.org/wiki/Digital_arrest_scam · https://www.tribuneindia.com/news/india/digital-arrest-scam-bengaluru-woman-loses-rs-31-cr-over-6-months-to-fake-cbi-officers/ · https://www.tribuneindia.com/news/delhi/four-nabbed-for-44-50l-digital-arrest-fraud |
| C04 Telegram task scam | Paid review tasks, then "prepaid tasks"; one mule account linked to 5 complaints in different jurisdictions | https://www.thehansindia.com/amp/news/cities/new-delhi/delhi-police-busts-telegram-based-part-time-cyber-job-scam-arrests-two-from-rajasthan-1105951 · https://www.millenniumpost.in/delhi/two-held-after-28l-job-scam-leads-police-to-mule-accounts-671348 |
| C05 fake trading app | WhatsApp stock-tip groups, fake apps showing profits, "tax" before withdrawal | https://theprint.in/india/from-mewat-to-jamtara-cybercrime-trail-drains-rs-30-cr-in-2-5-years-in-southwest-delhi/2741179/ · https://www.theweek.in/wire-updates/national/2026/02/02/investment-fraud-through-matrimonial-site-3-arrested-for-cheating-kochi-doctor-of-rs-37-lakh.html |
| C06 loan-app harassment | Contact-list access, morphed obscene photos sent to relatives, extortion | https://the420.in/mumbai-fake-loan-app-extortion-banker-arrested/ · https://www.pressreader.com/india/hindustan-times-st-mumbai/20240410/281784224122611 |
| C07 sextortion | WhatsApp video call recorded, then callers posing as Delhi Crime Branch demand money (Mewat/Bharatpur) | https://www.sakshipost.com/news/delhi-police-bust-major-sextortion-racket-operating-mewat-three-held-415550 · https://hindupost.in/crime/asib-khan-arrested-for-running-mewat-based-sextortion-gang-posing-as-cops/ |
| C08 fake army-officer OLX sale | Seller "posted on transfer", fake army ID, advance plus gate-pass/transport charges (Bharatpur/Mewat) | https://www.thenewsminute.com/tamil-nadu/duping-buyers-across-india-posing-army-officers-olx-tn-cops-crack-scam-119709 · https://www.dnaindia.com/jaipur/report-beware-of-gang-looting-buyers-through-fake-olx-ads-bharatpur-police-2624837 |
| C09 matrimonial fraud | Fake NRI doctor profile, "gift parcel" held at customs, clearance charges | https://medicaldialogues.in/news/health/doctors/kochi-doctor-defrauded-of-rs-37-lakh-in-nri-matrimonial-fraud-three-arrested-163857 · https://www.siasat.com/fake-nri-19-cases-hyderabad-matrimonial-fraudster-detained-3546359/ |
| C10-C12 street crime, vehicle theft, burglary | Bike-borne chain snatching, two-wheeler lifting rings, locked-house burglaries | Common urban crime patterns in police press notes. No single source; described generically. |

## Context from the problem statement
PS10 cites UP Police's CCTNS (3+ crore digitised FIRs, no NLP layer) and the Jamtara gang evading detection because inter-district FIR connections were never surfaced. This dataset reproduces exactly that: the same phone numbers, mule accounts and vehicles appear in FIRs at **different police stations in three districts**, written differently each time.
