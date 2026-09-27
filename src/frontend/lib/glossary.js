// Plain-language explanations shown next to terms in the UI (one place, so wording stays consistent).
export const GLOSSARY = {
  crimeCategory:
    "Broad category of the crime (Cyber, Property, Body, Economic). Police call this the 'Major Head' in the NCRB Crime Details Form.",
  crimeType:
    "The specific kind of crime, e.g. 'OTP/KYC bank fraud' or 'Chain snatching'. Police call this the 'Minor Head'.",
  classification:
    "CrimeFIR reads the FIR text and fills in what an investigating officer normally fills by hand later in the NCRB Crime Details Form (I.I.F.-II): crime category, crime type, method, victim and accused.",
  method:
    "Modus operandi (MO): how the crime was done, e.g. 'asked for OTP' or 'came on a motorcycle'.",
  group:
    "A repeat-offender group: FIRs connected because they share hard evidence (same phone number, bank account, UPI ID, vehicle, online handle or named accused). Likely the same person or gang.",
  highRisk:
    "Risk score 70-100: many FIRs, several stations or districts, large or recent losses, senior-citizen victims, a shared money trail. Score 45-69 is medium.",
  evidenceLink:
    "Two FIRs share the same hard evidence (e.g. the same phone number, even if written differently). Strong lead.",
  patternLink:
    "Two FIRs describe a very similar story but share no evidence. Weak lead; never used to flag anyone.",
  review:
    "Cases where the AI was not sure (confidence below 40%) and the Granite LLM could not give a second opinion. An officer should confirm or correct the crime type.",
  decidedBy:
    "Laya (local AI) decides when it is at least 40% sure. Otherwise IBM Granite (watsonx.ai) gives a second opinion. 'Rules' is only used if the AI service is offline; 'officer' means a person corrected it.",
  standalone: "FIRs that share no evidence with any other FIR (not part of any repeat-offender group).",
  brief:
    "Numbers are calculated from the FIRs of this station for the period. IBM Granite (watsonx.ai) then writes a short brief from those numbers. The brief is rejected if it contains any number not in the data, and a template brief is used instead.",
};
