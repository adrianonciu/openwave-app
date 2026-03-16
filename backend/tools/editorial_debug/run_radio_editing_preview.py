from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.config.env import get_openwave_debug_sample_dir, get_openwave_mode, get_openwave_real_samples_root
from app.models.user_personalization import EditorialPreferenceProfile, GeographyPreferenceMix, ListenerProfile, UserPersonalization
from app.services.editorial_pipeline_service import EditorialPipelineService
from app.services.radio_editing_service import RadioEditingService
from app.services.romanian_geo_resolver import resolve_listener_geography
from app.services.source_watcher_service import SourceWatcherService
from app.services.tts_pronunciation_helper import get_tts_pronunciation_map
from tools.editorial_debug.real_sample_workflow import (
    build_personalization,
    build_preview_payload_from_articles,
    default_sample_output_dir,
    load_real_sample,
    resolve_real_sample_dir,
    save_real_sample_bundle,
)

OUTPUT_DIR = BACKEND_ROOT / "debug_output"
JSON_OUTPUT_PATH = OUTPUT_DIR / "radio_editing_preview.json"
TEXT_OUTPUT_PATH = OUTPUT_DIR / "radio_editing_preview.txt"
GENERALIST_OUTPUT_PATH = OUTPUT_DIR / "sample_generalist_bulletin_mihai_bacau.txt"
VICTOR_VASLUI_OUTPUT_PATH = OUTPUT_DIR / "sample_generalist_bulletin_victor_vaslui.txt"
ANA_TIMISOARA_OUTPUT_PATH = OUTPUT_DIR / "sample_generalist_bulletin_ana_timisoara.txt"
ION_GALATI_OUTPUT_PATH = OUTPUT_DIR / "sample_generalist_bulletin_ion_galati.txt"
MARIA_OLT_OUTPUT_PATH = OUTPUT_DIR / "sample_generalist_bulletin_maria_olt.txt"
GEORGE_COVASNA_OUTPUT_PATH = OUTPUT_DIR / "sample_generalist_bulletin_george_covasna.txt"
NICU_CONSTANTA_OUTPUT_PATH = OUTPUT_DIR / "sample_generalist_bulletin_nicu_constanta.txt"
LIVE_NICU_CONSTANTA_OUTPUT_PATH = OUTPUT_DIR / "live_generalist_bulletin_nicu_constanta.txt"
LIVE_SOURCE_REGISTRY_AUDIT_PATH = OUTPUT_DIR / "live_source_registry_audit.json"
GEO_TAGGING_PREVIEW_PATH = OUTPUT_DIR / "geo_tagging_preview.json"
REAL_SAMPLE_BULLETIN_OUTPUT_PATH = OUTPUT_DIR / "sample_real_debug_bulletin.txt"

PREVIEW_FIXTURES = [
    {
        "story_id": "national_policy_01",
        "source_label": "Agerpres",
        "headline": "Ilie Bolojan anunta o ordonanta pentru simplificarea avizelor de investitii",
        "content_text": (
            "Premierul Ilie Bolojan a anuntat ca Guvernul Romaniei a adoptat o ordonanta care simplifica procedurile de avizare pentru proiectele mari de investitii. "
            "Actul reduce numarul de avize, scurteaza termenele de raspuns si introduce o platforma comuna pentru institutiile care emit aprobari. "
            "Ilie Bolojan a spus ca masura ar trebui sa grabeasca proiectele publice si private si sa reduca birocratia pentru investitori. "
            "Ministerul Finantelor estimeaza costuri administrative mai mici pentru companii. "
            "Primele efecte sunt asteptate in urmatoarele saptamani pentru proiectele aflate deja in procedura."
        ),
    },
    {
        "story_id": "justice_01",
        "source_label": "HotNews",
        "headline": "CSM da aviz negativ pentru un procuror-sef adjunct propus la DNA",
        "content_text": (
            "Consiliul Superior al Magistraturii a dat aviz negativ pentru numirea unui procuror-sef adjunct la DNA. "
            "CSM a transmis ca avizul vine dupa audieri si evaluarea planului de management. "
            "Ministerul Justitiei poate trimite propunerea mai departe catre Presedintie. "
            "Decizia mentine presiunea publica asupra numirilor din marile parchete. "
            "Asta inseamna ca Ministerul Justitiei trebuie sa revina cu o noua justificare sau cu alt nume pentru functie."
        ),
    },
    {
        "story_id": "economy_01",
        "source_label": "Digi24",
        "headline": "ANAF anunta controale extinse dupa o schema de frauda cu TVA",
        "content_text": (
            "ANAF a anuntat controale extinse dupa descoperirea unei scheme de frauda cu TVA care ar fi functionat prin firme fantoma si facturi fictive. "
            "Inspectorii spun ca prejudiciul estimat trece de 2.347.819 lei si ca verificarile vizeaza mai multe lanturi de tranzactii. "
            "ANAF a transmis ca a blocat deja o parte din rambursarile suspecte si lucreaza cu procurorii pentru recuperarea banilor. "
            "Asta inseamna presiune mai mare pe firmele verificate si pe colectarea la buget. "
            "Primele rezultate oficiale ar urma sa fie prezentate dupa centralizarea controalelor din teritoriu."
        ),
    },
    {
        "story_id": "international_impact_01",
        "source_label": "Reuters",
        "headline": "Statele Unite trimit nave suplimentare spre Stramtoarea Ormuz",
        "content_text": (
            "Casa Alba a anuntat ca Statele Unite trimit nave suplimentare spre Stramtoarea Ormuz dupa noi atacuri asupra transportului comercial. "
            "Washingtonul spune ca masura are rolul de a proteja rutele maritime si de a descuraja alte incidente. "
            "Iranul respinge acuzatiile privind implicarea directa. "
            "Pentru Romania si restul Europei, tensiunea poate duce la preturi mai mari la petrol si energie. "
            "Traderii urmaresc deja riscul unui nou soc pe piata petrolului si al unor costuri mai mari la transport."
        ),
    },
    {
        "story_id": "local_01",
        "source_label": "Monitorul de Bacau",
        "headline": "Primaria Bacau incepe lucrari noi pe un coridor important de trafic",
        "content_text": (
            "Primaria Bacau anunta ca incepe luni lucrari noi pe un coridor important de trafic dintre centru si zona de nord a orasului. "
            "Santierul include reabilitarea carosabilului, benzi pentru transportul public si modificari la semaforizare. "
            "Primaria a transmis ca soferii vor circula pe benzi restranse in mai multe etape. "
            "Impactul este direct pentru mii de navetisti si studenti care trec zilnic prin zona. "
            "Compania de Transport Public pregateste rute ocolitoare si timpi de asteptare mai mari la orele de varf."
        ),
    },
]

GENERALIST_BULLETIN_FIXTURES = [
    {
        "story_id": "bacau_01",
        "source_label": "Ziarul de Bacau",
        "headline": "Primaria Bacau incepe lucrari la pasajul din zona Garii",
        "content_text": (
            "Primarul Lucian Viziteu a anuntat ca Primaria Bacau incepe lucrari la pasajul din zona Garii. "
            "Santierul va inchide partial doua benzi si va muta statiile de autobuz timp de aproape o luna. "
            "Asta inseamna trafic mai greu la orele de varf pentru soferi si navetisti. "
            "Primele restrictii intra in vigoare de luni dimineata."
        ),
    },
    {
        "story_id": "bacau_02",
        "source_label": "Desteptarea",
        "headline": "Consiliul Judetean Bacau extinde programul pentru drumurile afectate de alunecari",
        "content_text": (
            "Consiliul Judetean Bacau a aprobat bani in plus pentru drumurile afectate de alunecari in vestul judetului. "
            "Lucrarile vizeaza consolidari rapide si refacerea santurilor pe trei tronsoane folosite zilnic de localnici. "
            "Masura ar putea scurta timpul de interventie pentru ambulante si autobuze scolare. "
            "Primele echipe intra pe teren la inceputul saptamanii viitoare."
        ),
    },
    {
        "story_id": "bacau_03",
        "source_label": "Monitorul de Bacau",
        "headline": "ISU Bacau dubleaza controalele dupa incendiile din gospodarii",
        "content_text": (
            "ISU Bacau a dublat controalele dupa seria de incendii din gospodarii anuntata in ultimele zile. "
            "Pompierii verifica instalatiile electrice si depozitarea combustibilului in comunele cu cele mai multe alerte. "
            "Asta inseamna controale mai dese si amenzi pentru proprietarii care ignora regulile de siguranta. "
            "Inspectoratul spune ca primele rezultate vor fi centralizate pana la finalul saptamanii."
        ),
    },
    {
        "story_id": "bacau_04",
        "source_label": "Bacau.net",
        "headline": "Spitalul Judetean Bacau deschide un nou program pentru urgente cardiace",
        "content_text": (
            "Spitalul Judetean Bacau a deschis un nou program pentru urgente cardiace in timpul noptii. "
            "Unitatea a adus doua echipe suplimentare si echipamente pentru monitorizare rapida in camera de garda. "
            "Masura poate reduce timpul de asteptare pentru pacientii care ajung cu simptome grave. "
            "Programul functioneaza de la inceputul acestei saptamani."
        ),
    },
    {
        "story_id": "bacau_05",
        "source_label": "Ziarul de Iasi",
        "headline": "Universitatile din Moldova pregatesc burse comune pentru studentii din regiune",
        "content_text": (
            "Universitatile din Moldova pregatesc un program comun de burse pentru studentii cu venituri mici. "
            "Rectorii din Iasi, Bacau si Suceava vor sa acopere costurile de cazare si transport pentru primul semestru. "
            "Asta ar putea reduce abandonul in randul studentilor din judetele sarace. "
            "Primele criterii de selectie vor fi publicate luna viitoare."
        ),
    },
    {
        "story_id": "national_01",
        "source_label": "Agerpres",
        "headline": "Premierul Ilie Bolojan anunta reguli noi pentru marile investitii",
        "content_text": (
            "Premierul Ilie Bolojan a anuntat reguli noi pentru marile investitii publice si private. "
            "Guvernul reduce numarul de avize si promite termene mai scurte pentru aprobari. "
            "Asta ar putea grabi santierele mari si reduce costurile pentru firme. "
            "Primele masuri intra in vigoare luna viitoare."
        ),
    },
    {
        "story_id": "national_02",
        "source_label": "HotNews",
        "headline": "CSM respinge propunerea pentru un post-cheie la DNA",
        "content_text": (
            "CSM a respins propunerea pentru un post-cheie la DNA. "
            "Avizul negativ vine dupa audieri si lasa Ministerul Justitiei fara un nume acceptat pentru functie. "
            "Decizia mentine presiunea asupra numirilor din marile parchete. "
            "Ministerul poate reveni cu o noua propunere in zilele urmatoare."
        ),
    },
    {
        "story_id": "national_03",
        "source_label": "Digi24",
        "headline": "ANAF extinde verificarile dupa o frauda cu TVA",
        "content_text": (
            "ANAF extinde verificarile dupa o frauda cu TVA care a implicat firme fantoma si facturi false. "
            "Inspectorii spun ca prejudiciul trece de 2.347.819 lei si ca o parte din rambursari a fost deja blocata. "
            "Asta inseamna presiune mai mare pe companiile verificate si pe colectarea la buget. "
            "Primele rezultate oficiale sunt asteptate dupa inchiderea controalelor din teritoriu."
        ),
    },
    {
        "story_id": "national_04",
        "source_label": "Economedia",
        "headline": "Guvernul pregateste schema noua de sprijin pentru facturile la energie",
        "content_text": (
            "Guvernul pregateste o schema noua de sprijin pentru facturile la energie din sezonul rece. "
            "Ministerul Energiei vrea ajutor tintit pentru gospodariile cu venituri mici si pentru unele firme. "
            "Asta poate schimba costurile lunare pentru consumatori vulnerabili. "
            "Proiectul ar urma sa fie prezentat in cateva zile."
        ),
    },
    {
        "story_id": "national_05",
        "source_label": "Edupedu",
        "headline": "Ministerul Educatiei lanseaza catalogul digital in mai multe judete",
        "content_text": (
            "Ministerul Educatiei lanseaza catalogul digital in mai multe judete din toamna. "
            "Platforma va aduna absentele, notele si comunicarile dintre profesori si parinti in acelasi loc. "
            "Asta poate reduce timpul pierdut cu hartiile in scoli si licee. "
            "Primele unitati intra in program la inceputul anului scolar."
        ),
    },
    {
        "story_id": "national_06",
        "source_label": "Agrointel",
        "headline": "Fermierii cer sprijin dupa seceta din sud si est",
        "content_text": (
            "Fermierii cer sprijin de urgenta dupa seceta din sud si est. "
            "Organizatiile din agricultura spun ca pierderile cresc si ca unele culturi nu mai pot fi salvate. "
            "Asta poate ridica presiunea pe preturile la alimente in urmatoarele luni. "
            "Ministerul Agriculturii pregateste evaluari finale pe teren."
        ),
    },
    {
        "story_id": "international_01",
        "source_label": "Reuters",
        "headline": "Statele Unite trimit nave suplimentare spre Stramtoarea Ormuz",
        "content_text": (
            "Casa Alba a anuntat ca Statele Unite trimit nave suplimentare spre Stramtoarea Ormuz dupa noi atacuri asupra transportului comercial. "
            "Washingtonul spune ca masura vizeaza protejarea rutelor maritime. "
            "Asta poate aduce noi scumpiri la petrol si energie in Europa. "
            "Traderii urmaresc deja riscul unui nou soc pe piata transportului."
        ),
    },
    {
        "story_id": "international_02",
        "source_label": "AP",
        "headline": "Uniunea Europeana impune reguli noi pentru bateriile importate",
        "content_text": (
            "Uniunea Europeana impune reguli noi pentru bateriile importate in blocul comunitar. "
            "Companiile vor trebui sa arate mai clar originea materialelor si standardele de reciclare. "
            "Asta poate schimba costurile pentru producatorii auto si pentru electronice. "
            "Noile cerinte se aplica treptat de anul viitor."
        ),
    },
    {
        "story_id": "international_03",
        "source_label": "BBC",
        "headline": "NATO muta exercitii suplimentare in zona Marii Negre",
        "content_text": (
            "NATO muta exercitii suplimentare in zona Marii Negre in urmatoarele saptamani. "
            "Alianta spune ca manevrele urmaresc reactii mai rapide pe flancul estic. "
            "Pentru Romania, asta inseamna atentie mai mare la securitatea regionala si la transportul militar. "
            "Programul final al exercitiilor va fi confirmat in curand."
        ),
    },
    {
        "story_id": "international_04",
        "source_label": "Financial Times",
        "headline": "SUA pregatesc restrictii noi pentru exporturile de cipuri AI",
        "content_text": (
            "Statele Unite pregatesc restrictii noi pentru exporturile de cipuri AI catre mai multe piete sensibile. "
            "Administratia spune ca vrea control mai strict asupra tehnologiilor cu impact militar. "
            "Asta poate lovi lanturile globale de aprovizionare si costurile din industria tech. "
            "Primele detalii oficiale sunt asteptate in aceasta luna."
        ),
    },
]


