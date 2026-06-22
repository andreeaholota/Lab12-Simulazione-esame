from datetime import date
import networkx as nx
from database.DAO import DAO


class Actor:

    def __init__(self, actor_id:int, name:str, eta:int):
        self._actor_id = actor_id
        self._name = name
        self._eta = eta

    @property
    def actor_id(self):
        return self._actor_id

    @property
    def name(self):
        return self._name

    @property
    def eta(self):
        return self._eta

    def __eq__(self,other):
        if not isinstance(other,Actor):
            return False
        return self._actor_id == other.actor_id

    def __hash__(self):
        return hash(self._actor_id)

    def __str__(self):
        return self._name

    def __repr__(self):
        return f"Actor({self.actor_id},{self.name},{self.eta})"


def _pulisci_incasso(testo_incasso):
    if testo_incasso is None:
        return 0.0

    try:
        pulito = "".join(carattere for carattere in str(testo_incasso) if carattere.isdigit() or carattere == ".")
        if pulito == "":
            return 0.0
        return float(pulito)
    except (ValueError, TypeError):
        return 0.0


def _calcola_eta(data_nascita):

    if data_nascita is None:
        return None # Dato anagrafico inesistente

    try:
        oggi = date.today()
        eta = oggi.year -data_nascita.year

        if (oggi.month, oggi.day) < (data_nascita.month, data_nascita.day):
            eta -= 1
    except (AttributeError, TypeError):
        return None # Data di nascita non è un oggetto valido

    if eta < 0 or eta > 120:
        return None  # età non plausibile

    return eta


class Model:
    def __init__(self):
        self._grafo = None
        self._id_map = {}
        self._migliore = []
        self._parziale = []

    # Converte la stringa di incasso in float

    def crea_grafo(self, rating_min, rating_max):
        self._grafo = nx.Graph() # NON ORIENTATO
        self._id_map = {}

        # 1. VERTICI

        lista_attori = DAO.get_attori_per_range(rating_min, rating_max)

        for actor_id, nome, data_nascita in lista_attori:
            eta = _calcola_eta(data_nascita)
            if eta is None:
                continue #età non valida: non lo inseriamo nel vertica

            self._id_map[actor_id] = Actor(actor_id, nome, eta)

        self._grafo.add_nodes_from(self._id_map.values())

        # 2. ARCHI

        righe = DAO.get_incassi_film_comuni(rating_min, rating_max)

        pesi_per_coppia = {}

        for id1, id2, incasso_testo in righe:
            if id1 not in self._id_map or id2 not in self._id_map:
                continue  # uno dei due non è un vertice valido

            # Puliamo la stringa "$ 6817391" trasformandola in numero
            valore = _pulisci_incasso(incasso_testo)
            chiave = (id1, id2)

            # Sommiamo gli incassi nel dizionario
            pesi_per_coppia[chiave] = pesi_per_coppia.get(chiave, 0.0) + valore

        # Adesso creiamo gli archi effettivi sul grafo
        for (id1, id2), peso_totale in pesi_per_coppia.items():
            # Aggiungiamo l'arco SOLO se l'incasso calcolato è valido e maggiore di 0
            if peso_totale > 0:
                a1 = self._id_map[id1]
                a2 = self._id_map[id2]
                self._grafo.add_edge(a1, a2, weight=peso_totale)

        return self._grafo.number_of_nodes(), self._grafo.number_of_edges()

    def get_top_5_archi(self):
        if self._grafo is None:
            return []

        lista_archi = list(self._grafo.edges(data=True))
        lista_archi.sort(key=lambda arco: arco[2]['weight'], reverse=True)

        return lista_archi[:5]

    def get_componenti_connesse(self):
        if self._grafo is None or self._grafo.number_of_nodes() == 0:
            return 0, []

        componenti = list(nx.connected_components(self._grafo))

        numero_componenti = len(componenti)
        componente_piu_grande = max(componenti, key=len)

        return numero_componenti, list(componente_piu_grande)

    def get_voti(self):
        return DAO.get_all_rating()

    def calcola_cammino_massimo(self):
        # Resettiamo il percorso migliore prima di ogni nuova ricerca
        self._migliore = []

        # Se il grafo non esiste o è vuoto, fermiamoci
        if self._grafo is None or self._grafo.number_of_nodes() == 0:
            return []

        # Proviamo a far partire il cammino da OGNI nodo del grafo
        for nodo_partenza in self._grafo.nodes():
            # Inizializziamo il percorso parziale inserendo il nodo di partenza
            self._ricorsione(nodo_partenza, [nodo_partenza])

        return self._migliore

    def _ricorsione(self, nodo_corrente, parziale):
        # 1. Controlliamo se il percorso che stiamo costruendo è il più lungo trovato finora
        if len(parziale) > len(self._migliore):
            # Facciamo una copia della lista parziale, altrimenti si modificherebbe
            self._migliore = list(parziale)

        # 2. Esploriamo i vicini del nodo in cui ci troviamo
        for vicino in self._grafo.neighbors(nodo_corrente):

            # Condizione A: Cammino Semplice (il vicino non deve essere già nel percorso)
            # Condizione B: Età strettamente decrescente
            if vicino not in parziale and vicino.eta < nodo_corrente.eta:
                # Aggiungiamo il vicino valido al percorso parziale
                parziale.append(vicino)

                # Richiamiamo la funzione su questo nuovo nodo (scendiamo in profondità)
                self._ricorsione(vicino, parziale)

                # BACKTRACKING: Finito di esplorare quel ramo, togliamo l'ultimo nodo
                # per poter provare altri vicini nel ciclo 'for'
                parziale.pop()
