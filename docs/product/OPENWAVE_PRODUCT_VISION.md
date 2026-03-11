# Viziunea De Produs OpenWave

## Misiune
OpenWave transforma consumul de stiri intr-o experienta audio zilnica, clara si personalizata, pentru oameni care vor sa inteleaga rapid ce conteaza.

## Problema rezolvata
- prea multe articole, prea putin timp
- zgomot informational si repetitie intre publicatii
- continut greu de consumat in mers
- lipsa unui produs de stiri construit nativ pentru audio

## Viziune
OpenWave devine briefingul audio de incredere care functioneaza ca o redactie automatizata: selecteaza cele mai relevante evenimente, le explica simplu si le livreaza intr-un format usor de ascultat.

## Principii de produs
- audio-first, nu text reciclat
- personalizare controlata, fara pierderea subiectelor importante
- focus pe utilitate publica si impact pentru cetateni
- experienta simpla, rapida si repetabila zilnic

## Regula De Selectie A Slotului De Bulletin
OpenWave produce jurnale pe sloturi editoriale fixe, de exemplu din ora in ora. Atunci cand utilizatorul apasa Play, aplicatia nu trebuie sa foloseasca ora exacta a apasarii ca eticheta editoriala a jurnalului. Ea trebuie sa selecteze cel mai recent jurnal disponibil.

### Definitii
- current playback time: momentul exact in care utilizatorul apasa Play
- bulletin slot time: ora editoriala fixa a jurnalului generat, de exemplu 06:00 sau 07:00
- latest available bulletin: cel mai recent jurnal care exista deja si poate fi redat la momentul apasarii Play

### Regula de selectie
- bulletins sunt generate pe sloturi fixe, de exemplu la fiecare ora
- la Play se selecteaza cel mai recent bulletin slot disponibil
- daca slotul curent exista deja, se reda acel slot
- daca slotul curent nu exista inca, se reda cel mai recent slot anterior disponibil

### Exemple
- utilizatorul apasa Play la 06:45
- bulletins disponibile: 05:00, 06:00
- aplicatia reda jurnalul de la 06:00

- utilizatorul apasa Play la 07:05
- daca jurnalul de la 07:00 exista, aplicatia reda 07:00
- daca nu exista inca, aplicatia reda cel mai recent jurnal anterior disponibil

## Intro Personalizat
Intro-ul trebuie sa includa patru lucruri:
- formula de salut dupa momentul zilei
- numele utilizatorului
- numele prezentatoarei sau prezentatorului
- ora slotului editorial selectat

Ora rostita in intro trebuie sa fie bulletin slot time, nu current playback time.

### Tipuri de salut
- morning: pentru intervalul de dimineata
- day: pentru intervalul de zi
- evening: pentru intervalul de seara

### Exemple in romana
- Morning: "Buna dimineata, {user_name}. Sunt Corina. Iata jurnalul tau de stiri de la ora {bulletin_hour}."
- Day: "Buna ziua, {user_name}. Sunt Corina. Iata jurnalul tau de stiri de la ora {bulletin_hour}."
- Evening: "Buna seara, {user_name}. Sunt Corina. Iata jurnalul tau de stiri de la ora {bulletin_hour}."

## Outro Personalizat
Outro-ul trebuie sa includa:
- ora slotului editorial selectat
- numele utilizatorului
- o inchidere flexibila care poate sau nu sa mentioneze urmatorul update

### Exemple in romana
- Varianta generica: "Acesta a fost jurnalul tau de la ora {bulletin_hour}, {user_name}. Ne reauzim la urmatorul jurnal."
- Varianta pentru format orar: "Acesta a fost jurnalul tau de la ora {bulletin_hour}, {user_name}. Revin cu un nou jurnal la urmatoarea actualizare."

### Regula de flexibilitate
- daca exista un program clar de jurnale orare, outro-ul poate mentiona urmatoarea actualizare
- daca programul nu este garantat, outro-ul trebuie sa foloseasca o inchidere generica
- si in outro, ora rostita trebuie sa fie cea a slotului selectat, nu ora exacta a apasarii Play

## Implicatii Minime De Implementare
- playerul sau stratul care cere redarea trebuie sa cunoasca current playback time
- selectia de continut trebuie sa intoarca selected bulletin slot
- generatorul de intro si outro trebuie sa primeasca user_name, presenter_name si bulletin_hour
- wording-ul audio trebuie sa fie legat de slotul selectat, nu de timestamp-ul de redare
