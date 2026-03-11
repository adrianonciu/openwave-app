# Modelul De Grupare A Stirilor

## Rol
Modelul de clustering grupeaza articolele care descriu acelasi eveniment pentru a evita repetitia si pentru a permite sinteza din multiple surse.

## Date folosite
- titlu si subtitlu
- entitati numite
- timp si locatie
- tema si taxonomie de domeniu
- similaritate semantica a continutului

## Obiectiv editorial
- un singur eveniment relevant produce un singur segment principal in briefing
- fiecare cluster ideal contine intre 2 si 4 surse utile
- duplicatele si reformularile minore sunt eliminate

## Reguli de calitate
- doua articole similare, dar despre momente diferite, nu trebuie unite automat
- subiectele cu evolutii noi pot genera un nou cluster
- daca similaritatea este ambigua, clusterul merge spre validare editoriala
