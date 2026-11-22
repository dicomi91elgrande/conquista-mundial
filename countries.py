# -*- coding: utf-8 -*-
"""Tabla de países (ISO alfa-2 | ISO numérico | nombre | continente | alias) y buscador difuso."""
import re
import unicodedata

CONTS = {'EU': 'Europa', 'AS': 'Asia', 'AF': 'África', 'NA': 'Norteamérica', 'SA': 'Sudamérica', 'OC': 'Oceanía'}

RAW = """
AL|008|Albania|EU|
AD|020|Andorra|EU|
AT|040|Austria|EU|
BY|112|Bielorrusia|EU|belarus
BE|056|Bélgica|EU|belgium
BA|070|Bosnia|EU|bosniayherzegovina,bosniaherzegovina
BG|100|Bulgaria|EU|
HR|191|Croacia|EU|croatia
CY|196|Chipre|EU|cyprus
CZ|203|Chequia|EU|republicacheca,checa,czechia
DK|208|Dinamarca|EU|denmark
EE|233|Estonia|EU|
FI|246|Finlandia|EU|finland
FR|250|Francia|EU|france
DE|276|Alemania|EU|germany,deutschland
GR|300|Grecia|EU|greece
HU|348|Hungría|EU|hungary
IS|352|Islandia|EU|iceland
IE|372|Irlanda|EU|ireland
IT|380|Italia|EU|italy
LV|428|Letonia|EU|latvia
LI|438|Liechtenstein|EU|
LT|440|Lituania|EU|lithuania
LU|442|Luxemburgo|EU|luxembourg
MT|470|Malta|EU|
MD|498|Moldavia|EU|moldova
MC|492|Mónaco|EU|
ME|499|Montenegro|EU|
NL|528|Países Bajos|EU|holanda,netherlands
MK|807|Macedonia del Norte|EU|macedonia
NO|578|Noruega|EU|norway
PL|616|Polonia|EU|poland
PT|620|Portugal|EU|
RO|642|Rumanía|EU|romania
RU|643|Rusia|EU|russia
SM|674|San Marino|EU|
RS|688|Serbia|EU|
SK|703|Eslovaquia|EU|slovakia
SI|705|Eslovenia|EU|slovenia
ES|724|España|EU|spain
SE|752|Suecia|EU|sweden
CH|756|Suiza|EU|switzerland
UA|804|Ucrania|EU|ukraine
GB|826|Reino Unido|EU|uk,inglaterra,granbretana,england,escocia,gales
VA|336|Vaticano|EU|ciudaddelvaticano
XK|-|Kosovo|EU|
AF|004|Afganistán|AS|afghanistan
AM|051|Armenia|AS|
AZ|031|Azerbaiyán|AS|azerbaijan,azerbayan
BH|048|Baréin|AS|bahrein,bahrain
BD|050|Bangladés|AS|bangladesh
BT|064|Bután|AS|bhutan
BN|096|Brunéi|AS|
KH|116|Camboya|AS|cambodia
CN|156|China|AS|
GE|268|Georgia|AS|
IN|356|India|AS|
ID|360|Indonesia|AS|
IR|364|Irán|AS|
IQ|368|Irak|AS|iraq
IL|376|Israel|AS|
JP|392|Japón|AS|japan
JO|400|Jordania|AS|jordan
KZ|398|Kazajistán|AS|kazajstan,kazakhstan,kazakistan
KW|414|Kuwait|AS|
KG|417|Kirguistán|AS|kirguizistan,kyrgyzstan
LA|418|Laos|AS|
LB|422|Líbano|AS|lebanon
MY|458|Malasia|AS|malaysia
MV|462|Maldivas|AS|maldives
MN|496|Mongolia|AS|
MM|104|Myanmar|AS|birmania
NP|524|Nepal|AS|
KP|408|Corea del Norte|AS|norcorea,northkorea
OM|512|Omán|AS|
PK|586|Pakistán|AS|
PS|275|Palestina|AS|palestine
PH|608|Filipinas|AS|philippines
QA|634|Catar|AS|qatar
SA|682|Arabia Saudita|AS|arabiasaudi,arabia,saudiarabia
SG|702|Singapur|AS|singapore
KR|410|Corea del Sur|AS|corea,surcorea,southkorea,korea
LK|144|Sri Lanka|AS|
SY|760|Siria|AS|syria
TW|158|Taiwán|AS|
TJ|762|Tayikistán|AS|tajikistan
TH|764|Tailandia|AS|thailand
TL|626|Timor Oriental|AS|timor,timorleste
TR|792|Turquía|AS|turkey,turkiye
TM|795|Turkmenistán|AS|
AE|784|Emiratos Árabes|AS|emiratosarabesunidos,emiratos,eau,dubai
UZ|860|Uzbekistán|AS|
VN|704|Vietnam|AS|
YE|887|Yemen|AS|
HK|344|Hong Kong|AS|
DZ|012|Argelia|AF|algeria
AO|024|Angola|AF|
BJ|204|Benín|AF|
BW|072|Botsuana|AF|botswana
BF|854|Burkina Faso|AF|burkina
BI|108|Burundi|AF|
CM|120|Camerún|AF|cameroon
CV|132|Cabo Verde|AF|
CF|140|República Centroafricana|AF|centroafrica,centroafricana
TD|148|Chad|AF|
KM|174|Comoras|AF|
CG|178|Congo|AF|republicadelcongo
CD|180|RD Congo|AF|republicademocraticadelcongo,congodemocratico,rdc
CI|384|Costa de Marfil|AF|ivorycoast
DJ|262|Yibuti|AF|djibouti
EG|818|Egipto|AF|egypt
GQ|226|Guinea Ecuatorial|AF|
ER|232|Eritrea|AF|
SZ|748|Esuatini|AF|suazilandia,swazilandia,eswatini
ET|231|Etiopía|AF|ethiopia
GA|266|Gabón|AF|
GM|270|Gambia|AF|
GH|288|Ghana|AF|
GN|324|Guinea|AF|
GW|624|Guinea-Bisáu|AF|guineabissau
KE|404|Kenia|AF|kenya
LS|426|Lesoto|AF|lesotho
LR|430|Liberia|AF|
LY|434|Libia|AF|libya
MG|450|Madagascar|AF|
MW|454|Malaui|AF|malawi
ML|466|Malí|AF|
MR|478|Mauritania|AF|
MU|480|Mauricio|AF|mauritius
MA|504|Marruecos|AF|morocco
MZ|508|Mozambique|AF|
NA|516|Namibia|AF|
NE|562|Níger|AF|
NG|566|Nigeria|AF|
RW|646|Ruanda|AF|rwanda
ST|678|Santo Tomé y Príncipe|AF|santotome
SN|686|Senegal|AF|
SC|690|Seychelles|AF|
SL|694|Sierra Leona|AF|
SO|706|Somalia|AF|
ZA|710|Sudáfrica|AF|surafrica,southafrica
SS|728|Sudán del Sur|AF|
SD|729|Sudán|AF|
TZ|834|Tanzania|AF|
TG|768|Togo|AF|
TN|788|Túnez|AF|tunisia
UG|800|Uganda|AF|
ZM|894|Zambia|AF|
ZW|716|Zimbabue|AF|zimbabwe
AG|028|Antigua y Barbuda|NA|antigua
BS|044|Bahamas|NA|
BB|052|Barbados|NA|
BZ|084|Belice|NA|belize
CA|124|Canadá|NA|
CR|188|Costa Rica|NA|
CU|192|Cuba|NA|
DM|212|Dominica|NA|
DO|214|República Dominicana|NA|dominicana,repdominicana
SV|222|El Salvador|NA|salvador
GD|308|Granada|NA|grenada
GT|320|Guatemala|NA|
HT|332|Haití|NA|
HN|340|Honduras|NA|
JM|388|Jamaica|NA|
MX|484|México|NA|mejico
NI|558|Nicaragua|NA|
PA|591|Panamá|NA|
KN|659|San Cristóbal y Nieves|NA|sancristobal
LC|662|Santa Lucía|NA|
VC|670|San Vicente y las Granadinas|NA|sanvicente
TT|780|Trinidad y Tobago|NA|trinidad
US|840|Estados Unidos|NA|eeuu,usa,eua,estadosunidosdeamerica,unitedstates
PR|630|Puerto Rico|NA|
GL|304|Groenlandia|NA|greenland
AR|032|Argentina|SA|
BO|068|Bolivia|SA|
BR|076|Brasil|SA|brazil
CL|152|Chile|SA|
CO|170|Colombia|SA|
EC|218|Ecuador|SA|
GY|328|Guyana|SA|
PY|600|Paraguay|SA|
PE|604|Perú|SA|
SR|740|Surinam|SA|suriname
UY|858|Uruguay|SA|
VE|862|Venezuela|SA|
AU|036|Australia|OC|
FJ|242|Fiyi|OC|fiji
KI|296|Kiribati|OC|
MH|584|Islas Marshall|OC|marshall
FM|583|Micronesia|OC|
NR|520|Nauru|OC|
NZ|554|Nueva Zelanda|OC|nuevazelandia,newzealand
PW|585|Palaos|OC|palau
PG|598|Papúa Nueva Guinea|OC|papua
WS|882|Samoa|OC|
SB|090|Islas Salomón|OC|salomon
TO|776|Tonga|OC|
TV|798|Tuvalu|OC|
VU|548|Vanuatu|OC|
"""


