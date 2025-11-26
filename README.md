
Kerosene-Flight-Optimizator ✈️
==============================

**Simulation animée d’optimisation carburant (Snapsac) pour avions de ligne – Tkinter + Matplotlib**

**Kerosene-Flight-Optimizator** simule, compare et **anime** la consommation de carburant de plusieurs avions (A320, B737, B777, A380) en fonction :

*   de la **vitesse** et **direction du vent** (_head/tail/side_),
    
*   de la **distance de vol**,
    
*   du **nombre de passagers**,
    
*   des **caractéristiques avion** (poids à vide, conso de base, vitesse de croisière, sensibilité au vent, capacité maximale).
    

L’app affiche **trois graphiques côte à côte**, synchronisés et animés :**Consommation totale (L)** · **Consommation par passager (L/pax)** · **Durée estimée (h)**avec un **panneau d’indicateurs** (KPI) et la **mise en avant du modèle gagnant** en temps réel.

🎥 Aperçu
---------

> Animation : balayage automatique du vent 0 → 300 km/h pour une séquence donnée (direction × distance × pax), puis passage à la séquence suivante.Chaque courbe représente un **modèle d’avion** ; la **ligne verticale** indique le **vent courant** ; les **étiquettes** suivent le dernier point ; le **fond** change selon la **direction du vent**.

_(Ajoute ici un GIF/Screenshot si tu veux)_

✨ Fonctionnalités
-----------------

*   **Animation 100% automatique** (aucun clic, aucun input requis)
    
*   **3 graphiques côte à côte** : L, L/pax, h
    
*   **Comparaison multi-modèles** (A320, B737, B777, A380)
    
*   **Surbrillance du meilleur avion** (critère : L/pax)
    
*   **Ligne de vent courant** + **étiquettes avion** sur le dernier point
    
*   **Échelle Y stable par séquence** (lisibilité)
    
*   **Fond coloré** par direction (head, tail, side) pour un repère visuel immédiat
    
*   **Panneau KPI** : direction, vent, distance, pax, conso totale, L/pax, durée, vitesse
    

🧠 Modèle & hypothèses
----------------------

Pour chaque avion :

*   **Conso par km** = conso\_base + impact\_masse + impact\_vent
    
    *   impact\_masse = (poids\_vide + pax \* (80 + 23)) / 1000 \* 0.1
        
    *   impact\_vent (selon direction)
        
        *   head: + vent \* 0.005 \* sens\_vent
            
        *   tail: - vent \* 0.003 \* sens\_vent
            
        *   side: + vent \* 0.001 \* sens\_vent
            
*   **Vitesse effective** bornée \[600, 1000\] km/h selon le vent
    
*   **Conso totale (L)** = conso\_km \* distance
    
*   **Conso/pax (L/pax)** = conso\_totale / pax
    
*   **Durée (h)** = distance / vitesse\_effective
    

> Ces coefficients sont **pédagogiques** pour visualiser les tendances et comparer des modèles.Ils peuvent être affinés avec données réelles (drag polaire, SFC moteur, flight levels, ISA, etc.).

📦 Installation
---------------

 # Cloner le dépôt  git clone https://github.com/VincentDesmouceaux/Kerosene-Flight-optimizator.git  cd Kerosene-Flight-optimizator  # (Optionnel) Créer un venv  python3 -m venv .venv  source .venv/bin/activate    # Windows: .venv\Scripts\activate  # Dépendances  pip install matplotlib  # (Tkinter est inclus avec Python sur macOS/Windows ; sur certaines distros Linux : sudo apt-get install python3-tk)   `

🚀 Lancer la simulation
-----------------------

 python snapsac_gui.py   `

*   Une fenêtre s’ouvre, l’animation démarre **automatiquement**.
    
*   Les séquences s’enchaînent (direction × distance × pax), chaque séquence balaye vent = 0 → 300.
    

🗂 Structure
------------

   Kerosene-Flight-optimizator/  ├─ snapsac_gui.py               # Application Tkinter + Matplotlib (3 graphes côte à côte)  ├─ README.md                    # Ce fichier  └─ .gitignore                   # Ignorés Python/macOS/venv   `

🔧 Paramétrage rapide
---------------------

Dans snapsac\_gui.py, tu peux ajuster :

 DIRECTIONS = ["head", "tail", "side"]  VENTS = list(range(0, 301, 10))  DISTANCES = [800, 1200, 1600, 2000]  PAX_LIST = [140, 160, 180, 200, 220, 240]   `

Et enrichir/ajuster les avions :

 AVIONS = {    "A320": {"poids_vide": 42000, "conso_base": 2.4, "max_pax": 180, "sens_vent": 1.0, "vitesse": 840},    ...  }   `

🖼 Design & lisibilité
----------------------

*   **Légendes** propres / **lignes épaisses** / **marqueurs supprimés** (plus lisible en animation)
    
*   **Étiquettes avion** qui suivent toujours le **dernier point**
    
*   **Ligne verticale** indiquant **le vent courant**
    
*   **Fond de graphe** adapté à la **direction** (head rouge clair, tail vert clair, side bleu clair)
    
*   **Échelles Y figées** par séquence pour **éviter les sauts**
    

🧪 Dépannage
------------

*   **Rien ne s’affiche / fenêtre vide**
    
    *   macOS (Homebrew) : lance avec pythonw snapsac\_gui.py
        
    *   Vérifie Tkinter : python3 -m tkinter doit ouvrir une petite fenêtre
        
    *   import matplotlibmatplotlib.use("TkAgg")
        
*   **Courbe statique / pas d’animation**
    
    *   Assure-toi que l’objet FuncAnimation est **gardé en variable d’instance** (c’est le cas dans le code).
        
*   **Performances**
    
    *   Réduis interval (ms) ou le nombre de valeurs de VENTS, PAX\_LIST, DISTANCES.
        

🛣️ Roadmap
-----------

*   Onglet **Énergie (MJ)** vs vent
    
*   Bouton **Export CSV** des points joués en live
    
*   **Pause/Reprise** de l’animation (barre espace)
    
*   **Comparaison multi-routes** (distance variable par avion)
    
*   Prise en compte **altitude** / **Mach** / **température ISA**
    

🤝 Contribuer
-------------

1.  Fork 🍴
    
2.  Branche feature : git checkout -b feat/ton-sujet
    
3.  Commits clairs : feat: ... / fix: ... / chore: ...
    
4.  PR 🚀
    

📝 Licence
----------

**MIT** — fais-en bon usage, améliore, partage, crédite si tu peux.

