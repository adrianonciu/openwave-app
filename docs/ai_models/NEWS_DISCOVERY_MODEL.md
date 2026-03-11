# Modelul De Descoperire A Stirilor

## Rol
Acest model detecteaza subiecte candidate din fluxurile de intrare si decide ce merita procesat mai departe in redactie.

## Surse de intrare
- feed-uri RSS
- publicatii selectate
- surse locale, nationale si globale
- surse generaliste si de nisa, in functie de taxonomie

## Semnale urmarite
- aparitia repetata a aceluiasi eveniment in surse independente
- cresterea brusca a acoperirii
- frecventa entitatilor si a cuvintelor-cheie
- noutatea fata de evenimentele deja procesate

## Filtre initiale
- eliminarea duplicatelor brute
- excluderea continutului promotional
- reducerea continutului cu valoare informationala slaba
- marcarea subiectelor sensibile pentru verificare suplimentara
