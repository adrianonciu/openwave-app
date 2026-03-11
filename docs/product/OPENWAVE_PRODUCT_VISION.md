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
OpenWave produce jurnale pe sloturi editoriale fixe. Atunci cand utilizatorul apasa Play, aplicatia nu trebuie sa foloseasca ora exacta a apasarii ca eticheta editoriala a jurnalului. Ea trebuie sa selecteze cel mai recent jurnal deja publicat.

### Definitii
- current playback time: momentul exact in care utilizatorul apasa Play
- bulletin slot time: ora editoriala fixa a jurnalului, de exemplu 06:00, 12:00 sau 22:00
- latest available bulletin: cel mai recent jurnal deja publicat si disponibil pentru redare la momentul apasarii Play

### Regula de selectie
- bulletins sunt generate pe sloturi fixe
- la Play se selecteaza cel mai recent bulletin slot deja publicat
- daca jurnalul din ora curenta este deja disponibil, aplicatia il reda pe acela
- daca jurnalul din ora curenta nu este inca publicat, aplicatia cade pe cel mai recent slot anterior publicat
- aplicatia nu trebuie sa faca referire la un slot viitor

### Exemple corectate
- Play la 06:45 -> se reda jurnalul de la 06:00
- Play la 12:05 -> se reda jurnalul de la 12:00 daca este publicat, altfel 11:00
- Play la 22:20 -> se reda jurnalul de la 22:00

## Fereastra Zilnica De Bulletins
- primul jurnal al zilei este la 06:00
- ultimul jurnal al zilei este la 22:00
- toate referintele editoriale la ora jurnalului trebuie sa foloseasca un slot din aceasta fereastra zilnica

## Rolul Editorial Al Jurnalului De La 06:00
- jurnalul de la 06:00 este morning opener
- poate include un scurt recap al celor mai importante stiri din seara si noaptea anterioara
- trebuie sa se simta totusi ca primul jurnal util al noii zile, nu ca o simpla repetitie a serii trecute

## Cadenta Weekday Vs Weekend
- in zilele lucratoare, bulletins ruleaza din ora in ora, de la 06:00 la 22:00
- sambata si duminica, bulletins ruleaza mai rar
- cadenta de weekend trebuie tratata ca politica editoriala configurabila
- varianta configurabila documentata: la fiecare 3 ore sau la fiecare 4 ore

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

### Regula de calcul pentru intro
- greeting_type depinde de playback_time
- bulletin_hour depinde de resolved published bulletin slot

### Exemplu de rezolvare
- playback la 12:05
- bulletin slot rezolvat la 12:00 daca este publicat, altfel 11:00
- daca 12:00 este publicat, linia rostita este: "Buna ziua, Adrian. Sunt Corina. Iata jurnalul tau de stiri de la ora 12."

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
- selectia de continut trebuie sa intoarca selected bulletin slot si starea lui de publicare
- generatorul de intro si outro trebuie sa primeasca user_name, presenter_name si bulletin_hour
- wording-ul audio trebuie sa fie legat de slotul selectat, nu de timestamp-ul de redare
- politica de weekend trebuie sa poata fi configurata separat de cadenta din timpul saptamanii