VICTOR_VASLUI_LOCAL_FIXTURES = [
    {
        "story_id": "vaslui_01",
        "source_label": "vnews.ro",
        "local_geo_origin": "vaslui_county",
        "headline": "ISU Vaslui intensifica verificarile la sobe dupa incendiile din weekend",
        "content_text": (
            "ISU Vaslui a intensificat verificarile la sobe dupa mai multe incendii produse in weekend. "
            "Pompierii verifica instalatiile de incalzire si cosurile de fum in comunele cu cele mai multe alerte. "
            "Asta inseamna controale mai dese si amenzi pentru gospodariile care ignora regulile de siguranta. "
            "Primele rezultate vor fi raportate pana la sfarsitul saptamanii."
        ),
    },
    {
        "story_id": "vaslui_02",
        "source_label": "stirivasluiene.ro",
        "local_geo_origin": "vaslui_county",
        "headline": "Primaria Vaslui muta traficul pe bulevardul Stefan cel Mare pentru lucrari",
        "content_text": (
            "Primaria Vaslui anunta lucrari pe bulevardul Stefan cel Mare pentru refacerea carosabilului si a gurilor de scurgere. "
            "Soferii vor circula pe o singura banda la orele de varf pe tronsonul din centru. "
            "Autobuzele vor opri temporar in statii mutate cu cateva zeci de metri. "
            "Restrictiile intra in vigoare de luni dimineata."
        ),
    },
    {
        "story_id": "vaslui_03",
        "source_label": "cotidianulvaslui.ro",
        "local_geo_origin": "vaslui_county",
        "headline": "Spitalul Judetean Vaslui deschide garda de seara pentru urgente pediatrice",
        "content_text": (
            "Spitalul Judetean Vaslui a deschis o garda de seara pentru urgente pediatrice. "
            "Pacientii au acum o linie separata pentru evaluare rapida dupa ora 18. "
            "Unitatea a adus un medic suplimentar si asistenti pentru intervalul cu cele mai multe prezentari. "
            "Programul functioneaza de la inceputul acestei saptamani."
        ),
    },
    {
        "story_id": "moldova_01",
        "source_label": "Ziarul de Iasi",
        "local_geo_origin": "moldova_region",
        "headline": "Universitatile din Moldova pregatesc burse comune pentru studentii din regiune",
        "content_text": (
            "Universitatile din Moldova pregatesc un program comun de burse pentru studentii cu venituri mici. "
            "Studentii din Vaslui, Iasi si Suceava ar putea primi sprijin pentru cazare si transport din primul semestru. "
            "Rectorii spun ca schema vizeaza mai ales judetele cu abandon universitar ridicat. "
            "Primele criterii de selectie vor fi publicate luna viitoare."
        ),
    },
    {
        "story_id": "moldova_02",
        "source_label": "Ziarul de Iasi",
        "local_geo_origin": "moldova_region",
        "headline": "Drumarii pregatesc reparatii rapide pe DN24 intre Vaslui si Iasi",
        "content_text": (
            "Drumarii pregatesc reparatii rapide pe DN24 intre Vaslui si Iasi dupa degradarile aparute la final de iarna. "
            "Soferii vor vedea limitari de viteza si echipe in teren pe tronsoanele cele mai circulate. "
            "Lucrarile vizeaza zonele cu gropi si acostamente rupte folosite zilnic de navetisti. "
            "Primele echipe intra pe traseu la inceputul saptamanii viitoare."
        ),
    },
]


ANA_TIMISOARA_LOCAL_FIXTURES = [
    {
        "story_id": "timis_01",
        "source_label": "opiniatimisoarei.ro",
        "local_geo_origin": "timis_county",
        "headline": "Primaria Timisoara muta circulatia in zona Garii de Nord pentru lucrari",
        "content_text": (
            "Primaria Timisoara anunta lucrari noi la carosabil si la liniile de tramvai din zona Garii de Nord. "
            "Soferii vor circula pe benzi ingustate si pe rute ocolitoare la orele de varf. "
            "Primaria a transmis ca restrictiile vor fi etapizate pe parcursul urmatoarelor doua saptamani. "
            "Primele limitari intra in vigoare de luni dimineata."
        ),
    },
    {
        "story_id": "timis_02",
        "source_label": "timponline.ro",
        "local_geo_origin": "timis_county",
        "headline": "Spitalul de Copii din Timisoara extinde programul pentru urgente respiratorii",
        "content_text": (
            "Spitalul de Copii din Timisoara extinde programul pentru urgente respiratorii dupa cresterea numarului de prezentari. "
            "Pacientii primesc triaj separat si consult mai rapid in intervalul de seara. "
            "Directorul unitatii spune ca echipele suplimentare raman in garda pana la finalul lunii. "
            "Programul extins functioneaza de la inceputul acestei saptamani."
        ),
    },
    {
        "story_id": "timis_03",
        "source_label": "banatulazi.ro",
        "local_geo_origin": "timis_county",
        "headline": "ISU Timis dubleaza controalele la blocurile cu risc dupa incendiul din Complex",
        "content_text": (
            "ISU Timis a dublat controalele la blocurile cu risc dupa incendiul din Complexul Studentesc. "
            "Inspectorii verifica instalatiile electrice, subsolurile si accesul autospecialelor in cartierele aglomerate. "
            "Inspectorul sef a precizat ca amenzile vor merge mai intai spre cazurile cu pericol imediat. "
            "Primele rezultate vor fi prezentate pana la finalul saptamanii."
        ),
    },
    {
        "story_id": "banat_01",
        "source_label": "opiniatimisoarei.ro",
        "local_geo_origin": "banat_region",
        "headline": "Fermierii din Banat cer ajutor dupa pierderile provocate de seceta",
        "content_text": (
            "Fermierii din Banat cer ajutor dupa pierderile provocate de seceta si de vantul puternic din ultimele saptamani. "
            "Fermierii spun ca lucrarile de primavara sunt deja intarziate in mai multe zone. "
            "Asta poate pune presiune pe costurile din ferme si pe preturile unor produse agricole. "
            "Primele evaluari oficiale sunt asteptate in cateva zile."
        ),
    },
    {
        "story_id": "banat_02",
        "source_label": "banatulazi.ro",
        "local_geo_origin": "banat_region",
        "headline": "Trenurile spre Timisoara au intarzieri dupa reparatii pe magistrala din vest",
        "content_text": (
            "Trenurile spre Timisoara au intarzieri dupa reparatii pe magistrala din vest. "
            "Calatorii vor vedea timpi mai mari de asteptare si modificari de peron in mai multe gari. "
            "CFR a transmis ca interventiile rapide vizeaza siguranta circulatiei pe tronsoanele cele mai uzate. "
            "Programul normal ar putea fi reluat la inceputul saptamanii viitoare."
        ),
    },
]

MARIA_OLT_LOCAL_FIXTURES = [
    {
        "story_id": "olt_01",
        "source_label": "stiriolt.ro",
        "headline": "Spitalul Judetean Slatina extinde accesul rapid pentru urgente neurologice",
        "content_text": (
            "Spitalul Judetean Slatina extinde accesul rapid pentru urgente neurologice incepand de saptamana viitoare. "
            "Managerul unitatii, Elena Dobre, a precizat ca pacientii cu suspiciune de AVC vor intra direct pe flux rapid. "
            "Masura poate reduce timpul pana la investigatii pentru cazurile grave din tot judetul Olt. "
            "Primele efecte sunt asteptate chiar din primele zile de program."
        ),
        "local_geo_origin": "olt_county",
    },
    {
        "story_id": "olt_02",
        "source_label": "cotidianulolt.ro",
        "headline": "Primaria Slatina muta circulatia pe rute ocolitoare in zona garii",
        "content_text": (
            "Primaria Slatina muta circulatia pe rute ocolitoare in zona garii din cauza unor lucrari la carosabil. "
            "Primarul Mario De Mezzo a anuntat ca soferii vor circula pe trasee deviate de luni dimineata. "
            "Restrictiile afecteaza accesul spre autogara si spre doua scoli din apropiere. "
            "Primele restrictii intra in vigoare de luni dimineata."
        ),
        "local_geo_origin": "olt_county",
    },
    {
        "story_id": "olt_03",
        "source_label": "realitateaolt.ro",
        "headline": "ISU Olt dubleaza controalele in centrele sociale ale judetului",
        "content_text": (
            "ISU Olt dubleaza controalele in centrele sociale ale judetului dupa mai multe alerte de incendiu. "
            "Inspectorii verifica instalatiile electrice si planurile de evacuare incepand chiar de astazi. "
            "Administratorii care nu respecta regulile risca amenzi si suspendarea activitatii. "
            "Primele rezultate vor fi centralizate pana la finalul saptamanii."
        ),
        "local_geo_origin": "olt_county",
    },
    {
        "story_id": "oltenia_01",
        "source_label": "Gazeta de Sud",
        "headline": "Fermierii din Oltenia cer sprijin dupa pierderile provocate de seceta",
        "content_text": (
            "Fermierii din Oltenia cer sprijin dupa pierderile provocate de seceta in mai multe judete din sud. "
            "Organizatiile agricole spun ca unele culturi nu mai pot fi salvate si ca presiunea pe costuri creste. "
            "Asta poate ridica preturile la alimente in urmatoarele luni pentru familiile din regiune. "
            "Ministerul Agriculturii pregateste evaluarile finale pe teren."
        ),
        "local_geo_origin": "oltenia_region",
    },
    {
        "story_id": "oltenia_02",
        "source_label": "Agerpres",
        "headline": "CFR muta trenuri regionale pe linii alternative in Oltenia",
        "content_text": (
            "CFR muta trenuri regionale pe linii alternative in Oltenia din cauza unor lucrari la infrastructura. "
            "Navetistii din Olt si Dolj vor vedea intarzieri si schimbari de peron in urmatoarele zile. "
            "Programul provizoriu afecteaza zilnic legaturile spre scoli, spitale si locuri de munca din zona. "
            "Orarul provizoriu se aplica de marti dimineata."
        ),
        "local_geo_origin": "oltenia_region",
    },
]


GEORGE_COVASNA_LOCAL_FIXTURES = [
    {
        "story_id": "covasna_01",
        "source_label": "covasnamedia.ro",
        "headline": "Spitalul Judetean Sfantu Gheorghe extinde programul pentru urgente",
        "content_text": (
            "Spitalul Judetean Sfantu Gheorghe extinde programul pentru urgente incepand de saptamana viitoare. "
            "Managerul unitatii, Emese Farkas, a precizat ca pacientii cu risc major intra direct pe flux rapid. "
            "Masura poate reduce timpul de asteptare pentru cazurile grave din tot judetul Covasna. "
            "Primele efecte sunt asteptate chiar din primele zile de program."
        ),
        "local_geo_origin": "covasna_county",
    },
    {
        "story_id": "covasna_02",
        "source_label": "observatorulcovei.ro",
        "headline": "Primaria Sfantu Gheorghe muta circulatia in zona centrala pentru lucrari",
        "content_text": (
            "Primaria Sfantu Gheorghe muta circulatia in zona centrala pentru lucrari la carosabil si retele. "
            "Primarul Arpad Antal a declarat ca soferii vor circula pe rute ocolitoare de luni dimineata. "
            "Restrictiile afecteaza accesul spre doua scoli si spre autogara. "
            "Primele restrictii intra in vigoare de luni dimineata."
        ),
        "local_geo_origin": "covasna_county",
    },
    {
        "story_id": "covasna_03",
        "source_label": "stiricovasna.ro",
        "headline": "ISU Covasna dubleaza controalele in centrele sociale",
        "content_text": (
            "ISU Covasna dubleaza controalele in centrele sociale dupa mai multe alerte. "
            "Inspectorii verifica instalatiile electrice si planurile de evacuare chiar de astazi. "
            "Administratorii care ignora regulile risca amenzi si suspendarea activitatii. "
            "Primele rezultate vor fi centralizate pana la finalul saptamanii."
        ),
        "local_geo_origin": "covasna_county",
    },
    {
        "story_id": "transilvania_01",
        "source_label": "Agerpres",
        "headline": "Universitatile din Transilvania extind bursele pentru studentii navetisti",
        "content_text": (
            "Universitatile din Transilvania extind bursele pentru studentii navetisti din orasele mici. "
            "Rectorii spun ca sprijinul nou poate acoperi transportul si o parte din cazare. "
            "Masura poate reduce abandonul universitar in familiile cu venituri mici. "
            "Primele criterii vor fi publicate luna viitoare."
        ),
        "local_geo_origin": "transilvania_region",
    },
    {
        "story_id": "transilvania_02",
        "source_label": "Biz Brasov",
        "headline": "CFR muta trenuri regionale pe linii alternative in sud-estul Transilvaniei",
        "content_text": (
            "CFR muta trenuri regionale pe linii alternative in sud-estul Transilvaniei din cauza unor lucrari. "
            "Navetistii din Covasna si Brasov vor vedea intarzieri si schimbari de peron in urmatoarele zile. "
            "Programul provizoriu afecteaza zilnic legaturile spre scoli, spitale si locuri de munca din zona. "
            "Orarul provizoriu se aplica de marti dimineata."
        ),
        "local_geo_origin": "transilvania_region",
    },
]


