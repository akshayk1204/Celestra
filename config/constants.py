# Region mapping based on ISO Alpha-2 codes
# AMER = US and CA
# LATAM = Other countries in the Americas
# EMEA = Europe, Middle East, and Africa
# APAC = Asia and Oceania

INCLUDED_REGIONS = {}

AMER_COUNTRIES = {"US", "CA"}
LATAM_COUNTRIES = {
    "AI", "AG", "AR", "AW", "BS", "BB", "BZ", "BM", "BO", "BQ", "BR", "BV", "CL", "CO", "CR", "CU", "CW",
    "DM", "DO", "EC", "SV", "FK", "GL", "GD", "GP", "GT", "GY", "HT", "HN", "JM", "MQ", "MX", "MS", "NI",
    "PA", "PY", "PE", "PR", "BL", "KN", "LC", "MF", "PM", "VC", "SR", "SX", "TT", "TC", "UY", "VE", "VG",
    "VI", "GS"
}
EMEA_COUNTRIES = {
    # Europe
    "AX", "AL", "AD", "AT", "BY", "BE", "BA", "BG", "HR", "CZ", "DK", "EE", "FO", "FI", "FR", "DE", "GI",
    "GR", "GG", "HU", "IS", "IE", "IM", "IT", "JE", "LV", "LI", "LT", "LU", "MT", "MD", "MC", "ME", "NL",
    "MK", "NO", "PL", "PT", "RO", "RU", "SM", "RS", "SK", "SI", "ES", "SJ", "SE", "CH", "UA", "GB", "VA",

    # Middle East (Asia region, but EMEA classification)
    "BH", "CY", "GE", "IR", "IQ", "IL", "JO", "KW", "LB", "OM", "PS", "QA", "SA", "SY", "AE", "YE", "TR",

    # Africa
    "DZ", "AO", "BJ", "BW", "BF", "BI", "CV", "CM", "CF", "TD", "KM", "CG", "CD", "CI", "DJ", "EG", "GQ",
    "ER", "SZ", "ET", "GA", "GM", "GH", "GN", "GW", "KE", "LS", "LR", "LY", "MG", "MW", "ML", "MR", "MU",
    "YT", "MA", "MZ", "NA", "NE", "NG", "RE", "RW", "SH", "ST", "SN", "SC", "SL", "ZA", "SO", "SS", "SD",
    "TZ", "TG", "TN", "UG", "EH", "ZM", "ZW", "TF"
}
APAC_COUNTRIES = {
    # Asia (excluding EMEA Middle East overlap)
    "AF", "AM", "AZ", "BD", "BT", "BN", "KH", "CN", "IN", "ID", "JP", "KZ", "KP", "KR", "KG", "LA", "MO",
    "MY", "MV", "MN", "MM", "NP", "PK", "PH", "SG", "LK", "TW", "TJ", "TH", "TL", "TM", "UZ", "VN",

    # Oceania
    "AS", "AU", "CX", "CC", "CK", "FJ", "PF", "GU", "HM", "KI", "MH", "FM", "NR", "NC", "NZ", "NU", "NF",
    "MP", "PW", "PG", "PN", "SB", "TK", "TO", "TV", "UM", "VU", "WF", "WS"
}

for country in AMER_COUNTRIES:
    INCLUDED_REGIONS[country] = "AMER"
for country in LATAM_COUNTRIES:
    INCLUDED_REGIONS[country] = "LATAM"
for country in EMEA_COUNTRIES:
    INCLUDED_REGIONS[country] = "EMEA"
for country in APAC_COUNTRIES:
    INCLUDED_REGIONS[country] = "APAC"

DEFAULT_REGION = "Other"
