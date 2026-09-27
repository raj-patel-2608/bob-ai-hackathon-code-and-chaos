"""Narrative templates for the "First Information contents" part of an FIR.

Every template is written in the style of real Indian FIRs (first-person
complaint, or the writer's third-person summary, sometimes with Hinglish).
The MO flags listed for a template are exactly the methods the text
describes, so the ground truth stays honest.

Placeholders:
  {slot}                 filled from the case context
  <<key|with|without>>   conditional segment: uses the first text when the
                         case has identifier `key`, otherwise the second
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Template:
    minor: str
    mo: tuple[str, ...]
    text: str
    gender: str | None = None   # complainant gender implied by the wording; None = any


T = Template

TEMPLATES: tuple[Template, ...] = (
    # ------------------------------------------------------------------ cyber.kyc_bank_impersonation
    T("cyber.kyc_bank_impersonation",
      ("impersonated_bank_official", "asked_otp_or_card_details", "money_to_mule_account"),
      "I received a call on my mobile <<phone|from number {phone}|from an unknown number>> at about {time}. "
      "The caller said his name is {persona} and he is speaking from {bank} credit card department and my reward "
      "points worth Rs. {small_amt} will lapse today. He asked me to tell the OTP which came on my phone to redeem "
      "the points. Trusting him I told the OTP two times. After some time {amount} got debited from my account in "
      "{n_txn} transactions. When I called the bank they told me the amount went to <<account|a/c no. {account}|some "
      "other account>>. The caller's phone is now switched off."),
    T("cyber.kyc_bank_impersonation",
      ("impersonated_bank_official", "remote_access_app", "phishing_link_or_fake_app", "money_to_mule_account"),
      "The complainant states that she received a call <<phone|from mobile no. {phone}|from a private number>> and "
      "the caller told that he is from {bank} KYC department and her KYC is pending, so her account will be blocked "
      "today itself. He sent a link on WhatsApp and asked her to install an application named {remote_app} to "
      "complete the KYC. After installing it he asked her to open her net banking. Within a few minutes {amount} was "
      "transferred out of her account <<upi|to UPI ID {upi}|without her knowledge>>. <<account|The bank statement "
      "shows the beneficiary account as {account}.|>>", gender="female"),
    T("cyber.kyc_bank_impersonation",
      ("impersonated_bank_official", "asked_otp_or_card_details", "money_to_mule_account"),
      "Mujhe <<phone|{phone}|ek unknown number>> se phone aaya, bola main {bank} head office se bol raha hoon, aapka "
      "debit card block ho jayega, card verify karna padega. He asked the card number, expiry and CVV and then the "
      "OTP. I told everything thinking he is from bank. After that {amount} was deducted from my savings account. "
      "Bank says the money was credited to <<account|account {account}|another bank account>> <<upi|and part of it "
      "to {upi}|>>. I request strict action."),
    T("cyber.kyc_bank_impersonation",
      ("impersonated_bank_official", "phishing_link_or_fake_app", "asked_otp_or_card_details", "money_to_mule_account"),
      "Complainant, aged about {age} years, states that an SMS came on his phone that his {bank} account KYC is "
      "expired and PAN card must be updated, with a link. He clicked the link and entered his customer ID, "
      "password and the OTP. <<phone|Then a person called from {phone} and asked for one more OTP for "
      "confirmation.|>> Thereafter {amount} was debited in {n_txn} transactions <<account|to account no. "
      "{account}|>>.", gender="male"),

    # ------------------------------------------------------------------ cyber.fake_customer_care
    T("cyber.fake_customer_care",
      ("impersonated_customer_care", "remote_access_app", "money_to_mule_account"),
      "I had ordered {product} from {ecom} and wanted a refund because the item was damaged. I searched the "
      "customer care number on Google and called <<phone|{phone}|the number shown there>>. The person said he is "
      "from {ecom} customer care and asked me to install {remote_app} to process the refund fast. He told me to "
      "enter Rs. 10 in UPI to verify my account. After that {amount} was debited from my account <<upi|and "
      "transferred to UPI ID {upi}|>>."),
    T("cyber.fake_customer_care",
      ("impersonated_customer_care", "phishing_link_or_fake_app", "asked_otp_or_card_details",
       "advance_or_fee_payment", "money_to_mule_account"),
      "The complainant states that his courier from {courier} was not delivered, so he called the helpline number "
      "<<phone|{phone}|which he found on the internet>>. The executive sent a link and told him to pay Rs. 5 "
      "re-delivery charge. After he entered his card details and OTP on that link, {amount} was debited "
      "<<account|and credited to account {account}|>>. The helpline number is not reachable now.", gender="male"),
    T("cyber.fake_customer_care",
      ("impersonated_customer_care", "remote_access_app", "money_to_mule_account"),
      "An SMS came that my electricity connection will be disconnected tonight at 9.30 pm because last month bill "
      "is not updated, and to call the electricity officer <<phone|on {phone}|on the number given>>. The person on "
      "phone told me to download {remote_app} and pay Rs. 11 online. When I did that, {amount} was taken from my "
      "account <<upi|to UPI {upi}|>> <<account|and account {account}|>>."),

    # ------------------------------------------------------------------ cyber.digital_arrest
    T("cyber.digital_arrest",
      ("impersonated_police_or_agency", "threat_of_arrest_or_case", "video_call_used", "money_to_mule_account"),
      "I received a call <<phone|from {phone}|from an unknown number>> saying a parcel in my name sent through "
      "{courier} to {country} has been seized by customs and it has {contraband}. The call was transferred to a "
      "person who said he is {cop_persona} of {agency}. He said a case is registered against me and I am under "
      "digital arrest, and made me stay on Skype video call for {hours} hours. He said my money must be verified by "
      "RBI and told me to transfer it to a safe account. Out of fear I transferred {amount} to <<account|account "
      "no. {account}|the account given by him>><<account2|, and later more money to account {account2}|>>."),
    T("cyber.digital_arrest",
      ("impersonated_police_or_agency", "threat_of_arrest_or_case", "video_call_used", "money_to_mule_account"),
      "The complainant, {a_occupation} aged {age} years, states that he got a WhatsApp video call <<phone|from "
      "{phone}|from an unknown number>> from a man in police uniform who said he is {cop_persona} from {agency}. "
      "He said the complainant's Aadhaar card was used to open a bank account for money laundering and an arrest "
      "warrant is issued. He was not allowed to disconnect the call and was told not to tell anyone in the family. "
      "He transferred {amount} through RTGS to <<account|account {account}|the account told by them>>"
      "<<account2| and {account2}|>>.", gender="male"),
    T("cyber.digital_arrest",
      ("impersonated_police_or_agency", "threat_of_arrest_or_case", "money_to_mule_account"),
      "Phone aaya <<phone|{phone}|unknown number>> se ki aapke naam ki SIM se illegal ads aur harassment messages "
      "gaye hain, TRAI aapka number band karega. Then a so-called {cop_persona} from {agency} said a FIR is "
      "registered in Mumbai and I will be arrested today if I do not cooperate. For 'verification' of my funds I "
      "sent {amount} to <<account|a/c {account}|their account>><<upi| and {upi}|>>. Later I understood it was fraud."),

    # ------------------------------------------------------------------ cyber.investment_trading
    T("cyber.investment_trading",
      ("promise_of_high_returns", "phishing_link_or_fake_app", "money_to_mule_account"),
      "I was added to a WhatsApp group called {group} where a person named {advisor} used to give daily stock "
      "market tips. He told me to download the trading app {app}<<handle| from {handle}|>> to get IPO allotment and "
      "block trades with 300 percent profit. The app showed my profit as Rs. {profit} but when I tried to withdraw "
      "they asked me to first pay 20 percent tax and service charge. In total I invested {amount} in {n_txn} "
      "transfers to <<account|account {account}|different accounts>><<upi| and UPI ID {upi}|>>."),
    T("cyber.investment_trading",
      ("promise_of_high_returns", "phishing_link_or_fake_app", "fake_relationship_or_marriage", "money_to_mule_account"),
      "The complainant states that a lady contacted him on Instagram, became friendly and told him she earns good "
      "money in crypto trading. She made him register on the website <<handle|{handle}|given by her>> where he "
      "invested small amounts first and saw profit. Then {advisor} from the 'support team' told him to invest more "
      "to reach VIP level. He deposited {amount} to <<account|account no. {account}|the accounts given by them>>. "
      "Now the website does not allow withdrawal.", gender="male"),

    # ------------------------------------------------------------------ cyber.job_task
    T("cyber.job_task",
      ("paid_tasks_or_job_offer", "advance_or_fee_payment", "money_to_mule_account"),
      "I got a WhatsApp message for a part-time work from home job of giving 5-star reviews to hotels on Google Maps, "
      "Rs. 150 per task. Then they added me to a Telegram group <<handle|{handle}|>>. First they paid me Rs. 450. "
      "Then the task manager {persona} gave me prepaid tasks and said I have to deposit money to complete the tasks "
      "and get commission. I deposited {amount} to <<upi|UPI ID {upi}|the UPI IDs given by them>><<account| and "
      "account {account}|>> but I did not get any money back."),
    T("cyber.job_task",
      ("paid_tasks_or_job_offer", "promise_of_high_returns", "advance_or_fee_payment", "money_to_mule_account"),
      "The complainant, {a_occupation}, states that she was offered an online job of liking YouTube videos by a "
      "person on Telegram <<handle|with the id {handle}|>>. After some tasks she was told to join 'merchant tasks' "
      "which give 30 percent return. She paid {amount} in {n_txn} parts to <<account|account {account}|different "
      "accounts>><<upi| and {upi}|>> and each time they asked more money to release her balance.", gender="female"),

    # ------------------------------------------------------------------ cyber.loan_app
    T("cyber.loan_app",
      ("loan_app_recovery_harassment", "morphed_or_obscene_content"),
      "I took a small loan of Rs. {small_amt} from the mobile app {loan_app} and repaid it on time. Still the "
      "recovery agents keep calling me <<phone|from {phone}|from different numbers>> and demand {amount}. They have "
      "morphed my photos into obscene pictures and sent them to my relatives from my contact list. They abuse me on "
      "phone and threaten to make the photos viral."),
    T("cyber.loan_app",
      ("loan_app_recovery_harassment", "morphed_or_obscene_content", "money_to_mule_account"),
      "The complainant states that after installing the loan app {loan_app} the app took access of his contacts and "
      "gallery. Even after repaying, the agents <<phone|calling from {phone}|>> sent his morphed photo with abusive "
      "message to his office colleagues. Out of fear he paid {amount} more <<upi|to UPI ID {upi}|to them>>, but the "
      "harassment has not stopped.", gender="male"),

    # ------------------------------------------------------------------ cyber.sextortion
    T("cyber.sextortion",
      ("video_call_used", "morphed_or_obscene_content", "impersonated_police_or_agency", "threat_of_arrest_or_case",
       "money_to_mule_account"),
      "I got a video call on WhatsApp <<phone|from {phone}|from an unknown number>> from a girl who said her name is "
      "{girl_name}. She showed obscene video and my face was recorded. Next day a person called <<phone2|from "
      "{phone2}|from another number>> saying he is {cop_persona} from Delhi Crime Branch and a case will be filed "
      "against me unless I pay to delete the video from YouTube. I paid {amount} to <<upi|UPI ID {upi}|the account "
      "he gave>>.", gender="male"),
    T("cyber.sextortion",
      ("video_call_used", "morphed_or_obscene_content", "money_to_mule_account"),
      "The complainant states that a friend request came on Facebook from a girl, then she asked his WhatsApp number "
      "and made a video call <<phone|from {phone}|>> at night. The call was recorded and edited into an obscene "
      "clip, and they threatened to send it to his family and friends. He paid {amount} <<upi|to {upi}|online>> but "
      "they are still demanding more money.", gender="male"),

    # ------------------------------------------------------------------ cyber.marketplace
    T("cyber.marketplace",
      ("fake_marketplace_listing", "impersonated_army_officer", "advance_or_fee_payment", "money_to_mule_account"),
      "I saw an advertisement on OLX for a {vehicle_item} for Rs. {price}. The seller said he is {army_persona} of "
      "the Indian Army posted at {cantonment} and he is selling urgently due to transfer. He sent photos of his army "
      "ID card and canteen card. He asked Rs. {small_amt} as advance and then gate pass charges and transport charges "
      "for army parcel service. I paid total {amount} to <<upi|UPI ID {upi}|the UPI given by him>>. His number "
      "<<phone|{phone}|>> is now switched off."),
    T("cyber.marketplace",
      ("fake_marketplace_listing", "impersonated_army_officer", "phishing_link_or_fake_app", "money_to_mule_account"),
      "The complainant had posted his sofa set for sale on OLX. A buyer who said he is {army_persona} from the army "
      "called <<phone|from {phone}|>> and agreed to buy. To send the payment he sent a QR code and asked the "
      "complainant to scan it and enter his UPI PIN to receive money. Instead {amount} was debited from the "
      "complainant's account <<upi|and went to {upi}|>>.", gender="male"),

    # ------------------------------------------------------------------ cyber.matrimonial
    T("cyber.matrimonial",
      ("fake_relationship_or_marriage", "advance_or_fee_payment", "money_to_mule_account"),
      "I came in contact with {groom_persona} on {matrimony_site} who said he is a doctor settled in {country}. We "
      "talked daily on WhatsApp<<phone| on number {phone}|>>. He said he sent me a gift parcel with gold jewellery "
      "and foreign currency. Then a lady from customs at Delhi airport called and asked for customs duty and "
      "clearance charges. I paid {amount} to <<account|account {account}|the accounts told by her>>. After that "
      "all contact stopped.", gender="female"),
    T("cyber.matrimonial",
      ("fake_relationship_or_marriage", "money_to_mule_account"),
      "The complainant, {a_occupation}, states that she met {groom_persona} through {matrimony_site}, who "
      "introduced himself as an engineer working abroad. After some weeks he said his mother is admitted in hospital "
      "and his cards are blocked. She transferred {amount} <<account|to account {account}|to him>><<upi| and to "
      "{upi}|>>. His profile is now deleted and phone is off.", gender="female"),

    # ------------------------------------------------------------------ property.vehicle_theft
    T("property.vehicle_theft",
      ("vehicle_taken_from_parking",),
      "I had parked my {bike_model} bearing registration no. {victim_vehicle} outside {parking_place} at about "
      "{time}. When I came back at {time2} it was not there. I searched nearby but could not find it. <<accused|The "
      "CCTV of a nearby shop shows {accused_desc} taking it away.|No CCTV is available at that place.>> The vehicle "
      "is worth about {amount}."),
    T("property.vehicle_theft",
      ("vehicle_taken_from_parking",),
      "The complainant states that on the night of {date_occ} he had parked his {bike_model} no. {victim_vehicle} "
      "in the society parking with handle lock. In the morning the vehicle was missing. Society watchman did not see "
      "anything. <<accused|Later a resident informed that {accused_desc} was roaming in the society the previous "
      "night.|>> <<vehicle|A tempo no. {vehicle} was seen standing outside the gate at night.|>>", gender="male"),
    T("property.vehicle_theft",
      ("vehicle_taken_from_parking",),
      "Maine apni {bike_model} ({victim_vehicle}) {parking_place} ke bahar park ki thi. Kaam khatam karke aaya to "
      "gaadi nahi thi. The key was with me. <<accused|Shopkeeper said {accused_desc} was checking the bikes there.|>> "
      "Value approx {amount}."),

    # ------------------------------------------------------------------ property.burglary
    T("property.burglary",
      ("forced_entry", "premises_unoccupied"),
      "The complainant states that his family had gone to {town} for a relative's wedding and the house was locked. "
      "On return they found the main door lock broken and the cupboard open. Gold ornaments of about {grams} grams "
      "and cash Rs. {cash} were missing, total value about {amount}. <<accused|A neighbour saw {accused_desc} near "
      "the house at night.|>> <<vehicle|A white car no. {vehicle} was seen parked outside that night.|>>", gender="male"),
    T("property.burglary",
      ("forced_entry", "premises_unoccupied"),
      "I run a shop at {place}. On the night of {date_occ} I closed the shop at 10 pm. In the morning I found the back window "
      "grill cut and the cash counter broken. Cash {amount} and some mobile phones were stolen<<imei|, including a "
      "phone with IMEI {imei}|>>. <<accused|In the CCTV footage {accused_desc} can be seen entering with a cutter.|>> "
      "<<vehicle|They came in a car with number {vehicle}.|>>"),
    T("property.burglary",
      ("forced_entry", "premises_unoccupied"),
      "Hum log {town} gaye the, ghar pe koi nahi tha. The neighbour called that our door is open. The lock was "
      "broken with some tool and silver and gold jewellery worth {amount} was stolen from the bedroom. "
      "<<accused|The police dog squad and CCTV show {accused_desc}.|>>"),

    # ------------------------------------------------------------------ property.snatching
    T("property.snatching",
      ("motorcycle_used",),
      "I was walking back from {place} at about {time} when two men came from behind on a black motorcycle and the "
      "pillion rider snatched my gold chain of about {grams} grams and they ran away. <<vehicle|I noted the number "
      "as {vehicle}.|I could not see the number plate.>> <<accused|Later from CCTV the rider was identified as "
      "{accused_name}.|>> The chain is worth about {amount}.", gender="female"),
    T("property.snatching",
      ("motorcycle_used",),
      "The complainant states that she was talking on her mobile near {place} when two youths on a bike came and "
      "snatched her mobile phone<<imei| (IMEI {imei})|>> and ran towards the main road. <<vehicle|The bike number was "
      "{vehicle}.|>> <<accused|People nearby said one of them was {accused_name}.|>> Value about {amount}.", gender="female"),

    # ------------------------------------------------------------------ property.robbery
    T("property.robbery",
      ("weapon_shown",),
      "At about {time} near {place} three persons stopped me, showed a knife and took my mobile phone, wallet with "
      "Rs. {cash} and gold ring. They threatened to kill me if I shouted. <<accused|One of them was called "
      "{accused_name} by the others.|>> Total loss about {amount}."),
    T("property.robbery",
      ("weapon_shown", "physical_violence", "motorcycle_used"),
      "The complainant, a delivery partner, states that while returning at night two persons on a motorcycle stopped "
      "him near {place}, hit him on the head and at knife point took his bag with cash {amount} and his "
      "phone<<imei| (IMEI {imei})|>>. <<vehicle|The motorcycle number was {vehicle}.|>>", gender="male"),

    # ------------------------------------------------------------------ property.theft_other
    T("property.theft_other",
      (),
      "I was travelling in AMTS bus from {place} to {place2}. In the crowd somebody took my wallet from my back pocket. "
      "It had Rs. {cash}, my Aadhaar card and ATM card. I noticed only when I got down."),
    T("property.theft_other",
      (),
      "The complainant states that he kept his mobile phone<<imei| (IMEI {imei})|>> on the bench while exercising at "
      "a gym at {place} and after 20 minutes it was missing. Value about {amount}. <<accused|He suspects "
      "{accused_name} who joined the gym recently.|>>", gender="male"),
    T("property.theft_other",
      (),
      "Our shop at {place} is facing shortage of goods for the last two months. On checking the stock and CCTV we "
      "found that the employee <<accused|{accused_name}|working at the counter>> was taking goods and cash. Total "
      "loss is about {amount}."),

    # ------------------------------------------------------------------ body.assault
    T("body.assault",
      ("physical_violence",),
      "There was an argument about parking of vehicle with my neighbour {accused_name}. He and his son came to my "
      "house at about {time}, abused me and beat me with a wooden stick. I got injury on my hand and head and was "
      "treated at civil hospital."),
    T("body.assault",
      ("physical_violence", "weapon_shown"),
      "The complainant states that {accused_name} had a money dispute with him. On {date_occ} near {place} the accused "
      "stopped him, abused him and hit him with a pipe, causing injury on the back. People gathered and the accused "
      "ran away saying he will see him again.", gender="male"),

    # ------------------------------------------------------------------ body.intimidation
    T("body.intimidation",
      ("verbal_threat_in_person",),
      "The complainant states that {accused_name} is pressuring him to sell his plot at {place} at a low price. "
      "On {date_occ} the accused came to his office with two other persons and threatened that if he does not sign the "
      "papers he and his family will face bad consequences.", gender="male"),
    T("body.intimidation",
      ("verbal_threat_in_person",),
      "Mera padosi {accused_name} roz gaali deta hai aur dhamki deta hai ki ghar khali karo warna jaan se maar "
      "dunga. On {date_occ} at {time} he again came to my door and threatened me in front of other residents."),

    # ------------------------------------------------------------------ economic.cheating_offline
    T("economic.cheating_offline",
      ("advance_or_fee_payment",),
      "The complainant states that {accused_name}, who runs an overseas placement office at {place}, promised "
      "him a job in Canada and took {amount} in cash and cheque for visa and processing. After six months neither "
      "visa nor money is given and the office is closed.", gender="male"),
    T("economic.cheating_offline",
      ("advance_or_fee_payment",),
      "I gave {amount} as token money to {accused_name} for purchase of a plot at {place}. Later I came to know the "
      "same plot was already sold to another person and the papers given to me are fake."),
)


def templates_for(minor: str) -> list[Template]:
    found = [t for t in TEMPLATES if t.minor == minor]
    if not found:
        raise KeyError(f"no templates for {minor}")
    return found