NICU_CONSTANTA_LOCAL_FIXTURES = [
    {
        "story_id": "constanta_01",
        "source_label": "ziuaconstanta.ro",
        "local_geo_origin": "constanta_county",
        "headline": "ISU Constanta dubleaza controalele in cluburile de pe litoral",
        "content_text": (
            "ISU Constanta a dublat controalele in cluburile si terasele de pe litoral dupa mai multe nereguli descoperite la final de saptamana. "
            "Pompierii verifica instalatiile electrice, iesirile de urgenta si capacitatea de evacuare in statiunile aglomerate. "
            "Turistii si angajatii risca evacuari rapide si amenzi pentru operatorii care ignora regulile. "
            "Primele rezultate vor fi anuntate pana la finalul saptamanii."
        ),
    },
    {
        "story_id": "constanta_02",
        "source_label": "cugetliber.ro",
        "local_geo_origin": "constanta_county",
        "headline": "Spitalul Judetean Constanta deschide flux rapid pentru urgente neurologice",
        "content_text": (
            "Spitalul Judetean Constanta a deschis un flux rapid pentru urgente neurologice si suspiciuni de AVC. "
            "Pacientii intra direct la evaluare imagistica si la triaj specializat, fara opriri inutile intre sectii. "
            "Managerul spitalului spune ca noul circuit scurteaza minutele critice pentru cazurile grave. "
            "Programul complet functioneaza chiar din aceasta saptamana."
        ),
    },
    {
        "story_id": "constanta_03",
        "source_label": "tomisnews.ro",
        "local_geo_origin": "constanta_county",
        "headline": "Primaria Constanta muta traficul din zona Garii pentru lucrari la carosabil",
        "content_text": (
            "Primaria Constanta muta traficul din zona Garii pentru lucrari la carosabil si retele subterane. "
            "Soferii vor circula pe benzi restranse, iar autobuzele vor opri temporar in statii mutate cu cateva zeci de metri. "
            "Primarul spune ca santierul trebuie sa ramana deschis toata noaptea pentru a scurta durata lucrarilor. "
            "Primele restrictii intra in vigoare de luni dimineata."
        ),
    },
    {
        "story_id": "constanta_04",
        "source_label": "ziuaconstanta.ro",
        "local_geo_origin": "constanta_county",
        "headline": "RAJA pregateste opriri de apa in mai multe cartiere din Constanta",
        "content_text": (
            "RAJA pregateste opriri de apa in mai multe cartiere din Constanta pentru inlocuirea unor vane principale. "
            "Locuitorii din zona centrala si din cartierele cu blocuri vechi vor avea program redus pentru consumul casnic. "
            "Compania spune ca echipele vor lucra pe tronsoanele cu cele mai multe avarii repetate. "
            "Programul actualizat va fi publicat in zilele urmatoare."
        ),
    },
    {
        "story_id": "constanta_05",
        "source_label": "cugetliber.ro",
        "local_geo_origin": "constanta_county",
        "headline": "Operatorii din turism cer controale mai dure pe plajele aglomerate din judet",
        "content_text": (
            "Operatorii din turism cer controale mai dure pe plajele aglomerate din judetul Constanta dupa valul de reclamatii din weekend. "
            "Turistii spun ca accesul, curatenia si siguranta se deterioreaza rapid in zonele cele mai aglomerate. "
            "Patronatele avertizeaza ca sezonul poate pierde clienti daca problemele raman nerezolvate. "
            "Primele verificari suplimentare sunt asteptate in zilele urmatoare."
        ),
    },
]

ION_GALATI_LOCAL_FIXTURES = [
    {
        "story_id": "galati_01",
        "source_label": "viata-libera.ro",
        "headline": "Spitalul Judetean Galati extinde liniile de garda pentru urgente",
        "content_text": (
            "Spitalul Judetean Galati extinde liniile de garda pentru urgente incepand de saptamana viitoare. "
            "Directorul unitatii, Andreea Munteanu, a precizat ca pacientii cu suspiciune de AVC vor intra direct pe flux rapid. "
            "Masura poate scurta timpii de asteptare pentru cazurile grave din oras si din judet. "
            "Primele efecte sunt asteptate chiar din primele zile de program."
        ),
        "local_geo_origin": "galati_county",
    },
    {
        "story_id": "galati_02",
        "source_label": "obiectivgalati.ro",
        "headline": "Primaria Galati muta traficul in zona Falezei pentru lucrari la carosabil",
        "content_text": (
            "Primaria Galati muta traficul in zona Falezei pentru lucrari la carosabil si la retelele subterane. "
            "Primarul Ionut Pucheanu a anuntat ca soferii vor circula pe rute ocolitoare incepand de luni dimineata. "
            "Restrictiile afecteaza traseele de autobuz si accesul spre doua parcari mari din oras. "
            "Primele restrictii intra in vigoare de luni dimineata."
        ),
        "local_geo_origin": "galati_county",
    },
    {
        "story_id": "galati_03",
        "source_label": "stirigalati.ro",
        "headline": "ISU Galati dubleaza controalele in caminele pentru varstnici",
        "content_text": (
            "ISU Galati dubleaza controalele in caminele pentru varstnici dupa doua alerte de incendiu. "
            "Inspectorul sef, Mihai Enache, a declarat ca pompierii verifica instalatiile electrice si planurile de evacuare in tot judetul. "
            "Masura inseamna verificari mai dese si amenzi rapide pentru administratorii care ignora regulile. "
            "Primele rezultate vor fi centralizate pana la finalul saptamanii."
        ),
        "local_geo_origin": "galati_county",
    },
    {
        "story_id": "moldova_03",
        "source_label": "Ziarul de Iasi",
        "headline": "Universitatile din Moldova extind bursele pentru studentii navetisti",
        "content_text": (
            "Universitatile din Moldova extind bursele pentru studentii navetisti din orasele mici ale regiunii. "
            "Rectorii spun ca sprijinul nou ar trebui sa acopere transportul si o parte din cazare pentru primul semestru. "
            "Masura poate reduce abandonul universitar in familiile cu venituri mici. "
            "Primele criterii de selectie vor fi publicate luna viitoare."
        ),
        "local_geo_origin": "moldova_region",
    },
    {
        "story_id": "moldova_04",
        "source_label": "Agerpres",
        "headline": "CFR muta mai multe trenuri regionale pe linii alternative in Moldova",
        "content_text": (
            "CFR muta mai multe trenuri regionale pe linii alternative in Moldova din cauza unor lucrari la infrastructura. "
            "Compania spune ca navetistii din Galati, Braila si Vaslui vor vedea intarzieri si schimbari de peron in urmatoarele zile. "
            "Modificarea afecteaza zilnic legaturile spre scoli, spitale si locuri de munca din regiune. "
            "Programul provizoriu se aplica de marti dimineata."
        ),
        "local_geo_origin": "moldova_region",
    },
]


def _note_value(notes: list[str], key: str, default: str) -> str:
    prefix = f"{key}="
    for note in notes:
        if note.startswith(prefix):
            return note.split("=", 1)[1]
    return default


def _extract_attribution_type(notes: list[str]) -> str:
    value = _note_value(notes, "attribution_slot", "none")
    return value.split(":", 1)[0]


def _sentence_counts(text: str) -> list[int]:
    return [len(sentence.split()) for sentence in text.replace("\n", " ").split(".") if sentence.strip()]