def slug(text):
    text = unicodedata.normalize('NFD', (text or '').strip().lower())
    text = ''.join(ch for ch in text if unicodedata.category(ch) != 'Mn')
    return re.sub(r'[^a-z0-9]', '', text)


COUNTRIES = []      # [{code, num, name, cont}]
BY_CODE = {}
INDEX = {}          # slug -> code
for _line in RAW.strip().splitlines():
    _code, _num, _name, _cont, _alias = _line.split('|')
    _c = {'code': _code, 'num': _num, 'name': _name, 'cont': _cont}
    COUNTRIES.append(_c)
    BY_CODE[_code] = _c
    for _s in [slug(_name)] + [slug(a) for a in _alias.split(',') if a]:
        INDEX.setdefault(_s, _code)

PREFIXES = ('a', 'al', 'el', 'la', 'los', 'las', 'en', 'de')


def edit_distance(a, b):
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def find_country(cands):
    """cands: uno o varios textos candidatos (ya sin el comando). Devuelve código ISO o None."""
    if isinstance(cands, str):
        cands = [cands]
    base = []
    for c in cands:
        s = slug(c)
        if s and s not in base:
            base.append(s)
    # 1) exacto
    for s in base:
        if s in INDEX:
            return INDEX[s]
    # 2) exacto quitando artículo/preposición inicial ("a alemania", "el salvador")
    stripped = []
    for s in base:
        for p in PREFIXES:
            if s.startswith(p) and len(s) - len(p) >= 4:
                t = s[len(p):]
                if t in INDEX:
                    return INDEX[t]
                stripped.append(t)
    allc = base + stripped
    # 3) el texto empieza por un país ("tailandiaporfavor") -> el más largo
    best = None
    for s in allc:
        for k, code in INDEX.items():
            if len(k) >= 4 and s.startswith(k) and (best is None or len(k) > len(best[0])):
                best = (k, code)
    if best:
        return best[1]
    # 4) el texto es el principio de un único país ("estadosuni")
    for s in allc:
        if len(s) >= 5:
            hits = {code for k, code in INDEX.items() if k.startswith(s)}
            if len(hits) == 1:
                return hits.pop()
    # 5) difuso (erratas), solo si hay un único mejor candidato
    best_d, best_codes = 99, set()
    for s in allc:
        if len(s) < 4:
            continue
        limit = 2 if len(s) >= 8 else 1
        for k, code in INDEX.items():
            if abs(len(k) - len(s)) > limit:
                continue
            d = edit_distance(s, k)
            if d <= limit:
                if d < best_d:
                    best_d, best_codes = d, {code}
                elif d == best_d:
                    best_codes.add(code)
    if len(best_codes) == 1:
        return best_codes.pop()
    return None
