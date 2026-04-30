# ⚡ Pannes Hydro-Québec pour Home Assistant


Une intégration personnalisée (Custom Component) pour Home Assistant permettant de surveiller les pannes d'électricité d'Hydro-Québec pour vos adresses spécifiques. 

Entièrement configurable via l'interface utilisateur, elle utilise le puissant moteur de géolocalisation ArcGIS pour trouver votre adresse exacte (sans clé API) et interroge les données ouvertes d'Hydro-Québec toutes les 15 minutes.

## ✨ Fonctionnalités

Pour chaque adresse ajoutée, l'intégration crée un "Appareil" contenant **8 capteurs détaillés** :

* **Statut du réseau :** En service ou Panne détectée.
* **Total pannes (QC) :** Le nombre total de pannes actives au Québec.
* **Clients affectés (QC) :** Le nombre total de clients dans le noir dans la province.
* **Clients affectés (Local) :** Le nombre de vos voisins touchés par la même panne.
* **Type de panne :** Panne imprévue ou Interruption planifiée.
* **Cause de la panne :** Végétation, bris d'équipement, conditions météo, etc.
* **Statut des travaux :** Équipe en route, équipe au travail, en évaluation, etc.
* **Rétablissement prévu :** Heure estimée du retour du courant fournie par Hydro-Québec.

## 📦 Installation

### Méthode 1 : Via HACS (Recommandée)
C'est la méthode la plus simple pour installer et garder l'intégration à jour.

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

## ⚙️ Configuration

L'intégration se configure entièrement depuis l'interface utilisateur, aucun code YAML n'est requis !

1. Allez dans **Paramètres** > **Appareils et services**.
2. Cliquez sur le bouton **+ Ajouter une intégration** en bas à droite.
3. Cherchez **Pannes Hydro-Québec**.
4. Remplissez le formulaire de recherche (Numéro civique, Rue, Ville). *Astuce : vous pouvez simplement entrer un code postal ou un nom de rue partiel, le moteur de recherche (ArcGIS) est très tolérant.*
5. Sélectionnez votre adresse exacte dans le menu déroulant qui s'affiche pour confirmer.
6. C'est fait ! Vous pouvez répéter l'opération pour ajouter d'autres adresses (bureau, chalet, parents, etc.).

## 🛠️ Dépannage

* **L'intégration n'apparaît pas dans la liste après l'installation ?** 
Videz la mémoire cache de votre navigateur (`Ctrl+F5` ou `Cmd+Shift+R`) ou effacez le cache de l'application mobile Home Assistant.
* **Aucun résultat pour mon adresse ?** 
Essayez d'être moins spécifique (retirez le numéro civique et cherchez uniquement la rue et la ville) pour voir ce que le système GPS vous propose dans le menu déroulant.

## ⚖️ Avertissement

Cette intégration n'est pas affiliée, sponsorisée ou approuvée par Hydro-Québec. Elle utilise le portail de données ouvertes d'Hydro-Québec. Les données sont fournies à titre indicatif. Ne vous fiez jamais uniquement à ces données pour des décisions critiques de sécurité.