def _build_story_payload(service: RadioEditingService, fixture: dict[str, str], position: int) -> dict[str, object]:
    edited = service.build_radio_story(fixture)
    story_band = _note_value(edited.editing_debug_notes, "story_band", "sparse")
    attribution_type = _extract_attribution_type(edited.editing_debug_notes)
    lead_word_count = int(_note_value(edited.editing_debug_notes, "lead_word_count", "0"))
    main_actor_early = _note_value(edited.editing_debug_notes, "main_actor_early", "True") == "True"
    repeated_person_name_count = int(_note_value(edited.editing_debug_notes, "repeated_person_name_count", "0"))
    multiple_attributions = _note_value(edited.editing_debug_notes, "multiple_attributions", "False") == "True"
    administrative_closure = _note_value(edited.editing_debug_notes, "administrative_closure", "False") == "True"
    simplified_operational_description_count = int(_note_value(edited.editing_debug_notes, "simplified_operational_description_count", "0"))
    source_scope = _note_value(edited.editing_debug_notes, "source_scope", "national")
    lead_title_overlap_score = float(_note_value(edited.editing_debug_notes, "lead_title_overlap_score", "0"))
    lead_rewritten_to_reduce_title_repetition = _note_value(edited.editing_debug_notes, "lead_rewritten_to_reduce_title_repetition", "False") == "True"
    lead_continuation_rewrite_applied = _note_value(edited.editing_debug_notes, "lead_continuation_rewrite_applied", "False") == "True"
    lead_opening_type = _note_value(edited.editing_debug_notes, "lead_opening_type", "institution_action")
    generated_lead_initial = _note_value(edited.editing_debug_notes, "generated_lead_initial", "")
    generated_lead_final = _note_value(edited.editing_debug_notes, "generated_lead_final", "")
    title_main_entity = _note_value(edited.editing_debug_notes, "title_main_entity", "")
    title_main_action_family = _note_value(edited.editing_debug_notes, "title_main_action_family", "")
    stories_with_lead_starting_with_institution = _note_value(edited.editing_debug_notes, "stories_with_lead_starting_with_institution", "False") == "True"
    stories_with_lead_starting_with_institution_and_title_like_action = _note_value(edited.editing_debug_notes, "stories_with_lead_starting_with_institution_and_title_like_action", "False") == "True"
    stories_rewritten_via_continuation_strategy = _note_value(edited.editing_debug_notes, "stories_rewritten_via_continuation_strategy", "False") == "True"
    lead_starter_family = _note_value(edited.editing_debug_notes, "lead_starter_family", lead_opening_type)
    closing_phrase_family = _note_value(edited.editing_debug_notes, "closing_phrase_family", "operational_timing")
    duplicate_sentence_removed = _note_value(edited.editing_debug_notes, "duplicate_sentence_removed", "False") == "True"
    stories_with_intra_story_repetition = _note_value(edited.editing_debug_notes, "stories_with_intra_story_repetition", "False") == "True"
    stories_with_duplicate_sentence_removed = _note_value(edited.editing_debug_notes, "stories_with_duplicate_sentence_removed", "False") == "True"
    stories_with_closing_variation_applied = _note_value(edited.editing_debug_notes, "stories_with_closing_variation_applied", "False") == "True"
    lead_has_personal_attribution = _note_value(edited.editing_debug_notes, "lead_has_personal_attribution", "False") == "True"
    second_sentence_has_personal_attribution = _note_value(edited.editing_debug_notes, "second_sentence_has_personal_attribution", "False") == "True"
    promoted_person_attribution_sentence_count = int(_note_value(edited.editing_debug_notes, "promoted_person_attribution_sentence_count", "0"))
    role_based_attribution_inserted_count = int(_note_value(edited.editing_debug_notes, "role_based_attribution_inserted_count", "0"))
    stories_with_personal_attribution = _note_value(edited.editing_debug_notes, "stories_with_personal_attribution", "False") == "True"
    stories_with_institution_only_attribution = _note_value(edited.editing_debug_notes, "stories_with_institution_only_attribution", "False") == "True"
    stories_with_media_attribution = _note_value(edited.editing_debug_notes, "stories_with_media_attribution", "False") == "True"
    stories_with_person_name_attribution = _note_value(edited.editing_debug_notes, "stories_with_person_name_attribution", "False") == "True"
    stories_with_person_role_and_name_attribution = _note_value(edited.editing_debug_notes, "stories_with_person_role_and_name_attribution", "False") == "True"
    stories_with_institution_attribution = _note_value(edited.editing_debug_notes, "stories_with_institution_attribution", "False") == "True"
    stories_with_media_source_attribution = _note_value(edited.editing_debug_notes, "stories_with_media_source_attribution", "False") == "True"
    stories_missing_attributed_voice = _note_value(edited.editing_debug_notes, "stories_missing_attributed_voice", "False") == "True"
    attribution_type_used = _note_value(edited.editing_debug_notes, "attribution_type_used", "none")
    attribution_level_used = _note_value(edited.editing_debug_notes, "attribution_level_used", "none")
    attributed_name_used = _note_value(edited.editing_debug_notes, "attributed_name_used", "")
    attributed_role_used = _note_value(edited.editing_debug_notes, "attributed_role_used", "")
    attributed_institution_used = _note_value(edited.editing_debug_notes, "attributed_institution_used", "")
    attributed_media_source_used = _note_value(edited.editing_debug_notes, "attributed_media_source_used", "")
    person_attribution_used = _note_value(edited.editing_debug_notes, "person_attribution_used", "False") == "True"
    person_name = _note_value(edited.editing_debug_notes, "person_name", "")
    person_role = _note_value(edited.editing_debug_notes, "person_role", "")
    stories_with_person_anchor = _note_value(edited.editing_debug_notes, "stories_with_person_anchor", "False") == "True"
    stories_with_role_anchor = _note_value(edited.editing_debug_notes, "stories_with_role_anchor", "False") == "True"
    stories_with_voice_of_people_anchor = _note_value(edited.editing_debug_notes, "stories_with_voice_of_people_anchor", "False") == "True"
    human_anchor_type = _note_value(edited.editing_debug_notes, "human_anchor_type", "none")
    human_density_score = float(_note_value(edited.editing_debug_notes, "human_density_score", "0"))
    radio_human_layer_applied = _note_value(edited.editing_debug_notes, "radio_human_layer_applied", "False") == "True"
    attribution_position_used = _note_value(edited.editing_debug_notes, "attribution_position_used", "none")
    has_named_person = _note_value(edited.editing_debug_notes, "has_named_person", "False") == "True"
    has_role_based_person = _note_value(edited.editing_debug_notes, "has_role_based_person", "False") == "True"
    lead_has_quote_or_person = _note_value(edited.editing_debug_notes, "lead_has_quote_or_person", "False") == "True"
    high_title_lead_overlap = _note_value(edited.editing_debug_notes, "high_title_lead_overlap", "False") == "True"
    romania_impact_included = _note_value(edited.editing_debug_notes, "romania_impact_included", "False") == "True"
    strong_closure = _note_value(edited.editing_debug_notes, "strong_closure", "False") == "True"
    sentence_lengths = _sentence_counts(edited.radio_text)
    input_people = service._extract_persons(f"{fixture['headline']} {fixture['content_text']}")
    return {
        "position": position,
        "story_id": edited.story_id,
        "story_band": story_band,
        "headline_original": edited.headline_original,
        "original_word_count": len(fixture["content_text"].split()),
        "compressed_word_count": edited.compression_debug.compressed_word_count,
        "radio_word_count": edited.estimated_word_count,
        "estimated_duration_seconds": edited.estimated_duration_seconds,
        "sentence_count": len(edited.radio_sentences),
        "lead_word_count": lead_word_count,
        "source_scope": source_scope,
        "lead_title_overlap_score": lead_title_overlap_score,
        "lead_rewritten_to_reduce_title_repetition": lead_rewritten_to_reduce_title_repetition,
        "lead_continuation_rewrite_applied": lead_continuation_rewrite_applied,
        "lead_opening_type": lead_opening_type,
        "lead_starter_family": lead_starter_family,
        "closing_phrase_family": closing_phrase_family,
        "duplicate_sentence_removed": duplicate_sentence_removed,
        "stories_with_intra_story_repetition": stories_with_intra_story_repetition,
        "stories_with_duplicate_sentence_removed": stories_with_duplicate_sentence_removed,
        "stories_with_closing_variation_applied": stories_with_closing_variation_applied,
        "original_headline": fixture["headline"],
        "generated_lead_initial": generated_lead_initial,
        "generated_lead_final": generated_lead_final,
        "title_main_entity": title_main_entity,
        "title_main_action_family": title_main_action_family,
        "stories_with_lead_starting_with_institution": stories_with_lead_starting_with_institution,
        "stories_with_lead_starting_with_institution_and_title_like_action": stories_with_lead_starting_with_institution_and_title_like_action,
        "stories_rewritten_via_continuation_strategy": stories_rewritten_via_continuation_strategy,
        "lead_has_personal_attribution": lead_has_personal_attribution,
        "second_sentence_has_personal_attribution": second_sentence_has_personal_attribution,
        "promoted_person_attribution_sentence_count": promoted_person_attribution_sentence_count,
        "role_based_attribution_inserted_count": role_based_attribution_inserted_count,
        "stories_with_personal_attribution": stories_with_personal_attribution,
        "stories_with_person_name_attribution": stories_with_person_name_attribution,
        "stories_with_person_role_and_name_attribution": stories_with_person_role_and_name_attribution,
        "stories_with_institution_only_attribution": stories_with_institution_only_attribution,
        "stories_with_institution_attribution": stories_with_institution_attribution,
        "stories_with_media_attribution": stories_with_media_attribution,
        "stories_with_media_source_attribution": stories_with_media_source_attribution,
        "stories_missing_attributed_voice": stories_missing_attributed_voice,
        "attribution_type_used": attribution_type_used,
        "attribution_level_used": attribution_level_used,
        "attributed_name_used": attributed_name_used,
        "attributed_role_used": attributed_role_used,
        "attributed_institution_used": attributed_institution_used,
        "attributed_media_source_used": attributed_media_source_used,
        "person_attribution_used": person_attribution_used,
        "person_name": person_name,
        "person_role": person_role,
        "stories_with_person_anchor": stories_with_person_anchor,
        "stories_with_role_anchor": stories_with_role_anchor,
        "stories_with_voice_of_people_anchor": stories_with_voice_of_people_anchor,
        "human_anchor_type": human_anchor_type,
        "human_density_score": human_density_score,
        "radio_human_layer_applied": radio_human_layer_applied,
        "attribution_position_used": attribution_position_used,
        "has_named_person": has_named_person,
        "has_role_based_person": has_role_based_person,
        "lead_has_quote_or_person": lead_has_quote_or_person,
        "high_title_lead_overlap": high_title_lead_overlap,
        "local_geo_origin": fixture.get("local_geo_origin"),
        "main_actor_early_in_lead": main_actor_early,
        "kept_entities": edited.kept_entities,
        "dropped_entities": edited.dropped_entities,
        "compressed_facts": edited.compressed_facts,
        "kept_sentences": [item.model_dump(mode="json") for item in edited.compression_debug.kept_sentences],
        "dropped_sentences": [item.model_dump(mode="json") for item in edited.compression_debug.dropped_sentences],
        "editing_debug_notes": edited.editing_debug_notes,
        "radio_text": edited.radio_text,
        "attribution_type": attribution_type,
        "sentence_lengths": sentence_lengths,
        "romania_impact_included": romania_impact_included,
        "strong_closure": strong_closure,
        "repeated_person_name_count": repeated_person_name_count,
        "multiple_attributions": multiple_attributions,
        "administrative_closure": administrative_closure,
        "simplified_operational_description_count": simplified_operational_description_count,
        "person_not_preserved": bool(input_people and not any(person in edited.kept_entities for person in input_people[:1])),
        "local_origin_type": "county" if str(fixture.get("local_geo_origin") or "").endswith("_county") else "fallback_region" if str(fixture.get("local_geo_origin") or "").endswith("_region") else source_scope,
    }


def _render_preview_text(payload: dict[str, object]) -> str:
    summary = payload["validation_summary"]
    lines = [
        "OPENWAVE RADIO EDITING PREVIEW V1.11",
        "",
        f"Stories: {payload['story_count']}",
        f"Bulletin estimated duration: {payload['bulletin_estimated_duration_seconds']} secunde",
        f"Average story words: {summary['average_word_count']}",
        f"Average story duration: {summary['average_estimated_duration_seconds']} secunde",
        f"Average lead/title overlap: {summary['average_lead_title_overlap_score']}",
        f"Stories with lead starting with institution: {summary['stories_with_lead_starting_with_institution']}",
        f"Stories with institution+title-like action lead: {summary['stories_with_lead_starting_with_institution_and_title_like_action']}",
        f"Stories rewritten via continuation strategy: {summary['stories_rewritten_via_continuation_strategy']}",
        f"Stories over 0.4 lead/title overlap: {summary['stories_over_0_4_lead_title_overlap']}",
        f"Stories over 0.5 lead/title overlap: {summary['stories_over_0_5_lead_title_overlap']}",
        f"Leads rewritten to reduce title repetition: {summary['leads_rewritten_to_reduce_title_repetition']}",
        f"Continuation lead rewrites: {summary['lead_continuation_rewrite_count']}",
        f"Lead opening counts: {json.dumps(summary['lead_opening_type_counts'], ensure_ascii=False)}",
        f"Human density score: {summary['human_density_score']}",
        f"Stories with person anchor: {summary['stories_with_person_anchor']}",
        f"Stories with role anchor: {summary['stories_with_role_anchor']}",
        f"Stories with voice-of-people anchor: {summary['stories_with_voice_of_people_anchor']}",
        f"Closing family distribution: {json.dumps(summary['closing_family_distribution'], ensure_ascii=False)}",
        f"Stories with personal attribution: {summary['stories_with_personal_attribution']}",
        f"Stories with person-name attribution: {summary['stories_with_person_name_attribution']}",
        f"Stories with role+name attribution: {summary['stories_with_person_role_and_name_attribution']}",
        f"Stories with institution attribution: {summary['stories_with_institution_attribution']}",
        f"Stories with media-source attribution: {summary['stories_with_media_source_attribution']}",
        f"Stories with intra-story repetition: {summary['stories_with_intra_story_repetition']}",
        f"Stories with duplicate sentence removed: {summary['stories_with_duplicate_sentence_removed']}",
        f"Stories with closing variation applied: {summary['stories_with_closing_variation_applied']}",
        f"Stories missing attributed voice: {summary['stories_missing_attributed_voice']}",
        f"Lead personal attribution count: {summary['lead_has_personal_attribution_count']}",
        f"Second-sentence personal attribution count: {summary['second_sentence_has_personal_attribution_count']}",
        f"Promoted person-attribution sentences: {summary['promoted_person_attribution_sentence_count']}",
        f"Role-based attribution insertions: {summary['role_based_attribution_inserted_count']}",
        f"Stories with institution-only attribution: {summary['stories_with_institution_only_attribution']}",
        f"Stories with media attribution: {summary['stories_with_media_attribution']}",
        f"Stories with high title/lead overlap: {summary['stories_with_high_title_lead_overlap']}",
        f"International stories with Romania impact: {summary['international_stories_with_romania_impact']}",
        f"Stories with strong closure: {summary['stories_with_strong_closure']}",
        f"Repeated person names: {summary['repeated_person_name_count']}",
        f"Stories with administrative closure: {summary['stories_with_administrative_closure']}",
        f"Stories with multiple attributions: {summary['stories_with_multiple_attributions']}",
        f"Operational simplifications applied: {summary['simplified_operational_description_count']}",
        f"TTS pronunciation entries: {summary['tts_pronunciation_entry_count']}",
        "",
    ]
    for item in payload["stories"]:
        lines.extend(
            [
                f"Story {item['position']}: {item['story_id']}",
                f"Band: {item['story_band']}",
                f"Headline original: {item['headline_original']}",
                f"Original words: {item['original_word_count']}",
                f"Final words: {item['radio_word_count']}",
                f"Sentence count: {item['sentence_count']}",
                f"Lead words: {item['lead_word_count']}",
                f"Scope: {item['source_scope']}",
                f"Original headline: {item['original_headline']}",
                f"Generated lead initial: {item['generated_lead_initial']}",
                f"Generated lead final: {item['generated_lead_final']}",
                f"Lead/title overlap: {item['lead_title_overlap_score']}",
                f"Title main entity: {item['title_main_entity'] or 'none'}",
                f"Title main action family: {item['title_main_action_family'] or 'none'}",
                f"Lead starter family: {item['lead_starter_family']}",
                f"Closing phrase family: {item['closing_phrase_family']}",
                f"Human anchor type: {item['human_anchor_type']}",
                f"Human layer applied: {item['radio_human_layer_applied']}",
                f"Local origin type: {item['local_origin_type']}",
                f"Duplicate sentence removed: {item['duplicate_sentence_removed']}",
                f"Lead rewrite applied: {item['lead_rewritten_to_reduce_title_repetition']}",
                f"Lead continuation rewrite: {item['lead_continuation_rewrite_applied']}",
                f"Lead opening type: {item['lead_opening_type']}",
                f"Attribution type used: {item['attribution_type_used']}",
                f"Attribution level used: {item['attribution_level_used']}",
                f"Attribution position used: {item['attribution_position_used']}",
                f"Attributed name: {item['attributed_name_used'] or 'none'}",
                f"Attributed role: {item['attributed_role_used'] or 'none'}",
                f"Attributed institution: {item['attributed_institution_used'] or 'none'}",
                f"Attributed media source: {item['attributed_media_source_used'] or 'none'}",
                f"Lead personal attribution: {item['lead_has_personal_attribution']}",
                f"Second sentence personal attribution: {item['second_sentence_has_personal_attribution']}",
                f"Has named person: {item['has_named_person']}",
                f"Has role-based person: {item['has_role_based_person']}",
                f"Estimated duration: {item['estimated_duration_seconds']} secunde",
                f"Attribution: {item['attribution_type']}",
                f"Romania impact included: {item['romania_impact_included']}",
                f"Strong closure: {item['strong_closure']}",
                f"Repeated person names: {item['repeated_person_name_count']}",
                f"Administrative closure: {item['administrative_closure']}",
                f"Multiple attributions: {item['multiple_attributions']}",
                f"Operational simplifications: {item['simplified_operational_description_count']}",
                f"Main actor early: {item['main_actor_early_in_lead']}",
                f"Kept entities: {', '.join(item['kept_entities']) or 'none'}",
                f"Dropped entities: {', '.join(item['dropped_entities']) or 'none'}",
                "Radio output:",
                item["radio_text"],
                "",
            ]
        )
    lines.extend([
        "Validation summary:",
        json.dumps(summary, ensure_ascii=False, indent=2),
        "",
        "Sample preview bulletin:",
        payload["bulletin_radio_text"],
    ])
    return "\n".join(lines).strip() + "\n"


