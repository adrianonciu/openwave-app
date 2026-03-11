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
