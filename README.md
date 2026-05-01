# ⚡ Pannes Hydro-Québec pour Home Assistant

Une intégration personnalisée (Custom Component) pour Home Assistant permettant de surveiller en temps réel les pannes d'électricité sur le réseau d'Hydro-Québec pour vos adresses spécifiques.

Entièrement configurable via l'interface utilisateur, elle utilise le puissant moteur de géolocalisation ArcGIS pour trouver votre adresse exacte (sans clé API) et interroge les données ouvertes (JSON et KMZ) d'Hydro-Québec toutes les 15 minutes.

## ✨ Fonctionnalités

Pour chaque adresse configurée, l'intégration crée un "Appareil" contenant **8 capteurs détaillés** :

*   **Statut du réseau :** En service ou Panne détectée. *(Inclut désormais les coordonnées du polygone exact de la panne en attribut !)*
*   **Total pannes (QC) :** Le nombre total de pannes actives au Québec.
*   **Clients affectés (QC) :** Le nombre total de clients dans le noir dans la province.
*   **Clients affectés (Local) :** Le nombre de vos voisins touchés par la même panne.
*   **Type de panne :** Panne imprévue ou Interruption planifiée.
*   **Cause de la panne :** Végétation, bris d'équipement, conditions météo, etc.
*   **Statut des travaux :** Équipe en route, équipe au travail, en évaluation, etc.
*   **Rétablissement prévu :** Heure estimée du retour du courant fournie par Hydro-Québec.

> **💡 Nouveautés sous le capot :**
> *   Support natif de **Python 3.14+** (mise à jour de la librairie géospatiale).
> *   Lecture complète des zones d'interruptions complexes (support des `MultiPolygon` KML) pour capturer 100% de la surface affectée.

---

## 📦 Installation

### Méthode 1 : Via HACS (Recommandée)
C'est la méthode la plus simple pour installer et garder l'intégration à jour.

[![Installer via HACS](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=moimeme81&repository=info-pannes&category=integration)

1. Ouvrez Home Assistant et allez dans **HACS** > **Intégrations**.
2. Cliquez sur les trois petits points en haut à droite et sélectionnez **Dépôts personnalisés** (Custom repositories).
3. Ajoutez l'URL de ce dépôt : `https://github.com/moimeme81/info-pannes`
4. Choisissez la catégorie **Intégration** et cliquez sur **Ajouter**.
5. Cherchez "Pannes Hydro-Québec" dans HACS, cliquez dessus puis sur **Télécharger**.
6. **Redémarrez Home Assistant**.

### Méthode 2 : Manuelle
1. Téléchargez le code source depuis GitHub.
2. Copiez le dossier `custom_components/panne-hydro-quebec` dans le dossier `custom_components` de votre configuration Home Assistant.
3. **Redémarrez Home Assistant**.

---

## ⚙️ Configuration

L'intégration se configure entièrement depuis l'interface utilisateur, aucun code YAML n'est requis !

1. Allez dans **Paramètres** > **Appareils et services**.
2. Cliquez sur le bouton **+ Ajouter une intégration** en bas à droite.
3. Cherchez **Pannes Hydro-Québec**.
4. Remplissez le formulaire de recherche (Numéro civique, Rue, Ville). *Astuce : vous pouvez simplement entrer un code postal ou un nom de rue partiel, le moteur de recherche (ArcGIS) est très tolérant.*
5. Sélectionnez votre adresse exacte dans le menu déroulant qui s'affiche pour confirmer.
6. C'est fait ! Vous pouvez répéter l'opération pour ajouter d'autres adresses (bureau, chalet, parents, etc.).

---

## 🗺️ Afficher les pannes sur une carte (Tableau de bord)

L'intégration extrait la forme géométrique exacte de la panne et la stocke au format standardisé GeoJSON dans les attributs du capteur de statut.

Vous pouvez créer une carte dynamique sur votre tableau de bord qui s'affichera **uniquement lorsqu'une panne est en cours**, et qui cadrera la vue automatiquement sur la zone affectée.

### Prérequis (via HACS)
Pour profiter de cette fonctionnalité avancée, installez ces deux cartes personnalisées depuis la section *Frontend* de HACS :
1.  **[auto-entities](https://github.com/thomasloven/lovelace-auto-entities)** : Pour filtrer automatiquement les adresses en panne.
2.  **[ha-map-card](https://github.com/nathanielbengtson/ha-map-card)** : Pour dessiner les polygones GeoJSON sur une carte.

### Le code de la carte (YAML)
Dans votre tableau de bord, ajoutez une carte manuelle et collez ce code YAML :
```yaml
type: custom:auto-entities
show_empty: false
card:
  type: custom:map-card
  auto_fit: true
filter:
  include:
    - entity_id: "sensor.*_statut"
      state: "Panne"
      options:
        display: marker
        geojson: zone_geographique
````

### Comment fonctionne cette carte magique ?
Discrète en temps normal : Grâce à show_empty: false, si le courant circule normalement à toutes vos adresses, la carte disparaît complètement de votre écran.

Auto-gestion : Le filtre sensor.*_statut scannera automatiquement toute nouvelle adresse que vous ajouterez à l'intégration, sans avoir à retoucher ce code YAML.

Cadrage automatique : L'option auto_fit: true ajuste le niveau de zoom de la carte pour que l'intégralité du polygone rouge soit visible, que la panne affecte deux rues ou plusieurs villes.

Note sur le rendu visuel : Lors de pannes mineures (très peu de clients) ou de pannes récentes ("En évaluation"), Hydro-Québec dessine souvent un simple cercle générique autour du point pour protéger la vie privée des clients. Lors de pannes majeures, le système affichera le tracé géométrique complexe qui suit le réseau électrique réel.

## 🛠️ Dépannage
L'intégration n'apparaît pas dans la liste après l'installation ?
Videz la mémoire cache de votre navigateur (Ctrl+F5 ou Cmd+Shift+R) ou effacez le cache de l'application mobile Home Assistant.

Aucun résultat pour mon adresse ?
Essayez d'être moins spécifique (retirez le numéro civique et cherchez uniquement la rue et la ville) pour voir ce que le système GPS vous propose dans le menu déroulant.

Erreur lors de l'installation ("shapely") ?
Assurez-vous que votre instance Home Assistant est à jour. L'intégration nécessite une version récente de Python (3.14+) pour compiler ses dépendances géographiques.

## ⚖️ Avertissement
Cette intégration n'est pas affiliée, sponsorisée ou approuvée par Hydro-Québec. Elle utilise le portail de données ouvertes d'Hydro-Québec. Les données sont fournies à titre indicatif. Ne vous fiez jamais uniquement à ces données pour des décisions critiques de sécurité.