def _render_generalist_bulletin(stories: list[dict[str, object]]) -> str:
    total_duration = sum(story["estimated_duration_seconds"] for story in stories)
    lines = [
        "OPENWAVE GENERALIST BULLETIN - MIHAI / BACAU",
        "",
        f"Stories: {len(stories)}",
        f"Estimated story-only duration: {total_duration} secunde",
        "Profil editorial: aproximativ 5 local, 6 national, 4 international.",
        "",
    ]
    for item in stories:
        lines.extend(
            [
                f"{item['position']}. {item['headline_original']}",
                item["radio_text"],
                "",
            ]
        )
    return "\n".join(lines).strip() + "\n"


def _fixture_scope(story_id: str) -> str:
    if story_id.startswith(("bacau_", "vaslui_", "moldova_", "timis_", "banat_", "galati_", "olt_", "oltenia_", "covasna_", "transilvania_", "constanta_", "dobrogea_")):
        return "local"
    if story_id.startswith("national_"):
        return "national"
    return "international"


def _victor_ordering_signals(item: dict[str, object]) -> dict[str, float]:
    text = f"{item['headline_original']} {item['radio_text']}".lower()
    scope = _fixture_scope(str(item['story_id']))
    signals = {
        "direct_listener_impact_score": 0.0,
        "urgency_score": 0.0,
        "emotional_proximity_score": 0.0,
        "cost_of_living_score": 0.0,
        "health_and_safety_score": 0.0,
        "traffic_and_daily_life_score": 0.0,
        "romania_relevance_score": 0.0,
        "locality_proximity_score": 0.0,
        "long_term_vs_immediate_penalty": 0.0,
    }
    if scope == "local":
        signals["direct_listener_impact_score"] += 2.6
        signals["emotional_proximity_score"] += 2.0
        signals["locality_proximity_score"] += 2.5
    if item.get("local_geo_origin") in {"vaslui_county", "timis_county", "galati_county", "olt_county", "covasna_county", "constanta_county"}:
        signals["direct_listener_impact_score"] += 1.4
        signals["locality_proximity_score"] += 2.2
    if item.get("local_geo_origin") in {"moldova_region", "banat_region", "oltenia_region", "transilvania_region", "dobrogea_region"}:
        signals["romania_relevance_score"] += 1.2
        signals["locality_proximity_score"] += 1.0
    if any(term in text for term in ("vaslui", "bacau", "iasi", "suceava", "moldova", "timisoara", "timis", "banat", "galati", "tecuci", "olt", "slatina", "oltenia", "covasna", "sfantu gheorghe", "transilvania", "constanta", "mangalia", "mamaia", "litoral", "dobrogea", "regiune")):
        signals["romania_relevance_score"] += 1.6
        signals["locality_proximity_score"] += 1.4
    if any(term in text for term in ("spital", "urgente", "incend", "isu", "siguranta", "cardiace", "avc")):
        signals["health_and_safety_score"] += 3.4
        signals["direct_listener_impact_score"] += 1.4
    if any(term in text for term in ("preturi", "facturi", "energie", "alimente", "seceta", "buget", "frauda", "tva")):
        signals["cost_of_living_score"] += 3.2
        signals["direct_listener_impact_score"] += 1.2
    if any(term in text for term in ("trafic", "pasaj", "lucrari", "drum", "transport", "benzi", "statii")):
        signals["traffic_and_daily_life_score"] += 3.0
        signals["direct_listener_impact_score"] += 1.1
    if any(term in text for term in ("de luni", "saptamanii", "luna viitoare", "in aceasta luna", "in cateva zile", "intra in vigoare")):
        signals["urgency_score"] += 2.6
    if any(term in text for term in ("romania", "marea neagra", "europei", "europa", "lanturile de aprovizionare", "petrol", "nato")):
        signals["romania_relevance_score"] += 2.4
    if any(term in text for term in ("treptat", "de anul viitor", "cipuri", "exporturile", "schema")):
        signals["long_term_vs_immediate_penalty"] += 1.4
    return {key: round(value, 2) for key, value in signals.items()}


def _story_hook_tags(item: dict[str, object]) -> set[str]:
    text = f"{item['headline_original']} {item['radio_text']}".lower()
    tags: set[str] = set()
    if any(term in text for term in ("spital", "urgente", "pacienti", "avc")):
        tags.add("health")
    if any(term in text for term in ("preturi", "facturi", "energie", "alimente", "buget", "tva", "benzina")):
        tags.add("money")
    if any(term in text for term in ("trafic", "gara", "tren", "restrictii", "drum", "apa", "transport", "lucrari")):
        tags.add("traffic")
    if any(term in text for term in ("isu", "incend", "siguranta", "controale", "evacuare", "nato", "securitate")):
        tags.add("safety")
    return tags

def _victor_radio_priority(item: dict[str, object]) -> float:
    signals = _victor_ordering_signals(item)
    score = (
        signals["direct_listener_impact_score"] * 1.7
        + signals["urgency_score"] * 1.4
        + signals["health_and_safety_score"] * 1.8
        + signals["cost_of_living_score"] * 1.5
        + signals["traffic_and_daily_life_score"] * 1.35
        + signals["romania_relevance_score"] * 1.15
        + signals["locality_proximity_score"] * 1.2
        + signals["emotional_proximity_score"] * 0.9
        - signals["long_term_vs_immediate_penalty"] * 1.2
    )
    return round(score, 2)


def _order_victor_vaslui_bulletin(stories: list[dict[str, object]]) -> list[dict[str, object]]:
    remaining = [dict(item, source_scope=_fixture_scope(str(item["story_id"]))) for item in stories]
    for item in remaining:
        item["ordering_signals"] = _victor_ordering_signals(item)
        item["radio_priority_score"] = _victor_radio_priority(item)
    ordered: list[dict[str, object]] = []
    while remaining:
        def candidate_key(candidate: dict[str, object]) -> tuple[float, float, str]:
            target_position = len(ordered) + 1
            scope_run_penalty = 0.0
            hook_penalty = 0.0
            if len(ordered) >= 2 and ordered[-1]["source_scope"] == ordered[-2]["source_scope"] == candidate["source_scope"]:
                scope_run_penalty = 12.0 if candidate["source_scope"] == "local" else 8.0
            early_mix_penalty = 0.0
            local_in_early_window = sum(1 for item in ordered[:5] if item["source_scope"] == "local")
            if target_position <= 6 and candidate["source_scope"] == "local" and local_in_early_window >= 2:
                early_mix_penalty = 14.0
            if target_position <= 4 and ordered and ordered[-1]["source_scope"] == candidate["source_scope"] == "local":
                early_mix_penalty = max(early_mix_penalty, 9.0)
            if target_position <= 6 and len(ordered) >= 2 and ordered[-1]["source_scope"] == ordered[-2]["source_scope"] == "local" and candidate["source_scope"] == "local":
                early_mix_penalty = max(early_mix_penalty, 18.0)
            international_in_opening = sum(1 for item in ordered[:5] if item["source_scope"] == "international")
            if target_position <= 6 and candidate["source_scope"] == "international" and international_in_opening >= 2:
                early_mix_penalty = max(early_mix_penalty, 5.0)
            topic_penalty = 0.0
            if ordered:
                previous_text = ordered[-1]["radio_text"].lower()
                candidate_text = candidate["radio_text"].lower()
                if any(term in previous_text and term in candidate_text for term in ("trafic", "energie", "buget", "nato", "spital", "educatie")):
                    topic_penalty = 0.6
            if target_position <= 3:
                covered_tags = set().union(*(_story_hook_tags(item) for item in ordered[: target_position - 1])) if ordered else set()
                candidate_tags = _story_hook_tags(candidate)
                focus_tags = {"health", "money", "traffic", "safety"}
                if len(covered_tags & focus_tags) < 2:
                    if candidate_tags & (focus_tags - covered_tags):
                        hook_penalty = -4.0
                    else:
                        hook_penalty = 3.5
            return (-candidate["radio_priority_score"] + scope_run_penalty + early_mix_penalty + topic_penalty + hook_penalty, scope_run_penalty + early_mix_penalty + hook_penalty, str(candidate["story_id"]))
        next_item = min(remaining, key=candidate_key)
        remaining.remove(next_item)
        ordered.append(next_item)
    for index, item in enumerate(ordered, start=1):
        item["position"] = index
    return ordered


def _collect_media_source_credits(stories: list[dict[str, object]]) -> list[str]:
    return sorted({
        str(item.get("source_label") or item.get("source") or "").strip()
        for item in stories
        if str(item.get("source_label") or item.get("source") or "").strip()
    })


def _render_victor_vaslui_bulletin(stories: list[dict[str, object]], geo_debug: dict[str, object]) -> str:
    total_duration = sum(story["estimated_duration_seconds"] for story in stories)
    lines = [
        "OPENWAVE GENERALIST BULLETIN - VICTOR / VASLUI",
        "",
        f"Stories: {len(stories)}",
        f"Estimated story-only duration: {total_duration} secunde",
        "Editorial target mix: local 5, national 6, international 4.",
        "Ordering rule: strongest listener impact first, with mixed local/national/international pacing.",
        f"Resolved user city: {geo_debug['resolved_user_city']}",
        f"Resolved user county: {geo_debug['resolved_user_county']}",
        f"Resolved user region: {geo_debug['resolved_user_region']}",
        f"Local source registry used: {geo_debug['local_source_registry_used']}",
        f"Local sources selected for county: {', '.join(geo_debug['local_sources_selected']) or 'none'}",
        f"Local story count from Vaslui: {geo_debug['local_story_count_from_vaslui']}",
        f"Local story count from Moldova region: {geo_debug['local_story_count_from_moldova_region']}",
        f"Lead continuation rewrites: {geo_debug['lead_continuation_rewrite_count']}",
        f"Lead opening counts: {json.dumps(geo_debug['lead_opening_type_counts'], ensure_ascii=False)}",
        "",
    ]
    for item in stories:
        lines.extend([
            f"{item['position']}. {item['headline_original']}",
            f"   Scope: {item['source_scope']}",
            f"   Local origin: {item.get('local_geo_origin') or 'none'}",
            f"   Radio priority: {item['radio_priority_score']}",
            f"   Ordering signals: {json.dumps(item['ordering_signals'], ensure_ascii=False)}",
            f"   Lead/title overlap: {item['lead_title_overlap_score']}",
            f"   Lead rewrite applied: {item['lead_rewritten_to_reduce_title_repetition']}",
            f"   Lead continuation rewrite applied: {item['lead_continuation_rewrite_applied']}",
            f"   Lead opening type: {item['lead_opening_type']}",
            item["radio_text"],
            "",
        ])
    return "\n".join(lines).strip() + "\n"


def _render_ana_timisoara_bulletin(stories: list[dict[str, object]], geo_debug: dict[str, object]) -> str:
    total_duration = sum(story["estimated_duration_seconds"] for story in stories)
    lines = [
        "OPENWAVE GENERALIST BULLETIN - ANA / TIMISOARA",
        "",
        f"Stories: {len(stories)}",
        f"Estimated story-only duration: {total_duration} secunde",
        "Editorial target mix: local 5, national 6, international 4.",
        "Ordering rule: strongest listener impact first, with mixed local/national/international pacing.",
        f"Resolved user city: {geo_debug['resolved_user_city']}",
        f"Resolved user county: {geo_debug['resolved_user_county']}",
        f"Resolved user region: {geo_debug['resolved_user_region']}",
        f"Local source registry used: {geo_debug['local_source_registry_used']}",
        f"Local sources selected for county: {', '.join(geo_debug['local_sources_selected']) or 'none'}",
        f"Local story count from Timis: {geo_debug['local_story_count_from_timis']}",
        f"Local story count from Banat region: {geo_debug['local_story_count_from_banat_region']}",
        f"Stories with personal attribution: {geo_debug['stories_with_personal_attribution']}",
        f"Lead continuation rewrites: {geo_debug['lead_continuation_rewrite_count']}",
        f"Lead opening counts: {json.dumps(geo_debug['lead_opening_type_counts'], ensure_ascii=False)}",
        "",
    ]
    for item in stories:
        lines.extend([
            f"{item['position']}. {item['headline_original']}",
            f"   Scope: {item['source_scope']}",
            f"   Local origin: {item.get('local_geo_origin') or 'none'}",
            f"   Radio priority: {item['radio_priority_score']}",
            f"   Ordering signals: {json.dumps(item['ordering_signals'], ensure_ascii=False)}",
            f"   Lead/title overlap: {item['lead_title_overlap_score']}",
            f"   Attribution type used: {item['attribution_type_used']}",
            f"   Attribution position used: {item['attribution_position_used']}",
            f"   Lead continuation rewrite applied: {item['lead_continuation_rewrite_applied']}",
            item["radio_text"],
            "",
        ])
    return "\n".join(lines).strip() + "\n"


