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
- selected_bulletin_slot: slotul editorial ales pentru redare, de exemplu 06:00 sau 07:00
- greeting_type: morning, day sau evening

### Regula de calcul
- greeting_type poate depinde de playback_time
- bulletin_hour trebuie sa depinda de selected_bulletin_slot
- wording-ul spus in intro si outro trebuie sa foloseasca selected_bulletin_slot, nu playback_time

## Flux extins pentru selectie si generare audio
1. Utilizatorul apasa Play in aplicatie.
2. Aplicatia sau backend-ul identifica playback_time.
3. Sistemul cauta cel mai recent bulletin slot disponibil pentru acel moment.
4. Rezultatul devine selected_bulletin_slot.
5. Din playback_time se calculeaza greeting_type.
6. Din selected_bulletin_slot se extrage bulletin_hour.
7. Generatorul de text primeste user_name, presenter_name, greeting_type si bulletin_hour.
8. Intro-ul si outro-ul sunt construite astfel incat sa spuna corect salutul, numele utilizatorului si ora jurnalului.
9. Segment generation si TTS folosesc acest text finalizat pentru audio playback.

## Implicatii minime de integrare
- stratul de selectie a briefingului trebuie sa intoarca selected_bulletin_slot impreuna cu continutul jurnalului
- generatorul de intro si outro nu trebuie sa deduca singur ora jurnalului din timestamp-ul de redare
- playerul trebuie sa poata afisa si reda acelasi bulletin_hour pe care il foloseste vocea
- daca slotul curent nu exista inca, sistemul trebuie sa foloseasca ultimul slot anterior disponibil fara a schimba wording-ul in functie de minutul curent
