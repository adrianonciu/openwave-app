# Arhitectura OpenWave

## Rezumat
OpenWave este un sistem editorial si tehnic construit pentru a produce briefuri audio personalizate. Platforma combina ingestia automata de continut, modele AI editoriale si reguli stricte de redactare radio.

## Componente principale
- ingestie de continut din RSS
- servicii de clustering si scorare
- motor editorial de filtrare si validare
- motor de personalizare
- generator de rezumate radio
- backend API pentru livrarea briefingului
- aplicatie mobila pentru redare audio

## Logica sistemului
OpenWave se comporta ca o redactie automatizata:
- descopera subiecte
- compara mai multe surse
- decide importanta editoriala
- adapteaza selectia la profilul utilizatorului
- livreaza un briefing audio coerent

## Flux general
1. Articolele intra in sistem prin RSS ingestion.
2. Sunt grupate in evenimente prin story clustering.
3. Fiecare eveniment este evaluat prin importance scoring.
4. Evenimentele trec prin editorial filtering si controversele sunt marcate.
5. Personalization ajusteaza mixul final de continut.
6. Story selection construieste lista finala de subiecte.
7. Radio summary generation produce textele audio-friendly.
8. Editorial validation verifica respectarea politicii editoriale.
9. Segment generation pregateste rezultatul pentru player.
10. Audio playback livreaza briefingul in aplicatie.

## Reguli editoriale incorporate
- rezumatul fiecarui subiect foloseste 2 pana la 4 surse
- sursele sunt prezente doar in forma scrisa la finalul briefingului
- sursele nu sunt citite in varianta audio
- titlurile urmeaza schema actor + verb + eveniment
- rezumatele urmaresc impactul asupra cetatenilor

### Story Continuity
The system should support tracking evolving stories within the same day.

Articles referring to the same major event should be grouped into a
single story thread. Later bulletins may include updates to that story
instead of treating each article as a completely new story.

Example:

Morning bulletin:
Lead story - "Government announces emergency economic measures"

Later bulletin:
Update - "Details emerge about the economic measures"

Both items belong to the same story thread.

### TTS Testing Mode
- sistemul poate genera audio direct din texte de briefing existente
- acest mod este folosit pentru testarea vocii prezentatorului si a ritmului de livrare
- este separat de viitorul pipeline automat de generare a bulletinurilor

### Editorial Speech Pacing
- OpenWave introduce pauze editoriale mici intre segmente pentru a imbunatati claritatea si a imita ritmul radio
- in TTS testing mode, textul este preformatat inainte de a fi trimis catre providerul TTS
- regulile actuale includ pauza dupa intro, intre stiri, inainte de citate si inainte de outro
- configuratia de pacing ramane usor de ajustat prin valorile TTS_PACING

### Official TTS Test Integration
- audio-ul de test pentru Corina foloseste un furnizor TTS oficial
- ElevenLabs este providerul preferat pentru testele de ascultare
- OpenAI TTS poate fi folosit ca fallback daca ElevenLabs nu este configurat
- acest mod este doar pentru pilot listening tests
- integrarea ramane separata de viitorul pipeline automat de generare a bulletinurilor

Required environment variables:
- TTS_PROVIDER
- TTS_VOICE_ID
- TTS_MODEL
- TTS_OUTPUT_FORMAT
- ELEVENLABS_API_KEY
- ELEVENLABS_VOICE_ID
- ELEVENLABS_MODEL_ID
- OPENAI_API_KEY
- OPENAI_TTS_MODEL
- OPENAI_TTS_VOICE

## Nota Pentru Intro Si Outro Personalizat
Pentru a genera un intro si un outro personalizat, sistemul trebuie sa transporte mai multe valori de context pana la etapa de audio generation.

### Inputuri necesare pentru generatie
- user_name
- presenter_name
- playback_time
- selected_bulletin_slot
- greeting_type

### Definitii de lucru
- playback_time: momentul exact in care utilizatorul apasa Play
- selected_bulletin_slot: slotul editorial rezolvat pentru redare, de exemplu 06:00, 12:00 sau 22:00
- greeting_type: morning, day sau evening

### Regula de calcul
- greeting_type poate depinde de playback_time
- bulletin_hour trebuie sa depinda de selected_bulletin_slot
- wording-ul spus in intro si outro trebuie sa foloseasca selected_bulletin_slot, nu playback_time

## Reguli De Program Editorial
- primul bulletin al zilei este la 06:00
- ultimul bulletin al zilei este la 22:00
- in timpul saptamanii, bulletins sunt programate orar intre 06:00 si 22:00
- in weekend, cadenta este mai rara si trebuie tratata ca setare configurabila de produs
- politica de weekend poate fi la fiecare 3 ore sau la fiecare 4 ore
- bulletinul de la 06:00 are rol de morning opener si poate include un recap scurt al serii sau noptii anterioare

## Flux extins pentru selectie si generare audio
1. Utilizatorul apasa Play in aplicatie.
2. Aplicatia sau backend-ul identifica playback_time.
3. Sistemul cauta cel mai recent bulletin slot deja publicat pentru acel moment.
4. Daca bulletinul din ora curenta este publicat, acesta devine selected_bulletin_slot.
5. Daca nu este publicat inca, sistemul cade pe ultimul slot anterior publicat.
6. Sistemul nu trebuie sa rezolve niciodata un slot viitor.
7. Din playback_time se calculeaza greeting_type.
8. Din selected_bulletin_slot se extrage bulletin_hour.
9. Generatorul de text primeste user_name, presenter_name, greeting_type si bulletin_hour.
10. Intro-ul si outro-ul sunt construite astfel incat sa spuna corect salutul, numele utilizatorului si ora jurnalului.
11. Segment generation si TTS folosesc acest text finalizat pentru audio playback.

## Exemple De Rezolvare
- playback la 06:45 -> selected_bulletin_slot = 06:00
- playback la 12:05 -> selected_bulletin_slot = 12:00 daca este publicat, altfel 11:00
- playback la 22:20 -> selected_bulletin_slot = 22:00
- exemplu de wording: playback la 12:05, greeting_type = day, selected_bulletin_slot = 12:00 -> "Buna ziua, Adrian. Sunt Corina. Iata jurnalul tau de stiri de la ora 12."

## Implicatii minime de integrare
- stratul de selectie a briefingului trebuie sa intoarca selected_bulletin_slot impreuna cu continutul jurnalului
- selectia trebuie sa stie daca slotul curent este deja publicat sau nu
- generatorul de intro si outro nu trebuie sa deduca singur ora jurnalului din timestamp-ul de redare
- playerul trebuie sa poata afisa si reda acelasi bulletin_hour pe care il foloseste vocea
- daca slotul curent nu exista inca, sistemul trebuie sa foloseasca ultimul slot anterior disponibil fara a schimba wording-ul in functie de minutul curent
- configuratia de weekend trebuie sa poata fi schimbata fara rescrierea regulilor editoriale de baza