def _render_ion_galati_bulletin(stories: list[dict[str, object]], geo_debug: dict[str, object]) -> str:
    total_duration = sum(story["estimated_duration_seconds"] for story in stories)
    lines = [
        "OPENWAVE GENERALIST BULLETIN - ION / GALATI",
        "",
        f"Stories: {len(stories)}",
        f"Estimated story-only duration: {total_duration} secunde",
        "Editorial target mix: local 5, national 6, international 4.",
        "Ordering rule: strongest listener impact first, with mixed local/national/international pacing.",
        f"Resolved user county: {geo_debug['resolved_user_county']}",
        f"Resolved user region: {geo_debug['resolved_user_region']}",
        f"Local source registry used: {geo_debug['local_source_registry_used']}",
        f"County-based routing active: {geo_debug['county_based_local_routing']}",
        f"Local sources selected for county: {', '.join(geo_debug['local_sources_selected']) or 'none'}",
        f"Local story count from Galati county: {geo_debug['local_story_count_from_galati_county']}",
        f"Local story count from regional fallback: {geo_debug['local_story_count_from_regional_fallback']}",
        f"Stories with person+role+name attribution: {geo_debug['stories_with_person_role_and_name_attribution']}",
        f"Stories with institution attribution: {geo_debug['stories_with_institution_attribution']}",
        f"Stories with media attribution: {geo_debug['stories_with_media_source_attribution']}",
        f"Stories missing attributed voice: {geo_debug['stories_missing_attributed_voice']}",
        f"Written source credits emitted: {geo_debug['written_source_credits_emitted']}",
        f"Bulletin unique media source count: {geo_debug['bulletin_unique_media_source_count']}",
        "",
    ]
    for item in stories:
        lines.extend([
            f"{item['position']}. {item['headline_original']}",
            f"   Scope: {item['source_scope']}",
            f"   Local origin: {item.get('local_geo_origin') or 'none'}",
            f"   Radio priority: {item['radio_priority_score']}",
            f"   Ordering signals: {json.dumps(item['ordering_signals'], ensure_ascii=False)}",
            f"   Attribution level used: {item['attribution_level_used']}",
            f"   Attribution type used: {item['attribution_type_used']}",
            f"   Attribution position used: {item['attribution_position_used']}",
            f"   Attributed name: {item['attributed_name_used'] or 'none'}",
            f"   Attributed role: {item['attributed_role_used'] or 'none'}",
            f"   Attributed institution: {item['attributed_institution_used'] or 'none'}",
            f"   Attributed media source: {item['attributed_media_source_used'] or 'none'}",
            f"   Lead/title overlap: {item['lead_title_overlap_score']}",
            f"   Lead continuation rewrite applied: {item['lead_continuation_rewrite_applied']}",
            item["radio_text"],
            "",
        ])
    lines.extend([
        "Outro:",
        "Acesta a fost jurnalul generalist OpenWave pentru Ion din judetul Galati.",
        "",
        "Written source credits for player:",
        *[f"- {source}" for source in geo_debug['written_source_credits']],
        "",
    ])
    return "\n".join(lines).strip() + "\n"


def _render_maria_olt_bulletin(stories: list[dict[str, object]], geo_debug: dict[str, object]) -> str:
    total_duration = sum(story["estimated_duration_seconds"] for story in stories)
    lines = [
        "OPENWAVE GENERALIST BULLETIN - MARIA / OLT",
        "",
        f"Stories: {len(stories)}",
        f"Estimated story-only duration: {total_duration} secunde",
        "Editorial target mix: local 5, national 6, international 4.",
        "Ordering rule: strongest listener impact first, with county-first local routing.",
        f"Resolved user county: {geo_debug['resolved_user_county']}",
        f"Resolved user region: {geo_debug['resolved_user_region']}",
        f"County-first local routing active: {geo_debug['county_first_local_routing']}",
        f"Local source registry used: {geo_debug['local_source_registry_used']}",
        f"Local sources selected for county: {', '.join(geo_debug['local_sources_selected']) or 'none'}",
        f"Local story count from Olt county: {geo_debug['local_story_count_from_olt_county']}",
        f"Local story count from Oltenia fallback: {geo_debug['local_story_count_from_oltenia_region']}",
        f"Stories rewritten via continuation strategy: {geo_debug['stories_rewritten_via_continuation_strategy']}",
        f"Stories with institution+title-like action lead: {geo_debug['stories_with_lead_starting_with_institution_and_title_like_action']}",
        f"Written source credits emitted: {geo_debug['written_source_credits_emitted']}",
        "",
    ]
    for item in stories:
        lines.extend([
            f"{item['position']}. {item['headline_original']}",
            f"   Scope: {item['source_scope']}",
            f"   Local origin: {item.get('local_geo_origin') or 'none'}",
            f"   Radio priority: {item['radio_priority_score']}",
            f"   Lead opening type: {item['lead_opening_type']}",
            f"   Initial lead: {item['generated_lead_initial']}",
            f"   Final lead: {item['generated_lead_final']}",
            f"   Title entity/action: {item['title_main_entity'] or 'none'} / {item['title_main_action_family'] or 'none'}",
            f"   Lead/title overlap: {item['lead_title_overlap_score']}",
            f"   Continuation rewrite applied: {item['lead_continuation_rewrite_applied']}",
            item['radio_text'],
            "",
        ])
    lines.extend([
        "Outro:",
        "Acesta a fost jurnalul generalist OpenWave pentru Maria din judetul Olt.",
        "",
        "Written source credits for player:",
        *[f"- {source}" for source in geo_debug['written_source_credits']],
        "",
    ])
    return "\n".join(lines).strip() + "\n"


def _render_george_covasna_bulletin(stories: list[dict[str, object]], geo_debug: dict[str, object]) -> str:
    total_duration = sum(story["estimated_duration_seconds"] for story in stories)
    lines = [
        "OPENWAVE GENERALIST BULLETIN - GEORGE / COVASNA",
        "",
        f"Stories: {len(stories)}",
        f"Estimated story-only duration: {total_duration} secunde",
        "Editorial target mix: local 5, national 6, international 4.",
        "Ordering rule: strongest listener impact first, with county-first local routing.",
        f"Resolved user county: {geo_debug['resolved_user_county']}",
        f"Resolved user region: {geo_debug['resolved_user_region']}",
        f"County-first local selection: {geo_debug['county_first_local_selection']}",
        f"Local source registry used: {geo_debug['local_source_registry_used']}",
        f"Local sources selected for county: {', '.join(geo_debug['local_sources_selected']) or 'none'}",
        f"Local story count from Covasna county: {geo_debug['local_story_count_from_covasna_county']}",
        f"Local story count from regional fallback: {geo_debug['local_story_count_from_transilvania_region']}",
        f"Lead starter family distribution: {json.dumps(geo_debug['lead_starter_family_distribution'], ensure_ascii=False)}",
        f"Stories with duplicate sentence removed: {geo_debug['stories_with_duplicate_sentence_removed']}",
        f"Stories with closing variation applied: {geo_debug['stories_with_closing_variation_applied']}",
        "",
    ]
    for item in stories:
        lines.extend([
            f"{item['position']}. {item['headline_original']}",
            f"   Scope: {item['source_scope']}",
            f"   Local origin: {item.get('local_geo_origin') or 'none'}",
            f"   Lead starter family: {item['lead_starter_family']}",
            f"   Closing phrase family: {item['closing_phrase_family']}",
            f"   Duplicate sentence removed: {item['duplicate_sentence_removed']}",
            f"   Person attribution used: {item['person_attribution_used']}",
            f"   Person: {item['person_role'] or 'none'} / {item['person_name'] or 'none'}",
            f"   Initial lead: {item['generated_lead_initial']}",
            f"   Final lead: {item['generated_lead_final']}",
            item['radio_text'],
            "",
        ])
    lines.extend([
        "Outro:",
        "Acesta a fost jurnalul generalist OpenWave pentru George din judetul Covasna.",
        "",
        "Written source credits for player:",
        *[f"- {source}" for source in geo_debug['written_source_credits']],
        "",
    ])
    return "\n".join(lines).strip() + "\n"


def _render_nicu_constanta_bulletin(stories: list[dict[str, object]], geo_debug: dict[str, object]) -> str:
    total_duration = sum(story["estimated_duration_seconds"] for story in stories)
    lines = [
        "OPENWAVE GENERALIST BULLETIN - NICU / CONSTANTA",
        "",
        f"Stories: {len(stories)}",
        f"Estimated story-only duration: {total_duration} secunde",
        "Editorial target mix: local 5, national 6, international 4.",
        "Ordering rule: strongest listener impact first, with county-only local selection unless fallback is required.",
        f"Resolved user county: {geo_debug['resolved_user_county']}",
        f"Resolved user region: {geo_debug['resolved_user_region']}",
        f"County-first local selection: {geo_debug['county_first_local_selection']}",
        f"Local source registry used: {geo_debug['local_source_registry_used']}",
        f"Local sources selected for county: {', '.join(geo_debug['local_sources_selected']) or 'none'}",
        f"Local story count from Constanta county: {geo_debug['local_story_count_from_constanta_county']}",
        f"Local story count from regional fallback: {geo_debug['local_story_count_from_regional_fallback']}",
        f"Human density score: {geo_debug['human_density_score']}",
        f"Stories with person anchor: {geo_debug['stories_with_person_anchor']}",
        f"Stories with role anchor: {geo_debug['stories_with_role_anchor']}",
        f"Stories with voice-of-people anchor: {geo_debug['stories_with_voice_of_people_anchor']}",
        f"Closing family distribution: {json.dumps(geo_debug['closing_family_distribution'], ensure_ascii=False)}",
        "",
    ]
    for item in stories:
        lines.extend([
            f"{item['position']}. {item['headline_original']}",
            f"   Scope: {item['source_scope']}",
            f"   Local origin: {item.get('local_geo_origin') or 'none'}",
            f"   Local origin type: {item['local_origin_type']}",
            f"   Lead starter family: {item['lead_starter_family']}",
            f"   Closing phrase family: {item['closing_phrase_family']}",
            f"   Human anchor type: {item['human_anchor_type']}",
            f"   Person attribution used: {item['person_attribution_used']}",
            f"   Person: {item['person_role'] or 'none'} / {item['person_name'] or 'none'}",
            f"   Duplicate sentence removed: {item['duplicate_sentence_removed']}",
            f"   Initial lead: {item['generated_lead_initial']}",
            f"   Final lead: {item['generated_lead_final']}",
            item['radio_text'],
            "",
        ])
    return "\n".join(lines).strip() + "\n"


def _build_live_nicu_constanta_personalization() -> UserPersonalization:
    return UserPersonalization(
        listener_profile=ListenerProfile(first_name="Nicu", country="Romania", region="Constanta"),
        editorial_preferences=EditorialPreferenceProfile(
            geography=GeographyPreferenceMix(local=35, national=40, international=25),
        ),
    )


def _cluster_local_origin_type(cluster, target_county: str) -> str:
    county_key = (target_county or '').strip().lower()
    local_members = [member for member in cluster.cluster.member_articles if member.is_local_source]
    local_regions = {str(member.source_region or '').strip().lower() for member in local_members if member.source_region}
    detected_counties = {str(member.county_detected or '').strip().lower() for member in local_members if member.county_detected}
    scopes = {member.source_scope for member in cluster.cluster.member_articles}
    if 'international' in scopes and len(local_members) <= 1:
        return 'international'
    if county_key and (county_key in local_regions or county_key in detected_counties):
        return 'county'
    if local_regions or detected_counties:
        return 'fallback_region'
    if 'international' in scopes:
        return 'international'
    return 'national'


def _render_live_preview_text(preview_payload: dict[str, object]) -> str:
    lines = [
        'OPENWAVE RADIO EDITING PREVIEW - LIVE MODE',
        '',
        f"Mode: {preview_payload['mode']}",
        f"Resolved user county: {preview_payload['resolved_user_county']}",
        f"Resolved user region: {preview_payload['resolved_user_region']}",
        f"County-first local selection: {preview_payload['county_first_local_selection']}",
        f"Fetched articles: {preview_payload['article_count']}",
        f"Selected stories: {preview_payload['story_count']}",
        f"Local stories from county: {preview_payload.get('local_story_count_from_county', preview_payload.get('local_story_count_from_constanta_county', 0))}",
        f"Local stories from regional fallback: {preview_payload['local_story_count_from_regional_fallback']}",
        f"Media source credits emitted: {preview_payload['written_source_credits_emitted']}",
        f"Registry audit path: {preview_payload['registry_audit_path']}",
        f"Geo tagging preview path: {preview_payload['geo_tagging_preview_path']}",
        f"Geo tagged county/regional/national/international: {preview_payload['geo_tagged_county']}/{preview_payload['geo_tagged_regional']}/{preview_payload['geo_tagged_national']}/{preview_payload['geo_tagged_international']}",
        f"Stories with multiple county hits: {preview_payload['stories_with_multiple_county_hits']}",
        '',
        'Stories:',
    ]
    for item in preview_payload['stories']:
        lines.extend([
            f"{item['position']}. {item['headline']}",
            f"   Scope: {item['scope']}",
            f"   Local origin type: {item['local_origin_type']}",
            f"   Sources: {', '.join(item['source_labels'])}",
            f"   Original URLs: {', '.join(item['original_urls'])}",
            f"   Radio text: {item['summary_text']}",
            '',
        ])
    lines.extend([
        'Written source credits:',
        ', '.join(preview_payload['media_source_credits']) or 'none',
        '',
    ])
    return '\n'.join(lines)


def _render_live_generalist_bulletin(preview_payload: dict[str, object]) -> str:
    lines = [
        f"OPENWAVE LIVE GENERALIST BULLETIN - {str(preview_payload.get('listener_name') or 'Nicu').upper()} / {str(preview_payload.get('listener_county') or 'Constanta').upper()}",
        '',
        f"Stories: {preview_payload['story_count']}",
        f"Resolved user county: {preview_payload['resolved_user_county']}",
        f"Resolved user region: {preview_payload['resolved_user_region']}",
        f"County-first local selection: {preview_payload['county_first_local_selection']}",
        f"Local story count from county: {preview_payload.get('local_story_count_from_county', preview_payload.get('local_story_count_from_constanta_county', 0))}",
        f"Local story count from regional fallback: {preview_payload['local_story_count_from_regional_fallback']}",
        '',
    ]
    for item in preview_payload['stories']:
        lines.extend([
            f"{item['position']}. {item['headline']}",
            f"   Scope: {item['scope']}",
            f"   Local origin type: {item['local_origin_type']}",
            f"   Sources: {', '.join(item['source_labels'])}",
            f"   Original URLs: {', '.join(item['original_urls'])}",
            item['summary_text'],
            '',
        ])
    lines.extend([
        'Written source credits after outro:',
        ', '.join(preview_payload['media_source_credits']) or 'none',
        '',
    ])
    return '\n'.join(lines)


