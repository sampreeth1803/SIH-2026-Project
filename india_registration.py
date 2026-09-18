"""Conservative Indian registration-mark validation and state lookup."""
from __future__ import annotations
import re
from privacy import normalize_plate
PLATE_PATTERN = re.compile(r"^([A-Z]{2})(\d{1,2})([A-Z]{0,3})(\d{1,4})$")
STATE_CODES = {"AP":"Andhra Pradesh","AR":"Arunachal Pradesh","AS":"Assam","BR":"Bihar","CG":"Chhattisgarh","CH":"Chandigarh","DD":"Dadra and Nagar Haveli and Daman and Diu","DL":"Delhi","GA":"Goa","GJ":"Gujarat","HP":"Himachal Pradesh","HR":"Haryana","JH":"Jharkhand","JK":"Jammu and Kashmir","KA":"Karnataka","KL":"Kerala","LA":"Ladakh","LD":"Lakshadweep","MH":"Maharashtra","ML":"Meghalaya","MN":"Manipur","MP":"Madhya Pradesh","MZ":"Mizoram","NL":"Nagaland","OD":"Odisha","PB":"Punjab","PY":"Puducherry","RJ":"Rajasthan","SK":"Sikkim","TN":"Tamil Nadu","TR":"Tripura","TS":"Telangana","UK":"Uttarakhand","UP":"Uttar Pradesh","WB":"West Bengal"}
KARNATAKA_RTO = {"01":"Bengaluru Central","02":"Bengaluru West","03":"Bengaluru East","04":"Bengaluru North","05":"Bengaluru South"}
def infer_indian_registration(value: str) -> dict:
    plate = normalize_plate(value); match = PLATE_PATTERN.fullmatch(plate)
    if not match or match.group(1) not in STATE_CODES: return {"supported":False,"country":None,"state":None,"registration_area":None,"reason":"The confirmed text does not match a supported Indian registration format."}
    state_code, office_code = match.group(1), match.group(2).zfill(2)
    return {"supported":True,"country":"India","state":STATE_CODES[state_code],"registration_area":KARNATAKA_RTO.get(office_code) if state_code == "KA" else None,"registration_code":f"{state_code}-{office_code}","reason":"Registration area is an issuance area, not a current vehicle location."}