def _load_registry_audit(sample_dir: Path) -> dict[str, object] | None:
    audit_path = sample_dir / "source_registry_audit.json"
    if not audit_path.exists():
        return None
    return json.loads(audit_path.read_text(encoding="utf-8"))


def _run_live_mode(user: str = "Nicu", county: str = "Constanta", save_sample_dir: str | None = None) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    personalization = build_personalization(user=user, county=county)
    pipeline_service = EditorialPipelineService()
    live_service = pipeline_service.live_source_ingestion_service
    live_service.write_registry()
    registry_audit = live_service.write_registry_audit(LIVE_SOURCE_REGISTRY_AUDIT_PATH, personalization=personalization)
    articles, ingestion_debug = live_service.fetch_articles(personalization=personalization)
    payload, geo_preview_payload = build_preview_payload_from_articles(
        articles=articles,
        personalization=personalization,
        mode_label="live",
        geo_tagging_preview_path=GEO_TAGGING_PREVIEW_PATH,
        registry_audit_path=LIVE_SOURCE_REGISTRY_AUDIT_PATH,
        registry_audit=registry_audit,
        ingestion_debug=ingestion_debug,
        sample_origin="live_fetch",
    )
    GEO_TAGGING_PREVIEW_PATH.write_text(json.dumps(geo_preview_payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    JSON_OUTPUT_PATH.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    preview_text = _render_live_preview_text(payload)
    bulletin_text = _render_live_generalist_bulletin(payload)
    TEXT_OUTPUT_PATH.write_text(preview_text, encoding="utf-8")
    LIVE_NICU_CONSTANTA_OUTPUT_PATH.write_text(bulletin_text, encoding="utf-8")

    output_dir = Path(save_sample_dir) if save_sample_dir else None
    if output_dir is not None:
        save_real_sample_bundle(
            output_dir=output_dir,
            preview_payload=payload,
            preview_text=preview_text,
            bulletin_text=bulletin_text,
            articles=articles,
            personalization=personalization,
            geo_preview_payload=geo_preview_payload,
            registry_audit=registry_audit,
            metadata={"workflow": "live_real_sample_generation"},
        )


def _run_saved_sample_mode(sample_dir: Path) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    loaded_sample = load_real_sample(sample_dir)
    registry_audit = _load_registry_audit(Path(sample_dir))
    payload, geo_preview_payload = build_preview_payload_from_articles(
        articles=loaded_sample["articles"],
        personalization=loaded_sample["personalization"],
        mode_label="debug",
        geo_tagging_preview_path=GEO_TAGGING_PREVIEW_PATH,
        registry_audit_path=Path(sample_dir) / "source_registry_audit.json",
        registry_audit=registry_audit,
        ingestion_debug={
            "sample_dir": str(sample_dir),
            "sample_generated_at": loaded_sample["metadata"].get("generated_at"),
            "sample_origin": "saved_real_sample",
        },
        sample_origin=f"real_sample:{Path(sample_dir).name}",
    )
    GEO_TAGGING_PREVIEW_PATH.write_text(json.dumps(geo_preview_payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    JSON_OUTPUT_PATH.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    TEXT_OUTPUT_PATH.write_text(_render_live_preview_text(payload), encoding="utf-8")
    REAL_SAMPLE_BULLETIN_OUTPUT_PATH.write_text(_render_live_generalist_bulletin(payload), encoding="utf-8")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run OpenWave radio editing preview in live or debug replay mode.")
    parser.add_argument("--user", default="Nicu")
    parser.add_argument("--county", default="Constanta")
    parser.add_argument("--sample-dir", default=None)
    parser.add_argument("--save-real-sample-dir", default=None)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    if get_openwave_mode() == "live":
        save_sample_dir = args.save_real_sample_dir or str(default_sample_output_dir(user=args.user, county=args.county, root=get_openwave_real_samples_root()))
        _run_live_mode(user=args.user, county=args.county, save_sample_dir=save_sample_dir)
        return

    resolved_sample_dir = resolve_real_sample_dir(
        explicit_dir=args.sample_dir or get_openwave_debug_sample_dir(),
        root=get_openwave_real_samples_root(),
    )
    if resolved_sample_dir is not None:
        _run_saved_sample_mode(resolved_sample_dir)
        return

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    service = RadioEditingService()
    pronunciation_map = get_tts_pronunciation_map()

    service.reset_variation_state()
    preview_stories = [_build_story_payload(service, fixture, index) for index, fixture in enumerate(PREVIEW_FIXTURES, start=1)]
    preview_word_counts = [item["radio_word_count"] for item in preview_stories]
    preview_duration_counts = [item["estimated_duration_seconds"] for item in preview_stories]
    explicit_attribution_counts = {"person": 0, "institution": 0, "media": 0}
    for item in preview_stories:
        if item["attribution_type"] in explicit_attribution_counts:
            explicit_attribution_counts[item["attribution_type"]] += 1

    lead_opening_type_counts = {
        "consequence": sum(1 for item in preview_stories if item["lead_opening_type"] == "consequence"),
        "action": sum(1 for item in preview_stories if item["lead_opening_type"] == "action"),
        "affected_audience": sum(1 for item in preview_stories if item["lead_opening_type"] == "affected_audience"),
        "person_role": sum(1 for item in preview_stories if item["lead_opening_type"] == "person_role"),
        "institution_action": sum(1 for item in preview_stories if item["lead_opening_type"] == "institution_action"),
    }
    validation_summary = {
        "story_count": len(preview_stories),
        "total_estimated_bulletin_duration_seconds": sum(preview_duration_counts),
        "average_word_count": round(statistics.mean(preview_word_counts), 1),
        "average_estimated_duration_seconds": round(statistics.mean(preview_duration_counts), 1),
        "average_lead_title_overlap_score": round(statistics.mean(item["lead_title_overlap_score"] for item in preview_stories), 2),
        "stories_with_lead_starting_with_institution": sum(1 for item in preview_stories if item["stories_with_lead_starting_with_institution"]),
        "stories_with_lead_starting_with_institution_and_title_like_action": sum(1 for item in preview_stories if item["stories_with_lead_starting_with_institution_and_title_like_action"]),
        "stories_rewritten_via_continuation_strategy": sum(1 for item in preview_stories if item["stories_rewritten_via_continuation_strategy"]),
        "stories_over_0_4_lead_title_overlap": sum(1 for item in preview_stories if item["lead_title_overlap_score"] > 0.4),
        "stories_over_0_5_lead_title_overlap": sum(1 for item in preview_stories if item["lead_title_overlap_score"] > 0.5),
        "min_word_count": min(preview_word_counts),
        "max_word_count": max(preview_word_counts),
        "min_estimated_duration_seconds": min(preview_duration_counts),
        "max_estimated_duration_seconds": max(preview_duration_counts),
        "sparse_story_count": sum(1 for item in preview_stories if item["story_band"] == "sparse"),
        "standard_story_count": sum(1 for item in preview_stories if item["story_band"] == "standard"),
        "major_story_count": sum(1 for item in preview_stories if item["story_band"] == "major"),
        "stories_under_65_words": sum(1 for count in preview_word_counts if count < 65),
        "stories_in_65_to_82_band": sum(1 for count in preview_word_counts if 65 <= count <= 82),
        "stories_in_85_to_105_band": sum(1 for count in preview_word_counts if 85 <= count <= 105),
        "stories_over_105_words": sum(1 for count in preview_word_counts if count > 105),
        "stories_with_sentences_over_24_words": sum(1 for item in preview_stories if any(length > 24 for length in item["sentence_lengths"])),
        "stories_with_sentence_over_25_words": sum(1 for item in preview_stories if any(length > 25 for length in item["sentence_lengths"])),
        "stories_with_lead_over_20_words": sum(1 for item in preview_stories if item["lead_word_count"] > 20),
        "stories_where_main_actor_does_not_appear_early_in_lead": sum(1 for item in preview_stories if not item["main_actor_early_in_lead"]),
        "stories_where_person_entity_existed_but_was_not_preserved": sum(1 for item in preview_stories if item["person_not_preserved"]),
        "leads_rewritten_to_reduce_title_repetition": sum(1 for item in preview_stories if item["lead_rewritten_to_reduce_title_repetition"]),
        "lead_continuation_rewrite_count": sum(1 for item in preview_stories if item["lead_continuation_rewrite_applied"]),
        "lead_opening_type_counts": lead_opening_type_counts,
        "lead_starter_family_distribution": lead_opening_type_counts,
        "human_density_score": round(sum(item["human_density_score"] for item in preview_stories) / max(1, len(preview_stories)), 2),
        "stories_with_person_anchor": sum(1 for item in preview_stories if item["stories_with_person_anchor"]),
        "stories_with_role_anchor": sum(1 for item in preview_stories if item["stories_with_role_anchor"]),
        "stories_with_voice_of_people_anchor": sum(1 for item in preview_stories if item["stories_with_voice_of_people_anchor"]),
        "closing_family_distribution": {family: sum(1 for item in preview_stories if item["closing_phrase_family"] == family) for family in ("operational_timing", "immediate_impact", "institution_followup", "policy_impact", "warning")},
        "stories_with_personal_attribution": sum(1 for item in preview_stories if item["stories_with_personal_attribution"]),
        "stories_with_person_name_attribution": sum(1 for item in preview_stories if item["stories_with_person_name_attribution"]),
        "stories_with_person_role_and_name_attribution": sum(1 for item in preview_stories if item["stories_with_person_role_and_name_attribution"]),
        "stories_with_institution_attribution": sum(1 for item in preview_stories if item["stories_with_institution_attribution"]),
        "stories_with_media_source_attribution": sum(1 for item in preview_stories if item["stories_with_media_source_attribution"]),
        "stories_with_intra_story_repetition": sum(1 for item in preview_stories if item["stories_with_intra_story_repetition"]),
        "stories_with_duplicate_sentence_removed": sum(1 for item in preview_stories if item["stories_with_duplicate_sentence_removed"]),
        "stories_with_closing_variation_applied": sum(1 for item in preview_stories if item["stories_with_closing_variation_applied"]),
        "stories_missing_attributed_voice": sum(1 for item in preview_stories if item["stories_missing_attributed_voice"]),
        "lead_has_personal_attribution_count": sum(1 for item in preview_stories if item["lead_has_personal_attribution"]),
        "second_sentence_has_personal_attribution_count": sum(1 for item in preview_stories if item["second_sentence_has_personal_attribution"]),
        "promoted_person_attribution_sentence_count": sum(item["promoted_person_attribution_sentence_count"] for item in preview_stories),
        "role_based_attribution_inserted_count": sum(item["role_based_attribution_inserted_count"] for item in preview_stories),
        "stories_with_institution_only_attribution": sum(1 for item in preview_stories if item["stories_with_institution_only_attribution"]),
        "stories_with_media_attribution": sum(1 for item in preview_stories if item["stories_with_media_attribution"]),
        "stories_with_high_title_lead_overlap": sum(1 for item in preview_stories if item["high_title_lead_overlap"]),
        "international_stories_with_romania_impact": sum(
            1 for item in preview_stories if item["source_scope"] == "international" and item["romania_impact_included"]
        ),
        "stories_with_strong_closure": sum(1 for item in preview_stories if item["strong_closure"]),
        "repeated_person_name_count": sum(item["repeated_person_name_count"] for item in preview_stories),
        "stories_with_administrative_closure": sum(1 for item in preview_stories if item["administrative_closure"]),
        "stories_with_multiple_attributions": sum(1 for item in preview_stories if item["multiple_attributions"]),
        "simplified_operational_description_count": sum(item["simplified_operational_description_count"] for item in preview_stories),
        "tts_pronunciation_entry_count": len(pronunciation_map),
        "explicit_attribution_counts": explicit_attribution_counts,
    }

    preview_payload = {
        "story_count": len(preview_stories),
        "stories": preview_stories,
        "validation_summary": validation_summary,
        "tts_pronunciation_map": pronunciation_map,
        "bulletin_radio_text": "\n\n".join(item["radio_text"] for item in preview_stories),
        "bulletin_estimated_duration_seconds": sum(preview_duration_counts),
    }
    JSON_OUTPUT_PATH.write_text(json.dumps(preview_payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    TEXT_OUTPUT_PATH.write_text(_render_preview_text(preview_payload), encoding="utf-8")

    service.reset_variation_state()
    generalist_stories = [_build_story_payload(service, fixture, index) for index, fixture in enumerate(GENERALIST_BULLETIN_FIXTURES, start=1)]
    GENERALIST_OUTPUT_PATH.write_text(_render_generalist_bulletin(generalist_stories), encoding="utf-8")

    victor_personalization = UserPersonalization(
        listener_profile=ListenerProfile(first_name="Victor", country="Romania", city="Vaslui"),
        editorial_preferences=EditorialPreferenceProfile(
            geography=GeographyPreferenceMix(local=35, national=40, international=25),
        ),
    )
    resolved_geo = resolve_listener_geography(city="Vaslui", region=None)
    local_resolution = SourceWatcherService().resolve_local_sources_for_personalization(victor_personalization)
    victor_mix_fixtures = VICTOR_VASLUI_LOCAL_FIXTURES + [
        fixture for fixture in GENERALIST_BULLETIN_FIXTURES if fixture["story_id"].startswith(("national_", "international_"))
    ]
    service.reset_variation_state()
    victor_base_stories = [_build_story_payload(service, fixture, index) for index, fixture in enumerate(victor_mix_fixtures, start=1)]
    victor_vaslui_stories = _order_victor_vaslui_bulletin(victor_base_stories)
    victor_geo_debug = {
        "resolved_user_city": resolved_geo.resolved_city,
        "resolved_user_county": resolved_geo.resolved_county,
        "resolved_user_region": resolved_geo.resolved_macro_region,
        "local_source_registry_used": local_resolution.local_source_registry_used,
        "local_sources_selected": [item.source_name for item in local_resolution.resolved_sources],
        "local_story_count_from_vaslui": sum(1 for item in victor_vaslui_stories if item.get("local_geo_origin") == "vaslui_county"),
        "local_story_count_from_moldova_region": sum(1 for item in victor_vaslui_stories if item.get("local_geo_origin") == "moldova_region"),
        "lead_continuation_rewrite_count": sum(1 for item in victor_vaslui_stories if item["lead_continuation_rewrite_applied"]),
        "lead_opening_type_counts": {
            "consequence": sum(1 for item in victor_vaslui_stories if item["lead_opening_type"] == "consequence"),
            "action": sum(1 for item in victor_vaslui_stories if item["lead_opening_type"] == "action"),
            "affected_audience": sum(1 for item in victor_vaslui_stories if item["lead_opening_type"] == "affected_audience"),
            "person_role": sum(1 for item in victor_vaslui_stories if item["lead_opening_type"] == "person_role"),
            "institution_action": sum(1 for item in victor_vaslui_stories if item["lead_opening_type"] == "institution_action"),
        },
    }
    VICTOR_VASLUI_OUTPUT_PATH.write_text(_render_victor_vaslui_bulletin(victor_vaslui_stories, victor_geo_debug), encoding="utf-8")

    ana_personalization = UserPersonalization(
        listener_profile=ListenerProfile(first_name="Ana", country="Romania", city="Timisoara"),
        editorial_preferences=EditorialPreferenceProfile(
            geography=GeographyPreferenceMix(local=35, national=40, international=25),
        ),
    )
    ana_geo = resolve_listener_geography(city="Timisoara", region=None)
    ana_local_resolution = SourceWatcherService().resolve_local_sources_for_personalization(ana_personalization)
    ana_mix_fixtures = ANA_TIMISOARA_LOCAL_FIXTURES + [
        fixture for fixture in GENERALIST_BULLETIN_FIXTURES if fixture["story_id"].startswith(("national_", "international_"))
    ]
    service.reset_variation_state()
    ana_base_stories = [_build_story_payload(service, fixture, index) for index, fixture in enumerate(ana_mix_fixtures, start=1)]
    ana_timisoara_stories = _order_victor_vaslui_bulletin(ana_base_stories)
    ana_geo_debug = {
        "resolved_user_city": ana_geo.resolved_city,
        "resolved_user_county": ana_geo.resolved_county,
        "resolved_user_region": ana_geo.resolved_macro_region,
        "local_source_registry_used": ana_local_resolution.local_source_registry_used,
        "local_sources_selected": [item.source_name for item in ana_local_resolution.resolved_sources],
        "local_story_count_from_timis": sum(1 for item in ana_timisoara_stories if item.get("local_geo_origin") == "timis_county"),
        "local_story_count_from_banat_region": sum(1 for item in ana_timisoara_stories if item.get("local_geo_origin") == "banat_region"),
        "stories_with_personal_attribution": sum(1 for item in ana_timisoara_stories if item["stories_with_personal_attribution"]),
        "lead_continuation_rewrite_count": sum(1 for item in ana_timisoara_stories if item["lead_continuation_rewrite_applied"]),
        "lead_opening_type_counts": {
            "consequence": sum(1 for item in ana_timisoara_stories if item["lead_opening_type"] == "consequence"),
            "action": sum(1 for item in ana_timisoara_stories if item["lead_opening_type"] == "action"),
            "affected_audience": sum(1 for item in ana_timisoara_stories if item["lead_opening_type"] == "affected_audience"),
            "person_role": sum(1 for item in ana_timisoara_stories if item["lead_opening_type"] == "person_role"),
            "institution_action": sum(1 for item in ana_timisoara_stories if item["lead_opening_type"] == "institution_action"),
        },
    }
    ANA_TIMISOARA_OUTPUT_PATH.write_text(_render_ana_timisoara_bulletin(ana_timisoara_stories, ana_geo_debug), encoding="utf-8")


    ion_personalization = UserPersonalization(
        listener_profile=ListenerProfile(first_name="Ion", country="Romania", region="Galati"),
        editorial_preferences=EditorialPreferenceProfile(
            geography=GeographyPreferenceMix(local=35, national=40, international=25),
        ),
    )
    ion_geo = resolve_listener_geography(city=None, region="Galati")
    ion_local_resolution = SourceWatcherService().resolve_local_sources_for_personalization(ion_personalization)
    ion_mix_fixtures = ION_GALATI_LOCAL_FIXTURES + [
        fixture for fixture in GENERALIST_BULLETIN_FIXTURES if fixture["story_id"].startswith(("national_", "international_"))
    ]
    service.reset_variation_state()
    ion_base_stories = [_build_story_payload(service, fixture, index) for index, fixture in enumerate(ion_mix_fixtures, start=1)]
    ion_galati_stories = _order_victor_vaslui_bulletin(ion_base_stories)
    ion_written_source_credits = _collect_media_source_credits(ion_mix_fixtures)
    ion_geo_debug = {
        "resolved_user_county": ion_geo.resolved_county,
        "resolved_user_region": ion_geo.resolved_macro_region,
        "local_source_registry_used": ion_local_resolution.local_source_registry_used,
        "county_based_local_routing": True,
        "local_sources_selected": [item.source_name for item in ion_local_resolution.resolved_sources],
        "local_story_count_from_galati_county": sum(1 for item in ion_galati_stories if item.get("local_geo_origin") == "galati_county"),
        "local_story_count_from_regional_fallback": sum(1 for item in ion_galati_stories if item.get("local_geo_origin") == "moldova_region"),
        "stories_with_person_role_and_name_attribution": sum(1 for item in ion_galati_stories if item["stories_with_person_role_and_name_attribution"]),
        "stories_with_institution_attribution": sum(1 for item in ion_galati_stories if item["stories_with_institution_attribution"]),
        "stories_with_media_source_attribution": sum(1 for item in ion_galati_stories if item["stories_with_media_source_attribution"]),
        "stories_missing_attributed_voice": sum(1 for item in ion_galati_stories if item["stories_missing_attributed_voice"]),
        "bulletin_unique_media_source_count": len(ion_written_source_credits),
        "written_source_credits_emitted": bool(ion_written_source_credits),
        "written_source_credits": ion_written_source_credits,
    }
    ION_GALATI_OUTPUT_PATH.write_text(_render_ion_galati_bulletin(ion_galati_stories, ion_geo_debug), encoding="utf-8")


    maria_personalization = UserPersonalization(
        listener_profile=ListenerProfile(first_name="Maria", country="Romania", region="Olt"),
        editorial_preferences=EditorialPreferenceProfile(
            geography=GeographyPreferenceMix(local=35, national=40, international=25),
        ),
    )
    maria_geo = resolve_listener_geography(city=None, region="Olt")
    maria_local_resolution = SourceWatcherService().resolve_local_sources_for_personalization(maria_personalization)
    maria_mix_fixtures = MARIA_OLT_LOCAL_FIXTURES + [
        fixture for fixture in GENERALIST_BULLETIN_FIXTURES if fixture["story_id"].startswith(("national_", "international_"))
    ]
    service.reset_variation_state()
    maria_base_stories = [_build_story_payload(service, fixture, index) for index, fixture in enumerate(maria_mix_fixtures, start=1)]
    maria_olt_stories = _order_victor_vaslui_bulletin(maria_base_stories)
    maria_written_source_credits = _collect_media_source_credits(maria_mix_fixtures)
    maria_geo_debug = {
        "resolved_user_county": maria_geo.resolved_county,
        "resolved_user_region": maria_geo.resolved_macro_region,
        "county_first_local_routing": True,
        "local_source_registry_used": maria_local_resolution.local_source_registry_used,
        "local_sources_selected": [item.source_name for item in maria_local_resolution.resolved_sources],
        "local_story_count_from_olt_county": sum(1 for item in maria_olt_stories if item.get("local_geo_origin") == "olt_county"),
        "local_story_count_from_oltenia_region": sum(1 for item in maria_olt_stories if item.get("local_geo_origin") == "oltenia_region"),
        "stories_rewritten_via_continuation_strategy": sum(1 for item in maria_olt_stories if item["stories_rewritten_via_continuation_strategy"]),
        "stories_with_lead_starting_with_institution_and_title_like_action": sum(1 for item in maria_olt_stories if item["stories_with_lead_starting_with_institution_and_title_like_action"]),
        "written_source_credits_emitted": bool(maria_written_source_credits),
        "written_source_credits": maria_written_source_credits,
    }
    MARIA_OLT_OUTPUT_PATH.write_text(_render_maria_olt_bulletin(maria_olt_stories, maria_geo_debug), encoding="utf-8")


    george_personalization = UserPersonalization(
        listener_profile=ListenerProfile(first_name="George", country="Romania", region="Covasna"),
        editorial_preferences=EditorialPreferenceProfile(
            geography=GeographyPreferenceMix(local=35, national=40, international=25),
        ),
    )
    george_geo = resolve_listener_geography(city=None, region="Covasna")
    george_local_resolution = SourceWatcherService().resolve_local_sources_for_personalization(george_personalization)
    george_mix_fixtures = GEORGE_COVASNA_LOCAL_FIXTURES + [
        fixture for fixture in GENERALIST_BULLETIN_FIXTURES if fixture["story_id"].startswith(("national_", "international_"))
    ]
    service.reset_variation_state()
    george_base_stories = [_build_story_payload(service, fixture, index) for index, fixture in enumerate(george_mix_fixtures, start=1)]
    george_covasna_stories = _order_victor_vaslui_bulletin(george_base_stories)
    george_written_source_credits = _collect_media_source_credits(george_mix_fixtures)
    george_geo_debug = {
        "resolved_user_county": george_geo.resolved_county,
        "resolved_user_region": george_geo.resolved_macro_region,
        "county_first_local_selection": True,
        "local_source_registry_used": george_local_resolution.local_source_registry_used,
        "local_sources_selected": [item.source_name for item in george_local_resolution.resolved_sources],
        "local_story_count_from_covasna_county": sum(1 for item in george_covasna_stories if item.get("local_geo_origin") == "covasna_county"),
        "local_story_count_from_transilvania_region": sum(1 for item in george_covasna_stories if item.get("local_geo_origin") == "transilvania_region"),
        "lead_starter_family_distribution": {
            family: sum(1 for item in george_covasna_stories if item["lead_starter_family"] == family)
            for family in ("consequence", "action", "affected_audience", "person_role", "institution_action")
        },
        "stories_with_duplicate_sentence_removed": sum(1 for item in george_covasna_stories if item["duplicate_sentence_removed"]),
        "stories_with_closing_variation_applied": sum(1 for item in george_covasna_stories if item["stories_with_closing_variation_applied"]),
        "written_source_credits": george_written_source_credits,
    }
    GEORGE_COVASNA_OUTPUT_PATH.write_text(_render_george_covasna_bulletin(george_covasna_stories, george_geo_debug), encoding="utf-8")

    nicu_personalization = UserPersonalization(
        listener_profile=ListenerProfile(first_name="Nicu", country="Romania", region="Constanta"),
        editorial_preferences=EditorialPreferenceProfile(
            geography=GeographyPreferenceMix(local=35, national=40, international=25),
        ),
    )
    nicu_geo = resolve_listener_geography(city=None, region="Constanta")
    nicu_local_resolution = SourceWatcherService().resolve_local_sources_for_personalization(nicu_personalization)
    nicu_mix_fixtures = NICU_CONSTANTA_LOCAL_FIXTURES + [
        fixture for fixture in GENERALIST_BULLETIN_FIXTURES if fixture["story_id"].startswith(("national_", "international_"))
    ]
    service.reset_variation_state()
    nicu_base_stories = [_build_story_payload(service, fixture, index) for index, fixture in enumerate(nicu_mix_fixtures, start=1)]
    nicu_constanta_stories = _order_victor_vaslui_bulletin(nicu_base_stories)
    nicu_geo_debug = {
        "resolved_user_county": nicu_geo.resolved_county,
        "resolved_user_region": nicu_geo.resolved_macro_region,
        "county_first_local_selection": True,
        "local_source_registry_used": nicu_local_resolution.local_source_registry_used,
        "local_sources_selected": [item.source_name for item in nicu_local_resolution.resolved_sources],
        "local_story_count_from_constanta_county": sum(1 for item in nicu_constanta_stories if item.get("local_geo_origin") == "constanta_county"),
        "local_story_count_from_regional_fallback": sum(1 for item in nicu_constanta_stories if item.get("local_geo_origin") == "dobrogea_region"),
        "human_density_score": round(sum(item["human_density_score"] for item in nicu_constanta_stories) / max(1, len(nicu_constanta_stories)), 2),
        "stories_with_person_anchor": sum(1 for item in nicu_constanta_stories if item["stories_with_person_anchor"]),
        "stories_with_role_anchor": sum(1 for item in nicu_constanta_stories if item["stories_with_role_anchor"]),
        "stories_with_voice_of_people_anchor": sum(1 for item in nicu_constanta_stories if item["stories_with_voice_of_people_anchor"]),
        "closing_family_distribution": {family: sum(1 for item in nicu_constanta_stories if item["closing_phrase_family"] == family) for family in ("operational_timing", "immediate_impact", "institution_followup", "policy_impact", "warning")},
    }
    NICU_CONSTANTA_OUTPUT_PATH.write_text(_render_nicu_constanta_bulletin(nicu_constanta_stories, nicu_geo_debug), encoding="utf-8")


if __name__ == "__main__":
    main()
